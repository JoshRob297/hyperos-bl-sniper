"""
Atomic Multi-NTP Synchronization and Microsecond Busy-Wait Timer.
"""

import time
import socket
import struct
from typing import List

NTP_SERVERS = [
    "time.google.com",
    "pool.ntp.org",
    "time.cloudflare.com",
    "time.apple.com",
]


def get_ntp_offset(servers: List[str] = None) -> float:
    """
    Queries multiple NTP servers in order and returns the clock offset in seconds.
    Offset = (T_ntp - T_local). Positive means local clock is behind real time.
    """
    targets = servers or NTP_SERVERS
    for server in targets:
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client.settimeout(2.0)
            data = b"\x1b" + 47 * b"\0"
            t_send = time.time()
            client.sendto(data, (server, 123))
            msg, _ = client.recvfrom(1024)
            t_recv = time.time()
            client.close()

            unpacked = struct.unpack("!12I", msg[0:48])
            ntp_time = unpacked[10] + float(unpacked[11]) / 2**32 - 2208988800
            local_mid = (t_send + t_recv) / 2
            offset = ntp_time - local_mid
            return offset
        except Exception:
            continue
    return 0.0


def wait_until(target_epoch: float, ntp_offset: float = 0.0, fine_tune_seconds: float = 2.0) -> None:
    """
    Hybrid sleeper:
    - Coarse phase: time.sleep() until `fine_tune_seconds` remain.
    - Medium phase: 5ms sleeps until 50ms remain.
    - Spin phase: perf_counter busy-wait for microsecond precision.

    perf_counter() is monotonic and high-resolution on Linux, macOS and Windows,
    unlike time.time() (which can have ~15ms granularity on Windows).
    """
    # Coarse phase
    while True:
        now_true = time.time() + ntp_offset
        remaining = target_epoch - now_true
        if remaining <= fine_tune_seconds:
            break
        time.sleep(min(max(remaining - fine_tune_seconds, 0.0), 0.5))

    # Medium phase (5ms granularity until 50ms left)
    while True:
        now_true = time.time() + ntp_offset
        remaining = target_epoch - now_true
        if remaining <= 0.05:
            break
        time.sleep(0.005)

    # Spin phase: convert absolute wall target into perf_counter domain (µs precision).
    # Sample both clocks back-to-back and use the midpoint to cancel out the
    # inter-sample gap, avoiding systematic skew in the computed target.
    wall_before = time.time()
    pc_before = time.perf_counter()
    wall_after = time.time()
    pc_after = time.perf_counter()
    start_wall = (wall_before + wall_after) / 2.0
    start_pc = (pc_before + pc_after) / 2.0
    target_pc = start_pc + (target_epoch - start_wall - ntp_offset)
    while time.perf_counter() < target_pc:
        pass