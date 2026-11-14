"""Serialization proofs everywhere; WinAPI proofs only on real Windows.

These tests do not register tasks. Scheduler/reboot acceptance is a separate
explicit native test and cannot be inferred from this module's portable cases.
"""
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
import pytest
from aion_indian_market_calendar.windows_supervision import task_xml, NS, CONTROL
from aion_indian_market_calendar import windows_runtime as win


def test_task_contract_is_interactive_unprivileged_and_passwordless():
    raw=task_xml(Path('C:/private root'), 'owned-test', Path('C:/private root/python.exe'), 'S-1-5-21-1', 60)
    tree=ET.fromstring(raw);n={'t':NS}
    assert tree.findtext('.//t:LogonType', namespaces=n)=='InteractiveToken'
    assert tree.findtext('.//t:RunLevel', namespaces=n)=='LeastPrivilege'
    assert tree.findtext('.//t:Settings/t:Enabled', namespaces=n)=='false'
    assert tree.findtext('.//t:Repetition/t:Interval', namespaces=n)=='PT60S'
    assert tree.findtext('.//t:MultipleInstancesPolicy', namespaces=n)=='IgnoreNew'
    assert tree.findtext('.//t:Exec/t:Command', namespaces=n)=='C:/private root/python.exe'
    assert 'password' not in raw.decode().lower()
    assert '$sid,$null,3,$security' in CONTROL


@pytest.mark.parametrize('bad', ['bad\npath', 'bad\rpath', 'bad\0path'])
def test_task_control_characters_refused(bad):
    with pytest.raises(ValueError):task_xml(Path(bad),'test',Path('python'),'sid',60)


def test_task_unicode_and_spaces_are_data():
    root=Path('C:/a path/ગુજરાત');raw=task_xml(root,'owned',Path('C:/a path/python.exe'),'sid',60)
    tree=ET.fromstring(raw);n={'t':NS}
    assert tree.findtext('.//t:WorkingDirectory',namespaces=n)==str(root)
    assert tree.findtext('.//t:Arguments',namespaces=n)==subprocess.list2cmdline(
        ['-I','-m','aion_indian_market_calendar.update_lifecycle','worker','--root',str(root)])


def test_task_ownership_precedes_mutations():
    assert CONTROL.index('if($task){Confirm-Owned $task}') < CONTROL.index('switch($d.operation)')
    assert 'Unexpected task access' in CONTROL and 'Task ownership/action mismatch' in CONTROL


if os.name != 'nt':
    def test_posix_cannot_claim_native_windows_execution():
        with pytest.raises(NotImplementedError):win.native()


if os.name == 'nt':
    def test_native_shared_and_exclusive_leases(tmp_path):
        first=win.open_guard(tmp_path/'lease',shared=True)
        second=win.open_guard(tmp_path/'lease',shared=True)
        try:
            with pytest.raises(BlockingIOError):win.open_guard(tmp_path/'lease')
        finally:os.close(first);os.close(second)
        fd=win.open_guard(tmp_path/'lease');os.close(fd)

    def test_native_lease_inherited_by_child(tmp_path):
        guard=win.open_guard(tmp_path/'lease')
        try:
            result=win.run_child([sys.executable,'-c',
                'from pathlib import Path;from aion_indian_market_calendar.windows_runtime import open_guard;'
                '\ntry: open_guard(Path('+repr(str(tmp_path/'lease'))+'))'
                '\nexcept BlockingIOError: print("blocked")'
                '\nelse: raise AssertionError("inherited lease lost")'],lease_fds=(guard,),capture_output=True,text=True,check=True)
            assert result.stdout.strip()=='blocked'
        finally:os.close(guard)

    def test_native_private_directory_acl(tmp_path):
        root=tmp_path/'owned';win.create_private_directory(root);win.private_path(root)
