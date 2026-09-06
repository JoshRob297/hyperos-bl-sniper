"""
Universal Multiplatform Notification Dispatcher.
Supports native OS notifications (Windows, macOS, Linux Desktop) and optional Telegram alerts.
"""

import platform
import subprocess
import urllib.request
import urllib.parse
from typing import Optional, Dict


def notify_desktop(title: str, message: str) -> None:
    """Dispatches a native OS toast or desktop banner."""
    os_name = platform.system()
    # Sanitizar comillas para evitar inyecciones o rupturas en comandos de shell
    safe_title = title.replace('"', '\\"').replace("'", "")
    safe_msg = message.replace('"', '\\"').replace("'", "")
    try:
        if os_name == "Linux":
            subprocess.run(["notify-send", safe_title, safe_msg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif os_name == "Darwin":
            script = f'display notification "{safe_msg}" with title "{safe_title}"'
            subprocess.run(["osascript", "-e", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif os_name == "Windows":
            # PowerShell balloon/toast invocation
            ps_script = f"""
            [reflection.assembly]::loadwithpartialname('System.Windows.Forms') | Out-Null
            $notify = new-object system.windows.forms.notifyicon
            $notify.icon = [System.Drawing.SystemIcons]::Information
            $notify.visible = $true
            $notify.showballoontip(10, '{safe_title}', '{safe_msg}', [system.windows.forms.tooltipicon]::Info)
            """
            subprocess.run(["powershell", "-Command", ps_script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def notify_telegram(bot_token: str, chat_id: str, text: str) -> bool:
    """Sends HTML-formatted alert via official Telegram Bot API."""
    if not bot_token or not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, method="POST")
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.status == 200
    except Exception:
        return False


def dispatch_notification(title: str, message: str, config: Optional[Dict] = None) -> None:
    """Sends notification to desktop and optionally to Telegram if configured."""
    notify_desktop(title, message)

    if config and "telegram" in config:
        tg = config.get("telegram", {})
        token = tg.get("bot_token")
        chat_id = tg.get("chat_id")
        if token and chat_id:
            html_msg = f"<b>{title}</b>\n{message}"
            notify_telegram(token, chat_id, html_msg)
