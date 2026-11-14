"""User-only OS supervision. Every mutation is limited to an owned job label.

macOS resumes on user login; Linux resumes when its user manager starts. A
pre-login Linux service requires separately authorized, pre-existing lingering.
This module never enables lingering, uses sudo, or restarts another service.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import subprocess


def quote(value: str) -> str:
    if '\n' in value or '\r' in value or '\0' in value:
        raise ValueError('Service argument contains a control character')
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'


class Service:
    def __init__(self, root: Path, cfg: dict, directory: Path | None = None):
        self.root, self.cfg = root, cfg
        self.system = platform.system()
        if self.system not in ('Darwin', 'Linux', 'Windows'):
            raise NotImplementedError('No supported user-scoped scheduler for this platform')
        if self.system == 'Windows':
            from .windows_runtime import native
            native()
        self.label = 'com.aion.calendar.updates.' + hashlib.sha256(str(root).encode()).hexdigest()[:16]
        existing = cfg.get('service')
        if existing and (existing['label'] != self.label or existing['system'] != self.system):
            raise ValueError('Service ownership record mismatch')
        self.directory = Path(existing['directory']) if existing else directory
        if self.directory is None:
            self.directory = (root / 'task-files' if self.system == 'Windows' else
                              Path.home() / ('Library/LaunchAgents' if self.system == 'Darwin' else '.config/systemd/user'))
        self.directory = self.directory.absolute()
        self.files = [self.directory / (self.label + ext) for ext in
                      (['.xml'] if self.system == 'Windows' else ['.plist'] if self.system == 'Darwin' else ['.service', '.timer'])]
        self.windows = None
        if self.system == 'Windows':
            from .windows_supervision import WindowsService
            self.windows = WindowsService(self)
            return
        self.domain = 'gui/' + str(os.getuid())
        self.target = self.domain + '/' + self.label

    def command(self, *args, allow_failure=False):
        result = subprocess.run(list(args), stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
        if result.returncode and not allow_failure:
            raise RuntimeError('OS service operation failed: ' + args[0] + ' exit ' + str(result.returncode))
        return result

    def owned(self):
        existing = self.cfg.get('service')
        if not existing:return
        for p in self.files:
            if p.is_symlink() or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != existing['hashes'].get(p.name):
                raise PermissionError('Service file changed or is not owned by this setup')

    def record(self):
        return {'system': self.system, 'label': self.label, 'directory': str(self.directory),
                'hashes': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.files}}

    def install(self):
        if self.windows:return self.windows.install()
        from .update_lifecycle import private_file
        if self.directory.is_symlink():raise PermissionError('Service directory must not be a symlink')
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        private_file(self.directory)
        if any(p.exists() or p.is_symlink() for p in self.files):
            raise FileExistsError('A service file already exists; no file was replaced')
        args = [str(self.root / 'controller/bin/python'), '-I', '-m',
                'aion_indian_market_calendar.update_lifecycle', 'worker', '--root', str(self.root)]
        environment = {'AION_IN_CALENDAR_OFFLINE': '0', 'TMPDIR': str(self.root / 'tmp'),
                       'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONNOUSERSITE': '1'}
        if self.system == 'Darwin':
            body = plistlib.dumps({'Label': self.label, 'ProgramArguments': args,
                                   'RunAtLoad': True, 'StartInterval': self.cfg['policy']['poll_seconds'],
                                   'ProcessType': 'Background', 'Nice': 10, 'LowPriorityIO': True,
                                   'WorkingDirectory': str(self.root), 'EnvironmentVariables': environment,
                                   'StandardOutPath': str(self.root / 'supervisor.stdout.log'),
                                   'StandardErrorPath': str(self.root / 'supervisor.stderr.log')})
            self.files[0].write_bytes(body)
        else:
            execstart = ' '.join(quote(a) for a in args)
            env = '\n'.join('Environment=' + quote(k + '=' + v) for k, v in environment.items())
            service = ('[Unit]\nDescription=AION Calendar isolated managed update check\n'
                       '[Service]\nType=oneshot\nExecStart=' + execstart + '\n' + env + '\n'
                       'TimeoutStartSec=240\nKillMode=control-group\nNice=10\nNoNewPrivileges=yes\n'
                       'CPUQuota=100%\nMemoryMax=512M\n')
            timer = ('[Unit]\nDescription=AION Calendar opted-in update schedule\n'
                     '[Timer]\nOnActiveSec=1s\nOnUnitInactiveSec=' + str(self.cfg['policy']['poll_seconds']) + 's\n'
                     'AccuracySec=1s\nUnit=' + self.label + '.service\n[Install]\nWantedBy=timers.target\n')
            self.files[0].write_text(service);self.files[1].write_text(timer)
        for p in self.files:p.chmod(0o600)

    def start(self):
        self.owned()
        if self.windows:return self.windows.start()
        if self.system == 'Darwin':
            self.command('launchctl', 'enable', self.target)
            if not self.status()['registered']:
                self.command('launchctl', 'bootstrap', self.domain, str(self.files[0]))
            self.command('launchctl', 'kickstart', self.target)
        else:
            for p in self.files:
                self.command('systemctl', '--user', 'link', str(p))
            self.command('systemctl', '--user', 'daemon-reload')
            self.command('systemctl', '--user', 'enable', '--now', self.label + '.timer')
        if not self.status()['scheduled']:
            raise RuntimeError('OS did not confirm an enabled update schedule')

    def stop(self):
        self.owned()
        if self.windows:return self.windows.stop()
        if self.system == 'Darwin':
            if self.status()['registered']:
                self.command('launchctl', 'bootout', self.target)
        else:
            self.command('systemctl', '--user', 'stop', self.label + '.timer', self.label + '.service', allow_failure=True)
            self._verify_linux_stopped()

    def _verify_linux_stopped(self, *, disabled=False):
        for ext in ('.timer', '.service'):
            r=self.command('systemctl', '--user', 'show', self.label+ext,
                           '--property=ActiveState,UnitFileState', allow_failure=True)
            values=dict(line.split('=',1) for line in r.stdout.splitlines() if '=' in line)
            if values.get('ActiveState') not in ('inactive', 'failed'):
                raise RuntimeError('OS did not confirm that the owned updater stopped')
            if disabled and values.get('UnitFileState') in ('enabled', 'enabled-runtime'):
                raise RuntimeError('OS did not confirm that the owned schedule was disabled')

    def disable(self):
        self.owned()
        if self.windows:return self.windows.disable()
        if self.system == 'Darwin':
            self.command('launchctl', 'disable', self.target)
            self.stop()
        else:
            # Disabling an externally linked user timer removes its link. A
            # second disable can report "not found"; accept only after actual
            # inactive/disabled readback, never merely because a command failed.
            self.command('systemctl', '--user', 'disable', '--now', self.label + '.timer', allow_failure=True)
            self.command('systemctl', '--user', 'stop', self.label + '.service', allow_failure=True)
            self._verify_linux_stopped(disabled=True)

    def status(self):
        # Read the provider even after a failed uninstall. A local tombstone
        # must never conceal a still-registered or still-running OS job.
        if self.windows:return self.windows.status()
        if self.system == 'Darwin':
            r = self.command('launchctl', 'print', self.target, allow_failure=True)
            disabled = self.command('launchctl', 'print-disabled', self.domain, allow_failure=True)
            is_disabled = ('"' + self.label + '" => true') in disabled.stdout
            registered = r.returncode == 0
            return {'registered': registered, 'scheduled': registered and not is_disabled,
                    'restart_scope': 'user-login', 'running': registered and '\n\tpid = ' in r.stdout}
        r = self.command('systemctl', '--user', 'show', self.label + '.timer',
                         '--property=LoadState,ActiveState,UnitFileState', allow_failure=True)
        values = dict(line.split('=', 1) for line in r.stdout.splitlines() if '=' in line)
        linger = self.command('loginctl', 'show-user', str(os.getuid()), '--property=Linger', '--value', allow_failure=True).stdout.strip() == 'yes'
        return {'registered': values.get('LoadState') == 'loaded',
                'scheduled': values.get('ActiveState') == 'active' and values.get('UnitFileState') in ('enabled', 'enabled-runtime'),
                'active_state': values.get('ActiveState'), 'unit_file_state': values.get('UnitFileState'),
                'restart_scope': 'boot-with-existing-linger' if linger else 'user-manager-start/login', 'linger': linger}

    def uninstall(self):
        if self.windows:
            # A second uninstall reads the provider again; a local tombstone
            # never substitutes for a deleted task.
            if any(p.exists() for p in self.files):self.owned()
            elif self.windows.status()['registered']:
                raise PermissionError('Task exists but owned definition is missing')
            return self.windows.uninstall()
        self.owned()
        # The caller's just-written uninstalled flag must not suppress the live
        # provider readback used by stop/disable.
        original = self.cfg.get('uninstalled');self.cfg['uninstalled'] = False
        try:self.disable()
        finally:self.cfg['uninstalled'] = original
        for p in self.files:p.unlink()
        if self.system == 'Linux':
            for p in self.files:
                link = Path.home() / '.config/systemd/user' / p.name
                if link.is_symlink() and link.resolve() == p:
                    link.unlink()
            self.command('systemctl', '--user', 'daemon-reload')
        # Managed environments, receipts and rollback evidence are retained.
