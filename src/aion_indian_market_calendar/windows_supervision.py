"""Staged Task Scheduler adapter for the existing managed update lifecycle.

Interactive user token only: no stored password, service account, elevation,
S4U fallback or promise of network checks while the user is logged out.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from . import windows_runtime as win

NS = 'http://schemas.microsoft.com/windows/2004/02/mit/task'
ET.register_namespace('', NS)


def task_xml(root: Path, label: str, python: Path, sid: str, seconds: int) -> bytes:
    """Pure serialization; not proof of a registered Windows task."""
    if not isinstance(seconds, int) or seconds < 60:
        raise ValueError('Task interval must be at least 60 seconds')
    values = [str(root), str(python), label, sid]
    if any(any(ord(c) < 32 for c in v) for v in values):
        raise ValueError('Task paths/identity cannot contain control characters')
    tree = ET.Element('Task', {'xmlns': NS, 'version': '1.4'})
    def add(parent, tag, value=None, **attrs):
        item = ET.SubElement(parent, tag, attrs)
        if value is not None:item.text = str(value)
        return item
    registration = add(tree, 'RegistrationInfo')
    add(registration, 'Description', label)
    triggers = add(tree, 'Triggers')
    timer = add(triggers, 'TimeTrigger')
    repetition = add(timer, 'Repetition')
    add(repetition, 'Interval', 'PT'+str(seconds)+'S')
    add(repetition, 'StopAtDurationEnd', 'false')
    add(timer, 'StartBoundary', (datetime.now(timezone.utc)+timedelta(seconds=5)).isoformat(timespec='seconds'))
    add(timer, 'Enabled', 'true')
    login = add(triggers, 'LogonTrigger');add(login, 'Enabled', 'true');add(login, 'UserId', sid)
    principals = add(tree, 'Principals');principal = add(principals, 'Principal', id='Owner')
    add(principal, 'UserId', sid);add(principal, 'LogonType', 'InteractiveToken');add(principal, 'RunLevel', 'LeastPrivilege')
    settings = add(tree, 'Settings')
    for tag, value in [('MultipleInstancesPolicy','IgnoreNew'),('DisallowStartIfOnBatteries','false'),
                       ('StopIfGoingOnBatteries','false'),('StartWhenAvailable','true'),
                       ('RunOnlyIfNetworkAvailable','false'),('Enabled','false'),
                       ('ExecutionTimeLimit','PT4M'),('Priority','7')]:add(settings, tag, value)
    actions = add(tree, 'Actions', Context='Owner');action = add(actions, 'Exec')
    add(action, 'Command', python)
    add(action, 'Arguments', subprocess.list2cmdline(['-I','-m','aion_indian_market_calendar.update_lifecycle','worker','--root',str(root)]))
    add(action, 'WorkingDirectory', root)
    return ET.tostring(tree, encoding='utf-8', xml_declaration=True)


# The script is fixed source. JSON metadata is encoded as data, never evaluated
# as shell text; no credential fields are accepted. Every mutation rechecks
# ownership and exact action.
CONTROL = win.IDENTITY + r'''
$svc=New-Object -ComObject 'Schedule.Service';$svc.Connect();$folder=$svc.GetFolder('\')
$task=$null
try {$task=$folder.GetTask($d.label)} catch {
 if($_.Exception.GetBaseException().HResult -ne -2147024894){throw}
}
function Confirm-Owned($t){
 $v=$t.Definition
 if($v.RegistrationInfo.Description -ne $d.label -or $v.Principal.UserId -ne $sid -or
    $v.Principal.LogonType -ne 3 -or $v.Principal.RunLevel -ne 0 -or
    $v.Actions.Count -ne 1 -or $v.Actions.Item(1).Type -ne 0 -or
    $v.Actions.Item(1).Path -ne $d.python -or $v.Actions.Item(1).Arguments -cne $d.arguments -or
    $v.Actions.Item(1).WorkingDirectory -ne $d.root){throw 'Task ownership/action mismatch'}
 $sddl=$t.GetSecurityDescriptor(4)
 $sd=[System.Security.AccessControl.RawSecurityDescriptor]::new($sddl)
 if($null -eq $sd.DiscretionaryAcl){throw 'Null task DACL refused'}
 foreach($ace in $sd.DiscretionaryAcl){
  if($ace.AceType -eq [System.Security.AccessControl.AceType]::AccessAllowed -and
     $ace.SecurityIdentifier.Value -notin @($sid,'S-1-5-18','S-1-5-32-544')){throw 'Unexpected task access'}
 }
}
if($task){Confirm-Owned $task}
switch($d.operation){
 'install' {
  if($session -eq 0){throw 'Interactive enrollment required'}
  if($task){throw 'Existing task will not be overwritten'}
  $security='D:P(A;;GA;;;'+$sid+')(A;;GA;;;SY)(A;;GA;;;BA)'
  $task=$folder.RegisterTask($d.label,$d.xml,2,$sid,$null,3,$security)
  Confirm-Owned $task
 }
 'start' {if(!$task){throw 'Owned task missing'};$task.Enabled=$true;$null=$task.Run($null)}
 'stop' {if($task){$task.Enabled=$false;$task.Stop(0)}}
 'disable' {if($task){$task.Enabled=$false;$task.Stop(0)}}
 'uninstall' {if($task){$task.Enabled=$false;$task.Stop(0)}}
 'status' {}
 default {throw 'Unknown operation'}
}
if($d.operation -in @('stop','disable','uninstall') -and $task){
 $until=[DateTime]::UtcNow.AddSeconds(20)
 while($task.GetInstances(0).Count -gt 0 -and [DateTime]::UtcNow -lt $until){Start-Sleep -Milliseconds 100}
 if($task.GetInstances(0).Count -ne 0){throw 'Owned task still running'}
}
if($d.operation -eq 'uninstall' -and $task){
 $folder.DeleteTask($d.label,0);$task=$null
 try {$null=$folder.GetTask($d.label);throw 'Task still registered'} catch {
  if($_.Exception.GetBaseException().HResult -ne -2147024894){throw}
 }
}
if($task){
 @{registered=$true;scheduled=[bool]$task.Enabled;running=($task.GetInstances(0).Count -gt 0);
   last_result=[int64]$task.LastTaskResult;restart_scope='interactive-user-logon';logged_out_checks=$false} | ConvertTo-Json -Compress
}else{
 @{registered=$false;scheduled=$false;running=$false;restart_scope='interactive-user-logon';logged_out_checks=$false} | ConvertTo-Json -Compress
}
'''


class WindowsService:
    def __init__(self, service):
        win.native()
        self.service = service

    def call(self, operation, **extra):
        from .update_lifecycle import controller_python
        s = self.service
        python = controller_python(s.root)
        return win.powershell(CONTROL, {'operation':operation,'root':str(s.root),'label':s.label,
              'python':str(python),'arguments':subprocess.list2cmdline(['-I','-m',
              'aion_indian_market_calendar.update_lifecycle','worker','--root',str(s.root)]),**extra})

    def install(self):
        from .update_lifecycle import controller_python, private_file
        s = self.service;identity = win.interactive_identity()
        if s.directory.exists():private_file(s.directory)
        else:win.create_private_directory(s.directory)
        if any(p.exists() for p in s.files):raise FileExistsError('Task record exists; no overwrite')
        raw = task_xml(s.root,s.label,controller_python(s.root),identity['sid'],s.cfg['policy']['poll_seconds'])
        s.files[0].write_bytes(raw)
        try:self.call('install',xml=raw.decode('utf-8'))
        except BaseException:
            # Retain the task definition on an ambiguous provider failure; an
            # operator can reconcile provider state before retrying.
            raise

    def start(self):
        result = self.call('start')
        if not result['scheduled']:raise RuntimeError('Task Scheduler did not enable the owned task')

    def stop(self):self.call('stop')
    def disable(self):self.call('disable')
    def status(self):return self.call('status')
    def uninstall(self):
        result = self.call('uninstall')
        if result['registered'] or result['running']:raise RuntimeError('Task teardown incomplete')
        for p in self.service.files:p.unlink(missing_ok=True)
