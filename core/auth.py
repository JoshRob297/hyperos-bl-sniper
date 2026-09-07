"""
Authentication and Session Management for Xiaomi HyperOS Community.
Handles cookie verification, account state interpretation, and passToken auto-renewal.
"""

import os
import json
import time
import ssl
import http.client
import http.cookiejar
import urllib.request
import urllib.parse
import hashlib
from typing import Tuple, Dict, Any, Optional

CONFIG_FILE = "config.json"
BBS_SID = "16391"
API_HOST = "sgp-api.buy.mi.com"
STATE_PATH = "/bbs/api/global/user/bl-switch/state"
OFFICIAL_VERSION_CODE = "500439"
OFFICIAL_VERSION_NAME = "5.4.39"


def generate_stable_device_id(user_id: str) -> str:
    """Generates a stable deviceId following Xiaomi's f.r formula: SHA1 uppercase hex."""
    seed = f"Xiaomi_HyperOS_Device_{user_id}_Sniper"
    digest = hashlib.sha1(seed.encode("utf-8")).digest()
    val = int.from_bytes(digest, "big")
    return f"{val:032X}"


def load_config(path: str = CONFIG_FILE) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_config(data: Dict[str, Any], path: str = CONFIG_FILE) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    mode = 0o600
    try:
        fd = os.open(path, flags, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


def extract_cookies_with_jar(redirect_url: str) -> Dict[str, str]:
    """
    Follows callback redirects with CookieJar enabled, capturing all Set-Cookie headers.
    """
    captured: Dict[str, str] = {}
    if not redirect_url:
        return captured

    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    req = urllib.request.Request(redirect_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

    try:
        with opener.open(req, timeout=10) as resp:
            # Check cookies in jar
            for c in cj:
                if c.name in ["userId", "cUserId", "new_bbs_serviceToken", "passToken", "serviceToken"]:
                    captured[c.name] = c.value

            # Also inspect headers directly
            for header, val in resp.headers.items():
                if header.lower() == "set-cookie":
                    for part in val.split(";"):
                        if "=" in part:
                            k, v = part.strip().split("=", 1)
                            if k in ["userId", "cUserId", "new_bbs_serviceToken", "passToken", "serviceToken"]:
                                captured[k] = v
    except Exception:
        pass
    return captured


def should_renew_token(cookies: Dict[str, Any], next_target_epoch: float, ttl_days: int = 5, margin_seconds: int = 7200) -> bool:
    """
    Evalúa proactivamente si al token le queda menos vida útil que el tiempo
    hasta el siguiente disparo + margen de seguridad (2 horas).
    """
    now = time.time()
    obtained_at = float(cookies.get("obtained_at", now))
    # TTL estimado por defecto de 5 días si no hay fecha explícita
    expires_at = float(cookies.get("expires_at", obtained_at + (ttl_days * 86400)))
    return expires_at < (next_target_epoch + margin_seconds)


def refresh_service_token_via_passtoken(cookies: Dict[str, str]) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Auto-renueva el new_bbs_serviceToken usando el passToken permanente de Xiaomi.
    Endpoint oficial: GET https://account.xiaomi.com/pass/serviceLogin?sid=16391&_json=true
    Returns: (success, new_service_token, error_msg)
    """
    user_id = cookies.get("userId")
    pass_token = cookies.get("passToken")
    if not user_id or not pass_token:
        return False, None, "Falta userId o passToken para auto-renovación."

    login_url = f"https://account.xiaomi.com/pass/serviceLogin?sid={BBS_SID}&_json=true"
    cookie_str = f"userId={user_id}; passToken={pass_token}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Cookie": cookie_str
    }

    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    req = urllib.request.Request(login_url, headers=headers)
    try:
        with opener.open(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8").replace("&&&START&&&", "")
            data = json.loads(raw)

            # Buscar token en CookieJar
            for c in cj:
                if c.name in ("new_bbs_serviceToken", "serviceToken"):
                    return True, c.value, None

            # Buscar en respuesta JSON o location
            location = data.get("location")
            if location:
                redirect_cookies = extract_cookies_with_jar(location)
                if "new_bbs_serviceToken" in redirect_cookies:
                    return True, redirect_cookies["new_bbs_serviceToken"], None
                elif "serviceToken" in redirect_cookies:
                    return True, redirect_cookies["serviceToken"], None

            sec_token = data.get("serviceToken")
            if sec_token:
                return True, sec_token, None

            return False, None, f"Respuesta inesperada al refrescar: {data.get('description', 'Sin token')}"
    except Exception as e:
        return False, None, str(e)


def check_session(cookies: Dict[str, str]) -> Tuple[bool, Dict[str, Any]]:
    """
    Checks if the provided cookies are still authenticated and authorized.
    Uses official Xiaomi Community cookie format and Accept header.
    Returns: (is_valid, response_data)
    """
    token = cookies.get("new_bbs_serviceToken", "")
    dev_id = cookies.get("deviceId") or generate_stable_device_id(cookies.get("userId", "default"))
    v_code = cookies.get("versionCode", OFFICIAL_VERSION_CODE)
    v_name = cookies.get("versionName", OFFICIAL_VERSION_NAME)

    cookie_str = f"new_bbs_serviceToken={token};versionCode={v_code};versionName={v_name};deviceId={dev_id};"
    headers = {
        "Host": API_HOST,
        "User-Agent": "Mozilla/5.0 (Linux; Android 14; 24069PC21G) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/128.0.6613.88 Mobile Safari/537.36 Xiaomi/MiuiForum/5.4.39",
        "Cookie": cookie_str,
        "Content-Type": "application/json;charset=utf-8",
        "Accept": "application/json",
        "Origin": "https://c.mi.com",
        "Referer": "https://c.mi.com/",
        "Connection": "close"
    }

    ctx = ssl.create_default_context()
    conn = http.client.HTTPSConnection(API_HOST, 443, context=ctx, timeout=8)
    try:
        conn.request("GET", STATE_PATH, headers=headers)
        resp = conn.getresponse()
        data = json.loads(resp.read().decode("utf-8"))
        code = data.get("code")
        if code == 0:
            return True, data
        return False, data
    except Exception as e:
        return False, {"error": str(e)}
    finally:
        conn.close()


def interpret_account_state(data: Dict[str, Any]) -> Tuple[bool, str, str]:
    """
    Interprets the /bl-switch/state payload into an actionable decision.

    Returns: (can_fire, status_code, message)
      status_code: "READY" | "APPROVED" | "TEMP_BLOCKED" | "ACCOUNT_TOO_NEW" | "UNKNOWN"

    Semantics (verified against the Xiaomi Community app):
      - is_pass == 1            -> request already approved, unlock window open.
      - is_pass == 4:
          * button_state == 1   -> account eligible, safe to fire.
          * button_state == 2   -> temporarily rate-limited until deadline_format.
          * button_state == 3   -> account younger than 30 days, not eligible.
      - anything else           -> unknown/transient state; fire anyway (single shot).
    """
    payload = data.get("data", {}) if isinstance(data, dict) else {}
    if not isinstance(payload, dict):
        payload = {}
    is_pass = payload.get("is_pass")
    button_state = payload.get("button_state")
    deadline = payload.get("deadline_format", "")

    if str(is_pass) in ("1", "True", "true"):
        return False, "APPROVED", f"Permiso aprobado; desbloqueo disponible hasta {deadline or 'fecha no especificada'}."

    if str(is_pass) in ("4", "4.0"):
        if str(button_state) == "1":
            return True, "READY", "Cuenta elegible: se puede enviar la solicitud."
        if str(button_state) == "2":
            return False, "TEMP_BLOCKED", (
                f"Cuenta bloqueada temporalmente hasta {deadline or 'fecha no especificada'}."
            )
        if str(button_state) == "3":
            return False, "ACCOUNT_TOO_NEW", (
                "La cuenta se creó hace menos de 30 días; Xiaomi aún no permite solicitar."
            )
        return True, "UNKNOWN", f"Estado de cuenta no reconocido (button_state={button_state}); se intentará el disparo."

    return True, "UNKNOWN", f"Estado de cuenta no reconocido (is_pass={is_pass}); se intentará el disparo."


def format_button_state(state: Any, lang: Optional[str] = None) -> str:
    """Normalizes raw Xiaomi button_state integer into localized human-readable labels."""
    from core.i18n import t
    s = str(state)
    if s == "1":
        return t("btn_ready", lang=lang)
    elif s == "2":
        return t("btn_cooldown", lang=lang)
    elif s == "3":
        return t("btn_too_new", lang=lang)
    return t("btn_unknown", lang=lang, state=state)


def format_pass_state(is_pass: Any, lang: Optional[str] = None) -> str:
    """Normalizes raw Xiaomi is_pass integer into localized human-readable labels."""
    from core.i18n import t
    s = str(is_pass)
    if s in ("1", "True", "true"):
        return t("pass_approved", lang=lang)
    elif s in ("4", "4.0"):
        return t("pass_pending", lang=lang)
    return t("pass_unknown", lang=lang, is_pass=is_pass)
