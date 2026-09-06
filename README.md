# HyperOS Bootloader Quota Sniper

[English](README.md) | [Español](README.es.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-brightgreen.svg)]()

Universal, cross-platform high-frequency network sniper for securing daily Xiaomi HyperOS Bootloader unlock permissions (`apply/bl-auth`).

---

## Architectural Comparison

| Feature | Traditional ADB Scripts | Legacy Bypass Tools | HyperOS BL Sniper (This Project) |
| :--- | :--- | :--- | :--- |
| **Authentication** | Manual cookie sniffing | Dead endpoints (30001) | **Official QR Code Flow + passToken Auto-Renewal** |
| **Execution Mode** | Single brute-force shot | Spoofing attempts (patched) | **Interleaved Dual-Socket Double-Tap Burst** |
| **Platform** | Requires USB phone connection | Windows only | **Windows, macOS & Linux (CLI / Headless / VPS)** |
| **Network Layer** | Cold TLS handshakes (~500ms lag)| Plain HTTP | **Parallel Dual TLS Keep-Alive Pre-Warming** |
| **Transit Timing** | Static guess | None | **Layer-4 Passive TCP RTT Profiling (`RTT / 2`)** |
| **Clock Source** | Local system time | None | **Multi-Server NTP + Microsecond Busy-Wait Loop** |
| **Server Skew Correction** | None | None | **HTTP Date Header Analysis + Daily Community Consensus** |
| **Post-Approval Action** | None | None | **Automatic Task Descheduling + Clear Next-Steps Guide** |

---

## Core Technologies

### 1. Dual-Socket Double-Tap Burst
Xiaomi's quota opening window spans only 50 to 150 milliseconds. To eliminate the risk of firing a few milliseconds too early while preventing competition from taking the quota, the sniper preheats two independent TLS connections in parallel:
* **Socket A (Primary):** Dispatched at `target_epoch - one_way_transit - bias` with payload `is_retry: false`.
* **Socket B (Safety Net):** Dispatched exactly `+100ms` later with payload `is_retry: true`.
If the primary socket arrives slightly before midnight, the secondary socket hits the active server window.

### 2. Autonomous Token Lifecycle (`passToken` Recovery)
When authenticating via QR code, the tool securely stores `userId`, `new_bbs_serviceToken`, and Xiaomi's long-lived `passToken`. If the service token expires (`code: 100004`), the sniper automatically contacts `account.xiaomi.com/pass/serviceLogin` to obtain a fresh session token without user intervention.

### 3. Collective Intelligence Network & The Sweet Spot
Securing a quota requires hitting the server within an ultra-narrow 50-150ms processing window. If you fire too early, Xiaomi rejects the request with the previous second's date header; if you fire too late, the competition takes the quota. The exact arrival point that wins is the **Sweet Spot**.

To find and adapt to this moving target without guesswork:
* **Strict Reciprocity Principle:** To benefit from the collective sweet spot calibration (`fetch_global_bias: true`), nodes must contribute their anonymous post-shot metrics (`share_metrics: true`). Leeching without sharing is disallowed by design.
* **100% Anonymous Telemetry:** Nodes report strictly numerical metrics (Layer-4 TCP RTT, applied lead time, Xiaomi HTTP Date header delta, and outcome code). Identifiers (`userId`, `cUserId`, `serviceToken`, `passToken`, and hardware MAC/IMEI) are cryptographically stripped before transmission. Node IDs are deterministic ephemeral hashes that rotate daily (`sha256(machine + date)[:12]`), making cross-day user tracking physically impossible.
* **Consensus Engine (1D DBSCAN + Trimmed Median):** The central aggregator filters out network outliers and attacks, calculates the cluster of winning nodes, and derives the daily optimal Sweet Spot offset (e.g. `+25.0 ms`).
* **Inertia Clamping:** Daily shifts are restricted to a maximum of `+-15.0 ms/day` to guarantee smooth, stable calibration curves.

Nodes synchronize this consensus Sweet Spot before firing, allowing new or uncalibrated users to benefit immediately from the community's learned precision.

---

## Quick Start

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/JoshRob297/hyperos-bl-sniper.git
cd hyperos-bl-sniper
pip install -r requirements.txt
```

### 2. Autonomous One-Click Execution (Recommended)
Run a single command that verifies authentication, auto-schedules the daily task, and enters the sniper loop:
```bash
python cli.py start
```
If no session exists, the assistant prompts for login. Once saved, it validates eligibility, schedules the daily OS background task, and waits in Deep Sleep mode until quota opening.

---

## Detailed Commands

### Login via Authentication Assistant
Supports official browser authorization, terminal password/OTP, and manual cookie injection:
```bash
python cli.py login
```
* **Option 1 (Official Assistant via `migate`):** Opens official Xiaomi web login (Browser), prompts terminal credentials (Terminal), or renders QR code.
* **Option 2 (Manual Cookie Injection):** Directly paste `userId` and `new_bbs_serviceToken` copied from [c.mi.com](https://c.mi.com) using browser developer tools (F12). Also accessible via `python cli.py login --manual`.

### Check Session & Account Status
```bash
python cli.py status
```
Displays current token validity, daily scheduled job status, and server permissions (`is_pass`, deadline, and remaining penalty intervals).

### Enable Daily Auto-Snipe (Cross-Platform)
Registers an automated background job in your operating system (Crontab on Linux, `launchd` on macOS, or Task Scheduler on Windows) set to fire 2 minutes before midnight Beijing time (00:00:00 GMT+8):
```bash
python cli.py schedule
```
To remove the scheduled task at any time:
```bash
python cli.py unschedule
```

---

## Rate-Limit & Account Safety (Anti-Ban Rules)
Xiaomi's risk control system is sensitive to network and IP changes during quota requests:
* **Avoid VPNs / Proxies:** Execute directly on your primary ISP connection (residential fiber / native IP). VPN egress hops increase latency and risk triggering temporary blocks (`Account Error / code 6`).
* **Do Not Switch Networks:** Never switch between Wi-Fi and mobile data close to the quota reset time. Keep one stable connection.
* **Avoid Custom DNS:** Standard ISP DNS or local resolvers prevent routing changes that trip Xiaomi's security filters.
* **Single Instance per Account:** Run only one instance per Xiaomi account to avoid triggering rate limits.

---

## Response Codes Reference

### `apply` Quota Request Codes (`apply/bl-auth`)

| Code | Status | Meaning |
| :---: | :--- | :--- |
| **`1`** | `[APPROVED]` | Quota granted. Bootloader unlock permission active until deadline. |
| **`2`** | `[ACCOUNT_ERROR]` | Account error or temporary restriction. Retry after deadline. |
| **`3`** | `[EXHAUSTED]` | Daily quota exhausted before request arrival. Next window at 00:00 GMT+8. |
| **`4`** | `[FAILED]` | Application failed. Retry on subsequent window. |
| **`5`** | `[WAIT]` | Short-term rate limit triggered. Retry in one minute. |
| **`6`** | `[RISK_CONTROL]` | Server risk control active. Avoid aggressive polling. |

### `state` Account Eligibility Codes (`bl-switch/state`)

| Code (`is_pass` / `button_state`) | Status | Meaning |
| :---: | :--- | :--- |
| `is_pass == 1` | `[APPROVED]` | Permission already active. No need to shoot. |
| `is_pass == 4`, `btn == 1` | `[READY]` | Account eligible. Ready to fire at 00:00 GMT+8. |
| `is_pass == 4`, `btn == 2` | `[TEMP_BLOCKED]` | Temporary cooldown active until deadline. |
| `is_pass == 4`, `btn == 3` | `[ACCOUNT_TOO_NEW]`| Account younger than 30 days. Not yet eligible. |

---

## Standalone / Deep Sleep Mode
If running on a VPS, server, or container:
```bash
python cli.py run
```
* **Early Execution Guard:** If executed more than 15 minutes before opening, the sniper enters **Deep Sleep Mode**, consuming zero CPU and zero network until T-15 minutes.
* **T-15m:** Wakes up, re-syncs NTP clock drift, measures passive TCP latency, and downloads the community bias.
* **T-12s:** Preheats dual TLS sockets to Singapore edge clusters.
* **T-0:** Executes high-precision busy-wait loop and fires the double-tap burst.
* **T+2s:** Evaluates server response, saves adaptive bias, delivers notifications, and deschedules future jobs if approved.

---

## Configuration (`config.json`)

```json
{
  "auth": {
    "userId": "1234567890",
    "cUserId": "h4sh3d_s3cr3t",
    "new_bbs_serviceToken": "token_here",
    "passToken": "permanent_token_here",
    "deviceId": "STABLE_ANONYMOUS_ID",
    "versionCode": "500439",
    "versionName": "5.4.39"
  },
  "sniper": {
    "mode": "double_tap",
    "tap_interval_ms": 100.0
  },
  "calibration": {
    "auto_tune": true,
    "bias_ms": 0.0
  },
  "community": {
    "share_metrics": true,
    "fetch_global_bias": true
  },
  "telegram": {
    "bot_token": "",
    "chat_id": ""
  }
}
```

---

## What to Do When Approved
Once the sniper wins a quota, it prints a post-approval runbook and dispatches a notification:
1. Insert a SIM card with **active mobile data** into your Xiaomi device.
2. Turn off Wi-Fi (binding fails if connected to Wi-Fi).
3. Open **Settings -> Additional settings -> Developer options -> Mi Unlock status**.
4. Tap **Add account and device**.
5. Your official waiting period (e.g. 72 hours) will begin. Once elapsed, connect via USB and unlock via PC.

---

## Test Suite
Run the built-in regression test suite (26 unit tests covering cryptography, time zones, token auto-renewal, network payload sanitization, and clean output):
```bash
python test_suite.py
```

---

## Credits & Acknowledgments
* **[offici5l / MiForge](https://github.com/offici5l/migate):** Author of the `migate` Python gateway library used for official Xiaomi account authorization and session handshakes, as well as the reference response code mappings from `MiCommunityTool`.

---

## License
This project is licensed under the [MIT License](LICENSE).
