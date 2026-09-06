"""
Adaptive Timing Engine for Xiaomi HyperOS Bootloader Snipe.
Performs coarse edge-correction based on Xiaomi server clock Skew (HTTP Date Header).
"""

import time
import email.utils
from typing import Dict, Any, Tuple, Optional
from core.i18n import t

STEP_DELAY_EARLY_MS = 60.0    # If arrived before server midnight (e.g. 15:59:59 GMT), delay next shot by 60ms
MAX_BIAS_MS = 180.0           # Max allowed bias shift (+180ms)


def parse_server_date_epoch(date_header: Optional[str]) -> Optional[float]:
    """Parses RFC 2822 HTTP Date header (e.g. 'Sun, 06 Sep 2026 16:00:00 GMT') into UTC epoch."""
    if not date_header or date_header == "N/A":
        return None
    try:
        parsed_tuple = email.utils.parsedate_to_datetime(date_header)
        return parsed_tuple.timestamp()
    except Exception:
        return None


def translate_xiaomi_result(code: Optional[int], apply_result: Optional[int], deadline: str = "", lang: Optional[str] = None) -> str:
    """Translates raw Xiaomi status and error codes into localized diagnostic messages."""
    if code == 100004:
        return t("res_token_expired", lang=lang)
    if code == 100001:
        return t("res_invalid_format", lang=lang)

    if apply_result == 1:
        return t("res_approved", lang=lang, deadline=deadline)
    elif apply_result == 2:
        return t("res_account_error", lang=lang, deadline=deadline)
    elif apply_result == 3:
        return t("res_exhausted", lang=lang, deadline=deadline)
    elif apply_result == 4:
        return t("res_apply_failed", lang=lang)
    elif apply_result == 5:
        return t("res_try_minute", lang=lang)
    elif apply_result == 6:
        return t("res_risk_control", lang=lang)
    else:
        return t("res_unknown", lang=lang, res=apply_result, code=code)


def evaluate_shot_feedback(
    target_epoch: float,
    current_bias_ms: float,
    server_date_header: Optional[str],
    apply_result: Optional[int],
    resp_latency_ms: float,
    arrival_est_epoch: float,
    lang: Optional[str] = None
) -> Tuple[float, str, Dict[str, Any]]:
    """
    Evaluates the shot result and determines the next bias adjustment.
    Returns: (new_bias_ms, decision_reason, telemetry_record)
    """
    server_epoch = parse_server_date_epoch(server_date_header)
    telemetry = {
        "timestamp": time.time(),
        "target_epoch": target_epoch,
        "arrival_est_epoch": arrival_est_epoch,
        "server_date": server_date_header,
        "server_epoch": server_epoch,
        "apply_result": apply_result,
        "resp_latency_ms": resp_latency_ms,
        "applied_bias_ms": current_bias_ms,
    }

    # Case 1: SUCCESS (Winning telemetry)
    if apply_result == 1:
        telemetry["outcome"] = "SUCCESS"
        return current_bias_ms, t("reason_win", lang=lang), telemetry

    # Case 2: Arrived BEFORE server midnight (Date header shows previous second, e.g. 15:59:59 GMT)
    if server_epoch is not None and server_epoch < target_epoch:
        new_bias = min(current_bias_ms + STEP_DELAY_EARLY_MS, MAX_BIAS_MS)
        reason = t("reason_early", lang=lang, server_date=server_date_header, step=STEP_DELAY_EARLY_MS)
        telemetry["outcome"] = "EARLY_SECOND"
        telemetry["new_bias_ms"] = new_bias
        return new_bias, reason, telemetry

    # Case 3: Arrived IN WINDOW (Date header shows 16:00:00 GMT or later)
    telemetry["outcome"] = "IN_WINDOW_EXHAUSTED"
    telemetry["new_bias_ms"] = current_bias_ms
    reason = t("reason_exhausted", lang=lang, server_date=server_date_header, bias=current_bias_ms)
    return current_bias_ms, reason, telemetry


def update_config_calibration(config: Dict[str, Any], new_bias_ms: float, telemetry: Dict[str, Any]) -> None:
    """Updates config dict in-place with new calibration settings and log."""
    if "calibration" not in config or not isinstance(config["calibration"], dict):
        config["calibration"] = {
            "auto_tune": True,
            "bias_ms": 0.0,
            "winning_telemetry": None,
            "history": []
        }

    cal = config["calibration"]
    cal["bias_ms"] = round(new_bias_ms, 2)

    if telemetry.get("outcome") == "SUCCESS":
        cal["winning_telemetry"] = telemetry

    history = cal.setdefault("history", [])
    history.append(telemetry)
    # Keep last 14 entries (2 weeks of snipes)
    if len(history) > 14:
        del history[:-14]
