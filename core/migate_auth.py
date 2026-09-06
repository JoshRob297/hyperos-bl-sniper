"""
Authentication Gateway Adapter for HyperOS BL Sniper.
Integrates `migate` (Xiaomi official authentication gateway) for robust
browser, terminal, and SMS/OTP logins without depending on fragile QR camera scanners.
Also provides a manual cookie injection flow for advanced users.
Zero emojis: strict clean UI compliance.
"""

import time
import getpass
from typing import Dict, Any, Optional
from core.auth import generate_stable_device_id, OFFICIAL_VERSION_CODE, OFFICIAL_VERSION_NAME, check_session
from core.i18n import t

BBS_AUTH_PARAMS = {"sid": "18n_bbs_global"}


def build_auth_block(pass_token_dict: Dict[str, Any], service_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pure mapping function: transforms migate's passToken and service responses
    into hyperos-bl-sniper's internal config.json auth schema.
    Guarantees stable SHA-1 deviceId formatted specifically for Xiaomi BBS.
    """
    user_id = str(pass_token_dict.get("userId", ""))
    pass_token = pass_token_dict.get("passToken", "")

    servicedata = service_dict.get("servicedata", {}) if isinstance(service_dict, dict) else {}
    cookies = service_dict.get("cookies", {}) if isinstance(service_dict, dict) else {}

    c_user_id = servicedata.get("cUserId") or cookies.get("cUserId", "")
    new_bbs_token = cookies.get("new_bbs_serviceToken") or cookies.get("serviceToken", "")

    # Derive deterministic SHA-1 deviceId based on userId to match Xiaomi Community app expectations
    device_id = generate_stable_device_id(user_id) if user_id else ""

    return {
        "userId": user_id,
        "cUserId": c_user_id,
        "new_bbs_serviceToken": new_bbs_token,
        "passToken": pass_token,
        "deviceId": device_id,
        "versionCode": OFFICIAL_VERSION_CODE,
        "versionName": OFFICIAL_VERSION_NAME,
        "obtained_at": int(time.time()),
    }


def login_with_migate(silent: bool = False) -> Optional[Dict[str, Any]]:
    """
    Executes official interactive Xiaomi login via migate gateway.
    Supports Browser (recommended, official QR), Terminal (password), and SMS code.
    Returns clean auth block or None on failure.
    """
    try:
        import migate
    except ImportError:
        print("[ERROR] Library 'migate' is not installed. Run: pip install migate")
        return None

    pass_token = migate.get_passtoken(BBS_AUTH_PARAMS, silent=silent)
    if not pass_token:
        print("[ERROR] Failed to obtain passToken from Xiaomi authentication gateway.")
        return None

    service = migate.get_service(pass_token, BBS_AUTH_PARAMS)
    if not service:
        print("[ERROR] Failed to obtain BBS serviceToken from Xiaomi.")
        return None

    auth_block = build_auth_block(pass_token, service)
    if not auth_block.get("userId") or not auth_block.get("new_bbs_serviceToken"):
        print("[ERROR] Authentication response missing critical tokens.")
        return None

    return auth_block


def login_manual_prompt() -> Optional[Dict[str, Any]]:
    """
    Interactive manual cookie injection assistant.
    Guides the user to paste cookies from c.mi.com and validates them immediately.
    """
    print("\n" + "=" * 65)
    print(" [MANUAL COOKIE INJECTION ASSISTANT]")
    print(" Instructions:")
    print(" 1. Open https://c.mi.com in your PC browser and log in.")
    print(" 2. Press F12 -> Application/Storage tab -> Cookies -> https://c.mi.com")
    print(" 3. Copy the values of 'userId' and 'new_bbs_serviceToken'")
    print("=" * 65 + "\n")

    try:
        user_id = input("Enter your Xiaomi Account ID (userId): ").strip()
        if not user_id:
            print("[ERROR] Account ID cannot be empty.")
            return None

        c_user_id = input("Enter cUserId (optional, leave blank to auto-derive): ").strip()

        token = getpass.getpass("Paste new_bbs_serviceToken (hidden input): ").strip()
        if not token:
            print("[ERROR] Token cannot be empty.")
            return None

        pass_token = getpass.getpass("Paste passToken (optional, enables auto-renewal): ").strip()

        auth_candidate = {
            "userId": user_id,
            "cUserId": c_user_id or user_id,
            "new_bbs_serviceToken": token,
            "passToken": pass_token,
            "deviceId": generate_stable_device_id(user_id),
            "versionCode": OFFICIAL_VERSION_CODE,
            "versionName": OFFICIAL_VERSION_NAME,
            "obtained_at": int(time.time()),
        }

        print("\n[*] Validating cookies directly with Xiaomi server...")
        valid, data = check_session(auth_candidate)
        if not valid:
            print(f"[ERROR] Xiaomi rejected provided cookies: {data.get('msg', 'Invalid session')}")
            return None

        print("[OK] Cookies validated successfully with Xiaomi server.")
        return auth_candidate

    except (KeyboardInterrupt, EOFError):
        print("\n[!] Manual input cancelled.")
        return None
