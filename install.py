#!/usr/bin/env python
"""
Florian Dheer Pipeline - Friendly First-Run Installer
-----------------------------------------------------
A single command that takes a brand-new machine to a working Pipeline Hub.

It walks you through six small steps, asks before touching anything, and
prints a clear "all green" report at the end:

  1. Prerequisites      - Python version, pip, optional git
  2. Python packages    - pip install -r requirements.txt
  3. External tools     - FFmpeg / FLAC / rclone, with winget offers (Windows)
  4. Environment        - folders, subst drive mappings, Synology checks, config
  5. Desktop shortcut   - Fastrak.lnk you can pin to the taskbar
  6. Doctor             - verifies the end state is actually healthy

Re-run any time. Every step is idempotent.

Usage:
    python install.py                  # full guided install
    python install.py --yes            # accept every prompt (CI-friendly)
    python install.py --skip-externals # skip the FFmpeg/FLAC/rclone step
    python install.py --step deps      # run just one step
    python install.py --dry-run        # show what would happen, change nothing
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
APP_NAME = "Florian Dheer Pipeline"
STEPS = ("prereq", "deps", "externals", "env", "shortcut", "doctor")


# ============================================================
# Pretty console output - stdlib only, Windows-aware
# ============================================================

def _supports_ansi() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            return False
    return True


_USE_COLOR = _supports_ansi()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def bold(t): return _c("1", t)
def dim(t):  return _c("2", t)
def red(t):  return _c("31", t)
def grn(t):  return _c("32", t)
def ylw(t):  return _c("33", t)
def blu(t):  return _c("34", t)
def mag(t):  return _c("35", t)
def cyn(t):  return _c("36", t)


CHECK = grn("[ok]")
CROSS = red("[xx]")
WARN = ylw("[!!]")
ARROW = cyn(">>")
DOTS = dim("...")
BULLET = dim(" - ")
LINE = "=" * 64


def title_box(text: str):
    pad = 64 - 4 - len(text)
    pad_left = pad // 2
    pad_right = pad - pad_left
    print()
    print(bold(LINE))
    print(bold(f"==  {' ' * pad_left}{text}{' ' * pad_right}  =="[:64]))
    print(bold(LINE))


def step_header(num: int, total: int, text: str):
    print()
    print(bold(f"[Step {num}/{total}] ") + bold(cyn(text)))
    print(dim("-" * 64))


def status(label: str, ok: bool, detail: str = "", warn: bool = False):
    icon = (WARN if warn else CHECK) if ok else CROSS
    line = f"  {icon} {label}"
    if detail:
        line += f"  {dim(detail)}"
    print(line)


def confirm(prompt: str, auto_yes: bool, default_yes: bool = True) -> bool:
    suffix = "(Y/n)" if default_yes else "(y/N)"
    if auto_yes:
        print(f"  {prompt} {suffix} {dim('-- auto-yes')}")
        return True
    answer = input(f"  {prompt} {suffix} ").strip().lower()
    if not answer:
        return default_yes
    return answer in ("y", "yes")


# ============================================================
# Step 1: Prerequisites
# ============================================================

def step_prereq(opts) -> bool:
    step_header(1, 6, "Prerequisites")

    ok = True

    # Python version
    ver = sys.version_info
    py_ok = ver >= (3, 8)
    status(f"Python {ver.major}.{ver.minor}.{ver.micro}",
           py_ok, "3.8+ required" if not py_ok else sys.executable)
    if not py_ok:
        ok = False

    # pip
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        pip_ver = result.stdout.strip().split()[1] if result.returncode == 0 else None
        status(f"pip {pip_ver}" if pip_ver else "pip", pip_ver is not None,
               "" if pip_ver else "missing")
        if pip_ver is None:
            ok = False
    except Exception as e:
        status("pip", False, str(e))
        ok = False

    # git (optional but recommended)
    git_path = shutil.which("git")
    status("git", git_path is not None,
           "optional - used for updates" if git_path is None else git_path,
           warn=git_path is None)

    # Platform
    is_windows = sys.platform == "win32"
    status("Windows", is_windows,
           "drive mappings, shortcut, winget require Windows"
           if not is_windows else f"{sys.platform}",
           warn=not is_windows)

    return ok


# ============================================================
# Step 2: Python dependencies
# ============================================================

def step_deps(opts) -> bool:
    step_header(2, 6, "Python packages")

    req = SCRIPT_DIR / "requirements.txt"
    if not req.exists():
        status("requirements.txt", False, "not found - skipping")
        return False

    lines = [
        ln.strip() for ln in req.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    status("requirements.txt", True, f"{len(lines)} package(s)")

    # Quick already-installed check
    installed_count = sum(1 for ln in lines if _is_pkg_installed(ln))
    print(f"  {dim('Installed:')} {installed_count}/{len(lines)}")

    if installed_count == len(lines):
        print(f"  {CHECK} All Python packages already present.")
        return True

    print()
    if not confirm("Install / update from requirements.txt?", opts.yes):
        print(f"  {dim('Skipped.')}")
        return False

    if opts.dry_run:
        print(f"  {dim('[dry-run] would run: pip install -r requirements.txt')}")
        return True

    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(req)]
        )
    except subprocess.CalledProcessError as e:
        print(f"  {CROSS} pip failed: {e}")
        print(f"  {dim('Try: python -m pip install --upgrade pip, then re-run.')}")
        return False

    print(f"  {CHECK} Python packages installed.")
    return True


# pip name → top-level import name, for packages where they differ.
_PIP_TO_IMPORT = {
    "pillow": "PIL",
    "pyyaml": "yaml",
    "beautifulsoup4": "bs4",
    "python-dateutil": "dateutil",
    "opencv-python": "cv2",
}


def _is_pkg_installed(req_line: str) -> bool:
    base = req_line.split(">=")[0].split("==")[0].split("<")[0].split("[")[0].strip()
    key = base.lower()
    import_name = _PIP_TO_IMPORT.get(key, key.replace("-", "_"))
    return importlib.util.find_spec(import_name) is not None


# ============================================================
# Step 3: External tools (FFmpeg / FLAC / rclone)
# ============================================================

EXTERNAL_TOOLS = [
    {
        "name": "FFmpeg",
        "exe": "ffmpeg",
        "winget_id": "Gyan.FFmpeg",
        "url": "https://ffmpeg.org/download.html",
        "why": "audio conversion + format handling",
    },
    {
        "name": "FLAC (metaflac)",
        "exe": "metaflac",
        "winget_id": "Xiph.Flac",
        "url": "https://xiph.org/flac/download.html",
        "why": "writing iTunes playlist metadata into FLAC tags",
    },
    {
        "name": "rclone",
        "exe": "rclone",
        "winget_id": "Rclone.Rclone",
        "url": "https://rclone.org/downloads/",
        "why": "cloud sync (OneDrive / Google Drive / etc.)",
        "local_fallback": SCRIPT_DIR / "tools" / "rclone" / "rclone.exe",
    },
]


def step_externals(opts) -> bool:
    step_header(3, 6, "External tools")
    print(f"  {dim('Optional helpers used by specific pipeline scripts.')}")
    print()

    winget_available = shutil.which("winget") is not None

    missing = []
    for tool in EXTERNAL_TOOLS:
        path = shutil.which(tool["exe"])
        local = tool.get("local_fallback")
        local_ok = local and Path(local).exists()

        if path:
            detail = f"{path}  ({tool['why']})"
            status(tool["name"], True, detail)
        elif local_ok:
            detail = f"{local}  ({tool['why']}, local copy)"
            status(tool["name"], True, detail, warn=True)
        else:
            status(tool["name"], False, f"missing - {tool['why']}", warn=True)
            missing.append(tool)

    if not missing:
        print()
        print(f"  {CHECK} All external tools available.")
        return True

    print()
    if not winget_available:
        print(f"  {WARN} winget not found - cannot auto-install.")
        print(f"  {dim('Download each missing tool from its homepage:')}")
        for t in missing:
            print(f"    {BULLET}{t['name']:<18} {cyn(t['url'])}")
        return True  # not fatal

    print(f"  {ARROW} winget can install these for you:")
    for t in missing:
        print(f"    {BULLET}{t['name']:<18} {dim('winget install --id ' + t['winget_id'])}")

    print()
    if not confirm(f"Install {len(missing)} missing tool(s) via winget?", opts.yes, default_yes=True):
        print(f"  {dim('Skipped. Install manually later if you need those scripts.')}")
        return True

    if opts.dry_run:
        print(f"  {dim('[dry-run] would install via winget')}")
        return True

    failed = []
    for t in missing:
        print()
        print(f"  {ARROW} Installing {bold(t['name'])} {DOTS}")
        try:
            subprocess.run(
                ["winget", "install", "--id", t["winget_id"],
                 "--accept-source-agreements", "--accept-package-agreements",
                 "--silent"],
                check=True,
            )
            print(f"     {CHECK} {t['name']}")
        except subprocess.CalledProcessError:
            print(f"     {CROSS} {t['name']} - install via {cyn(t['url'])}")
            failed.append(t)

    if failed:
        print()
        print(f"  {WARN} {len(failed)} tool(s) failed to install. Pipeline still usable;")
        print(f"  {dim('scripts that need them will tell you what is missing.')}")

    return True  # never block the install on optionals


# ============================================================
# Step 4: Environment setup (folders, drives, config)
# ============================================================

def step_env(opts) -> bool:
    step_header(4, 6, "Environment setup")

    cfg_path = SCRIPT_DIR / "setup_config.json"
    example = SCRIPT_DIR / "setup_config.json.example"

    if not cfg_path.exists():
        status("setup_config.json", False, "not found", warn=True)
        if not example.exists():
            print(f"  {CROSS} setup_config.json.example missing too - cannot proceed.")
            return False

        print()
        print(f"  {dim('Every PC needs its own setup_config.json (drive letters, paths, etc).')}")
        if not confirm("Copy the example template now?", opts.yes, default_yes=True):
            print(f"  {dim('Skipped. Create setup_config.json by hand and re-run.')}")
            return False

        if opts.dry_run:
            print(f"  {dim('[dry-run] would copy ' + example.name + ' to ' + cfg_path.name)}")
        else:
            shutil.copyfile(example, cfg_path)
            print(f"  {CHECK} Copied {example.name} -> {cfg_path.name}")

        print()
        print(f"  {ARROW} Open {bold(cfg_path.name)} and adjust:")
        print(f"     {BULLET}drive_mappings (I:, P:, ...)")
        print(f"     {BULLET}folder_structure.bases  (where your Active / Archive folders live)")
        print(f"     {BULLET}pipeline_config (active_base, archive_base, ...)")
        print()
        if sys.platform == "win32" and not opts.dry_run:
            if confirm("Open setup_config.json in your default editor now?", opts.yes, default_yes=True):
                try:
                    os.startfile(str(cfg_path))  # type: ignore[attr-defined]
                except Exception as e:
                    print(f"  {dim('(could not auto-open: ' + str(e) + ')')}")
        print()
        print(f"  {WARN} After editing, re-run {bold('python install.py')} to apply.")
        return False  # block doctor until config edited

    status("setup_config.json", True, str(cfg_path))

    # Delegate to setup_environment.main()
    print()
    if not confirm("Run environment setup (folders, drives, Synology checks, config)?",
                   opts.yes, default_yes=True):
        print(f"  {dim('Skipped.')}")
        return True

    # Build argv for setup_environment
    env_argv = ["setup_environment.py", "--config", str(cfg_path)]
    if opts.yes:
        env_argv.append("--yes")
    if opts.dry_run:
        env_argv.append("--dry-run")

    saved_argv = sys.argv
    try:
        sys.argv = env_argv
        # Make modules/ importable the same way setup_environment does
        modules_dir = str(SCRIPT_DIR / "modules")
        if modules_dir not in sys.path:
            sys.path.insert(0, modules_dir)
        # Import lazily so install.py works even if setup_environment has issues
        import setup_environment  # noqa: WPS433
        setup_environment.main()
    except SystemExit as e:
        if e.code not in (0, None):
            return False
    except Exception as e:
        print(f"  {CROSS} setup_environment failed: {e}")
        return False
    finally:
        sys.argv = saved_argv

    # Seed per-user invoice_manager config so the hub doesn't crash on first launch.
    _seed_invoice_manager_config(opts)

    return True


def _seed_invoice_manager_config(opts) -> None:
    """Copy invoice_manager's config.json.example into the per-user AppData dir.

    The hub raises ConfigError on startup if this file is missing; we copy
    the template so first launch works, and the user edits company details
    after the fact.
    """
    example = (
        SCRIPT_DIR
        / "modules" / "invoice_manager" / "core" / "config.json.example"
    )
    if not example.exists():
        return  # nothing to seed

    if sys.platform == "win32":
        data_dir = Path.home() / "AppData" / "Local" / "PipelineManager" / "global_invoice"
    else:
        data_dir = Path.home() / ".local" / "share" / "PipelineManager" / "global_invoice"
    target = data_dir / "config.json"

    print()
    if target.exists():
        status("invoice_manager config.json", True, str(target))
        return

    if opts.dry_run:
        print(f"  {dim('[dry-run] would copy ' + str(example) + ' to ' + str(target))}")
        return

    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(example, target)
    except OSError as e:
        status("invoice_manager config.json", False, f"could not seed: {e}", warn=True)
        return

    status("invoice_manager config.json", True, f"seeded from template -> {target}")
    print(f"  {ARROW} Edit {bold(str(target))} to set your")
    print(f"     {BULLET}legal name, VAT, address, IBAN/BIC")
    print(f"     {BULLET}per-company invoice template + output_prefix")


# ============================================================
# Step 5: Desktop shortcut
# ============================================================

def step_shortcut(opts) -> bool:
    step_header(5, 6, "Desktop shortcut")

    if sys.platform != "win32":
        status("shortcut", True, "skipped - Windows only", warn=True)
        return True

    target = SCRIPT_DIR / "Fastrak.lnk"
    if target.exists():
        status("Fastrak.lnk", True, str(target))
        if not confirm("Re-generate the shortcut anyway?", opts.yes, default_yes=False):
            return True

    if opts.dry_run:
        print(f"  {dim('[dry-run] would run make_shortcut.py')}")
        return True

    if not confirm("Create Fastrak.lnk next to fastrak_hub.py?", opts.yes, default_yes=True):
        print(f"  {dim('Skipped.')}")
        return True

    try:
        subprocess.check_call([sys.executable, str(SCRIPT_DIR / "make_shortcut.py")])
    except subprocess.CalledProcessError as e:
        print(f"  {CROSS} Shortcut creation failed: {e}")
        return False

    print()
    print(f"  {ARROW} Right-click {bold('Fastrak.lnk')} -> {cyn('Pin to taskbar')} (or Start menu)")
    return True


# ============================================================
# Step 6: Doctor - end-to-end health check
# ============================================================

def step_doctor(opts) -> bool:
    step_header(6, 6, "Doctor - is everything healthy?")

    all_ok = True

    # Python deps actually importable?
    req = SCRIPT_DIR / "requirements.txt"
    if req.exists():
        lines = [
            ln.strip() for ln in req.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        missing_py = [ln for ln in lines if not _is_pkg_installed(ln)]
        status("Python deps", not missing_py,
               "all importable" if not missing_py
               else f"{len(missing_py)} missing: {', '.join(m.split('>=')[0] for m in missing_py[:3])}")
        if missing_py:
            all_ok = False

    # fastrak_hub.py imports cleanly?
    hub = SCRIPT_DIR / "fastrak_hub.py"
    status("fastrak_hub.py present", hub.exists(), str(hub))
    if not hub.exists():
        all_ok = False

    # rak_config.json valid paths?
    try:
        modules_dir = str(SCRIPT_DIR / "modules")
        if modules_dir not in sys.path:
            sys.path.insert(0, modules_dir)
        from rak_settings import RakSettings  # type: ignore[import-not-found]
        settings = RakSettings()
        results = settings.validate_all()
        bad = [(k, msg) for k, (ok, msg) in results.items() if not ok]
        status("rak_config paths", not bad,
               "all valid" if not bad else f"{len(bad)} invalid")
        for k, msg in bad:
            print(f"     {BULLET}{k}: {dim(msg)}")
    except Exception as e:
        status("rak_config paths", False, f"could not check: {e}", warn=True)

    # Shortcut?
    if sys.platform == "win32":
        lnk = SCRIPT_DIR / "Fastrak.lnk"
        status("Fastrak.lnk", lnk.exists(),
               str(lnk) if lnk.exists() else "not created (optional)",
               warn=not lnk.exists())

    # External tools - informational only
    found_externals = [t["name"] for t in EXTERNAL_TOOLS
                       if shutil.which(t["exe"]) or
                       (t.get("local_fallback") and Path(t["local_fallback"]).exists())]
    status("external tools",
           len(found_externals) == len(EXTERNAL_TOOLS),
           f"{len(found_externals)}/{len(EXTERNAL_TOOLS)} present",
           warn=len(found_externals) < len(EXTERNAL_TOOLS))

    # invoice_manager config (per-user AppData)
    if sys.platform == "win32":
        inv_cfg = Path.home() / "AppData" / "Local" / "PipelineManager" / "global_invoice" / "config.json"
    else:
        inv_cfg = Path.home() / ".local" / "share" / "PipelineManager" / "global_invoice" / "config.json"
    status("invoice_manager config", inv_cfg.exists(),
           str(inv_cfg) if inv_cfg.exists()
           else "missing - hub will disable Business tab",
           warn=not inv_cfg.exists())

    return all_ok


# ============================================================
# Welcome + final report
# ============================================================

def welcome():
    title_box(f"Welcome to {APP_NAME}")
    print()
    print(f"  This installer takes you from a fresh machine to a working")
    print(f"  {bold('Pipeline Hub')} in six small steps:")
    print()
    print(f"    {cyn('1.')} Prerequisites      {dim('Python, pip, git')}")
    print(f"    {cyn('2.')} Python packages    {dim('pillow, pdfplumber, invoice2data, ...')}")
    print(f"    {cyn('3.')} External tools     {dim('FFmpeg, FLAC, rclone (winget)')}")
    print(f"    {cyn('4.')} Environment        {dim('folders, drive mappings, config')}")
    print(f"    {cyn('5.')} Desktop shortcut   {dim('Fastrak.lnk to pin')}")
    print(f"    {cyn('6.')} Doctor             {dim('verify everything works')}")
    print()
    print(f"  {dim('Every step asks before touching anything. Safe to re-run.')}")
    print()


def final_report(results: dict, opts):
    title_box("All done")
    print()
    for name, ok in results.items():
        status(name, ok)

    any_failed = not all(results.values())
    print()
    if any_failed:
        print(f"  {WARN} Some steps had issues - see notes above.")
        print(f"  {dim('Re-run install.py after fixing, or run a single step with --step.')}")
    else:
        print(f"  {grn(bold('Everything is green. Have fun!'))}")

    print()
    print(bold("  How to launch:"))
    if sys.platform == "win32":
        lnk = SCRIPT_DIR / "Fastrak.lnk"
        if lnk.exists():
            print(f"    {ARROW} Double-click {bold('Fastrak.lnk')}  {dim('(or pin to taskbar)')}")
    print(f"    {ARROW} {bold('python fastrak_hub.py')}")
    print()
    print(bold("  Useful next steps:"))
    print(f"    {BULLET}Press {cyn('F1')} in the app to see keyboard shortcuts")
    print(f"    {BULLET}Open {cyn('Settings (Ctrl+,)')} to tweak paths anytime")
    print(f"    {BULLET}Re-run {cyn('python install.py')} on a new PC - it just works")
    print()


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} - friendly first-run installer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Accept every prompt (CI / unattended)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would happen without changing anything")
    parser.add_argument("--step", choices=STEPS + ("all",), default="all",
                        help="Run only one step (default: all)")
    parser.add_argument("--skip-externals", action="store_true",
                        help="Skip the FFmpeg / FLAC / rclone step")
    parser.add_argument("--skip-shortcut", action="store_true",
                        help="Skip Windows shortcut creation")
    opts = parser.parse_args()

    welcome()

    if opts.step == "all" and not opts.yes:
        try:
            input("  Press Enter to begin, or Ctrl+C to quit. ")
        except KeyboardInterrupt:
            print()
            print(dim("  Cancelled."))
            return

    results: dict[str, bool] = {}
    run = opts.step
    run_all = run == "all"

    # The pipeline of steps. Each entry: (key, label, fn, skip-flag-attr-or-none)
    pipeline: list[tuple[str, str, Callable[[object], bool], str | None]] = [
        ("prereq",    "Prerequisites",    step_prereq,    None),
        ("deps",      "Python packages",  step_deps,      None),
        ("externals", "External tools",   step_externals, "skip_externals"),
        ("env",       "Environment",      step_env,       None),
        ("shortcut",  "Desktop shortcut", step_shortcut,  "skip_shortcut"),
        ("doctor",    "Doctor",           step_doctor,    None),
    ]

    for key, label, fn, skip_attr in pipeline:
        if not (run_all or run == key):
            continue
        if skip_attr and getattr(opts, skip_attr, False):
            print()
            print(f"  {dim(f'[skipping {label}]')}")
            results[label] = True
            continue
        ok = fn(opts)
        results[label] = ok
        # If prerequisites or deps fail completely, halt - downstream will only confuse.
        if key in ("prereq", "deps") and not ok and run_all:
            print()
            print(f"  {CROSS} {label} failed. Fix the issue above and re-run.")
            results["(remaining steps)"] = False
            break

    if run_all:
        final_report(results, opts)
    else:
        print()
        print(dim(f"  Step '{run}' done."))

    if os.name == "nt" and not sys.stdin.isatty():
        input("\n  Press Enter to close this window...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print(red("  Installation cancelled."))
        sys.exit(1)
    except Exception as e:
        print()
        print(red(f"  Unexpected error: {e}"))
        import traceback
        traceback.print_exc()
        if os.name == "nt" and not sys.stdin.isatty():
            input("\n  Press Enter to close...")
        sys.exit(1)
