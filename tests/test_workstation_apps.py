"""Tests for modules/workstation_apps.py.

Covers the pure-logic surface: config loading, category grouping,
profile expansion, skip-list round-trip. Install execution itself is
not tested here (it shells out to winget); instead we verify the
``install_app`` dispatch routes correctly between winget and manual.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "modules"))

import workstation_apps as wa  # noqa: E402


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def isolated_paths(tmp_path, monkeypatch):
    """Redirect config + state to a temp dir so tests don't see the
    real setup_config.json or scribble in setup_apps_state.json."""
    cfg = tmp_path / "setup_config.json"
    example = tmp_path / "setup_config.json.example"
    state = tmp_path / "setup_apps_state.json"
    monkeypatch.setattr(wa, "CONFIG_PATH", cfg)
    monkeypatch.setattr(wa, "EXAMPLE_PATH", example)
    monkeypatch.setattr(wa, "STATE_PATH", state)
    return {"cfg": cfg, "example": example, "state": state}


def _write(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


# ============================================================
# load_apps / category defaults
# ============================================================

def test_load_apps_empty_when_no_config(isolated_paths):
    assert wa.load_apps() == []


def test_load_apps_reads_config(isolated_paths):
    _write(isolated_paths["cfg"], {
        "workstation_apps": [
            {"name": "Foo", "category": "Visual", "exe": "foo"},
            {"name": "Bar", "category": "Audio", "exe": "bar"},
        ],
    })
    apps = wa.load_apps()
    assert [a.name for a in apps] == ["Foo", "Bar"]
    assert apps[0].category == "Visual"
    assert apps[1].category == "Audio"


def test_load_apps_defaults_category_when_missing(isolated_paths):
    """Old configs (pre-category-field) still load — entries land in
    'General' so the picker has somewhere to put them."""
    _write(isolated_paths["cfg"], {
        "workstation_apps": [{"name": "Legacy", "exe": "legacy"}],
    })
    apps = wa.load_apps()
    assert apps[0].category == "General"
    assert apps[0].categories == ["General"]


def test_load_apps_accepts_list_category(isolated_paths):
    """Polymorphic category field: an app can live in multiple
    categories at once. Primary (a.category) is the first entry."""
    _write(isolated_paths["cfg"], {
        "workstation_apps": [
            {"name": "MusicBee", "category": ["Audio", "Media"], "exe": "mb"},
        ],
    })
    apps = wa.load_apps()
    assert apps[0].categories == ["Audio", "Media"]
    assert apps[0].category == "Audio"


def test_load_apps_empty_list_category_falls_back_to_default(isolated_paths):
    _write(isolated_paths["cfg"], {
        "workstation_apps": [{"name": "X", "category": [], "exe": "x"}],
    })
    apps = wa.load_apps()
    assert apps[0].categories == ["General"]


def test_load_apps_falls_back_to_example(isolated_paths):
    """If setup_config.json doesn't exist we read the .example so a
    fresh checkout has a working catalog."""
    _write(isolated_paths["example"], {
        "workstation_apps": [{"name": "FromExample", "exe": "x"}],
    })
    apps = wa.load_apps()
    assert [a.name for a in apps] == ["FromExample"]


def test_load_apps_skips_malformed_entries(isolated_paths):
    _write(isolated_paths["cfg"], {
        "workstation_apps": [
            {"name": "Good", "exe": "good"},
            {"no_name": "bad"},
            "not even a dict",
        ],
    })
    apps = wa.load_apps()
    assert [a.name for a in apps] == ["Good"]


# ============================================================
# Grouping
# ============================================================

def test_apps_by_category_preserves_insertion_order(isolated_paths):
    _write(isolated_paths["cfg"], {
        "workstation_apps": [
            {"name": "V1", "category": "Visual", "exe": "v1"},
            {"name": "A1", "category": "Audio",  "exe": "a1"},
            {"name": "V2", "category": "Visual", "exe": "v2"},
        ],
    })
    grouped = wa.apps_by_category()
    # Categories appear in the order first seen; apps within a category
    # in document order.
    assert list(grouped.keys()) == ["Visual", "Audio"]
    assert [a.name for a in grouped["Visual"]] == ["V1", "V2"]


def test_apps_by_category_lists_multicat_app_under_each(isolated_paths):
    """A multi-category app appears once per category in the grouped
    dict — the picker uses this to show it under each section."""
    _write(isolated_paths["cfg"], {
        "workstation_apps": [
            {"name": "MusicBee", "category": ["Audio", "Media"], "exe": "mb"},
            {"name": "Kodi",     "category": "Media",            "exe": "kodi"},
        ],
    })
    grouped = wa.apps_by_category()
    assert [a.name for a in grouped["Audio"]] == ["MusicBee"]
    assert [a.name for a in grouped["Media"]] == ["MusicBee", "Kodi"]
    # categories_present collapses dupes
    assert wa.categories_present() == ["Audio", "Media"]


def test_status_counts_treats_multicat_app_as_single(isolated_paths, monkeypatch):
    """Even though MusicBee is in two categories, status_counts still
    counts it once — otherwise the summary line over-reports."""
    _write(isolated_paths["cfg"], {
        "workstation_apps": [
            {"name": "MusicBee", "category": ["Audio", "Media"], "exe": "mb"},
        ],
    })
    monkeypatch.setattr(wa, "is_installed", lambda a: True)
    counts = wa.status_counts()
    assert counts.total == 1
    assert counts.installed == 1


# ============================================================
# Profiles
# ============================================================

def test_expand_profile_pulls_category_members(isolated_paths):
    _write(isolated_paths["cfg"], {
        "workstation_apps": [
            {"name": "V1", "category": "Visual", "exe": "v1"},
            {"name": "V2", "category": "Visual", "exe": "v2"},
            {"name": "A1", "category": "Audio",  "exe": "a1"},
        ],
        "workstation_profiles": [
            {"name": "Visual rig", "categories": ["Visual"]},
        ],
    })
    profiles = wa.load_profiles()
    assert len(profiles) == 1
    expanded = wa.expand_profile(profiles[0])
    assert [a.name for a in expanded] == ["V1", "V2"]


def test_expand_profile_adds_extras_from_other_categories(isolated_paths):
    """VJ rig pulls Traktor in even though Traktor is an Audio app —
    this is the canonical 'extra_apps' use case."""
    _write(isolated_paths["cfg"], {
        "workstation_apps": [
            {"name": "Resolume", "category": "RealTime", "exe": "resolume"},
            {"name": "Traktor",  "category": "Audio",    "exe": "traktor"},
            {"name": "Ableton",  "category": "Audio",    "exe": "ableton"},
        ],
        "workstation_profiles": [
            {"name": "VJ rig",
             "categories": ["RealTime"],
             "extra_apps": ["Traktor"]},
        ],
    })
    expanded = wa.expand_profile(wa.load_profiles()[0])
    names = [a.name for a in expanded]
    assert "Resolume" in names
    assert "Traktor" in names
    # extras should NOT pull in the rest of their category
    assert "Ableton" not in names


def test_expand_profile_dedupes(isolated_paths):
    """If an extra_app is already in a selected category it's only
    listed once."""
    _write(isolated_paths["cfg"], {
        "workstation_apps": [
            {"name": "A1", "category": "Audio", "exe": "a1"},
        ],
        "workstation_profiles": [
            {"name": "Audio", "categories": ["Audio"], "extra_apps": ["A1"]},
        ],
    })
    expanded = wa.expand_profile(wa.load_profiles()[0])
    assert [a.name for a in expanded] == ["A1"]


def test_expand_profile_dedupes_multicat_app(isolated_paths):
    """When a profile pulls two categories that share a multi-category
    app, that app is still only listed once in the expansion."""
    _write(isolated_paths["cfg"], {
        "workstation_apps": [
            {"name": "MusicBee", "category": ["Audio", "Media"], "exe": "mb"},
            {"name": "Kodi",     "category": "Media",            "exe": "kodi"},
        ],
        "workstation_profiles": [
            {"name": "AV", "categories": ["Audio", "Media"]},
        ],
    })
    expanded = wa.expand_profile(wa.load_profiles()[0])
    assert [a.name for a in expanded] == ["MusicBee", "Kodi"]


def test_expand_profile_extras_case_insensitive(isolated_paths):
    _write(isolated_paths["cfg"], {
        "workstation_apps": [
            {"name": "Traktor Pro", "category": "Audio", "exe": "traktor"},
        ],
        "workstation_profiles": [
            {"name": "VJ", "categories": [], "extra_apps": ["traktor pro"]},
        ],
    })
    expanded = wa.expand_profile(wa.load_profiles()[0])
    assert [a.name for a in expanded] == ["Traktor Pro"]


# ============================================================
# Skip-list (per-machine state)
# ============================================================

def test_skip_list_empty_when_no_state_file(isolated_paths):
    assert wa.load_skip_list() == set()


def test_skip_list_round_trip(isolated_paths):
    wa.mark_skipped("Houdini")
    wa.mark_skipped("Resolume")
    assert wa.load_skip_list() == {"Houdini", "Resolume"}

    wa.unskip("Houdini")
    assert wa.load_skip_list() == {"Resolume"}


def test_skip_list_is_idempotent(isolated_paths):
    wa.mark_skipped("Houdini")
    wa.mark_skipped("Houdini")
    assert wa.load_skip_list() == {"Houdini"}


def test_unskip_unknown_app_is_noop(isolated_paths):
    wa.unskip("NeverAdded")
    assert wa.load_skip_list() == set()


def test_skip_list_persists_to_disk(isolated_paths):
    wa.mark_skipped("Foo")
    raw = json.loads(isolated_paths["state"].read_text(encoding="utf-8"))
    assert raw == {"skipped": ["Foo"]}


# ============================================================
# Status counts
# ============================================================

def test_status_counts_counts_skipped_separately(isolated_paths, monkeypatch):
    _write(isolated_paths["cfg"], {
        "workstation_apps": [
            {"name": "A", "exe": "a"},
            {"name": "B", "exe": "b"},
            {"name": "C", "exe": "c"},
        ],
    })
    # Pretend A is installed; B and C aren't.
    monkeypatch.setattr(wa, "is_installed",
                        lambda app: app.name == "A")
    wa.mark_skipped("C")

    counts = wa.status_counts()
    assert counts.total == 3
    assert counts.installed == 1
    assert counts.missing == 1   # only B (C is skipped, not missing)
    assert counts.skipped == 1


# ============================================================
# is_installed — detection paths
# ============================================================

@pytest.fixture
def no_real_detection(monkeypatch):
    """Force all detection paths to negative so each test enables only
    the one it wants to exercise."""
    monkeypatch.setattr(wa.shutil, "which", lambda exe: None)
    monkeypatch.setattr(wa, "installed_programs", lambda: set())
    yield


def test_is_installed_finds_via_path(isolated_paths, monkeypatch, no_real_detection):
    monkeypatch.setattr(wa.shutil, "which",
                        lambda exe: r"C:\tools\blender.exe" if exe == "blender" else None)
    app = wa.App(name="Blender", exe="blender")
    assert wa.is_installed(app) is True


def test_is_installed_finds_via_detect_paths(isolated_paths, monkeypatch, no_real_detection, tmp_path):
    fake = tmp_path / "fake_synology" / "SynologyDrive.exe"
    fake.parent.mkdir(parents=True)
    fake.write_text("stub")
    app = wa.App(name="Synology Drive Client",
                 exe="SynologyDrive",
                 detect_paths=[str(fake)])
    assert wa.is_installed(app) is True


def test_is_installed_expands_env_vars_in_detect_paths(isolated_paths, monkeypatch, no_real_detection, tmp_path):
    fake = tmp_path / "WizTree.exe"
    fake.write_text("stub")
    monkeypatch.setenv("FAKE_PROG_FILES", str(tmp_path))
    app = wa.App(name="WizTree", exe="WizTree",
                 detect_paths=["%FAKE_PROG_FILES%\\WizTree.exe"])
    assert wa.is_installed(app) is True


def test_is_installed_finds_via_registry_substring(isolated_paths, monkeypatch, no_real_detection):
    monkeypatch.setattr(wa, "installed_programs",
                        lambda: {"winscp 6.5", "ableton live 12 suite"})
    assert wa.is_installed(wa.App(name="WinSCP", exe="WinSCP")) is True
    assert wa.is_installed(wa.App(name="Ableton Live", exe="Ableton Live 12 Suite")) is True


def test_is_installed_honors_detect_name_override(isolated_paths, monkeypatch, no_real_detection):
    """Affinity Suite's installer DisplayName is 'Affinity Photo 2' —
    a detect_name override lets the catalog keep its conceptual name."""
    monkeypatch.setattr(wa, "installed_programs",
                        lambda: {"affinity photo 2"})
    app = wa.App(name="Affinity Suite", detect_name="Affinity Photo",
                 exe="Affinity Photo 2")
    assert wa.is_installed(app) is True


def test_is_installed_missing_when_nothing_matches(isolated_paths, no_real_detection):
    app = wa.App(name="Houdini", exe="houdini")
    assert wa.is_installed(app) is False


def test_invalidate_program_cache_forces_rescan(isolated_paths, monkeypatch):
    calls = []

    def fake_read():
        calls.append(1)
        return {"foo"}

    monkeypatch.setattr(wa, "_read_uninstall_display_names", fake_read)
    wa.invalidate_program_cache()
    wa.installed_programs()
    wa.installed_programs()
    assert len(calls) == 1  # cached

    wa.invalidate_program_cache()
    wa.installed_programs()
    assert len(calls) == 2  # re-read after invalidation


# ============================================================
# install_app dispatch
# ============================================================

def test_install_app_rejects_manual_apps(isolated_paths):
    app = wa.App(name="Houdini", install_method="manual",
                 url="https://sidefx.com/")
    result = wa.install_app(app, dry_run=True)
    assert result.success is False
    assert "manual" in result.detail


def test_install_app_dry_run_skips_subprocess(isolated_paths, monkeypatch):
    monkeypatch.setattr(wa, "winget_available", lambda: True)
    called = []
    monkeypatch.setattr(wa.subprocess, "run",
                        lambda *a, **kw: called.append(("run",) + a))

    app = wa.App(name="WinDirStat", install_method="winget",
                 winget_id="WinDirStat.WinDirStat")
    result = wa.install_app(app, dry_run=True)

    assert result.success is True
    assert result.detail == "dry-run"
    assert called == []  # subprocess never invoked


def test_install_app_reports_winget_unavailable(isolated_paths, monkeypatch):
    monkeypatch.setattr(wa, "winget_available", lambda: False)
    app = wa.App(name="WinDirStat", install_method="winget",
                 winget_id="WinDirStat.WinDirStat")
    result = wa.install_app(app, dry_run=False)
    assert result.success is False
    assert "winget" in result.detail
