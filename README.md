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

### 3. Collective Intelligence Network
Nodes running around the world report anonymous timing metrics (RTT, applied bias, server response delta) to an isolated edge endpoint. A daily consensus algorithm (1D DBSCAN clustering, trimmed median, and strict Anti-Sybil gates) compiles the winning bias and publishes `community_bias.json` to GitHub. Nodes synchronize this recommended bias before shooting. Zero personal data, credentials, or hardware IDs are ever transmitted.

---

## Quick Start

### 1. Clone & Install Dependencies
```bash
git clone git@github.com:JoshRob297/hyperos-bl-sniper.git
cd hyperos-bl-sniper
pip install -r requirements.txt
```

### 2. Login via Authentication Assistant
Supports official browser authorization, terminal password/OTP, and manual cookie injection:
```bash
python cli.py login
```
* **Option 1 (Official Assistant via `migate`):** Opens official Xiaomi web login (Browser), prompts terminal credentials (Terminal), or renders QR code.
* **Option 2 (Manual Cookie Injection):** Directly paste `userId` and `new_bbs_serviceToken` copied from [c.mi.com](https://c.mi.com) using browser developer tools (F12). Also accessible via `python cli.py login --manual`.

### 3. Check Session & Account Status
```bash
python cli.py status
```
Displays current token validity, daily scheduled job status, and server permissions (`is_pass`, deadline, and remaining penalty intervals).

### 4. Enable Daily Auto-Snipe (Cross-Platform)
Registers an automated background job in your operating system (Crontab on Linux, `launchd` on macOS, or Task Scheduler on Windows) set to fire 2 minutes before midnight Beijing time (00:00:00 GMT+8):
```bash
python cli.py schedule
```
To remove the scheduled task at any time:
```bash
python cli.py unschedule
```

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
Run the built-in regression test suite (23 unit tests covering cryptography, time zones, token auto-renewal, network payload sanitization, and clean output):
```bash
python test_suite.py
```

---

## License
This project is licensed under the [MIT License](LICENSE).
