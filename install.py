#!/usr/bin/env python
"""
Florian Dheer Pipeline - Friendly First-Run Installer
-----------------------------------------------------
A single command that takes a brand-new machine to a working Pipeline Hub.

It walks you through seven small steps, asks before touching anything, and
prints a clear "all green" report at the end:

  1. Prerequisites      - Python version, pip, optional git
  2. Python packages    - pip install -r requirements.txt
  3. External tools     - FFmpeg / FLAC / rclone, with winget offers (Windows)
  4. Environment        - folders, subst drive mappings, Synology checks, config
  5. Workstation apps   - KeePassXC, Synology Drive, Visual Subst (winget)
  6. Desktop shortcut   - Fastrak.lnk you can pin to the taskbar
  7. Doctor             - verifies the end state is actually healthy

Re-run any time. Every step is idempotent.

Usage:
    python install.py                  # full guided install
    python install.py --yes            # accept every prompt (alias: --unattended)
    python install.py --skip-externals # skip the FFmpeg/FLAC/rclone step
    python install.py --skip-apps      # skip the workstation apps step
    python install.py --step deps      # run just one step
    python install.py --dry-run        # show what would happen, change nothing

At the start prompt you can also press A to enable unattended mode
without re-launching with --yes.
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
STEPS = ("prereq", "deps", "externals", "env", "apps", "shortcut", "doctor")
TOTAL_STEPS = 7


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
    step_header(1, TOTAL_STEPS, "Prerequisites")

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
    step_header(2, TOTAL_STEPS, "Python packages")

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
    step_header(3, TOTAL_STEPS, "External tools")
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
    step_header(4, TOTAL_STEPS, "Environment setup")

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
# Step 5: Workstation apps
# ============================================================
#
# Delegates app catalog / install / skip-list logic to
# modules/workstation_apps.py — same code path the Settings dialog
# uses, so the CLI and GUI can't drift apart.


def _import_workstation_apps():
    """Lazy import so install.py works even if modules/ has issues."""
    modules_dir = str(SCRIPT_DIR / "modules")
    if modules_dir not in sys.path:
        sys.path.insert(0, modules_dir)
    import workstation_apps  # noqa: WPS433
    return workstation_apps


def step_apps(opts) -> bool:
    step_header(5, TOTAL_STEPS, "Workstation apps")
    print(f"  {dim('Apps you may want on this PC. Pipeline runs without them - never fatal.')}")
    print()

    try:
        wa = _import_workstation_apps()
    except Exception as e:
        print(f"  {CROSS} Could not load workstation_apps module: {e}")
        return False

    all_apps = wa.load_apps()
    if not all_apps:
        # Two distinct cases:
        #   (a) setup_config.json exists but predates this feature →
        #       offer to overwrite with the bundled .example so the
        #       catalog appears.
        #   (b) no setup_config.json at all → step_env handled that.
        if wa.user_config_lacks_apps() and not opts.dry_run:
            if _offer_config_overwrite(opts):
                all_apps = wa.load_apps()  # re-read after overwrite
        if not all_apps:
            print(f"  {dim('No workstation_apps configured in setup_config.json. Skipping.')}")
            return True

    skip_set = wa.load_skip_list()
    _print_apps_status(wa, all_apps, skip_set)

    missing = [a for a in all_apps
               if a.name not in skip_set and not wa.is_installed(a)]
    if not missing:
        print()
        print(f"  {CHECK} All workstation apps present (or skipped on this machine).")
        return True

    # Unattended: install everything missing via winget, list manual URLs.
    if opts.yes:
        return _install_set(wa, missing, opts, label="all missing")

    # Interactive: ask the user how they want to pick.
    target = _pick_apps(wa, all_apps, missing, opts)
    if target is None:
        print(f"  {dim('Skipped. Re-run with: python install.py --step apps')}")
        return True
    if not target:
        print(f"  {dim('Nothing selected.')}")
        return True

    return _install_set(wa, target, opts, label=f"{len(target)} app(s)")


def _print_apps_status(wa, apps, skip_set):
    """Per-category status table; mirrors the format the Settings dialog
    will eventually show."""
    counts = wa.status_counts(apps, skip_set)
    print(f"  {dim(f'{counts.installed}/{counts.total} installed, '
                   f'{counts.missing} missing, {counts.skipped} skipped')}")
    grouped = wa.apps_by_category(apps)
    for cat, cat_apps in grouped.items():
        print()
        print(f"  {bold(cat)}")
        for a in cat_apps:
            if a.name in skip_set:
                status(a.name, True,
                       f"skipped on this machine - {a.why}", warn=True)
            elif wa.is_installed(a):
                detail = a.why or ""
                status(a.name, True, detail)
            else:
                method = "winget" if a.install_method == "winget" else "manual"
                status(a.name, False, f"missing ({method}) - {a.why}", warn=True)


def _pick_apps(wa, all_apps, missing, opts):
    """Return the list of App objects the user wants to install, or None
    to skip the step entirely. Empty list = nothing selected."""
    print()
    print(f"  {ARROW} How do you want to install the missing apps?")
    print(f"    {bold('[E]')} Everything missing                  ({len(missing)} app(s))")
    print(f"    {bold('[C]')} By category")
    print(f"    {bold('[I]')} Individual pick")
    print(f"    {bold('[P]')} Profile (VJ rig / Audio rig / ...)")
    print(f"    {bold('[S]')} Skip this step")
    print()
    choice = input("  > ").strip().lower()

    if choice in ("", "s", "skip", "q"):
        return None
    if choice in ("e", "all", "everything"):
        return missing
    if choice in ("c", "category", "categories"):
        return _pick_by_category(wa, missing)
    if choice in ("i", "individual", "pick"):
        return _pick_individual(missing)
    if choice in ("p", "profile"):
        return _pick_by_profile(wa, all_apps, missing)

    print(f"  {WARN} Unknown choice {choice!r}, skipping.")
    return None


def _pick_by_category(wa, missing):
    by_cat = wa.apps_by_category(missing)
    cats = list(by_cat.keys())
    if not cats:
        print(f"  {dim('No missing apps grouped by category.')}")
        return []
    print()
    print(f"  {ARROW} Categories with missing apps:")
    for idx, c in enumerate(cats, 1):
        print(f"    {cyn(str(idx))}. {c:<14} {dim(f'({len(by_cat[c])} missing)')}")
    print(f"    {dim('Enter comma-separated numbers (e.g. 1,3) or A for all:')}")
    raw = input("  > ").strip().lower()
    if not raw:
        return []
    if raw in ("a", "all"):
        picks = cats
    else:
        picks = []
        for tok in raw.split(","):
            tok = tok.strip()
            if not tok.isdigit():
                continue
            i = int(tok) - 1
            if 0 <= i < len(cats):
                picks.append(cats[i])
    out = []
    for c in picks:
        out.extend(by_cat.get(c, []))
    return out


def _pick_individual(missing):
    print()
    print(f"  {ARROW} Missing apps:")
    for idx, a in enumerate(missing, 1):
        method = "winget" if a.install_method == "winget" else "manual"
        print(f"    {cyn(str(idx))}. {a.name:<22} {dim(f'[{a.category}/{method}] {a.why}')}")
    print(f"    {dim('Enter comma-separated numbers (e.g. 1,3,5) or A for all:')}")
    raw = input("  > ").strip().lower()
    if not raw:
        return []
    if raw in ("a", "all"):
        return missing
    out = []
    for tok in raw.split(","):
        tok = tok.strip()
        if not tok.isdigit():
            continue
        i = int(tok) - 1
        if 0 <= i < len(missing):
            out.append(missing[i])
    return out


def _pick_by_profile(wa, all_apps, missing):
    profiles = wa.load_profiles()
    if not profiles:
        print(f"  {dim('No workstation_profiles configured. Falling back to all-missing.')}")
        return missing
    print()
    print(f"  {ARROW} Profiles:")
    for idx, p in enumerate(profiles, 1):
        print(f"    {cyn(str(idx))}. {p.name:<14} {dim(p.description)}")
    print(f"    {dim('Pick one number:')}")
    raw = input("  > ").strip()
    if not raw.isdigit():
        return []
    i = int(raw) - 1
    if not (0 <= i < len(profiles)):
        return []
    profile_apps = wa.expand_profile(profiles[i], all_apps)
    # Only install the ones from the profile that are actually missing
    missing_names = {a.name for a in missing}
    return [a for a in profile_apps if a.name in missing_names]


def _install_set(wa, target, opts, label: str) -> bool:
    """Run installs for one set of apps. Winget apps via winget, manual
    apps via 'open download URL' (CLI prints the URL and offers to open)."""
    winget_targets = [a for a in target if a.install_method == "winget"]
    manual_targets = [a for a in target if a.install_method != "winget"]

    # Winget block
    if winget_targets:
        if not wa.winget_available():
            print()
            print(f"  {WARN} winget not found - cannot auto-install these:")
            for a in winget_targets:
                print(f"    {BULLET}{a.name:<22} {cyn(a.url)}")
        else:
            print()
            print(f"  {ARROW} winget will install ({label}):")
            for a in winget_targets:
                print(f"    {BULLET}{a.name:<22} {dim('winget install --id ' + (a.winget_id or ''))}")
            print()
            if confirm(f"Install {len(winget_targets)} app(s) via winget?",
                       opts.yes, default_yes=True):
                for a in winget_targets:
                    print()
                    print(f"  {ARROW} Installing {bold(a.name)} {DOTS}")
                    result = wa.install_app(a, dry_run=opts.dry_run)
                    if result.success:
                        print(f"     {CHECK} {a.name}  {dim(result.detail)}")
                    else:
                        print(f"     {CROSS} {a.name} - {dim(result.detail)}")
                        if a.url:
                            print(f"     {dim('Fallback: ' + a.url)}")
                        _offer_skip(wa, a, opts)

    # Manual block — just URLs, optionally opened in browser.
    # Unattended mode (--yes) deliberately NEVER auto-opens browser tabs —
    # opening a dozen pages without the user watching is the opposite of
    # what "unattended" means.
    if manual_targets:
        print()
        print(f"  {ARROW} Manual installs (license-gated or no winget):")
        for a in manual_targets:
            print(f"    {BULLET}{a.name:<22} {cyn(a.url)}")
        if not opts.yes:
            print()
            if confirm("Open these download pages in your browser now?",
                       auto_yes=False, default_yes=False):
                for a in manual_targets:
                    if opts.dry_run:
                        print(f"  {dim('[dry-run] would open ' + a.url)}")
                    else:
                        wa.open_download_page(a)
            for a in manual_targets:
                _offer_skip(wa, a, opts)

    return True  # never block downstream


def _offer_config_overwrite(opts) -> bool:
    """When the user's setup_config.json predates the workstation_apps
    feature, offer to overwrite it with the bundled .example.

    Destructive: replaces the entire file including drive_mappings and
    pipeline_config. We back the old file up to setup_config.json.bak
    first and default the prompt to NO.
    """
    cfg_path = SCRIPT_DIR / "setup_config.json"
    example_path = SCRIPT_DIR / "setup_config.json.example"
    if not example_path.exists():
        print(f"  {CROSS} setup_config.json.example is missing - cannot overwrite.")
        return False

    print()
    print(f"  {WARN} Your setup_config.json is missing the {bold('workstation_apps')} section.")
    print(f"  {dim('It was probably created before this feature existed.')}")
    print()
    print(f"  {ARROW} Overwriting will {bold('replace the entire file')} with the bundled example,")
    print(f"     including {bold('drive_mappings')} and {bold('pipeline_config')}.")
    print(f"     A backup is written to {cyn('setup_config.json.bak')} first.")
    print(f"     You'll need to re-check the drive letters / paths afterwards.")
    print()
    if not confirm("Overwrite setup_config.json with the example now?",
                   auto_yes=False, default_yes=False):
        print(f"  {dim('Skipped. Add the workstation_apps section to setup_config.json by hand,')}")
        print(f"  {dim('or copy from setup_config.json.example.')}")
        return False

    try:
        backup_path = cfg_path.with_suffix(".json.bak")
        shutil.copyfile(cfg_path, backup_path)
        shutil.copyfile(example_path, cfg_path)
    except OSError as e:
        print(f"  {CROSS} Overwrite failed: {e}")
        return False
    print(f"  {CHECK} Backed up old config -> {backup_path.name}")
    print(f"  {CHECK} Wrote bundled example -> {cfg_path.name}")
    print(f"  {WARN} Open {bold(cfg_path.name)} and confirm the drive letters / paths match this PC.")
    return True


def _offer_skip(wa, app, opts):
    """After a failed/declined install, offer to remember the skip."""
    if opts.yes or opts.dry_run:
        return
    if wa.is_skipped(app):
        return
    if confirm(f"  Don't ask about {bold(app.name)} again on this machine?",
               auto_yes=False, default_yes=False):
        wa.mark_skipped(app.name)
        print(f"     {dim('Marked as skipped in setup_apps_state.json')}")


# ============================================================
# Step 6: Desktop shortcut
# ============================================================

def step_shortcut(opts) -> bool:
    step_header(6, TOTAL_STEPS, "Desktop shortcut")

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
    step_header(7, TOTAL_STEPS, "Doctor - is everything healthy?")

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

    # Workstation apps - informational only, never blocks green.
    # Skipped apps (per-machine) count as "intentionally absent" so the
    # doctor stays useful instead of nagging forever.
    try:
        wa = _import_workstation_apps()
        apps_list = wa.load_apps()
        skip_set = wa.load_skip_list()
        counts = wa.status_counts(apps_list, skip_set)
        missing_unskipped = [
            a.name for a in apps_list
            if a.name not in skip_set and not wa.is_installed(a)
        ]
        detail = f"{counts.installed}/{counts.total} installed"
        if counts.skipped:
            detail += f", {counts.skipped} skipped"
        if missing_unskipped:
            detail += f"  (missing: {', '.join(missing_unskipped[:4])}"
            if len(missing_unskipped) > 4:
                detail += f", +{len(missing_unskipped) - 4} more"
            detail += ")"
        status("workstation apps", not missing_unskipped,
               detail, warn=bool(missing_unskipped))
    except Exception as e:
        status("workstation apps", False,
               f"could not check: {e}", warn=True)

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
    print(f"  {bold('Pipeline Hub')} in seven small steps:")
    print()
    print(f"    {cyn('1.')} Prerequisites      {dim('Python, pip, git')}")
    print(f"    {cyn('2.')} Python packages    {dim('pillow, pdfplumber, invoice2data, ...')}")
    print(f"    {cyn('3.')} External tools     {dim('FFmpeg, FLAC, rclone (winget)')}")
    print(f"    {cyn('4.')} Environment        {dim('folders, drive mappings, config')}")
    print(f"    {cyn('5.')} Workstation apps   {dim('KeePassXC, Synology Drive, Visual Subst')}")
    print(f"    {cyn('6.')} Desktop shortcut   {dim('Fastrak.lnk to pin')}")
    print(f"    {cyn('7.')} Doctor             {dim('verify everything works')}")
    print()
    print(f"  {dim('Every step asks before touching anything. Safe to re-run.')}")
    print(f"  {dim('Tip: pass --yes / --unattended (or press A at the start prompt)')}")
    print(f"  {dim('     to accept every prompt automatically.')}")
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

    # Manual downloads still pending — surface URLs the user needs to
    # click. Recomputed from live state so apps installed mid-run drop
    # off the list automatically. Skipped apps are intentionally absent
    # on this machine and don't get nagged about.
    try:
        wa = _import_workstation_apps()
        skip_set = wa.load_skip_list()
        still_manual = [
            a for a in wa.load_apps()
            if a.install_method != "winget"
            and a.name not in skip_set
            and not wa.is_installed(a)
            and a.url
        ]
    except Exception:
        still_manual = []
    if still_manual:
        print()
        print(bold("  Still to install manually:"))
        for app in still_manual:
            print(f"    {BULLET}{app.name:<22} {cyn(app.url)}")

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
# Interactive start choice
# ============================================================

def _prompt_start_choice() -> str:
    """Ask the user how to run the installer at startup.

    Returns one of: 'step' (default, prompt each step), 'all'
    (unattended, accept everything), 'cancel'. On Windows we use
    msvcrt.getch() for a real single-keystroke prompt; everywhere else
    we fall back to input() which still works but needs Enter.
    """
    prompt = (
        "  Press "
        + bold("Enter") + " to step through, "
        + bold("A") + " to run all unattended, "
        + bold("Q") + " to quit: "
    )
    print(prompt, end="", flush=True)

    if sys.platform == "win32":
        try:
            import msvcrt  # local — Windows-only stdlib
            while True:
                ch = msvcrt.getch()
                if ch in (b"\r", b"\n"):
                    print()
                    return "step"
                if ch in (b"a", b"A"):
                    print("A")
                    return "all"
                if ch in (b"q", b"Q", b"\x03"):  # q or Ctrl+C
                    print("Q")
                    return "cancel"
                # ignore other keys, keep waiting
        except (KeyboardInterrupt, OSError):
            print()
            return "cancel"

    # Non-Windows fallback: line-based input.
    try:
        answer = input("").strip().lower()
    except KeyboardInterrupt:
        print()
        return "cancel"
    if answer in ("a", "all", "unattended"):
        return "all"
    if answer in ("q", "quit", "cancel"):
        return "cancel"
    return "step"


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} - friendly first-run installer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--yes", "-y", "--unattended", dest="yes",
                        action="store_true",
                        help="Accept every prompt (CI / unattended)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would happen without changing anything")
    parser.add_argument("--step", choices=STEPS + ("all",), default="all",
                        help="Run only one step (default: all)")
    parser.add_argument("--skip-externals", action="store_true",
                        help="Skip the FFmpeg / FLAC / rclone step")
    parser.add_argument("--skip-apps", action="store_true",
                        help="Skip the KeePassXC / Synology Drive / Visual Subst step")
    parser.add_argument("--skip-shortcut", action="store_true",
                        help="Skip Windows shortcut creation")
    opts = parser.parse_args()

    welcome()

    if opts.step == "all" and not opts.yes:
        choice = _prompt_start_choice()
        if choice == "cancel":
            print()
            print(dim("  Cancelled."))
            return
        if choice == "all":
            opts.yes = True
            print(f"  {dim('Unattended mode enabled - skipping per-step prompts.')}")
            print()

    results: dict[str, bool] = {}
    run = opts.step
    run_all = run == "all"

    # The pipeline of steps. Each entry: (key, label, fn, skip-flag-attr-or-none)
    pipeline: list[tuple[str, str, Callable[[object], bool], str | None]] = [
        ("prereq",    "Prerequisites",    step_prereq,    None),
        ("deps",      "Python packages",  step_deps,      None),
        ("externals", "External tools",   step_externals, "skip_externals"),
        ("env",       "Environment",      step_env,       None),
        ("apps",      "Workstation apps", step_apps,      "skip_apps"),
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
