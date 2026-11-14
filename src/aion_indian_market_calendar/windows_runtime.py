"""Native Windows primitives for the existing managed lifecycle.

No scheduler, authorization, trust or promotion policy is implemented here.
Exclusive/shared file handles retain leases through child inheritance. The
dedicated CLI worker owns a kill-on-close job; no unrelated process is assigned.
Native execution is a separate release gate, never inferred from POSIX tests.
"""
from __future__ import annotations
import base64
import contextlib
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import stat
import subprocess
import threading

_spawn_lock=threading.Lock()
_worker_jobs=[]


def native():
    if os.name!='nt':raise NotImplementedError('This adapter requires native Windows')


def powershell(script: str, data: dict) -> dict:
    native()
    # This adapter carries only local task/path metadata, never credentials or
    # key material. Avoid Console.In semantics under redirected/native runners.
    if set(data) - {'path','label','root','python','arguments','operation','xml'}:
        raise ValueError('Unsupported native metadata field')
    payload=base64.b64encode(json.dumps(data,ensure_ascii=True).encode()).decode('ascii')
    prefix='''
$ErrorActionPreference='Stop'
$env:PSModulePath=$PSHOME+'\\Modules'
Import-Module ($PSHOME+'\\Modules\\Microsoft.PowerShell.Utility\\Microsoft.PowerShell.Utility.psd1') -ErrorAction Stop
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
''' + "$d=[System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+payload+"')) | ConvertFrom-Json\n"
    encoded=base64.b64encode((prefix+script).encode('utf-16-le')).decode('ascii')
    exe=Path(os.environ['SYSTEMROOT'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
    try:
        result=subprocess.run([str(exe),'-NoLogo','-NoProfile','-NonInteractive','-EncodedCommand',encoded],
                              stdin=subprocess.DEVNULL,capture_output=True,text=True,
                              encoding='utf-8',timeout=30)
    except subprocess.TimeoutExpired:
        raise TimeoutError('Native Windows operation timed out; no policy was weakened') from None
    if result.returncode:
        raise PermissionError('Native Windows operation failed; no policy was weakened')
    return json.loads(result.stdout.lstrip('\ufeff').strip())


IDENTITY='''
$id=[System.Security.Principal.WindowsIdentity]::GetCurrent()
$sid=$id.User.Value
$principal=[System.Security.Principal.WindowsPrincipal]::new($id)
$session=[System.Diagnostics.Process]::GetCurrentProcess().SessionId
if($id.IsSystem -or $sid -in @('S-1-5-18','S-1-5-19','S-1-5-20')){throw 'Service-account enrollment refused'}
'''


def interactive_identity() -> dict:
    out=powershell(IDENTITY+'''
if($session -eq 0){throw 'An interactive user session is required'}
@{sid=$sid;interactive=$true;elevated=$principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)} | ConvertTo-Json -Compress
''',{})
    return out


def reject_reparse(path: Path):
    native()
    for p in (path,*path.parents):
        if p.exists() or p.is_symlink():
            if p.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise PermissionError('Windows reparse points are not allowed in managed paths')


def private_path(path: Path):
    reject_reparse(path)
    powershell(IDENTITY+'''
if([System.IO.Directory]::Exists($d.path)){$acl=[System.IO.Directory]::GetAccessControl($d.path)}else{$acl=[System.IO.File]::GetAccessControl($d.path)}
$descriptor=[System.Security.AccessControl.RawSecurityDescriptor]::new($acl.GetSecurityDescriptorSddlForm([System.Security.AccessControl.AccessControlSections]::All))
if($null -eq $descriptor.DiscretionaryAcl){throw 'Null DACL refused'}
$owner=$acl.GetOwner([System.Security.Principal.SecurityIdentifier]).Value
$trusted=@($sid,'S-1-5-18','S-1-5-32-544')
if($owner -notin $trusted){throw 'Untrusted owner'}
$writeMask=2 -bor 4 -bor 16 -bor 64 -bor 256 -bor 65536 -bor 262144 -bor 524288
foreach($ace in $acl.GetAccessRules($true,$true,[System.Security.Principal.SecurityIdentifier])){
 if($ace.PropagationFlags -band [System.Security.AccessControl.PropagationFlags]::InheritOnly){continue}
 if($ace.AccessControlType -eq 'Allow'){
  $who=$ace.IdentityReference.Value
  if(($who -notin $trusted) -and (([int]$ace.FileSystemRights -band $writeMask) -ne 0)){throw 'Untrusted writable ACL'}
 }
}
@{private=$true} | ConvertTo-Json -Compress
''',{'path':str(path)})


def create_private_directory(path: Path):
    private_path(path.parent)
    path.mkdir()
    powershell(IDENTITY+'''
$acl=[System.Security.AccessControl.DirectorySecurity]::new()
$acl.SetOwner([System.Security.Principal.SecurityIdentifier]::new($sid))
$acl.SetAccessRuleProtection($true,$false)
foreach($who in @($sid,'S-1-5-18','S-1-5-32-544')){
 $rule=[System.Security.AccessControl.FileSystemAccessRule]::new(
  [System.Security.Principal.SecurityIdentifier]::new($who),'FullControl',
  [System.Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit',
  [System.Security.AccessControl.PropagationFlags]::None,[System.Security.AccessControl.AccessControlType]::Allow)
 $acl.AddAccessRule($rule)
}
[System.IO.Directory]::SetAccessControl($d.path,$acl)
@{private=$true} | ConvertTo-Json -Compress
''',{'path':str(path)})
    private_path(path)


def open_guard(path: Path, *, shared: bool=False) -> int:
    native();reject_reparse(path)
    import msvcrt
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    create=kernel.CreateFileW;create.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,
                                             ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
    create.restype=wintypes.HANDLE
    handle=create(str(path),0x80000000|0x40000000,3 if shared else 0,None,4,0x00200000,None)
    if handle==ctypes.c_void_p(-1).value:
        error=ctypes.get_last_error()
        if error in (32,33):raise BlockingIOError('A managed Windows lease is held')
        raise ctypes.WinError(error)
    try:
        os.set_handle_inheritable(handle,False)
        return msvcrt.open_osfhandle(handle,os.O_RDWR|os.O_BINARY)
    except BaseException:
        kernel.CloseHandle(wintypes.HANDLE(handle));raise


def run_child(args, *, lease_fds=(), timeout=None, check=False, **kwargs):
    native();import msvcrt
    if kwargs.pop("capture_output", False):
        if "stdout" in kwargs or "stderr" in kwargs:raise ValueError("capture_output conflicts with explicit streams")
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    handles=[msvcrt.get_osfhandle(fd) for fd in lease_fds]
    # Only the construction window marks handles inheritable. No global
    # close_fds=False or unbounded ambient-handle inheritance is permitted.
    with _spawn_lock:
        for handle in handles:os.set_handle_inheritable(handle,True)
        try:
            startup=subprocess.STARTUPINFO(lpAttributeList={'handle_list':handles})
            proc=subprocess.Popen(args,startupinfo=startup,close_fds=True,**kwargs)
        finally:
            for handle in handles:os.set_handle_inheritable(handle,False)
    try:stdout,stderr=proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        subprocess.run([str(Path(os.environ['SYSTEMROOT'])/'System32/taskkill.exe'),'/PID',str(proc.pid),'/T','/F'],
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15)
        proc.communicate();raise
    result=subprocess.CompletedProcess(args,proc.returncode,stdout,stderr)
    if check and result.returncode:raise subprocess.CalledProcessError(result.returncode,args,stdout,stderr)
    return result


def attach_worker_job():
    """Dedicated CLI process only. Never call on an unrelated application."""
    native()
    if _worker_jobs:return
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    class Basic(ctypes.Structure):
        _fields_=[('ProcessTime',ctypes.c_int64),('JobTime',ctypes.c_int64),('Flags',wintypes.DWORD),
                  ('MinWS',ctypes.c_size_t),('MaxWS',ctypes.c_size_t),('Active',wintypes.DWORD),
                  ('Affinity',ctypes.c_size_t),('Priority',wintypes.DWORD),('Scheduling',wintypes.DWORD)]
    class IO(ctypes.Structure):
        _fields_=[(name,ctypes.c_uint64) for name in ['ReadOps','WriteOps','OtherOps','ReadBytes','WriteBytes','OtherBytes']]
    class Limits(ctypes.Structure):
        _fields_=[('Basic',Basic),('IO',IO),('ProcessMemory',ctypes.c_size_t),('JobMemory',ctypes.c_size_t),
                  ('PeakProcessMemory',ctypes.c_size_t),('PeakJobMemory',ctypes.c_size_t)]
    kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR];kernel.CreateJobObjectW.restype=wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE]
    kernel.GetCurrentProcess.restype=wintypes.HANDLE
    handle=kernel.CreateJobObjectW(None,None)
    if not handle:raise ctypes.WinError(ctypes.get_last_error())
    limits=Limits();limits.Basic.Flags=0x2000
    if not kernel.SetInformationJobObject(handle,9,ctypes.byref(limits),ctypes.sizeof(limits)) or not kernel.AssignProcessToJobObject(handle,kernel.GetCurrentProcess()):
        error=ctypes.get_last_error();kernel.CloseHandle(wintypes.HANDLE(handle))
        raise PermissionError('Windows process-tree containment unavailable: '+str(error))
    os.set_handle_inheritable(handle,False)
    # Retain until this dedicated process exits. Closing it earlier would
    # terminate the caller too; children never inherit the controlling handle.
    _worker_jobs.append(handle)
