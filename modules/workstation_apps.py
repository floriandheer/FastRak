"""
Workstation apps — shared catalog, install, skip-list logic.

Both ``install.py``'s Step 5 (CLI install flow) and the Settings dialog's
"Workstation Apps" tab call into this module so the two surfaces can't
drift apart.

Reads:
  - setup_config.json   ``workstation_apps`` + ``workstation_profiles``
  - setup_apps_state.json   per-machine skip-list (gitignored)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ============================================================
# Paths
# ============================================================

_SCRIPT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = _SCRIPT_DIR / "setup_config.json"
EXAMPLE_PATH = _SCRIPT_DIR / "setup_config.json.example"
STATE_PATH = _SCRIPT_DIR / "setup_apps_state.json"

DEFAULT_CATEGORY = "General"
WINGET = "winget"
MANUAL = "manual"


# ============================================================
# Data
# ============================================================

@dataclass
class App:
    name: str
    # One or more categories the app belongs to. JSON accepts either
    # a string ("Audio") or a list (["Audio", "Media"]); load_apps
    # normalises both to a list. An app listed in N categories appears
    # under each in the picker / status table but is only ever installed
    # once (callers dedupe by name).
    categories: list[str] = field(default_factory=lambda: [DEFAULT_CATEGORY])
    install_method: str = MANUAL  # "winget" | "manual"
    winget_id: Optional[str] = None
    exe: str = ""
    why: str = ""
    url: str = ""
    # Optional list of absolute paths (env vars OK) where the executable
    # might live. Used when the app does not put itself on PATH — which
    # is most Windows GUI apps. Examples:
    #   "%ProgramFiles%\\Synology\\SynologyDrive\\SynologyDrive.exe"
    detect_paths: list[str] = field(default_factory=list)
    # Optional override for registry detection. Defaults to App.name —
    # set this when the installer's DisplayName doesn't contain the
    # catalog name (e.g. an "Affinity Suite" catalog entry whose
    # installer DisplayName is "Affinity Photo 2" would set
    # detect_name="Affinity Photo").
    detect_name: Optional[str] = None

    @property
    def category(self) -> str:
        """Primary category — back-compat shim for callers that only
        care about the first/owning category (status display, default
        sort order). Iterate ``categories`` for the full list."""
        return self.categories[0] if self.categories else DEFAULT_CATEGORY


@dataclass
class Profile:
    name: str
    description: str = ""
    categories: list[str] = field(default_factory=list)
    # extra_apps lets a profile pull in one or two apps that live in
    # other categories (e.g. VJ rig wants Traktor even though Traktor is
    # an Audio app). Match is by App.name (case-insensitive).
    extra_apps: list[str] = field(default_factory=list)


@dataclass
class InstallResult:
    app: App
    success: bool
    detail: str = ""


# ============================================================
# Config loading
# ============================================================

def _load_config_dict() -> dict:
    """Read setup_config.json, falling back to the .example only if the
    user hasn't created their own yet.

    If setup_config.json exists but is missing the workstation_apps
    section, that returns an empty catalog — the caller is expected to
    notice and prompt the user (see install.py's step_apps, which
    offers to overwrite with the bundled .example)."""
    path = CONFIG_PATH if CONFIG_PATH.exists() else EXAMPLE_PATH
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def user_config_lacks_apps() -> bool:
    """True iff setup_config.json exists but has no usable
    workstation_apps section. Used by the installer to decide whether to
    propose an overwrite."""
    if not CONFIG_PATH.exists():
        return False
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False
    raw = cfg.get("workstation_apps")
    return not (isinstance(raw, list) and raw)


def load_apps(config: Optional[dict] = None) -> list[App]:
    cfg = config if config is not None else _load_config_dict()
    raw = cfg.get("workstation_apps", [])
    if not isinstance(raw, list):
        return []
    out: list[App] = []
    for entry in raw:
        if not isinstance(entry, dict) or "name" not in entry:
            continue
        out.append(App(
            name=entry["name"],
            categories=_parse_categories(entry.get("category")),
            install_method=entry.get("install_method", MANUAL),
            winget_id=entry.get("winget_id"),
            exe=entry.get("exe", ""),
            why=entry.get("why", ""),
            url=entry.get("url", ""),
            detect_paths=list(entry.get("detect_paths", [])),
            detect_name=entry.get("detect_name"),
        ))
    return out


def _parse_categories(raw) -> list[str]:
    """Accept ``"Audio"``, ``["Audio", "Media"]``, or missing/empty.
    Always returns a non-empty list so downstream code can assume
    ``categories[0]`` exists."""
    if isinstance(raw, list):
        cats = [str(c).strip() for c in raw if isinstance(c, str) and c.strip()]
        return cats or [DEFAULT_CATEGORY]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return [DEFAULT_CATEGORY]


def load_profiles(config: Optional[dict] = None) -> list[Profile]:
    cfg = config if config is not None else _load_config_dict()
    raw = cfg.get("workstation_profiles", [])
    if not isinstance(raw, list):
        return []
    out: list[Profile] = []
    for entry in raw:
        if not isinstance(entry, dict) or "name" not in entry:
            continue
        out.append(Profile(
            name=entry["name"],
            description=entry.get("description", ""),
            categories=list(entry.get("categories", [])),
            extra_apps=list(entry.get("extra_apps", [])),
        ))
    return out


def apps_by_category(apps: Optional[list[App]] = None) -> dict[str, list[App]]:
    """Group apps by category, preserving insertion order of categories
    so the UI doesn't re-shuffle on every load.

    Multi-category apps appear under each of their categories — callers
    that flatten back into an install list must dedupe by ``App.name``.
    """
    if apps is None:
        apps = load_apps()
    out: dict[str, list[App]] = {}
    for a in apps:
        for cat in a.categories:
            out.setdefault(cat, []).append(a)
    return out


def categories_present(apps: Optional[list[App]] = None) -> list[str]:
    if apps is None:
        apps = load_apps()
    seen: list[str] = []
    for a in apps:
        for cat in a.categories:
            if cat not in seen:
                seen.append(cat)
    return seen


def expand_profile(profile: Profile,
                   apps: Optional[list[App]] = None) -> list[App]:
    """Resolve a profile to the concrete list of App objects it covers."""
    if apps is None:
        apps = load_apps()
    by_cat = apps_by_category(apps)
    seen: set[str] = set()
    out: list[App] = []
    for cat in profile.categories:
        for a in by_cat.get(cat, []):
            if a.name not in seen:
                out.append(a)
                seen.add(a.name)
    extras = {n.lower() for n in profile.extra_apps}
    for a in apps:
        if a.name.lower() in extras and a.name not in seen:
            out.append(a)
            seen.add(a.name)
    return out


# ============================================================
# Detection
# ============================================================

def _read_uninstall_display_names() -> set[str]:
    """Read DisplayName values from Windows uninstall registry keys.

    This is the authoritative list of installed programs from the
    user's perspective — MSI installers, NSIS installers, winget,
    Add/Remove Programs all populate the same hives. Pure Python via
    ``winreg``; no admin needed; both HKLM (system-wide) and HKCU
    (per-user) are read so apps installed for the current user only
    are also caught."""
    if sys.platform != "win32":
        return set()
    try:
        import winreg  # local — Windows-only
    except ImportError:
        return set()

    names: set[str] = set()
    targets = [
        (winreg.HKEY_LOCAL_MACHINE,
         r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER,
         r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hive, subkey in targets:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                count = winreg.QueryInfoKey(key)[0]
                for i in range(count):
                    try:
                        child_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, child_name) as child:
                            display, _ = winreg.QueryValueEx(child, "DisplayName")
                            if isinstance(display, str) and display.strip():
                                names.add(display.lower())
                    except OSError:
                        continue
        except OSError:
            continue
    return names


_INSTALLED_PROGRAMS_CACHE: Optional[set[str]] = None


def installed_programs() -> set[str]:
    """Memoised view of installed-program DisplayNames (lowercased).

    Cached for the lifetime of the process because reading the registry
    is mildly expensive (~50–200 ms). Call
    ``invalidate_program_cache()`` after running an installer so the
    next ``is_installed()`` reflects the new state."""
    global _INSTALLED_PROGRAMS_CACHE
    if _INSTALLED_PROGRAMS_CACHE is None:
        _INSTALLED_PROGRAMS_CACHE = _read_uninstall_display_names()
    return _INSTALLED_PROGRAMS_CACHE


def invalidate_program_cache() -> None:
    global _INSTALLED_PROGRAMS_CACHE
    _INSTALLED_PROGRAMS_CACHE = None


def is_installed(app: App) -> bool:
    """Three independent checks, fast first:
      1. ``shutil.which(exe)`` — covers anything on PATH
      2. ``detect_paths`` — explicit absolute paths (env vars expanded)
      3. Registry DisplayName substring match (catches most GUI apps)
    """
    if app.exe and shutil.which(app.exe):
        return True
    for raw in app.detect_paths:
        if not raw:
            continue
        expanded = Path(os.path.expandvars(raw))
        if expanded.exists():
            return True
    needle = (app.detect_name or app.name).lower().strip()
    if needle:
        for display in installed_programs():
            if needle in display:
                return True
    return False


def winget_available() -> bool:
    return sys.platform == "win32" and shutil.which(WINGET) is not None


def refresh_path_from_registry() -> None:
    """Pick up PATH changes made by winget without restarting the shell.

    winget installs typically add their bin directory to the system or
    user ``Path`` in the registry. The running Python process still has
    the PATH it inherited at startup, so ``shutil.which`` (used by
    doctor + ``is_installed``) would say the just-installed tool is
    missing. Re-reading both hives and appending any new entries to
    ``os.environ['PATH']`` fixes that in-process. No-op off Windows.
    """
    if sys.platform != "win32":
        return
    try:
        import winreg  # local — Windows-only
    except ImportError:
        return

    current = os.environ.get("PATH", "")
    have = {p.lower().rstrip("\\")
            for p in current.split(os.pathsep) if p}
    additions: list[str] = []
    hives = [
        (winreg.HKEY_LOCAL_MACHINE,
         r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
        (winreg.HKEY_CURRENT_USER, r"Environment"),
    ]
    for hive, subkey in hives:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                value, _ = winreg.QueryValueEx(key, "Path")
        except OSError:
            continue
        if not isinstance(value, str) or not value:
            continue
        for raw in os.path.expandvars(value).split(os.pathsep):
            entry = raw.strip()
            if not entry:
                continue
            key2 = entry.lower().rstrip("\\")
            if key2 in have:
                continue
            additions.append(entry)
            have.add(key2)
    if additions:
        prefix = current + os.pathsep if current else ""
        os.environ["PATH"] = prefix + os.pathsep.join(additions)


@dataclass
class StatusCounts:
    total: int
    installed: int
    missing: int
    skipped: int


def status_counts(apps: Optional[list[App]] = None,
                  skip_list: Optional[set[str]] = None) -> StatusCounts:
    if apps is None:
        apps = load_apps()
    if skip_list is None:
        skip_list = load_skip_list()
    installed = missing = skipped = 0
    for a in apps:
        if a.name in skip_list:
            skipped += 1
        elif is_installed(a):
            installed += 1
        else:
            missing += 1
    return StatusCounts(len(apps), installed, missing, skipped)


def missing_apps(apps: Optional[list[App]] = None,
                 include_skipped: bool = False) -> list[App]:
    """Apps not currently on PATH. Skipped apps are filtered out unless
    include_skipped=True."""
    if apps is None:
        apps = load_apps()
    skip = set() if include_skipped else load_skip_list()
    return [a for a in apps if a.name not in skip and not is_installed(a)]


# ============================================================
# Skip-list (per-machine)
# ============================================================

def load_skip_list() -> set[str]:
    if not STATE_PATH.exists():
        return set()
    try:
        with STATE_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("skipped", [])
        return {str(x) for x in items}
    except (OSError, json.JSONDecodeError):
        return set()


def _save_skip_list(items: set[str]) -> None:
    payload = {"skipped": sorted(items)}
    STATE_PATH.write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )


def mark_skipped(name: str) -> None:
    items = load_skip_list()
    if name in items:
        return
    items.add(name)
    _save_skip_list(items)


def unskip(name: str) -> None:
    items = load_skip_list()
    if name not in items:
        return
    items.discard(name)
    _save_skip_list(items)


def is_skipped(app: App) -> bool:
    return app.name in load_skip_list()


# ============================================================
# Install
# ============================================================

def install_app(app: App, dry_run: bool = False) -> InstallResult:
    """Install one winget-eligible app.

    Manual apps are intentionally NOT auto-installed here — they return
    success=False with detail='manual' so the caller can decide whether
    to print the URL (CLI) or open it in a browser (GUI).
    """
    if app.install_method != WINGET or not app.winget_id:
        return InstallResult(app, False, "manual")
    if not winget_available():
        return InstallResult(app, False, "winget unavailable")
    if dry_run:
        return InstallResult(app, True, "dry-run")
    try:
        subprocess.run(
            [WINGET, "install", "--id", app.winget_id,
             "--accept-source-agreements", "--accept-package-agreements",
             "--silent"],
            check=True,
        )
        # Pick up the new PATH entry winget just registered so
        # subsequent is_installed / which calls see the freshly-
        # installed exe in the same process.
        refresh_path_from_registry()
        return InstallResult(app, True, "installed")
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        return InstallResult(app, False, str(exc))


def install_many(apps: list[App],
                 dry_run: bool = False) -> list[InstallResult]:
    return [install_app(a, dry_run=dry_run) for a in apps]


def open_download_page(app: App) -> bool:
    """Open the vendor download URL in the default browser.

    Used by the Settings dialog's "Install" button for manual apps and
    by the CLI's "Open download page now?" prompt.
    """
    if not app.url:
        return False
    try:
        webbrowser.open(app.url)
        return True
    except Exception:
        return False
