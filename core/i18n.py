"""
Internationalization (i18n) Engine for HyperOS BL Sniper.
Automatically detects OS locale (defaults to English, falls back to Spanish for es_*).
Supports explicit override in config.json via "language": "es" | "en"
or environment variable HYPEROS_LANG=es.
Strict Clean UI compliance: zero emojis.
"""

import os
import locale
from typing import Optional

_CURRENT_LANG: Optional[str] = None


def detect_system_language() -> str:
    """
    Resolves active language based on:
    1. HYPEROS_LANG environment variable
    2. OS locale settings
    3. Global fallback to 'en' (international standard)
    """
    env_lang = os.environ.get("HYPEROS_LANG", "").strip().lower()
    if env_lang.startswith("es"):
        return "es"
    if env_lang.startswith("en"):
        return "en"

    try:
        loc = locale.getlocale()[0]
        if loc and loc.lower().startswith("es"):
            return "es"
    except Exception:
        pass

    for key in ("LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(key, "").lower()
        if val.startswith("es"):
            return "es"

    return "en"


def set_language(lang: str) -> None:
    """Sets active language globally for the current session."""
    global _CURRENT_LANG
    normalized = lang.strip().lower() if lang else "en"
    _CURRENT_LANG = "es" if normalized.startswith("es") else "en"


def get_language() -> str:
    """Returns currently active language code ('en' or 'es')."""
    global _CURRENT_LANG
    if _CURRENT_LANG is None:
        _CURRENT_LANG = detect_system_language()
    return _CURRENT_LANG


STRINGS = {
    "en": {
        # Login
        "login_banner": "   HyperOS BL Sniper - Official Terminal QR Authentication",
        "login_contacting": "[*] Contacting Xiaomi servers for authentication ticket...",
        "login_ticket_error": "[ERROR] Failed to obtain Xiaomi ticket. Check your Internet connection.",
        "login_scan_prompt": "\n[+] Scan this QR code with Mi Account app, Camera, or Xiaomi Community:",
        "login_timeout": "[ERROR] Authentication was not completed or timed out.",
        "login_community_title": "\n[INFO] Collective Intelligence Network (Community):",
        "login_community_desc": "   Enables automatic synchronization of optimal bias discovered by other users.",
        "login_community_prompt": "Do you want to enable the Collective Intelligence Network? (Y/n): ",
        "login_success": " [OK] Authentication completed successfully.",
        "login_saved_config": " [OK] Credentials securely saved to: config.json",
        # Status
        "status_no_config": "[!] No saved session found. Run first: python cli.py login",
        "status_checking": "[*] Verifying account ID: {user_id}...",
        "status_header": "\n--- Account Status ---",
        "status_sched": "• Daily scheduled task in system: {state}",
        "status_active": "[ACTIVE]",
        "status_inactive": "[INACTIVE]",
        "status_token_valid": "• Token Session: [VALID AND AUTHENTICATED]",
        "status_is_pass": "• Approved Permission (is_pass): {is_pass}",
        "status_btn_state": "• Button State: {btn_state}",
        "status_deadline": "• Validity: {deadline}",
        "status_diag": "• Diagnostic: {state_msg}",
        "status_cal": "• Adaptive Calibration: {bias:+.1f} ms accumulated bias",
        "status_token_expired_100004": "• Token Session: [EXPIRED] (code 100004)\n  Run 'python cli.py login' to renew session.",
        "status_token_invalid": "• Token Session: [EXPIRED OR INVALID] ({msg})\n  Recommendation: Run 'python cli.py login' to renew.",
        # Schedule
        "sched_success": "[OK] {msg}\n[*] The bot will execute automatically 2 minutes before midnight Beijing time.",
        "sched_error": "[ERROR] Failed to configure task: {msg}",
        "unsched_info": "[*] {msg}",
        # Run
        "run_no_config": "[!] Valid configuration not found. Run 'python cli.py login'.",
        "run_token_refreshing": "[*] Token expired (100004). Attempting auto-renewal with passToken...",
        "run_token_refreshed": "[OK] Session auto-renewed successfully. Re-verifying...",
        "run_token_expired_stop": "Token expired for account {user_id}. Run 'python cli.py login' to renew.",
        "run_token_invalid_stop": "Session expired for account {user_id}. Re-authenticate with 'python cli.py login'.",
        "run_approved_desched": "Account {user_id}: {state_msg} Disabling daily task.",
        "run_not_eligible": "Account {user_id}: {state_msg} The bot will not fire today and remains scheduled.",
        "run_target_beijing": "[*] Universal Target: 00:00:00 GMT+8 (Beijing)",
        "run_target_local": "[*] In your Timezone:  {local_time} ({local_tz})",
        "run_ntp_sync": "[*] Local clock drift synchronized: {offset:+.2f} ms",
        "run_deep_sleep_banner": " [*] {duration} remaining until next quota window opening.\n     No need to keep this terminal open consuming battery or resources.",
        "run_deep_sleep_prompt": "\nDo you want to schedule automatic background execution with 'schedule'? (Y/n): ",
        "run_deep_sleep_scheduled": "\n[OK] System will wake up 2 minutes before reset. You can now close this terminal.",
        "run_deep_sleep_entering": "\n[*] Entering Deep Sleep Mode.\n    Bot will consume zero CPU and zero network until 15 minutes before target...",
        "run_deep_sleep_waking": "\n[INFO] Waking up: {duration} remaining. Starting high-frequency preparation.",
        "run_deep_sleep_waiting": "[{time}] In passive wait: {remaining} remaining (next check in {chunk})...",
        "run_stealth_waiting": "[*] Stealth mode active. Waiting for trigger window...",
        "run_prewarm_dual": "[*] Pre-warming Socket A and Socket B in parallel (Double-Tap Mode)...",
        "run_prewarm_dual_ok": "[OK] Dual Sockets ready (Channel A: {rtt_a:.1f} ms, Channel B: {rtt_b:.1f} ms).",
        "run_prewarm_dual_err": "[!] Error pre-warming dual sockets: {err}",
        "run_prewarm_single": "[*] Pre-warming secure HTTPS connection to Singapore...",
        "run_prewarm_single_ok": "[OK] TLS Socket ready in {tls_rtt:.1f} ms. Channel hot.",
        "run_prewarm_single_err": "[!] Error pre-warming socket: {err}",
        "run_community_sync": "[INFO] [Community] Synchronizing recommended global bias: {bias:+.1f} ms (Nodes: {nodes})",
        "run_compensated_trigger": "[+] Compensated shot scheduled {lead_ms:.1f} ms in advance (Base: {base_ms:.1f} ms, Bias: {bias:+.1f} ms).",
        "run_firing_double": "[*] FIRING DOUBLE-TAP (Channel A + Channel B at +{interval:.0f}ms)...",
        "run_firing_single": "[*] FIRING QUOTA REQUEST (Single Shot)...",
        "run_res_double_banner": "================ DOUBLE-TAP RESULT ================",
        "run_res_shot1": "• Shot 1 (is_retry=False): Status {status}, apply_result={res} (RTT: {rtt:.1f} ms)",
        "run_res_shot2": "• Shot 2 (is_retry=True):  Status {status}, apply_result={res} (RTT: {rtt:.1f} ms)",
        "run_diag_header": "\n[DIAGNOSTIC]: {msg}",
        "run_cal_header": "\n[ADAPTIVE CALIBRATION]:",
        "run_cal_saved": "• Next bias saved in config.json: {bias:+.1f} ms",
        "run_community_sent": "[INFO] [Community] Anonymous metrics synchronized successfully with network.",
        "run_win_title": "BOOTLOADER PERMISSION GRANTED",
        "run_win_guide": "\n\nCRITICAL STEPS ON YOUR DEVICE NOW:\n1. Insert a SIM card with ACTIVE MOBILE DATA.\n2. TURN OFF WI-FI (binding strictly fails over Wi-Fi).\n3. Go to: Settings -> Additional settings -> Developer options -> Mi Unlock status.\n4. Tap 'Add account and device'.\n5. Your official waiting period (e.g. 72h) will begin for PC unlocking.",
        "run_win_label_primary": "Shot 1 (Primary)",
        "run_win_label_secondary": "Shot 2 (Safety Net)",
        "run_win_label_single": "Single Shot",
        "run_shot_error": "[ERROR] Error during shot execution: {err}",
        # Results translation
        "res_token_expired": "[ERROR] Your Xiaomi session/token has expired. Re-authentication required.",
        "res_invalid_format": "[ERROR] Invalid format or request parameters.",
        "res_approved": "[APPROVED] Request approved. Your account has permission to unlock bootloader until {deadline}.",
        "res_exhausted": "[EXHAUSTED] Daily quota exhausted. Quotas closed before processing your request. Next opening: {deadline}.",
        "res_blocked": "[BLOCKED] Account temporarily blocked. Active penalty until {deadline}.",
        "res_risk_control": "[RISK_CONTROL] Risk control triggered (Rate Limit / Too many requests). Wait before retrying.",
        "res_unknown": "Request result returned: code {res} (general code: {code}).",
        # Feedback decision reasons
        "reason_win": "Winning shot! Triumphant calibration preserved.",
        "reason_early": "Server processed request in previous second ({server_date}). Arrived too early. Adjusting bias by +{step:.1f} ms to fire later tomorrow.",
        "reason_exhausted": "Arrived within opening second ({server_date}). Window was active but quota was taken by competition. Holding current bias ({bias:.1f} ms).",
    },
    "es": {
        # Login
        "login_banner": "   HyperOS BL Sniper - Inicio de Sesion Oficial por QR",
        "login_contacting": "[*] Contactando servidores de Xiaomi para generar ticket de acceso...",
        "login_ticket_error": "[ERROR] Error obteniendo ticket de Xiaomi. Verifica tu conexion a Internet.",
        "login_scan_prompt": "\n[+] Escanea este codigo QR con la app Mi Account, Camara o Xiaomi Community:",
        "login_timeout": "[ERROR] No se completo la autenticacion o se agoto el tiempo de espera.",
        "login_community_title": "\n[INFO] Red de Inteligencia Colectiva (Comunidad):",
        "login_community_desc": "   Permite sincronizar el bias optimo y calibracion ganadora descubierta por otros usuarios.",
        "login_community_prompt": "Deseas activar la Inteligencia Colectiva comunitaria? (S/n): ",
        "login_success": " [OK] Autenticacion completada con exito.",
        "login_saved_config": " [OK] Credenciales guardadas con permisos seguros en: config.json",
        # Status
        "status_no_config": "[!] No hay sesion guardada. Ejecuta primero: python cli.py login",
        "status_checking": "[*] Verificando cuenta ID: {user_id}...",
        "status_header": "\n--- Estado de la Cuenta ---",
        "status_sched": "• Tarea diaria programada en el sistema: {state}",
        "status_active": "[ACTIVA]",
        "status_inactive": "[INACTIVA]",
        "status_token_valid": "• Sesion de Token: [VALIDA Y AUTENTICADA]",
        "status_is_pass": "• Permiso Aprobado (is_pass): {is_pass}",
        "status_btn_state": "• Estado del Boton: {btn_state}",
        "status_deadline": "• Vigencia: {deadline}",
        "status_diag": "• Diagnostico: {state_msg}",
        "status_cal": "• Calibracion Adaptativa: {bias:+.1f} ms de bias acumulado",
        "status_token_expired_100004": "• Sesion de Token: [EXPIRADA] (codigo 100004)\n  Ejecuta 'python cli.py login' para renovar la sesion.",
        "status_token_invalid": "• Sesion de Token: [EXPIRADA O INVALIDA] ({msg})\n  Recomendacion: Ejecuta 'python cli.py login' para renovar.",
        # Schedule
        "sched_success": "[OK] {msg}\n[*] El bot se ejecutara automaticamente 2 minutos antes de las 00:00:00 de Beijing.",
        "sched_error": "[ERROR] Error configurando tarea: {msg}",
        "unsched_info": "[*] {msg}",
        # Run
        "run_no_config": "[!] No se encontro configuracion valida. Ejecuta 'python cli.py login'.",
        "run_token_refreshing": "[*] Token expirado (100004). Intentando auto-renovacion con passToken...",
        "run_token_refreshed": "[OK] Sesion auto-renovada con exito. Re-verificando...",
        "run_token_expired_stop": "Token expirado para la cuenta {user_id}. Ejecuta 'python cli.py login' para renovar.",
        "run_token_invalid_stop": "Sesion caducada para cuenta {user_id}. Vuelve a iniciar sesion con 'python cli.py login'.",
        "run_approved_desched": "Cuenta {user_id}: {state_msg} Desactivando la tarea diaria.",
        "run_not_eligible": "Cuenta {user_id}: {state_msg} El bot no disparara hoy y seguira programado.",
        "run_target_beijing": "[*] Objetivo Universal: 00:00:00 GMT+8 (Beijing)",
        "run_target_local": "[*] En tu Zona Horaria:  {local_time} ({local_tz})",
        "run_ntp_sync": "[*] Desfase de reloj local sincronizado: {offset:+.2f} ms",
        "run_deep_sleep_banner": " [*] Faltan {duration} para la proxima apertura de cupos.\n     No necesitas dejar esta ventana abierta gastando bateria o recursos.",
        "run_deep_sleep_prompt": "\nDeseas programar el disparo automatico en segundo plano con 'schedule'? (S/n): ",
        "run_deep_sleep_scheduled": "\n[OK] El sistema despertara solo 2 minutos antes del reinicio. Ya puedes cerrar esta terminal.",
        "run_deep_sleep_entering": "\n[*] Entrando en Modo Suspension Profunda (Deep Sleep).\n    El bot no consumira CPU ni red hasta 15 minutos antes de la hora cero...",
        "run_deep_sleep_waking": "\n[INFO] Despertando: Faltan {duration}. Iniciando preparacion de alta frecuencia.",
        "run_deep_sleep_waiting": "[{time}] En espera pasiva: faltan {remaining} (proximo check en {chunk})...",
        "run_stealth_waiting": "[*] Modo sigiloso activo. Esperando ventana de disparo...",
        "run_prewarm_dual": "[*] Precalentando Socket A y Socket B en paralelo (Modo Double-Tap)...",
        "run_prewarm_dual_ok": "[OK] Sockets Duales listos (Canal A: {rtt_a:.1f} ms, Canal B: {rtt_b:.1f} ms).",
        "run_prewarm_dual_err": "[!] Error precalentando sockets duales: {err}",
        "run_prewarm_single": "[*] Precalentando conexion segura HTTPS a Singapur...",
        "run_prewarm_single_ok": "[OK] Socket TLS listo en {tls_rtt:.1f} ms. Canal en caliente.",
        "run_prewarm_single_err": "[!] Error al precalentar socket: {err}",
        "run_community_sync": "[INFO] [Comunidad] Sincronizando bias global recomendado: {bias:+.1f} ms (Nodos: {nodes})",
        "run_compensated_trigger": "[+] Disparo compensado programado con {lead_ms:.1f} ms de anticipacion (Base: {base_ms:.1f} ms, Bias: {bias:+.1f} ms).",
        "run_firing_double": "[*] DISPARANDO DOUBLE-TAP (Canal A + Canal B a +{interval:.0f}ms)...",
        "run_firing_single": "[*] DISPARANDO SOLICITUD DE CUOTA (Single Shot)...",
        "run_res_double_banner": "================ RESULTADO DOUBLE-TAP ================",
        "run_res_shot1": "• Disparo 1 (is_retry=False): Status {status}, apply_result={res} (RTT: {rtt:.1f} ms)",
        "run_res_shot2": "• Disparo 2 (is_retry=True):  Status {status}, apply_result={res} (RTT: {rtt:.1f} ms)",
        "run_diag_header": "\n[DIAGNOSTICO]: {msg}",
        "run_cal_header": "\n[CALIBRACION ADAPTATIVA]:",
        "run_cal_saved": "• Proximo bias guardado en config.json: {bias:+.1f} ms",
        "run_community_sent": "[INFO] [Comunidad] Metricas anonimas sincronizadas exitosamente con la red.",
        "run_win_title": "PERMISO DE BOOTLOADER OBTENIDO",
        "run_win_guide": "\n\nPASOS CRITICOS EN TU DISPOSITIVO:\n1. Inserta una SIM con DATOS MOVILES ACTIVOS.\n2. APAGA EL WI-FI (la vinculacion falla obligatoriamente en Wi-Fi).\n3. Ve a: Ajustes -> Ajustes adicionales -> Opciones de desarrollador -> Estado de Mi Unlock.\n4. Toca en 'Agregar cuenta y dispositivo'.\n5. Comenzara tu tiempo de espera oficial (ej. 72h) para desbloquear en PC.",
        "run_win_label_primary": "Disparo 1 (Primario)",
        "run_win_label_secondary": "Disparo 2 (Paracaidas)",
        "run_win_label_single": "Disparo Unico",
        "run_shot_error": "[ERROR] Error durante el disparo: {err}",
        # Results translation
        "res_token_expired": "[ERROR] Tu sesion/token de Xiaomi ha expirado. Necesitas volver a extraer la cookie o iniciar sesion.",
        "res_invalid_format": "[ERROR] Error en el formato o parametros de la solicitud.",
        "res_approved": "[APROBADA] Solicitud aprobada. Tu cuenta ya tiene permiso para desbloquear el bootloader hasta {deadline}.",
        "res_exhausted": "[AGOTADO] Cupo diario agotado. Los cupos del dia se terminaron antes de que entrara tu solicitud. Proxima apertura: {deadline}.",
        "res_blocked": "[BLOQUEADA] Cuenta bloqueada temporalmente. Tienes una penalizacion activa hasta {deadline}.",
        "res_risk_control": "[CONTROL_RIESGO] Control de riesgo activado (Rate Limit / Muchas peticiones). Debes esperar antes de volver a intentar.",
        "res_unknown": "Resultado de solicitud devuelto: codigo {res} (codigo general: {code}).",
        # Feedback decision reasons
        "reason_win": "Disparo ganador. Se preserva la calibracion triunfante.",
        "reason_early": "El servidor proceso la solicitud en el segundo previo ({server_date}). Llego demasiado temprano. Ajustando bias en +{step:.1f} ms para disparar mas tarde manana.",
        "reason_exhausted": "Llego dentro del segundo de apertura ({server_date}). La ventana estaba activa pero la cuota volo. Manteniendo bias actual ({bias:.1f} ms).",
    }
}


def t(key: str, lang: Optional[str] = None, **kwargs) -> str:
    """
    Translates string key using explicit lang or active language.
    Safely falls back to English, then to the key itself.
    Interpolates any provided kwargs.
    """
    active = lang or get_language()
    catalog = STRINGS.get(active, STRINGS["en"])
    template = catalog.get(key, STRINGS["en"].get(key, key))
    if kwargs:
        try:
            return template.format(**kwargs)
        except Exception:
            return template
    return template
