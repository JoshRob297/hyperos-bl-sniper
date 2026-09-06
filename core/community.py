"""
Community Collective Intelligence Module for HyperOS BL Sniper.
Enables anonymous telemetry submission and global bias synchronization
without exposing credentials or server IPs.
"""

import json
import time
import hashlib
import platform
import urllib.request
from typing import Dict, Any, Optional

# Official telemetry intake endpoint (VPS edge, HTTPS)
TELEMETRY_ENDPOINT = "https://telemetry.joces.org/v1/telemetry"

# GitHub CDN raw URL for published consensus calibration
COMMUNITY_BIAS_URL = "https://raw.githubusercontent.com/JoshRob297/hyperos-bl-sniper/data/community_bias.json"

VERSION = "1.1.0"


def generate_ephemeral_node_id() -> str:
    """
    Generates an anonymous deterministic node ID for the current day.
    Prevents long-term cross-day user tracking while allowing single-vote rate limiting per day.
    """
    day_str = time.strftime("%Y-%m-%d", time.gmtime())
    raw_seed = f"{platform.node()}-{platform.machine()}-{day_str}"
    return hashlib.sha256(raw_seed.encode("utf-8")).hexdigest()[:12]


def fetch_community_bias(timeout: float = 3.0) -> Optional[Dict[str, Any]]:
    """
    Fetches the latest consensus bias from the official GitHub data branch.
    Fails safely and quickly (3s timeout) to never block execution before shooting.
    """
    try:
        req = urllib.request.Request(
            COMMUNITY_BIAS_URL,
            headers={"User-Agent": f"HyperOSSniper/{VERSION} (Collective-Intelligence)"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return data
    except Exception:
        # Transparent fallback to local calibration on any network/format issue
        return None
    return None


def sanitize_telemetry_payload(raw_telemetry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Strips all sensitive keys and keeps ONLY sanitized numerical and timing metrics.
    Ensures zero leakage of credentials, tokens, account numbers or hardware IDs.
    """
    allowed_keys = {
        "v", "nid", "ts", "rtt", "one_way", "bias_applied",
        "mode", "winner", "shot1_res", "shot2_res",
        "srv_date", "arrival_delta_ms", "outcome"
    }

    clean = {k: v for k, v in raw_telemetry.items() if k in allowed_keys}
    clean["v"] = VERSION
    clean["nid"] = str(clean.get("nid", generate_ephemeral_node_id()))
    return clean


def report_telemetry_async(telemetry_data: Dict[str, Any], timeout: float = 4.0) -> bool:
    """
    Transmits sanitized, anonymous shot telemetry to the official HTTPS collector.
    Fails gracefully without throwing exceptions or interrupting user workflow.
    """
    clean_data = sanitize_telemetry_payload(telemetry_data)
    try:
        req_data = json.dumps(clean_data, separators=(",", ":")).encode("utf-8")
        req = urllib.request.Request(
            TELEMETRY_ENDPOINT,
            data=req_data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": f"HyperOSSniper/{VERSION}"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False