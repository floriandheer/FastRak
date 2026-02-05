#!/usr/bin/env python
"""
Florian Dheer Pipeline - New PC Setup Script
---------------------------------------------
Automates new PC provisioning: folder creation, subst drive mappings
with registry persistence, Synology Drive status checks, and pipeline
config generation.

Usage:
    python setup_new_pc.py [--config PATH] [--dry-run] [--yes] [--step STEP]
"""

import sys
import os
import json
import argparse
import subprocess
from pathlib import Path

# Add modules/ to path (same pattern as floriandheer_pipeline.py)
SCRIPT_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(SCRIPT_FILE_DIR, "modules")
sys.path.insert(0, SCRIPTS_DIR)

from shared_logging import setup_logging, get_logger

logger = get_logger("setup_new_pc")

# ============================================================
# Constants
# ============================================================

STEPS = ("folders", "drives", "synology", "config")
BANNER_WIDTH = 60


# ============================================================
# Helpers
# ============================================================

def banner(title: str):
    """Print a section banner."""
    print()
    print("=" * BANNER_WIDTH)
    print(f"  {title}")
    print("=" * BANNER_WIDTH)


def status_line(label: str, ok: bool, detail: str = ""):
    """Print a coloured status line."""
    tag = "[OK]" if ok else "[!!]"
    msg = f"  {tag} {label}"
    if detail:
        msg += f" - {detail}"
    print(msg)


def confirm(prompt: str, auto_yes: bool) -> bool:
    """Ask for confirmation unless --yes was passed."""
    if auto_yes:
        print(f"{prompt} (auto-confirmed via --yes)")
        return True
    answer = input(f"{prompt} (y/n): ")
    return answer.strip().lower() in ("y", "yes")


def load_config(config_path: str) -> dict:
    """Load and validate setup_config.json."""
    path = Path(config_path)
    if not path.exists():
        example = Path(SCRIPT_FILE_DIR) / "setup_config.json.example"
        print(f"ERROR: Config file not found: {path}")
        if example.exists():
            print(f"  Copy the example and edit it:")
            print(f"    copy setup_config.json.example setup_config.json")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # Basic validation
    required = ("drive_mappings", "folder_structure", "synology_drive", "pipeline_config")
    missing = [k for k in required if k not in cfg]
    if missing:
        print(f"ERROR: Config missing required keys: {', '.join(missing)}")
        sys.exit(1)

    return cfg


def parse_subst_output() -> dict:
    """
    Parse `subst` output and return {drive_letter: target_path}.

    Output format:  I:\\: => D:\\_work\\Active
    """
    mapping = {}
    try:
        result = subprocess.run(
            ["subst"], capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            # e.g. "I:\: => D:\_work\Active"
            parts = line.split(" => ", 1)
            if len(parts) == 2:
                drive = parts[0].rstrip("\\:")  # "I:\:" -> "I"
                drive = drive.strip()
                if len(drive) == 1:
                    drive = f"{drive.upper()}:"
                target = parts[1].strip()
                mapping[drive] = target
    except Exception as e:
        logger.warning(f"Could not parse subst output: {e}")
    return mapping


# ============================================================
# Step 1: Prerequisites
# ============================================================

def step_prerequisites(cfg: dict) -> bool:
    """Verify platform, Python version, and config."""
    banner("Step 1: Prerequisites")

    ok = True

    # Platform
    if sys.platform != "win32":
        print("  ERROR: This script must be run on Windows (not WSL/Linux).")
        print("         Drive mappings and registry entries require native Windows.")
        return False
    status_line("Platform", True, "Windows")

    # Python version
    ver = sys.version_info
    py_ok = ver >= (3, 8)
    status_line("Python", py_ok, sys.version.split()[0])
    if not py_ok:
        print("  ERROR: Python 3.8+ required.")
        ok = False

    # Modules importable
    try:
        from rak_settings import RakSettings  # noqa: F401
        status_line("Modules", True, "rak_settings importable")
    except ImportError as e:
        status_line("Modules", False, str(e))
        ok = False

    # Config loaded (already done before this step, but confirm)
    status_line("Config", True, "setup_config.json loaded")

    return ok


# ============================================================
# Step 2: Folder Structure
# ============================================================

def step_folders(cfg: dict, dry_run: bool, auto_yes: bool) -> bool:
    """Create folder structure from config."""
    banner("Step 2: Folder Structure")

    fs = cfg["folder_structure"]
    bases = fs.get("bases", [])
    categories = fs.get("categories", [])
    subcategories = fs.get("subcategories", {})
    extra_dirs = fs.get("extra_dirs", [])

    # Build full list of directories
    dirs_to_create = []

    for base in bases:
        dirs_to_create.append(base)
        for cat in categories:
            cat_path = os.path.join(base, cat)
            dirs_to_create.append(cat_path)
            for sub in subcategories.get(cat, []):
                dirs_to_create.append(os.path.join(cat_path, sub))

    for d in extra_dirs:
        dirs_to_create.append(d)

    # Check status
    existing = []
    needed = []
    for d in dirs_to_create:
        if os.path.isdir(d):
            existing.append(d)
        else:
            needed.append(d)

    print(f"  Total directories: {len(dirs_to_create)}")
    print(f"  Already exist:     {len(existing)}")
    print(f"  To create:         {len(needed)}")

    if not needed:
        print("  All directories already exist.")
        return True

    print()
    print("  Directories to create:")
    for d in needed:
        print(f"    {d}")

    if dry_run:
        print("\n  [DRY RUN] No directories created.")
        return True

    if not confirm("\n  Create these directories?", auto_yes):
        print("  Skipped.")
        return True

    created = 0
    for d in needed:
        try:
            os.makedirs(d, exist_ok=True)
            created += 1
            logger.info(f"Created directory: {d}")
        except OSError as e:
            print(f"  ERROR creating {d}: {e}")
            logger.error(f"Failed to create directory {d}: {e}")

    print(f"  Created {created}/{len(needed)} directories.")
    return created == len(needed)


# ============================================================
# Step 3: Drive Mappings (subst + Registry)
# ============================================================

def step_drives(cfg: dict, dry_run: bool, auto_yes: bool) -> bool:
    """Set up subst drive mappings and registry autorun entries."""
    banner("Step 3: Drive Mappings (subst + Registry)")

    mappings = cfg.get("drive_mappings", [])
    if not mappings:
        print("  No drive mappings configured.")
        return True

    current_subst = parse_subst_output()
    ok = True

    for m in mappings:
        drive = m["drive_letter"].upper()
        target = m["target_path"]
        desc = m.get("description", "")
        reg_name = m.get("registry_name", f"SubstDrive_{drive[0]}")

        print(f"\n  {drive} -> {target}")
        if desc:
            print(f"    ({desc})")

        # --- subst mapping ---
        if drive in current_subst:
            current_target = current_subst[drive]
            if os.path.normcase(os.path.normpath(current_target)) == os.path.normcase(os.path.normpath(target)):
                status_line(f"{drive} subst", True, "already mapped correctly")
            else:
                status_line(f"{drive} subst", False,
                            f"mapped to WRONG target: {current_target}")
                print(f"    Expected: {target}")
                print(f"    Remove manually with: subst {drive} /d")
                ok = False
                continue
        else:
            if dry_run:
                print(f"    [DRY RUN] Would run: subst {drive} \"{target}\"")
            else:
                if not confirm(f"    Mount {drive} -> {target}?", auto_yes):
                    print("    Skipped.")
                    continue
                try:
                    subprocess.run(
                        ["subst", drive, target],
                        check=True, capture_output=True, text=True, timeout=10
                    )
                    status_line(f"{drive} subst", True, "mounted")
                    logger.info(f"Mounted subst drive: {drive} -> {target}")
                except subprocess.CalledProcessError as e:
                    status_line(f"{drive} subst", False, f"subst failed: {e.stderr.strip()}")
                    logger.error(f"subst failed for {drive}: {e}")
                    ok = False
                    continue

        # --- Registry autorun entry ---
        reg_value = f'subst {drive} "{target}"'
        _ok = _ensure_registry_autorun(reg_name, reg_value, dry_run)
        if not _ok:
            ok = False

    # Verify accessibility
    if not dry_run:
        print()
        for m in mappings:
            drive = m["drive_letter"].upper()
            accessible = os.path.isdir(f"{drive}\\")
            status_line(f"{drive} accessible", accessible)
            if not accessible:
                ok = False

    return ok


def _ensure_registry_autorun(name: str, value: str, dry_run: bool) -> bool:
    """Write or verify a HKCU\\...\\Run registry entry."""
    try:
        import winreg
    except ImportError:
        print("    WARNING: winreg not available (not on Windows?)")
        return False

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

    # Read existing value
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                            winreg.KEY_READ) as key:
            existing, _ = winreg.QueryValueEx(key, name)
            if existing == value:
                status_line(f"Registry '{name}'", True, "already set")
                return True
            else:
                print(f"    Registry '{name}' has different value:")
                print(f"      Current:  {existing}")
                print(f"      Expected: {value}")
    except FileNotFoundError:
        pass  # Value doesn't exist yet
    except Exception as e:
        print(f"    WARNING: Could not read registry: {e}")

    if dry_run:
        print(f"    [DRY RUN] Would set registry '{name}' = {value}")
        return True

    # Write the value
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                            winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        status_line(f"Registry '{name}'", True, "written")
        logger.info(f"Registry autorun set: {name} = {value}")
        return True
    except Exception as e:
        status_line(f"Registry '{name}'", False, str(e))
        logger.error(f"Failed to write registry {name}: {e}")
        return False


# ============================================================
# Step 4: Synology Drive Check
# ============================================================

def step_synology(cfg: dict) -> bool:
    """Check Synology Drive installation and sync folder status."""
    banner("Step 4: Synology Drive Check")

    sd_cfg = cfg.get("synology_drive", {})
    sync_folders = sd_cfg.get("sync_folders", [])
    ok = True

    # Detect installation
    install_paths = [
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                     "Synology", "SynologyDrive"),
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                     "Synology", "SynologyDrive"),
        os.path.join(os.path.expanduser("~"), "AppData", "Local",
                     "SynologyDrive"),
    ]

    installed = any(os.path.isdir(p) for p in install_paths)
    status_line("Synology Drive installed", installed)

    # Check if running
    running = False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq SynologyDrive.exe"],
            capture_output=True, text=True, timeout=10
        )
        running = "SynologyDrive.exe" in result.stdout
    except Exception:
        pass
    status_line("Synology Drive running", running)

    if not installed:
        print("\n  ACTION REQUIRED: Install Synology Drive Client")
        print("    https://www.synology.com/en-global/dsm/feature/drive")
        ok = False

    # Check sync folders
    print()
    missing_tasks = []
    for sf in sync_folders:
        name = sf["name"]
        expected = sf["expected_path"]
        exists = os.path.isdir(expected)
        populated = False
        if exists:
            try:
                populated = len(os.listdir(expected)) > 0
            except OSError:
                pass

        if exists and populated:
            status_line(f"Sync: {name}", True, f"{expected} (populated)")
        elif exists:
            status_line(f"Sync: {name}", False, f"{expected} (empty - sync task may be missing)")
            missing_tasks.append(name)
        else:
            status_line(f"Sync: {name}", False, f"{expected} (not found)")
            missing_tasks.append(name)

    if missing_tasks:
        print("\n  ACTION REQUIRED: Create Synology Drive sync tasks for:")
        for t in missing_tasks:
            print(f"    - {t}")
        print("  (Synology Drive has no CLI/API - must be configured manually)")
        ok = False

    return ok


# ============================================================
# Step 5: Pipeline Config Generation
# ============================================================

def step_config(cfg: dict, dry_run: bool) -> bool:
    """Generate / update rak_config.json via RakSettings."""
    banner("Step 5: Pipeline Config Generation")

    try:
        from rak_settings import RakSettings
    except ImportError as e:
        print(f"  ERROR: Cannot import RakSettings: {e}")
        return False

    pc = cfg.get("pipeline_config", {})

    if dry_run:
        print("  [DRY RUN] Would apply the following settings:")
        for key, val in pc.items():
            print(f"    {key} = {val}")
        return True

    # Instantiate (creates rak_config.json if needed)
    settings = RakSettings()
    print(f"  Config file: {settings.config_path}")

    # Apply overrides
    if "work_drive" in pc:
        settings.set_work_drive(pc["work_drive"])
        print(f"  Set work_drive = {pc['work_drive']}")

    if "active_base" in pc:
        settings.set_active_base(pc["active_base"])
        print(f"  Set active_base = {pc['active_base']}")

    if "archive_base" in pc:
        settings.set_archive_base(pc["archive_base"])
        print(f"  Set archive_base = {pc['archive_base']}")

    if "mapped_software_path" in pc:
        settings.set_mapped_software_path(pc["mapped_software_path"])
        print(f"  Set mapped_software_path = {pc['mapped_software_path']}")

    if "launchers_base_path" in pc:
        settings.set_launchers_base_path(pc["launchers_base_path"])
        print(f"  Set launchers_base_path = {pc['launchers_base_path']}")

    # Validate
    print("\n  Validation:")
    results = settings.validate_all()
    all_ok = True
    for path_name, (valid, msg) in results.items():
        status_line(path_name, valid, msg)
        if not valid:
            all_ok = False

    return all_ok


# ============================================================
# Step 6: Final Report
# ============================================================

def final_report(results: dict):
    """Print summary of all steps."""
    banner("Setup Complete")

    for step_name, ok in results.items():
        status_line(step_name, ok)

    any_failed = not all(results.values())

    if any_failed:
        print("\n  Some steps had issues. Review the output above.")
    else:
        print("\n  All steps completed successfully.")

    print("\n  Manual steps remaining:")
    print("    1. Create Synology Drive sync tasks (if not done)")
    print("    2. Use Visual Subst to set drive labels (I: = Work, P: = Pipeline)")
    print("       https://www.ntwind.com/software/visual-subst.html")
    print("    3. Reboot to verify drive persistence via registry")
    print("    4. Launch Pipeline Manager and verify paths in Settings (Ctrl+,)")


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Florian Dheer Pipeline - New PC Setup"
    )
    parser.add_argument(
        "--config", default="./setup_config.json",
        help="Path to setup_config.json (default: ./setup_config.json)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would happen without making changes"
    )
    parser.add_argument(
        "--yes", action="store_true",
        help="Skip confirmation prompts"
    )
    parser.add_argument(
        "--step", choices=STEPS + ("all",), default="all",
        help="Run only one step: folders, drives, synology, config, or all"
    )

    args = parser.parse_args()

    # Set up logging (console only for setup script, file handler deferred)
    setup_logging("setup_new_pc", include_console=False)

    # Banner
    print("=" * BANNER_WIDTH)
    print("  Florian Dheer Pipeline - New PC Setup")
    print("=" * BANNER_WIDTH)
    print(f"  Python:  {sys.version.split()[0]}")
    print(f"  Config:  {args.config}")
    if args.dry_run:
        print("  Mode:    DRY RUN (no changes will be made)")
    if args.step != "all":
        print(f"  Step:    {args.step} only")
    print("=" * BANNER_WIDTH)

    # Load config
    cfg = load_config(args.config)

    run_all = args.step == "all"
    results = {}

    # Step 1: Prerequisites (always runs)
    if run_all or args.step in STEPS:
        ok = step_prerequisites(cfg)
        results["Prerequisites"] = ok
        if not ok and run_all:
            print("\n  Prerequisites not met. Fix the issues above and re-run.")
            sys.exit(1)

    # Step 2: Folders
    if run_all or args.step == "folders":
        results["Folder Structure"] = step_folders(cfg, args.dry_run, args.yes)

    # Step 3: Drives
    if run_all or args.step == "drives":
        results["Drive Mappings"] = step_drives(cfg, args.dry_run, args.yes)

    # Step 4: Synology
    if run_all or args.step == "synology":
        results["Synology Drive"] = step_synology(cfg)

    # Step 5: Config
    if run_all or args.step == "config":
        results["Pipeline Config"] = step_config(cfg, args.dry_run)

    # Step 6: Report
    final_report(results)

    # Windows console keep-alive
    if os.name == "nt" and not sys.stdin.isatty():
        print("\nPress Enter to exit...")
        input()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSetup cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        logger.exception("Setup failed")
        if os.name == "nt" and not sys.stdin.isatty():
            print("\nPress Enter to exit...")
            input()
        sys.exit(1)
