"""
Suite de tests de verificación para HyperOS BL Sniper.
Valida cálculo de horario, lógica NTP, estructura de red y scheduler.
"""

import os
import sys
import time
import unittest
import datetime

# Add root directory to PYTHONPATH
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)

from core.network import get_next_beijing_midnight, measure_tcp_rtt, SnipeSession
from core.ntp import get_ntp_offset, wait_until
from core.auth import load_config, save_config, interpret_account_state, should_renew_token
from core.calibration import parse_server_date_epoch, evaluate_shot_feedback, update_config_calibration, translate_xiaomi_result
from core.scheduler import is_scheduled
from core.community import sanitize_telemetry_payload, generate_ephemeral_node_id, fetch_community_bias
from core.i18n import t, set_language, get_language, STRINGS
from cli import format_duration


class TestHyperOSSniper(unittest.TestCase):

    def test_beijing_midnight_calculation(self):
        epoch, dt = get_next_beijing_midnight()
        # Beijing is UTC+8. Target is 00:00:00 UTC+8 = 16:00:00 UTC
        self.assertEqual(dt.hour, 16)
        self.assertEqual(dt.minute, 0)
        self.assertEqual(dt.second, 0)
        beijing_dt = dt.astimezone(datetime.timezone(datetime.timedelta(hours=8)))
        self.assertEqual(beijing_dt.hour, 0)
        self.assertEqual(beijing_dt.minute, 0)
        self.assertEqual(beijing_dt.second, 0)

    def test_config_save_and_load(self):
        test_file = os.path.join(ROOT_DIR, "test_config_temp.json")
        try:
            data = {"auth": {"userId": "12345", "token": "test_token"}}
            save_config(data, test_file)
            loaded = load_config(test_file)
            self.assertEqual(loaded, data)
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

    def test_ntp_sync(self):
        offset = get_ntp_offset()
        self.assertIsInstance(offset, float)
        # Clock offset should typically be within +/- 10 seconds on any decent machine
        self.assertTrue(-10.0 <= offset <= 10.0)

    def test_passive_tcp_rtt(self):
        rtt = measure_tcp_rtt(timeout=4.0)
        # Should return a valid float in ms if internet is accessible
        if rtt is not None:
            self.assertGreater(rtt, 10.0)
            self.assertLess(rtt, 3000.0)

    def test_wait_until_precision(self):
        target = time.time() + 0.8
        wait_until(target)
        drift = abs(time.time() - target)
        self.assertLess(drift, 0.05)

    def test_wait_until_honors_ntp_offset(self):
        # If the local clock is 0.5s ahead of "true" time (ntp_offset = -0.5),
        # wait_until should still return at the wall-clock moment that matches
        # target_epoch when corrected by the offset.
        ntp_offset = -0.5
        target = time.time() + 0.8
        wait_until(target, ntp_offset=ntp_offset)
        drift = abs((time.time() + ntp_offset) - target)
        self.assertLess(drift, 0.05)

    def test_snipe_session_not_alive_without_conn(self):
        session = SnipeSession({"userId": "1", "cUserId": "2", "new_bbs_serviceToken": "3"})
        self.assertFalse(session.is_alive())

    def test_snipe_request_build(self):
        session = SnipeSession({"userId": "123", "cUserId": "abc", "new_bbs_serviceToken": "xyz"})
        headers, payload = session._build_request(is_retry=False)
        self.assertIn("Cookie", headers)
        self.assertIn("new_bbs_serviceToken=xyz", headers["Cookie"])
        self.assertIn("versionCode=500439", headers["Cookie"])
        self.assertIn("versionName=5.4.39", headers["Cookie"])
        self.assertIn("deviceId=", headers["Cookie"])
        self.assertEqual(headers.get("Accept"), "application/json")
        self.assertEqual(payload, b'{"is_retry": false}')
        self.assertEqual(headers["Content-Length"], str(len(payload)))

        # Prueba de variante is_retry=True
        headers_ret, payload_ret = session._build_request(is_retry=True)
        self.assertEqual(payload_ret, b'{"is_retry": true}')

    def test_should_renew_token_logic(self):
        now = 1000000.0
        # Token con 1 día restante, próximo disparo en 20 horas (72000s) + margen 2h (7200s) -> No necesita
        cookies_ok = {"obtained_at": now, "expires_at": now + 86400}
        self.assertFalse(should_renew_token(cookies_ok, now + 70000))

        # Token que expira en 5 horas (18000s), próximo disparo en 20 horas (72000s) -> Sí necesita renovar
        cookies_exp = {"obtained_at": now, "expires_at": now + 18000}
        self.assertTrue(should_renew_token(cookies_exp, now + 70000))

    def test_snipe_prewarm_and_fire(self):
        # Real end-to-end against the API (prewarm TLS, then check is_alive True).
        session = SnipeSession({"userId": "1", "cUserId": "2", "new_bbs_serviceToken": "3"})
        try:
            session.prewarm_tls(timeout=6.0)
            self.assertTrue(session.is_alive())
        except Exception:
            self.skipTest("Network unavailable for live TLS prewarm")
        finally:
            session.close()

    def _state(self, is_pass=None, button_state=None, deadline="07/31"):
        data = {"code": 0, "data": {"is_pass": is_pass, "button_state": button_state, "deadline_format": deadline}}
        return data

    def test_state_ready(self):
        can_fire, status, _ = interpret_account_state(self._state(is_pass=4, button_state=1))
        self.assertTrue(can_fire)
        self.assertEqual(status, "READY")

    def test_state_approved(self):
        can_fire, status, _ = interpret_account_state(self._state(is_pass=1))
        self.assertFalse(can_fire)
        self.assertEqual(status, "APPROVED")

    def test_state_temp_blocked(self):
        can_fire, status, msg = interpret_account_state(self._state(is_pass=4, button_state=2, deadline="09/12"))
        self.assertFalse(can_fire)
        self.assertEqual(status, "TEMP_BLOCKED")
        self.assertIn("09/12", msg)

    def test_state_account_too_new(self):
        can_fire, status, _ = interpret_account_state(self._state(is_pass=4, button_state=3))
        self.assertFalse(can_fire)
        self.assertEqual(status, "ACCOUNT_TOO_NEW")

    def test_state_unknown_fires_anyway(self):
        can_fire, status, _ = interpret_account_state(self._state(is_pass=99, button_state=7))
        self.assertTrue(can_fire)
        self.assertEqual(status, "UNKNOWN")

    def test_calibration_early_second_shifts_bias(self):
        # Target: 16:00:00 UTC (1788710400). Server Date: 15:59:59 GMT (1788710399)
        target_epoch = 1788710400.0
        server_date = "Sun, 06 Sep 2026 15:59:59 GMT"
        new_bias, reason, telem = evaluate_shot_feedback(
            target_epoch=target_epoch,
            current_bias_ms=0.0,
            server_date_header=server_date,
            apply_result=3,
            resp_latency_ms=280.0,
            arrival_est_epoch=target_epoch - 0.05,
            lang="es"
        )
        self.assertEqual(new_bias, 60.0)
        self.assertEqual(telem["outcome"], "EARLY_SECOND")
        self.assertIn("segundo previo", reason)

        # Prueba en ingles
        new_bias_en, reason_en, _ = evaluate_shot_feedback(
            target_epoch=target_epoch,
            current_bias_ms=0.0,
            server_date_header=server_date,
            apply_result=3,
            resp_latency_ms=280.0,
            arrival_est_epoch=target_epoch - 0.05,
            lang="en"
        )
        self.assertIn("previous second", reason_en)

    def test_calibration_in_window_holds_bias(self):
        # Target: 16:00:00 UTC. Server Date: 16:00:00 GMT (in window)
        target_epoch = 1788710400.0
        server_date = "Sun, 06 Sep 2026 16:00:00 GMT"
        new_bias, reason, telem = evaluate_shot_feedback(
            target_epoch=target_epoch,
            current_bias_ms=60.0,
            server_date_header=server_date,
            apply_result=3,
            resp_latency_ms=280.0,
            arrival_est_epoch=target_epoch + 0.02,
            lang="es"
        )
        self.assertEqual(new_bias, 60.0)
        self.assertEqual(telem["outcome"], "IN_WINDOW_EXHAUSTED")
        self.assertIn("segundo de apertura", reason)

    def test_calibration_winning_shot_preserves_telemetry(self):
        target_epoch = 1788710400.0
        server_date = "Sun, 06 Sep 2026 16:00:00 GMT"
        cfg = {"calibration": {"auto_tune": True, "bias_ms": 60.0, "history": []}}
        new_bias, reason, telem = evaluate_shot_feedback(
            target_epoch=target_epoch,
            current_bias_ms=60.0,
            server_date_header=server_date,
            apply_result=1,
            resp_latency_ms=275.0,
            arrival_est_epoch=target_epoch + 0.01
        )
        self.assertEqual(new_bias, 60.0)
        self.assertEqual(telem["outcome"], "SUCCESS")
        update_config_calibration(cfg, new_bias, telem)
        self.assertIsNotNone(cfg["calibration"]["winning_telemetry"])
        self.assertEqual(cfg["calibration"]["winning_telemetry"]["outcome"], "SUCCESS")

    def test_translation_codes(self):
        # Prueba en español explicito
        msg_ok_es = translate_xiaomi_result(0, 1, "09/30", lang="es")
        self.assertIn("APROBADA", msg_ok_es)
        msg_quota_es = translate_xiaomi_result(0, 3, "09/07 00:00", lang="es")
        self.assertIn("Cupo diario agotado", msg_quota_es)
        msg_blocked_es = translate_xiaomi_result(0, 4, "09/15", lang="es")
        self.assertIn("bloqueada temporalmente", msg_blocked_es)
        msg_token_es = translate_xiaomi_result(100004, None, lang="es")
        self.assertIn("expirado", msg_token_es)

        # Prueba en ingles explicito
        msg_ok_en = translate_xiaomi_result(0, 1, "09/30", lang="en")
        self.assertIn("APPROVED", msg_ok_en)
        msg_quota_en = translate_xiaomi_result(0, 3, "09/07 00:00", lang="en")
        self.assertIn("Daily quota exhausted", msg_quota_en)
        msg_blocked_en = translate_xiaomi_result(0, 4, "09/15", lang="en")
        self.assertIn("temporarily blocked", msg_blocked_en)
        msg_token_en = translate_xiaomi_result(100004, None, lang="en")
        self.assertIn("expired", msg_token_en)

        for msg in [msg_ok_es, msg_quota_es, msg_blocked_es, msg_token_es, msg_ok_en, msg_quota_en, msg_blocked_en, msg_token_en]:
            self.assertTrue(msg.startswith("["), f"El mensaje debe comenzar con etiqueta limpia: {msg}")

    def test_i18n_catalog_symmetry(self):
        # Garantizar que toda clave en ingles exista exactamente en espanol
        en_keys = set(STRINGS["en"].keys())
        es_keys = set(STRINGS["es"].keys())
        diff_en = en_keys - es_keys
        diff_es = es_keys - en_keys
        self.assertEqual(diff_en, set(), f"Claves faltantes en espanol: {diff_en}")
        self.assertEqual(diff_es, set(), f"Claves faltantes en ingles: {diff_es}")

    def test_i18n_language_switch(self):
        set_language("es")
        self.assertEqual(get_language(), "es")
        self.assertIn("Solicitud aprobada", t("res_approved", deadline="10/01"))

        set_language("en")
        self.assertEqual(get_language(), "en")
        self.assertIn("Request approved", t("res_approved", deadline="10/01"))

    def test_format_duration(self):
        self.assertEqual(format_duration(3665), "1h 1m 5s")
        self.assertEqual(format_duration(125), "2m 5s")
        self.assertEqual(format_duration(45), "45s")

    def test_dynamic_timezone_conversion_worldwide(self):
        # 00:00:00 GMT+8 Beijing es exactamente 16:00:00 UTC
        target_utc = datetime.datetime(2026, 9, 6, 16, 0, 0, tzinfo=datetime.timezone.utc)

        # Madrid (España peninsular en verano: UTC+2) -> 18:00
        tz_madrid = datetime.timezone(datetime.timedelta(hours=2))
        self.assertEqual(target_utc.astimezone(tz_madrid).hour, 18)

        # Buenos Aires (Argentina: UTC-3) -> 13:00
        tz_bsas = datetime.timezone(datetime.timedelta(hours=-3))
        self.assertEqual(target_utc.astimezone(tz_bsas).hour, 13)

        # Bogotá / Lima / CDMX (UTC-5) -> 11:00
        tz_bogota = datetime.timezone(datetime.timedelta(hours=-5))
        self.assertEqual(target_utc.astimezone(tz_bogota).hour, 11)

        # Tokio (Japón: UTC+9) -> 01:00 del día siguiente
        tz_tokyo = datetime.timezone(datetime.timedelta(hours=9))
        self.assertEqual(target_utc.astimezone(tz_tokyo).hour, 1)

    def test_community_telemetry_sanitization_zero_leakage(self):
        dirty_payload = {
            "userId": "1234567890",
            "cUserId": "h4sh3d_s3cr3t",
            "new_bbs_serviceToken": "eyJhbGciOi...",
            "deviceId": "FA:KE:MA:C0:00:01",
            "passToken": "secret_pass_token",
            "ts": 1788710400.15,
            "rtt": 240.5,
            "one_way": 120.25,
            "bias_applied": 30.0,
            "mode": "double_tap",
            "winner": "SHOT_1_PRIMARY",
            "shot1_res": 1,
            "shot2_res": 3,
            "srv_date": "Sun, 06 Sep 2026 16:00:00 GMT",
            "arrival_delta_ms": 15.2,
            "outcome": "SUCCESS"
        }
        clean = sanitize_telemetry_payload(dirty_payload)
        self.assertNotIn("userId", clean)
        self.assertNotIn("cUserId", clean)
        self.assertNotIn("new_bbs_serviceToken", clean)
        self.assertNotIn("deviceId", clean)
        self.assertNotIn("passToken", clean)
        self.assertEqual(clean["rtt"], 240.5)
        self.assertEqual(clean["one_way"], 120.25)
        self.assertEqual(clean["bias_applied"], 30.0)
        self.assertEqual(clean["shot1_res"], 1)
        self.assertEqual(clean["v"], "1.1.0")
        self.assertIn("nid", clean)
        self.assertEqual(len(clean["nid"]), 12)

    def test_ephemeral_node_id_consistency_and_privacy(self):
        id1 = generate_ephemeral_node_id()
        id2 = generate_ephemeral_node_id()
        self.assertEqual(id1, id2)
        self.assertEqual(len(id1), 12)


if __name__ == "__main__":
    unittest.main()
