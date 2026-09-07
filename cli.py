#!/usr/bin/env python3
"""
HyperOS Bootloader Quota Sniper (Unified Multi-Platform CLI)
Usage:
  python cli.py start       - Unified All-in-One: checks session, auto-schedules, and enters sniper loop
  python cli.py login       - Interactive Xiaomi official assistant or manual cookie injection
  python cli.py status      - Checks token validity and permission state
  python cli.py schedule    - Auto-registers daily background task in OS
  python cli.py unschedule  - Removes background task
  python cli.py run         - Starts the microsecond sniper loop
"""

import sys
import os
import time
import json
import datetime
from core.auth import (
    load_config, save_config, check_session, interpret_account_state,
    should_renew_token, refresh_service_token_via_passtoken,
    format_button_state, format_pass_state
)
from core.calibration import evaluate_shot_feedback, update_config_calibration, translate_xiaomi_result
from core.ntp import get_ntp_offset, wait_until
from core.network import measure_tcp_rtt, get_next_beijing_midnight, SnipeSession
from core.scheduler import enable_schedule, disable_schedule, is_scheduled
from core.notifier import dispatch_notification
from core.community import fetch_community_bias, report_telemetry_async
from core.i18n import t, set_language, get_language
from core.migate_auth import login_with_migate, login_manual_prompt

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def cmd_login():
    config = load_config(CONFIG_PATH) or {}
    if "language" in config:
        set_language(config["language"])

    # Check for direct manual flag: python cli.py login --manual
    is_manual = "--manual" in sys.argv

    print("=" * 65)
    print(t("login_banner"))
    print("=" * 65)

    if not is_manual:
        print("\n" + t("login_menu_title"))
        try:
            choice = input("\n" + t("login_menu_prompt")).strip()
            if choice == "2":
                is_manual = True
        except (KeyboardInterrupt, EOFError):
            return

    if is_manual:
        auth_block = login_manual_prompt()
    else:
        auth_block = login_with_migate()

    if not auth_block:
        print(t("login_timeout"))
        return

    config["auth"] = auth_block

    # Configuracion comunitaria (Opt-in interactivo con reciprocidad obligatoria)
    if "community" not in config:
        print(t("login_community_title"))
        print(t("login_community_desc"))
        try:
            ans = input(t("login_community_prompt")).strip().lower()
            opt_in = ans in ("", "s", "si", "sí", "y", "yes")
        except (EOFError, KeyboardInterrupt):
            opt_in = True
        config["community"] = {
            "share_metrics": opt_in,
            "fetch_global_bias": opt_in
        }

    # Regla de Reciprocidad Simetrica: Si el usuario desea beneficiarse del bias comunitario,
    # es obligatorio compartir metricas anonimas tras el disparo.
    comm_cfg = config.get("community", {})
    if comm_cfg.get("fetch_global_bias", False) and not comm_cfg.get("share_metrics", False):
        comm_cfg["share_metrics"] = True
        config["community"] = comm_cfg

    save_config(config, CONFIG_PATH)

    print("\n" + "=" * 60)
    print(t("login_success"))
    print(f" [OK] User ID: {auth_block.get('userId')}")
    print(t("login_saved_config"))
    print("=" * 60)


def cmd_status():
    config = load_config(CONFIG_PATH)
    if not config or "auth" not in config:
        print(t("status_no_config"))
        return

    if "language" in config:
        set_language(config["language"])

    cookies = config["auth"]
    user_id = cookies.get("userId", "N/A")
    print(t("status_checking", user_id=user_id))
    valid, data = check_session(cookies)
    sched = is_scheduled()

    print(t("status_header"))
    sched_label = t("status_active") if sched else t("status_inactive")
    print(t("status_sched", state=sched_label))
    if valid:
        can_fire, status_code, state_msg = interpret_account_state(data)
        raw_btn_state = data.get("data", {}).get("button_state")
        raw_is_pass = data.get("data", {}).get("is_pass")
        deadline = data.get("data", {}).get("deadline_format", "N/A")

        btn_label = format_button_state(raw_btn_state)
        pass_label = format_pass_state(raw_is_pass)

        print(t("status_token_valid"))
        print(t("status_is_pass", is_pass=pass_label))
        print(t("status_btn_state", btn_state=btn_label))
        print(t("status_deadline", deadline=deadline))
        print(t("status_diag", state_msg=state_msg))
        cal_cfg = config.get("calibration", {})
        if cal_cfg:
            b_ms = cal_cfg.get("bias_ms", 0.0)
            print(t("status_cal", bias=b_ms))
    else:
        code = data.get("code")
        if code == 100004:
            print(t("status_token_expired_100004"))
        else:
            print(t("status_token_invalid", msg=data.get('msg', 'Error desconocido')))
            print("  Recomendación: Ejecuta 'python cli.py login' para renovar.")


def format_duration(seconds: float) -> str:
    """Devuelve un formato legible de duración (ej. 23h 45m o 12m 30s)."""
    s = int(max(0, seconds))
    hours = s // 3600
    minutes = (s % 3600) // 60
    secs = s % 60
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


def cmd_schedule():
    config = load_config(CONFIG_PATH) or {}
    if "language" in config:
        set_language(config["language"])
    success, msg = enable_schedule(__file__)
    if success:
        print(t("sched_success", msg=msg))
    else:
        print(t("sched_error", msg=msg))


def cmd_unschedule():
    config = load_config(CONFIG_PATH) or {}
    if "language" in config:
        set_language(config["language"])
    success, msg = disable_schedule()
    print(t("unsched_info", msg=msg))


def cmd_run():
    config = load_config(CONFIG_PATH)
    if not config or "auth" not in config:
        print(t("run_no_config"))
        return

    if "language" in config:
        set_language(config["language"])

    cookies = config["auth"]
    user_id = cookies.get("userId", "N/A")

    # 1. Validar sesion antes de esperar y auto-renovar si es necesario
    valid, data = check_session(cookies)
    if not valid:
        code = data.get("code")
        # Intento reactivo de auto-renovacion con passToken si expiro (100004)
        if code == 100004 and cookies.get("passToken"):
            print(t("run_token_refreshing"))
            ok_renew, new_tok, err = refresh_service_token_via_passtoken(cookies)
            if ok_renew and new_tok:
                cookies["new_bbs_serviceToken"] = new_tok
                cookies["obtained_at"] = int(time.time())
                config["auth"] = cookies
                save_config(config, CONFIG_PATH)
                print(t("run_token_refreshed"))
                valid, data = check_session(cookies)

        if not valid:
            if code == 100004:
                err_msg = t("run_token_expired_stop", user_id=user_id)
            else:
                err_msg = t("run_token_invalid_stop", user_id=user_id)
            print(f"[ERROR] {err_msg}")
            dispatch_notification("Alerta Xiaomi Unlock", err_msg, config)
            return

    # 2. Interpretar el estado de la cuenta antes de decidir disparar
    can_fire, status_code, state_msg = interpret_account_state(data)
    if not can_fire:
        if status_code == "APPROVED":
            msg = t("run_approved_desched", user_id=user_id, state_msg=state_msg)
            print(f"[OK] {msg}")
            disable_schedule()
        else:
            msg = t("run_not_eligible", user_id=user_id, state_msg=state_msg)
            print(f"[!] {msg}")
        dispatch_notification("Xiaomi Unlock", msg, config)
        return

    target_epoch, target_utc = get_next_beijing_midnight()
    local_time = target_utc.astimezone()
    local_tz_name = datetime.datetime.now().astimezone().tzname() or "Hora Local"
    print(t("run_target_beijing"))
    print(t("run_target_local", local_time=local_time.strftime('%Y-%m-%d a las %H:%M:%S'), local_tz=local_tz_name))

    # 2. Sincronizacion NTP inicial
    ntp_offset = get_ntp_offset()
    print(t("run_ntp_sync", offset=ntp_offset*1000))

    now_true = time.time() + ntp_offset
    diff_initial = target_epoch - now_true

    # 3. Guarda de Espera Larga (> 15 minutos): Evitar spam TCP y sugerir scheduler
    if diff_initial > 900.0:
        duration_str = format_duration(diff_initial)
        print("\n" + "=" * 65)
        print(t("run_deep_sleep_banner", duration=duration_str))
        print("=" * 65)

        # Si corre en terminal interactiva, ofrecer registrar la tarea en el OS
        if sys.stdin.isatty():
            try:
                ans = input(t("run_deep_sleep_prompt")).strip().lower()
                if ans in ("", "s", "si", "sí", "y", "yes"):
                    cmd_schedule()
                    print(t("run_deep_sleep_scheduled"))
                    return
            except (EOFError, KeyboardInterrupt):
                pass

        print(t("run_deep_sleep_entering"))
        while True:
            now_true = time.time() + ntp_offset
            remaining = target_epoch - now_true
            if remaining <= 900.0:
                print(t("run_deep_sleep_waking", duration=format_duration(remaining)))
                ntp_offset = get_ntp_offset()
                break
            # Dormir en bloques de 15 minutos (o lo que sobre hasta T-15m)
            sleep_chunk = min(900.0, remaining - 900.0)
            local_now = (datetime.datetime.now() + datetime.timedelta(seconds=ntp_offset)).strftime('%H:%M:%S')
            print(t("run_deep_sleep_waiting", time=local_now, remaining=format_duration(remaining), chunk=format_duration(sleep_chunk)), flush=True)
            time.sleep(sleep_chunk)

    # 4. Profiling pasivo TCP de red (Solo en los últimos 15 minutos)
    tcp_samples = []
    print(t("run_stealth_waiting"))

    while True:
        now_true = time.time() + ntp_offset
        diff = target_epoch - now_true
        if diff <= 12.0:
            break
        sample = measure_tcp_rtt()
        if sample:
            tcp_samples.append(sample)
            if len(tcp_samples) > 5:
                tcp_samples.pop(0)
        # Dormir adaptativamente sin pasarse de T-12s
        now_true = time.time() + ntp_offset
        rem_to_prewarm = (target_epoch - now_true) - 12.0
        if rem_to_prewarm > 0:
            time.sleep(min(15.0, rem_to_prewarm))

    # 4. Modo de Disparo (Single Shot vs Double-Tap)
    sniper_cfg = config.get("sniper", {})
    snipe_mode = sniper_cfg.get("mode", "double_tap")
    tap_interval_ms = float(sniper_cfg.get("tap_interval_ms", 100.0))

    # 5. Precalentamiento TLS (12s antes)
    sniper = SnipeSession(cookies)
    if snipe_mode == "double_tap":
        print(t("run_prewarm_dual"))
        try:
            rtt_a, rtt_b = sniper.prewarm_tls_dual()
            print(t("run_prewarm_dual_ok", rtt_a=rtt_a, rtt_b=rtt_b))
        except Exception as e:
            print(t("run_prewarm_dual_err", err=e))
            sniper.close()
            return
    else:
        print(t("run_prewarm_single"))
        try:
            tls_rtt = sniper.prewarm_tls()
            print(t("run_prewarm_single_ok", tls_rtt=tls_rtt))
        except Exception as e:
            print(t("run_prewarm_single_err", err=e))
            sniper.close()
            return

    # Compensación de ida estimada + bias adaptativo
    cal_cfg = config.get("calibration", {})
    auto_tune = cal_cfg.get("auto_tune", True)
    applied_bias_ms = float(cal_cfg.get("bias_ms", 0.0)) if auto_tune else 0.0

    # Consulta a la Red Comunitaria si no hay bias previo aprendido
    # Principio de reciprocidad estricta: solo se descarga el bias si tambien se comparte
    comm_cfg = config.get("community", {"share_metrics": True, "fetch_global_bias": True})
    can_fetch = comm_cfg.get("fetch_global_bias", True) and comm_cfg.get("share_metrics", True)
    if can_fetch and applied_bias_ms == 0.0:
        comm_bias_data = fetch_community_bias()
        if comm_bias_data and "recommended_bias_ms" in comm_bias_data:
            rec_bias = float(comm_bias_data["recommended_bias_ms"])
            print(t("run_community_sync", bias=rec_bias, nodes=comm_bias_data.get('total_reports', 'N/A')))
            applied_bias_ms = rec_bias

    avg_tcp = sum(tcp_samples) / len(tcp_samples) if tcp_samples else 240.0
    base_one_way = (avg_tcp / 1000.0) / 2.0  # RTT / 2
    if base_one_way < 0.080 or base_one_way > 0.220:
        base_one_way = 0.135

    # Lead time total = ida física + corrección aprendida (bias)
    total_lead_time = base_one_way + (applied_bias_ms / 1000.0)
    trigger_epoch = target_epoch - total_lead_time
    print(t("run_compensated_trigger", lead_ms=total_lead_time*1000, base_ms=base_one_way*1000, bias=applied_bias_ms))

    # 6. Espera de alta precisión con busy-wait
    wait_until(trigger_epoch, ntp_offset)

    # 7. Disparo
    t_shoot_wall = time.time() + ntp_offset
    try:
        if snipe_mode == "double_tap":
            print(t("run_firing_double", interval=tap_interval_ms))
            dt_res = sniper.fire_double_tap(interval_ms=tap_interval_ms)
            shot_1 = dt_res["shot_1"]
            shot_2 = dt_res["shot_2"]
            winner = dt_res["winner"]

            print(t("run_res_double_banner"))
            print(t("run_res_shot1", status=shot_1['status'], res=shot_1['apply_result'], rtt=shot_1['rtt_ms']))
            print(t("run_res_shot2", status=shot_2['status'], res=shot_2['apply_result'], rtt=shot_2['rtt_ms']))

            winning_shot = shot_1 if winner == "SHOT_1_PRIMARY" else (shot_2 if winner == "SHOT_2_SECONDARY" else shot_1)
            res_code = winning_shot["apply_result"]
            gen_code = winning_shot["data"].get("code")
            deadline = winning_shot["data"].get("data", {}).get("deadline_format", "")
            server_date = winning_shot["headers"].get("Date")
            resp_latency = winning_shot["rtt_ms"]
            arrival_est = t_shoot_wall + (resp_latency / 2000.0)
        else:
            print(t("run_firing_single"))
            status, resp_data, resp_latency, resp_headers = sniper.fire()
            arrival_est = t_shoot_wall + (resp_latency / 2000.0)
            res_code = resp_data.get("data", {}).get("apply_result")
            gen_code = resp_data.get("code")
            deadline = resp_data.get("data", {}).get("deadline_format", "")
            server_date = resp_headers.get("Date")
            winner = "SINGLE" if res_code == 1 else None

        readable_msg = translate_xiaomi_result(gen_code, res_code, deadline)

        # Bucle adaptativo de feedback
        new_bias, reason, telemetry = evaluate_shot_feedback(
            target_epoch=target_epoch,
            current_bias_ms=applied_bias_ms,
            server_date_header=server_date,
            apply_result=res_code,
            resp_latency_ms=resp_latency,
            arrival_est_epoch=arrival_est
        )
        print(t("run_diag_header", msg=readable_msg))
        print(t("run_cal_header"))
        print(f"• {reason}")
        if auto_tune:
            update_config_calibration(config, new_bias, telemetry)
            save_config(config, CONFIG_PATH)
            print(t("run_cal_saved", bias=new_bias))

        # Emisión anónima a la Red Comunitaria (si está activado)
        if comm_cfg.get("share_metrics", True):
            comm_report = {
                "ts": round(t_shoot_wall, 3),
                "rtt": round(resp_latency, 2),
                "one_way": round(base_one_way * 1000.0, 2),
                "bias_applied": round(applied_bias_ms, 2),
                "mode": snipe_mode,
                "winner": winner,
                "shot1_res": shot_1["apply_result"] if snipe_mode == "double_tap" else res_code,
                "shot2_res": shot_2["apply_result"] if snipe_mode == "double_tap" else None,
                "srv_date": server_date,
                "arrival_delta_ms": round((arrival_est - target_epoch) * 1000.0, 2),
                "outcome": telemetry.get("outcome", "UNKNOWN")
            }
            sent_ok = report_telemetry_async(comm_report)
            if sent_ok:
                print(t("run_community_sent"))

        if res_code == 1:
            win_label = t("run_win_label_primary") if winner == "SHOT_1_PRIMARY" else (t("run_win_label_secondary") if winner == "SHOT_2_SECONDARY" else t("run_win_label_single"))
            title = t("run_win_title")
            post_guide = t("run_win_guide")
            text = f"{readable_msg}\n• <b>Winner:</b> {win_label}\n• <b>Account:</b> <code>{user_id}</code>{post_guide}"
            print(f"\n{title}\n{text}")
            disable_schedule()
            dispatch_notification(title, text, config)
        else:
            title = "Xiaomi Unlock"
            text = f"{readable_msg}\n• Latency: {resp_latency:.1f} ms\n• Feedback: {reason}"
            dispatch_notification(title, text, config)
    except Exception as e:
        print(t("run_shot_error", err=e))
        dispatch_notification("Error Xiaomi Unlock", str(e), config)
    finally:
        sniper.close()


def cmd_start():
    """
    Unified All-in-One workflow:
    1. Checks if configuration and session exist. If not, launches login.
    2. Validates account status and eligibility.
    3. Auto-configures daily background schedule if not yet active.
    4. Runs deep-sleep waiting loop until quota trigger time.
    """
    config = load_config(CONFIG_PATH) or {}
    if "language" in config:
        set_language(config["language"])

    print("=" * 65)
    print("   HyperOS BL Sniper - All-in-One Autonomous Execution")
    print("=" * 65)

    # Step 1: Ensure authentication
    if not config or "auth" not in config:
        print("\n[*] Initial setup: No active session found. Launching authentication...")
        cmd_login()
        config = load_config(CONFIG_PATH) or {}
        if not config or "auth" not in config:
            print("[ERROR] Setup incomplete. Run 'python cli.py login' to authenticate.")
            return

    # Step 2: Validate account state
    cookies = config.get("auth", {})
    user_id = cookies.get("userId", "N/A")
    print(f"\n[*] Checking account status for ID: {user_id}...")
    valid, data = check_session(cookies)
    if not valid:
        code = data.get("code")
        if code == 100004 and cookies.get("passToken"):
            print("[*] Session token expired. Auto-renewing with passToken...")
            ok_renew, new_tok, _ = refresh_service_token_via_passtoken(cookies)
            if ok_renew and new_tok:
                cookies["new_bbs_serviceToken"] = new_tok
                cookies["obtained_at"] = int(time.time())
                config["auth"] = cookies
                save_config(config, CONFIG_PATH)
                valid, data = check_session(cookies)

        if not valid:
            print(f"[ERROR] Session invalid for account {user_id}. Run 'python cli.py login'.")
            return

    can_fire, status_code, state_msg = interpret_account_state(data)
    if not can_fire:
        if status_code == "APPROVED":
            print(f"[OK] Account already approved: {state_msg}")
            disable_schedule()
        else:
            print(f"[!] Account not eligible to shoot today: {state_msg}")
        return

    # Step 3: Ensure daily background task is scheduled
    if not is_scheduled():
        print("[*] Registering automatic daily background schedule in OS...")
        enable_schedule(__file__)

    # Step 4: Hand over directly to high-precision sniper loop
    print("\n[*] Initial checks passed. Entering autonomous sniper loop...")
    cmd_run()


def main():
    if len(sys.argv) < 2:
        cmd_start()
        return

    cmd = sys.argv[1].lower()
    if cmd in ("start", "--start"):
        cmd_start()
    elif cmd == "login":
        cmd_login()
    elif cmd == "status":
        cmd_status()
    elif cmd == "schedule":
        cmd_schedule()
    elif cmd == "unschedule":
        cmd_unschedule()
    elif cmd == "run":
        cmd_run()
    else:
        print(f"Comando desconocido: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()
