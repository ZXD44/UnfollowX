"""
UnfollowX Windows Desktop Notification Helper
Uses PowerShell balloon / toast natively without third-party dependencies.
"""

import subprocess
import threading

def show_desktop_notification(title, message):
    def _run():
        try:
            # Clean text for PowerShell command line
            clean_title = title.replace('"', '\"').replace("'", "")
            clean_msg = message.replace('"', '\"').replace("'", "")
            ps_script = f"""
            [reflection.assembly]::loadwithpartialname('System.Windows.Forms') | Out-Null
            $notify = New-Object System.Windows.Forms.NotifyIcon
            $notify.Icon = [System.Drawing.SystemIcons]::Information
            $notify.Visible = $True
            $notify.ShowBalloonTip(5000, '{clean_title}', '{clean_msg}', [System.Windows.Forms.ToolTipIcon]::Info)
            Start-Sleep -Seconds 6
            $notify.Dispose()
            """
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", ps_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=8
            )
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()
