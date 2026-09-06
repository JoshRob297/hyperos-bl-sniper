"""
Multi-Platform Scheduler Manager.
Supports Linux (Crontab), macOS (launchd), and Windows (Task Scheduler).
"""

import os
import sys
import platform
import subprocess
from typing import Tuple

TASK_NAME = "HyperOS_BL_Sniper"


def is_scheduled() -> bool:
    """Checks whether the automated task is currently active on the OS."""
    os_name = platform.system()
    try:
        if os_name == "Linux":
            res = subprocess.run(["crontab", "-l"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return "hyperos-bl-sniper" in res.stdout or TASK_NAME in res.stdout
        elif os_name == "Darwin":
            plist_path = os.path.expanduser(f"~/Library/LaunchAgents/com.{TASK_NAME.lower()}.plist")
            return os.path.exists(plist_path)
        elif os_name == "Windows":
            res = subprocess.run(["schtasks", "/Query", "/TN", TASK_NAME], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return res.returncode == 0
    except Exception:
        pass
    return False


def enable_schedule(cli_path: str) -> Tuple[bool, str]:
    """
    Registers a daily scheduled task to run at 23:58 Beijing time
    (which translates dynamically according to the machine's local time offset).
    """
    os_name = platform.system()
    python_bin = sys.executable
    abs_cli = os.path.abspath(cli_path)
    workdir = os.path.dirname(abs_cli)

    # 00:00 GMT+8 is 16:00 UTC. 2 minutes before = 15:58 UTC.
    import datetime
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    target_utc = now_utc.replace(hour=15, minute=58, second=0, microsecond=0)
    local_time = target_utc.astimezone()
    cron_minute = local_time.minute
    cron_hour = local_time.hour

    try:
        if os_name == "Linux":
            res = subprocess.run(["crontab", "-l"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            existing = res.stdout if res.returncode == 0 else ""
            cleaned = [line for line in existing.splitlines() if TASK_NAME not in line and "hyperos-bl-sniper" not in line]
            cron_cmd = f"{cron_minute} {cron_hour} * * * cd \"{workdir}\" && \"{python_bin}\" \"{abs_cli}\" run >> \"{workdir}/sniper.log\" 2>&1 # {TASK_NAME}"
            cleaned.append(cron_cmd)
            new_crontab = "\n".join(cleaned) + "\n"
            p = subprocess.run(["crontab", "-"], input=new_crontab, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if p.returncode == 0:
                return True, f"Crontab registrado diariamente a las {cron_hour:02d}:{cron_minute:02d} (Hora local)."
            return False, p.stderr

        elif os_name == "Darwin":
            plist_dir = os.path.expanduser("~/Library/LaunchAgents")
            os.makedirs(plist_dir, exist_ok=True)
            plist_path = os.path.join(plist_dir, f"com.{TASK_NAME.lower()}.plist")
            plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.{TASK_NAME.lower()}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_bin}</string>
        <string>{abs_cli}</string>
        <string>run</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{workdir}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>{cron_hour}</integer>
        <key>Minute</key>
        <integer>{cron_minute}</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>{workdir}/sniper.log</string>
    <key>StandardErrorPath</key>
    <string>{workdir}/sniper.log</string>
</dict>
</plist>
"""
            with open(plist_path, "w", encoding="utf-8") as f:
                f.write(plist_content)
            subprocess.run(["launchctl", "unload", plist_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            p = subprocess.run(["launchctl", "load", plist_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if p.returncode == 0:
                return True, f"macOS LaunchAgent registrado a las {cron_hour:02d}:{cron_minute:02d}."
            return False, p.stderr

        elif os_name == "Windows":
            time_str = f"{cron_hour:02d}:{cron_minute:02d}"
            # Windows Task Scheduler's /TR argument is notorious for mangling nested
            # quotes. Use a small .bat wrapper to keep the command line single-level.
            bat_path = os.path.join(workdir, "sniper_run.bat")
            bat_content = (
                "@echo off\r\n"
                "cd /d \"%~dp0\"\r\n"
                f"\"{python_bin}\" \"{abs_cli}\" run >> \"{workdir}\\sniper.log\" 2>&1\r\n"
            )
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write(bat_content)
            cmd = [
                "schtasks", "/Create", "/F",
                "/TN", TASK_NAME,
                "/TR", f'cmd.exe /c ""{bat_path}""',
                "/SC", "DAILY",
                "/ST", time_str,
            ]
            p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if p.returncode == 0:
                return True, f"Windows Task Scheduler registrado para las {time_str} (Hora local)."
            return False, p.stderr

        return False, f"Sistema operativo no soportado para auto-scheduling: {os_name}"
    except Exception as e:
        return False, str(e)


def disable_schedule() -> Tuple[bool, str]:
    """Disables and removes the scheduled task from the operating system."""
    os_name = platform.system()
    try:
        if os_name == "Linux":
            res = subprocess.run(["crontab", "-l"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode != 0:
                return True, "No se encontró crontab activo."
            cleaned = [line for line in res.stdout.splitlines() if TASK_NAME not in line and "hyperos-bl-sniper" not in line]
            new_crontab = "\n".join(cleaned) + "\n" if cleaned else ""
            if new_crontab.strip():
                subprocess.run(["crontab", "-"], input=new_crontab, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            else:
                subprocess.run(["crontab", "-r"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True, "Crontab eliminado con éxito."

        elif os_name == "Darwin":
            plist_path = os.path.expanduser(f"~/Library/LaunchAgents/com.{TASK_NAME.lower()}.plist")
            if os.path.exists(plist_path):
                subprocess.run(["launchctl", "unload", plist_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                os.remove(plist_path)
            return True, "LaunchAgent de macOS eliminado con éxito."

        elif os_name == "Windows":
            cmd = ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            bat_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sniper_run.bat")
            bat_path = os.path.abspath(bat_path)
            if os.path.exists(bat_path):
                try:
                    os.remove(bat_path)
                except Exception:
                    pass
            return True, "Tarea de Windows Task Scheduler eliminada con éxito."

        return False, f"Sistema operativo no soportado: {os_name}"
    except Exception as e:
        return False, str(e)
