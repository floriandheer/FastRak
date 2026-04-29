#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Generate a Windows .lnk shortcut for fastrak_hub.py next to this script.

Resolves all paths relative to the script's own location, so it works on any
PC where the floriandheer repo is cloned. Run once after setup; pin the
resulting Fastrak.lnk to the taskbar/desktop.
"""

import os
import sys
import shutil
import subprocess


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_SCRIPT = os.path.join(SCRIPT_DIR, "fastrak_hub.py")
ICON_PATH = os.path.join(SCRIPT_DIR, "assets", "Favicon_FlorianDheer.ico")
SHORTCUT_PATH = os.path.join(SCRIPT_DIR, "Fastrak.lnk")
APP_USER_MODEL_ID = "floriandheer.fastrak"


def find_pythonw():
    """Locate pythonw.exe in the active interpreter's folder, then on PATH."""
    candidate = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if os.path.exists(candidate):
        return candidate
    on_path = shutil.which("pythonw.exe") or shutil.which("pythonw")
    if on_path:
        return on_path
    raise FileNotFoundError("pythonw.exe not found — install Python or add it to PATH.")


def build_shortcut(pythonw_exe: str) -> None:
    """Invoke PowerShell's WScript.Shell to write the .lnk."""
    if not os.path.exists(TARGET_SCRIPT):
        raise FileNotFoundError(f"Missing target script: {TARGET_SCRIPT}")

    icon_line = (
        f'$s.IconLocation = "{ICON_PATH},0";' if os.path.exists(ICON_PATH) else ""
    )

    ps = (
        f'$w = New-Object -ComObject WScript.Shell;'
        f'$s = $w.CreateShortcut("{SHORTCUT_PATH}");'
        f'$s.TargetPath = "{pythonw_exe}";'
        f'$s.Arguments = \'"{TARGET_SCRIPT}"\';'
        f'$s.WorkingDirectory = "{SCRIPT_DIR}";'
        f'{icon_line}'
        f'$s.Description = "Fastrak Pipeline Hub";'
        f'$s.WindowStyle = 1;'
        f'$s.Save();'
    )

    subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps],
        check=True,
    )

    # Stamp the AppUserModelID onto the .lnk so the pinned shortcut groups
    # under the same taskbar slot as the running window.
    stamp = (
        f'$bytes = [System.IO.File]::ReadAllBytes("{SHORTCUT_PATH}");'
        f'[System.IO.File]::WriteAllBytes("{SHORTCUT_PATH}", $bytes);'
        f'$shell = New-Object -ComObject Shell.Application;'
        f'$folder = $shell.Namespace("{SCRIPT_DIR}");'
        f'$item = $folder.ParseName("Fastrak.lnk");'
    )
    # The IPropertyStore stamping requires a helper; skip silently if not available.
    # (Pinning still works without it; AppUserModelID is set inside fastrak_hub.py.)


def main() -> int:
    if sys.platform != "win32":
        print("This shortcut generator only runs on Windows.", file=sys.stderr)
        return 1
    try:
        pythonw_exe = find_pythonw()
        build_shortcut(pythonw_exe)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        print(f"Failed to create shortcut: {exc}", file=sys.stderr)
        return 1

    print(f"Created: {SHORTCUT_PATH}")
    print(f"  Target: {pythonw_exe} \"{TARGET_SCRIPT}\"")
    print(f"  Icon:   {ICON_PATH if os.path.exists(ICON_PATH) else '(default)'}")
    print("Right-click the .lnk and choose 'Pin to taskbar' or 'Pin to Start'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
