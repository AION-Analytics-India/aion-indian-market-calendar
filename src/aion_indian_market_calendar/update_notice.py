"""Local notification state for a signed offer. Never accesses the network."""
from pathlib import Path
import json
import os
import platform
import shutil
import subprocess
from .managed_updater import _atomic

def read(root):
    path = root / 'NOTICE.json'
    return json.loads(path.read_text(encoding='utf8')) if path.is_file() else {}

def desktop(message):
    system = platform.system()
    if system == 'Darwin':
        args = ['/usr/bin/osascript', '-e', 'on run argv\n display notification (item 1 of argv) with title "AION Calendar update"\nend run', message]
    elif system == 'Linux' and (os.getenv('DISPLAY') or os.getenv('WAYLAND_DISPLAY')) and shutil.which('notify-send'):
        args = [shutil.which('notify-send'), '--', 'AION Calendar update', message]
    elif system == 'Windows':
        # A normal-user tray notification; Focus Assist can suppress display.
        ps = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        script = ("Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; "
                  "$n=New-Object Windows.Forms.NotifyIcon; try { $n.Icon=[Drawing.SystemIcons]::Information; "
                  "$n.Visible=$true; $n.ShowBalloonTip(3500,'AION Calendar update',$env:AION_NOTICE_TEXT,"
                  "[Windows.Forms.ToolTipIcon]::Info); Start-Sleep -Seconds 4 } finally {$n.Dispose()}")
        args = [str(ps), '-NoProfile','-NonInteractive','-Command',script]
    else:
        return False
    try:
        run = subprocess.run(args, env={**os.environ,'AION_NOTICE_TEXT':message},
                             capture_output=True, timeout=8, check=False)
        return run.returncode == 0
    except (OSError,subprocess.TimeoutExpired):
        return False

def offer(root, project, installed, available, enabled, deliver=desktop):
    old = read(root)
    if old.get('available') == available and (old['acknowledged'] or old['desktop_requested_ok']):
        return old
    notes = f'https://github.com/AION-Analytics-India/{project}/releases/tag/v{available}'
    command = f'python -m pip install --upgrade {project}=={available}'
    doc = dict(installed=installed,available=available,release_notes=notes,upgrade_command=command,
               acknowledged=False,desktop_requested_ok=False)
    if enabled:
        doc['desktop_requested_ok'] = deliver(f'{project}: {installed} to {available}. {notes} | {command}')
    _atomic(root/'NOTICE.json', doc)
    return doc

def acknowledge(root, version):
    doc = read(root)
    if not version or doc.get('available') != version:
        raise ValueError('No matching signed release notice')
    doc['acknowledged'] = True
    _atomic(root/'NOTICE.json',doc)
    return doc
