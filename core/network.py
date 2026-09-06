"""
Network Engine: Passive TCP Profiling, Dual TLS Pre-Warming, and Millisecond Quota Snipe.
Supports Single Shot and Dual-Socket Double-Tap (false primary + true secondary).
"""

import time
import socket
import ssl
import select
import json
import http.client
import datetime
import hashlib
from typing import Dict, Any, Tuple, Optional, List

API_HOST = "sgp-api.buy.mi.com"
API_PATH = "/bbs/api/global/apply/bl-auth"


def measure_tcp_rtt(host: str = API_HOST, port: int = 443, timeout: float = 3.0) -> Optional[float]:
    """
    Measures pure Layer-4 network round-trip time via TCP SYN-ACK handshake.
    Zero HTTP requests sent = No WAF triggers, no risk rate-limits.
    Returns: RTT in milliseconds.
    """
    try:
        t0 = time.perf_counter()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((host, port))
        rtt_ms = (time.perf_counter() - t0) * 1000.0
        s.close()
        return rtt_ms
    except Exception:
        return None


def get_next_beijing_midnight() -> Tuple[float, datetime.datetime]:
    """
    Calculates the exact UTC epoch and datetime for the upcoming 00:00:00 (GMT+8 / Beijing time).
    Note: 00:00:00 GMT+8 = 16:00:00 UTC of the previous day.
    """
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    target_utc = now_utc.replace(hour=16, minute=0, second=0, microsecond=0)
    if now_utc >= target_utc:
        target_utc += datetime.timedelta(days=1)
    return target_utc.timestamp(), target_utc


class SnipeSession:
    def __init__(self, cookies: Dict[str, str]):
        self.cookies = cookies
        self.host = API_HOST
        self.path = API_PATH
        self.conn_a: Optional[http.client.HTTPSConnection] = None
        self.conn_b: Optional[http.client.HTTPSConnection] = None

    def _create_ssl_conn(self, timeout: float = 10.0) -> http.client.HTTPSConnection:
        ctx = ssl.create_default_context()
        conn = http.client.HTTPSConnection(self.host, 443, context=ctx, timeout=timeout)
        conn.connect()
        return conn

    def prewarm_tls(self, timeout: float = 10.0) -> float:
        """Single-socket prewarm."""
        if self.conn_a:
            try:
                self.conn_a.close()
            except Exception:
                pass
        t0 = time.perf_counter()
        self.conn_a = self._create_ssl_conn(timeout=timeout)
        return (time.perf_counter() - t0) * 1000.0

    def prewarm_tls_dual(self, timeout: float = 10.0) -> Tuple[float, float]:
        """
        Prewarms two independent TLS keep-alive connections (Socket A and Socket B)
        in parallel/sequence ahead of the target window.
        """
        self.close()
        t0 = time.perf_counter()
        self.conn_a = self._create_ssl_conn(timeout=timeout)
        rtt_a = (time.perf_counter() - t0) * 1000.0

        t1 = time.perf_counter()
        self.conn_b = self._create_ssl_conn(timeout=timeout)
        rtt_b = (time.perf_counter() - t1) * 1000.0
        return rtt_a, rtt_b

    def is_alive(self, conn: Optional[http.client.HTTPSConnection] = None) -> bool:
        c = conn or self.conn_a
        if not c or not c.sock:
            return False
        try:
            select.select([c.sock], [], [], 0)
            return True
        except Exception:
            return False

    def _build_request(self, is_retry: bool = False) -> Tuple[Dict[str, str], bytes]:
        token = self.cookies.get("new_bbs_serviceToken", "")
        dev_id = self.cookies.get("deviceId")
        if not dev_id:
            seed = f"HyperOS_BL_Sniper_Device_{token}"
            digest = hashlib.sha1(seed.encode("utf-8")).digest()
            val = int.from_bytes(digest, "big")
            dev_id = f"{val:032X}"

        version_code = self.cookies.get("versionCode", "500439")
        version_name = self.cookies.get("versionName", "5.4.39")
        cookie_str = f"new_bbs_serviceToken={token};versionCode={version_code};versionName={version_name};deviceId={dev_id};"

        payload = json.dumps({"is_retry": is_retry}).encode("utf-8")
        headers = {
            "Host": self.host,
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 24069PC21G) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/128.0.6613.88 Mobile Safari/537.36 Xiaomi/MiuiForum/5.4.39",
            "Cookie": cookie_str,
            "Content-Type": "application/json;charset=utf-8",
            "Content-Length": str(len(payload)),
            "Accept": "application/json",
            "Origin": "https://c.mi.com",
            "Referer": "https://c.mi.com/",
            "Connection": "keep-alive",
        }
        return headers, payload

    def fire_single(self, is_retry: bool = False) -> Tuple[int, Dict[str, Any], float, Dict[str, str]]:
        headers, payload = self._build_request(is_retry=is_retry)
        t_fire = time.perf_counter()
        last_error: Optional[Exception] = None

        for attempt in (1, 2):
            if not self.conn_a or not self.is_alive(self.conn_a):
                try:
                    self.prewarm_tls(timeout=5.0)
                except Exception as e:
                    self.conn_a = None
                    last_error = e
                    if attempt == 2:
                        break
                    continue
            try:
                self.conn_a.request("POST", self.path, body=payload, headers=headers)
                resp = self.conn_a.getresponse()
                resp_latency = (time.perf_counter() - t_fire) * 1000.0
                resp_headers = dict(resp.getheaders())
                body = resp.read().decode("utf-8")
                try:
                    data = json.loads(body)
                except Exception:
                    data = {"raw": body}
                return resp.status, data, resp_latency, resp_headers
            except (TimeoutError, ConnectionError, BrokenPipeError, http.client.RemoteDisconnected) as e:
                self.close()
                last_error = e
                if attempt == 2:
                    break

        raise RuntimeError(f"No se pudo completar el disparo: {last_error}")

    def fire(self) -> Tuple[int, Dict[str, Any], float, Dict[str, str]]:
        """Compatibility wrapper for single shot."""
        return self.fire_single(is_retry=False)

    def fire_double_tap(self, interval_ms: float = 100.0) -> Dict[str, Any]:
        """
        Executes an interleaved Double-Tap burst:
        1. Socket A fires Primary (is_retry=False).
        2. Waits interval_ms via perf_counter.
        3. Socket B fires Secondary (is_retry=True).
        Returns consolidated telemetry identifying winner and outcomes.
        """
        headers_a, payload_a = self._build_request(is_retry=False)
        headers_b, payload_b = self._build_request(is_retry=True)

        # Fallback check if sockets dropped
        if not self.conn_a or not self.is_alive(self.conn_a):
            try:
                self.conn_a = self._create_ssl_conn(timeout=5.0)
            except Exception:
                pass
        if not self.conn_b or not self.is_alive(self.conn_b):
            try:
                self.conn_b = self._create_ssl_conn(timeout=5.0)
            except Exception:
                pass

        # Disparo 1 (Primario)
        t_fire_1 = time.perf_counter()
        self.conn_a.request("POST", self.path, body=payload_a, headers=headers_a)

        # Micro-espera exacta al milisegundo para Disparo 2
        t_target_2 = t_fire_1 + (interval_ms / 1000.0)
        while time.perf_counter() < t_target_2:
            pass

        # Disparo 2 (Paracaídas)
        t_fire_2 = time.perf_counter()
        self.conn_b.request("POST", self.path, body=payload_b, headers=headers_b)

        # Recoger Respuesta 1
        resp_a = self.conn_a.getresponse()
        rtt_1 = (time.perf_counter() - t_fire_1) * 1000.0
        headers_resp_a = dict(resp_a.getheaders())
        raw_a = resp_a.read().decode("utf-8")
        try:
            data_a = json.loads(raw_a)
        except Exception:
            data_a = {"raw": raw_a}

        # Recoger Respuesta 2
        resp_b = self.conn_b.getresponse()
        rtt_2 = (time.perf_counter() - t_fire_2) * 1000.0
        headers_resp_b = dict(resp_b.getheaders())
        raw_b = resp_b.read().decode("utf-8")
        try:
            data_b = json.loads(raw_b)
        except Exception:
            data_b = {"raw": raw_b}

        res_code_a = data_a.get("data", {}).get("apply_result")
        res_code_b = data_b.get("data", {}).get("apply_result")

        winner = None
        if res_code_a == 1:
            winner = "SHOT_1_PRIMARY"
        elif res_code_b == 1:
            winner = "SHOT_2_SECONDARY"

        return {
            "mode": "DOUBLE_TAP",
            "winner": winner,
            "shot_1": {
                "variant": "is_retry=False",
                "rtt_ms": rtt_1,
                "status": resp_a.status,
                "data": data_a,
                "headers": headers_resp_a,
                "apply_result": res_code_a,
                "tc": data_a.get("tc")
            },
            "shot_2": {
                "variant": "is_retry=True",
                "rtt_ms": rtt_2,
                "status": resp_b.status,
                "data": data_b,
                "headers": headers_resp_b,
                "apply_result": res_code_b,
                "tc": data_b.get("tc")
            }
        }

    def close(self):
        for c in (self.conn_a, self.conn_b):
            if c:
                try:
                    c.close()
                except Exception:
                    pass
        self.conn_a = None
        self.conn_b = None
