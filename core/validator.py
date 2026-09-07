"""
Hardware Validator, USB Detection & Official Bootloader Authorization Auditor.
Handles ADB authorization detection, automatic transition to Fastboot,
ahaUnlock cryptographic verification, and local unlock date projection.
Strict Clean UI compliance: zero emojis.
"""

import os
import sys
import time
import json
import hashlib
import random
import datetime
import subprocess
from typing import Dict, Any, Tuple, Optional
from core.i18n import t


def run_cmd(cmd_list: list) -> Tuple[int, str]:
    """Safely runs a subprocess command returning (returncode, stdout+stderr)."""
    try:
        p = subprocess.run(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=15)
        return p.returncode, p.stdout.strip()
    except subprocess.TimeoutExpired:
        return -1, "Command timed out"
    except FileNotFoundError:
        return -1, f"Command not found: {cmd_list[0]}"
    except Exception as e:
        return -1, str(e)


def detect_fastboot_device(fastboot_bin: str = "fastboot") -> Optional[str]:
    """Returns serial number if a device is connected in Fastboot mode, else None."""
    code, out = run_cmd([fastboot_bin, "devices"])
    if code == 0 and out:
        for line in out.splitlines():
            parts = line.strip().split()
            if len(parts) >= 2 and parts[1] == "fastboot":
                return parts[0]
    return None


def detect_adb_status(adb_bin: str = "adb") -> Tuple[Optional[str], Optional[str]]:
    """
    Checks ADB device state.
    Returns: (serial, state) where state in ("device", "unauthorized", None)
    """
    code, out = run_cmd([adb_bin, "devices"])
    if code == 0 and out:
        for line in out.splitlines():
            line = line.strip()
            if not line or line.startswith("List of devices"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                return parts[0], parts[1].lower()
    return None, None


def wait_for_adb_authorization(adb_bin: str = "adb", timeout_seconds: int = 35) -> bool:
    """
    Guides the user and polls until ADB authorization dialog is accepted on phone.
    """
    print(t("val_adb_unauth_notice"))
    print(t("val_adb_unauth_instructions"))

    start = time.time()
    while time.time() - start < timeout_seconds:
        serial, state = detect_adb_status(adb_bin)
        if state == "device":
            print(t("val_adb_auth_success"))
            return True
        time.sleep(1.5)
    return False


def transition_adb_to_fastboot(adb_bin: str = "adb", fastboot_bin: str = "fastboot") -> bool:
    """
    Reboots device from authorized ADB mode into Fastboot and confirms presence.
    """
    print(t("val_adb_rebooting"))
    run_cmd([adb_bin, "reboot", "bootloader"])

    start = time.time()
    while time.time() - start < 15:
        serial = detect_fastboot_device(fastboot_bin)
        if serial:
            time.sleep(1)
            return True
        time.sleep(1)
    return False


def prompt_and_prepare_device(fastboot_bin: str = "fastboot", adb_bin: str = "adb") -> Tuple[bool, Optional[str]]:
    """
    Interactive assistant inviting the user to connect the phone via ADB or Fastboot.
    Handles ADB RSA authorization checks and automatic bootloader rebooting.
    Returns: (success, fastboot_serial)
    """
    while True:
        # Check if already in Fastboot
        serial = detect_fastboot_device(fastboot_bin)
        if serial:
            return True, serial

        # Check if in ADB
        adb_serial, adb_state = detect_adb_status(adb_bin)
        if adb_state == "unauthorized":
            if wait_for_adb_authorization(adb_bin):
                if transition_adb_to_fastboot(adb_bin, fastboot_bin):
                    return True, detect_fastboot_device(fastboot_bin)
        elif adb_state == "device":
            if transition_adb_to_fastboot(adb_bin, fastboot_bin):
                return True, detect_fastboot_device(fastboot_bin)

        # Nothing detected; invite user to plug USB cable
        print("\n" + "=" * 65)
        print(t("val_prompt_header"))
        print(t("val_prompt_instructions"))
        print("=" * 65)

        try:
            choice = input(t("val_prompt_press_enter")).strip().lower()
            if choice in ("s", "q", "exit", "skip"):
                return False, None
        except (KeyboardInterrupt, EOFError):
            return False, None

        # Check again after user pressed enter
        time.sleep(1)
        serial = detect_fastboot_device(fastboot_bin)
        if serial:
            return True, serial

        adb_serial, adb_state = detect_adb_status(adb_bin)
        if adb_state == "unauthorized":
            if wait_for_adb_authorization(adb_bin):
                if transition_adb_to_fastboot(adb_bin, fastboot_bin):
                    return True, detect_fastboot_device(fastboot_bin)
        elif adb_state == "device":
            if transition_adb_to_fastboot(adb_bin, fastboot_bin):
                return True, detect_fastboot_device(fastboot_bin)

        print(t("val_no_device_found"))
        try:
            retry = input(t("val_prompt_retry")).strip().lower()
            if retry not in ("", "s", "si", "sí", "y", "yes"):
                return False, None
        except (KeyboardInterrupt, EOFError):
            return False, None


def get_fastboot_identifiers(fastboot_bin: str = "fastboot") -> Tuple[Optional[str], Optional[str]]:
    """Extracts hardware codename (product) and device token from processor via Fastboot."""
    code_p, out_p = run_cmd([fastboot_bin, "getvar", "product"])
    product = None
    if code_p == 0:
        for line in out_p.splitlines():
            if "product:" in line:
                product = line.split("product:")[1].strip()
                break

    code_t, out_t = run_cmd([fastboot_bin, "getvar", "token"])
    token = None
    if code_t == 0:
        for line in out_t.splitlines():
            if "token:" in line:
                token = line.split("token:")[1].strip()
                break

    return product, token


def format_unlock_projection(wait_hours: int, lang: Optional[str] = None) -> Dict[str, Any]:
    """
    Calculates exact local unlock date and time from wait_hours.
    """
    unlock_epoch = time.time() + (wait_hours * 3600)
    local_dt = datetime.datetime.fromtimestamp(unlock_epoch).astimezone()
    tz_name = local_dt.tzname() or "Hora Local"
    formatted_date = local_dt.strftime("%Y-%m-%d %H:%M:%S")

    return {
        "wait_hours": wait_hours,
        "unlock_epoch": unlock_epoch,
        "formatted_local": f"{formatted_date} ({tz_name})",
        "iso_utc": local_dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    }


def query_official_unlock_state(config: Dict[str, Any], fastboot_bin: str = "fastboot") -> Dict[str, Any]:
    """
    Performs official cryptographic consultation against Xiaomi's ahaUnlock security cluster.
    Returns normalized dictionary describing the unlock verdict.
    """
    try:
        import migate
        from miunlock.utils import _send
    except ImportError:
        return {"code": -1, "error": "Libraries 'migate' or 'miunlock' not found"}

    # 1. Load active unlockApi session
    pt = migate.get_passtoken({"sid": "unlockApi"}, silent=True)
    if not pt:
        return {"code": -1, "error": "No active unlockApi session found. Run 'python cli.py login' first."}

    svc = migate.get_service(pt, {"sid": "unlockApi"})
    if not svc:
        return {"code": -1, "error": "Failed to negotiate unlockApi service session with Xiaomi."}

    ssec = svc.get("servicedata", {}).get("ssecurity")
    cookies = svc.get("cookies", {})
    device_id_web = svc.get("servicedata", {}).get("deviceId", "")

    # 2. Determine region domain
    try:
        region = migate.get_region(pt)
    except Exception:
        region = "SG"

    if region == "CN":
        domain = "https://unlock.update.miui.com"
    elif region == "IN":
        domain = "https://in-unlock.update.intl.miui.com"
    elif region == "RU":
        domain = "https://ru-unlock.update.intl.miui.com"
    else:
        domain = "https://unlock.update.intl.miui.com"

    # 3. Request cryptographic nonce
    r_val = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=16))
    nonce_resp = _send("/api/v2/nonce", {"r": r_val}, domain, ssec, cookies)
    if "error" in nonce_resp or nonce_resp.get("code") != 0:
        return {"code": -1, "error": f"Failed to obtain nonce: {nonce_resp}"}
    nonce = nonce_resp["nonce"]

    # 4. Extract hardware parameters from USB Fastboot
    product, device_token = get_fastboot_identifiers(fastboot_bin)
    if not product or not device_token:
        return {"code": -1, "error": "Could not read product or deviceToken from Fastboot"}

    # 5. Check hardware eligibility and clean status
    _send("/api/v2/unlock/device/clear", {"appId": "1", "data": {"product": product}, "nonce": nonce}, domain, ssec, cookies)

    # 6. Execute official ahaUnlock consultation
    data_payload = {
        "clientId": "2",
        "clientVersion": "7.6.727.43",
        "deviceInfo": {"boardVersion": "", "deviceName": "", "product": product, "socId": ""},
        "deviceToken": device_token,
        "language": "en",
        "operate": "unlock",
        "pcId": hashlib.md5(device_id_web.encode()).hexdigest(),
        "region": "",
        "uid": cookies.get("userId"),
    }

    result = _send("/api/v3/ahaUnlock", {"appId": "1", "data": data_payload, "nonce": nonce}, domain, ssec, cookies)
    result["product"] = product
    result["userId"] = cookies.get("userId")
    return result


def safe_fastboot_reboot(fastboot_bin: str = "fastboot") -> bool:
    """Safely reboots device back to Android OS."""
    code, _ = run_cmd([fastboot_bin, "reboot"])
    return code == 0
