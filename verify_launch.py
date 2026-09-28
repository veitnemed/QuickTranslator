"""Check installed launcher and Windows Calculator app-command routing."""
import ctypes
from ctypes import wintypes
import subprocess
import time
from pathlib import Path

user32 = ctypes.WinDLL('user32', use_last_error=True)
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.GetShellWindow.restype = wintypes.HWND
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

def visible():
    hwnd = user32.FindWindowW(None, 'Quick Translator')
    return bool(hwnd and user32.IsWindowVisible(hwnd))

def wait_for(expected):
    deadline = time.monotonic() + 10
    while visible() != expected:
        if time.monotonic() > deadline:
            raise AssertionError(f'Expected visible={expected}')
        time.sleep(.05)

wait_for(True)
launcher = str(Path(__file__).with_name('launch.vbs'))
subprocess.run(['wscript.exe', launcher], check=True)
wait_for(False)
subprocess.run(['wscript.exe', launcher], check=True)
wait_for(True)
print('PASS: installed launcher hides and restores existing window')
shell = user32.GetShellWindow()
if not shell:
    raise AssertionError('Explorer shell not available')
user32.PostMessageW(shell, 0x319, shell, 18 << 16)
wait_for(False)
user32.PostMessageW(shell, 0x319, shell, 18 << 16)
wait_for(True)
print('PASS: Windows Calculator app command hides and restores translator')
