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
    category: str = DEFAULT_CATEGORY
    install_method: str = MANUAL  # "winget" | "manual"
    winget_id: Optional[str] = None
    exe: str = ""
    why: str = ""
    url: str = ""


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
    """Read setup_config.json, falling back to the .example if the user
    hasn't created their own yet."""
    path = CONFIG_PATH if CONFIG_PATH.exists() else EXAMPLE_PATH
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


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
            category=entry.get("category") or DEFAULT_CATEGORY,
            install_method=entry.get("install_method", MANUAL),
            winget_id=entry.get("winget_id"),
            exe=entry.get("exe", ""),
            why=entry.get("why", ""),
            url=entry.get("url", ""),
        ))
    return out


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
    so the UI doesn't re-shuffle on every load."""
    if apps is None:
        apps = load_apps()
    out: dict[str, list[App]] = {}
    for a in apps:
        out.setdefault(a.category, []).append(a)
    return out


def categories_present(apps: Optional[list[App]] = None) -> list[str]:
    if apps is None:
        apps = load_apps()
    seen: list[str] = []
    for a in apps:
        if a.category not in seen:
            seen.append(a.category)
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

def is_installed(app: App) -> bool:
    if not app.exe:
        return False
    return shutil.which(app.exe) is not None


def winget_available() -> bool:
    return sys.platform == "win32" and shutil.which(WINGET) is not None


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
