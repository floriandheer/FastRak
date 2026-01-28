#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Project Tracker

Standalone GUI for managing active projects, clients, and archives.
Provides overview of all projects, search/filter, archive/unarchive, and import functionality.

Can be run standalone or embedded as a tab in the Pipeline Manager.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import os
import sys
from pathlib import Path
import re
import shutil
import json
from datetime import datetime
from typing import List, Dict, Optional

# Add modules to path (modules folder is a subdirectory)
SCRIPT_DIR = Path(__file__).parent
MODULES_DIR = SCRIPT_DIR / "modules"
sys.path.insert(0, str(MODULES_DIR))

from shared_logging import get_logger, setup_logging
from shared_project_db import ProjectDatabase
from rak_settings import get_rak_settings
from shared_creator_registry import (
    CREATOR_REGISTRY, CREATIVE_CATEGORIES,
    get_subtypes_for_category, get_subtype_display_name,
    has_multiple_subtypes, get_creator_class, is_creative_category
)

# Module name for logging (must match setup_logging call)
MODULE_NAME = "project_tracker"

# Get logger reference (configured in main())
logger = get_logger(MODULE_NAME)

def _get_platform_path(windows_path: str) -> Path:
    """
    Convert Windows path to appropriate platform path.
    On WSL/Linux, converts 'D:\\folder' to '/mnt/d/folder'.
    On Windows, returns the path unchanged.
    """
    if sys.platform == "win32":
        return Path(windows_path)

    # WSL/Linux: convert Windows path to /mnt/ path
    # Handle both D:\folder and D:/folder formats
    path_str = windows_path.replace("\\", "/")

    # Check for drive letter pattern (e.g., "D:/", "I:/")
    if len(path_str) >= 2 and path_str[1] == ":":
        drive_letter = path_str[0].lower()
        rest_of_path = path_str[2:]  # Skip "D:"
        if rest_of_path.startswith("/"):
            rest_of_path = rest_of_path[1:]
        return Path(f"/mnt/{drive_letter}/{rest_of_path}")

    return Path(windows_path)


# Category colors matching pipeline manager
CATEGORY_COLORS = {
    "Audio": "#9333ea",      # Purple
    "Photo": "#10b981",      # Emerald
    "Visual": "#f97316",     # Orange
    "Web": "#eab308",        # Yellow
    "Physical": "#ec4899",   # Pink
    "RealTime": "#06b6d4",   # Cyan
}

# Project type icons and display names
PROJECT_TYPES = {
    # New Visual types
    "Visual-Graphic Design": {"icon": "🖼️", "name": "Visual-Graphic Design", "color": "#f97316"},
    "Visual-Visual Effects": {"icon": "🎬", "name": "Visual-Visual Effects", "color": "#f97316"},
    "Visual-Live Video": {"icon": "💫", "name": "Visual-Live Video", "color": "#f97316"},
    # Legacy Visual types (for backwards compatibility)
    "GD": {"icon": "🖼️", "name": "Visual-Graphic Design", "color": "#f97316"},
    "FX": {"icon": "🎬", "name": "Visual-Visual Effects", "color": "#f97316"},
    "VFX": {"icon": "🎬", "name": "Visual-Visual Effects", "color": "#f97316"},
    "VJ": {"icon": "💫", "name": "Visual-Live Video", "color": "#f97316"},
    # Old legacy types (backwards compatibility)
    "Visual-Computer Graphics": {"icon": "🎬", "name": "Visual-Visual Effects", "color": "#f97316"},
    "Visual-VJ": {"icon": "💫", "name": "Visual-Live Video", "color": "#f97316"},
    # Other types
    "Audio": {"icon": "🎵", "name": "Audio", "color": "#9333ea"},
    "Physical": {"icon": "🔧", "name": "3D Print", "color": "#ec4899"},
    "Godot": {"icon": "⚡", "name": "Godot", "color": "#06b6d4"},
    "TD": {"icon": "⚡", "name": "TouchDesigner", "color": "#06b6d4"},
    "RealTime": {"icon": "⚡", "name": "RealTime", "color": "#06b6d4"},
    "Photo": {"icon": "📷", "name": "Photo", "color": "#10b981"},
    "Web": {"icon": "🌐", "name": "Web", "color": "#eab308"},
}

# Archive category mapping
ARCHIVE_CATEGORIES = {
    # New Visual types
    "Visual-Graphic Design": "Visual",
    "Visual-Visual Effects": "Visual",
    "Visual-Live Video": "Visual",
    # Legacy Visual types (for backwards compatibility)
    "GD": "Visual",
    "FX": "Visual",
    "VFX": "Visual",
    "VJ": "Visual",
    # Old legacy types (backwards compatibility)
    "Visual-Computer Graphics": "Visual",
    "Visual-VJ": "Visual",
    # Other types
    "Audio": "Audio",
    "Physical": "Physical",
    "Godot": "RealTime",
    "TD": "RealTime",
    "RealTime": "RealTime",
    "Photo": "Photo",
    "Web": "Web",
}


def _get_appdata_path() -> Path:
    """Get the appropriate AppData path for the platform."""
    if sys.platform == "win32":
        return Path.home() / "AppData" / "Local" / "PipelineManager"
    else:
        # WSL/Linux: use Windows user profile via /mnt/c
        windows_appdata = Path("/mnt/c/Users")
        if windows_appdata.exists():
            username = os.environ.get("USER", "")
            user_path = windows_appdata / username
            if user_path.exists():
                return user_path / "AppData" / "Local" / "PipelineManager"
        # Fallback to Linux standard location
        return Path.home() / ".local" / "share" / "PipelineManager"


class TrackerSettings:
    """Manages UI settings persistence for Project Tracker."""

    DEFAULT_SETTINGS = {
        "view_mode": "list",
        "list_scale": 100,
        "grid_scale": 100,
        "filter_status": "active",
        "file_manager": "",  # Empty = system default, or path like "C:\\Program Files\\fman\\fman.exe"
    }

    def __init__(self):
        self.settings_path = _get_appdata_path() / "tracker_settings.json"
        self.settings = self._load()

    def _load(self) -> Dict:
        """Load settings from file or return defaults."""
        try:
            if self.settings_path.exists():
                with open(self.settings_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # Merge with defaults to handle new settings
                    return {**self.DEFAULT_SETTINGS, **loaded}
        except Exception as e:
            logger.warning(f"Failed to load tracker settings: {e}")
        return self.DEFAULT_SETTINGS.copy()

    def save(self):
        """Save settings to file."""
        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.settings_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2)
            logger.debug("Tracker settings saved")
        except Exception as e:
            logger.warning(f"Failed to save tracker settings: {e}")

    def get(self, key: str, default=None):
        """Get a setting value."""
        return self.settings.get(key, default)

    def set(self, key: str, value):
        """Set a setting value and save."""
        self.settings[key] = value
        self.save()


class ArchiveManager:
    """Handles archiving and unarchiving of project folders."""

    @staticmethod
    def _get_archive_dir(project_type: str, is_personal: bool) -> Path:
        """Get the archive directory for a project type."""
        settings = get_rak_settings()
        archive_category = ARCHIVE_CATEGORIES.get(project_type, "Other")
        archive_path_str = settings.get_archive_path(archive_category)
        archive_dir = _get_platform_path(archive_path_str)

        if is_personal:
            archive_dir = archive_dir / "_Personal"

        return archive_dir

    @staticmethod
    def _get_active_dir(project_type: str, is_personal: bool) -> Path:
        """Get the active directory for a project type."""
        settings = get_rak_settings()
        archive_category = ARCHIVE_CATEGORIES.get(project_type, "Other")
        work_path_str = settings.get_work_path(archive_category)
        active_dir = _get_platform_path(work_path_str)

        if is_personal:
            active_dir = active_dir / "_Personal"

        return active_dir

    @staticmethod
    def archive_project(project: Dict, db: ProjectDatabase) -> bool:
        """
        Archive a project by moving it to the archive directory.

        Args:
            project: Project dictionary
            db: ProjectDatabase instance

        Returns:
            True if successful, False otherwise
        """
        try:
            source_path = Path(project["path"])

            if not source_path.exists():
                messagebox.showerror(
                    "Folder Not Found",
                    f"Project folder does not exist:\n{source_path}"
                )
                return False

            # Determine archive category
            project_type = project.get("project_type", "")

            # Check if this is a personal project
            metadata = project.get("metadata", {})
            is_personal = metadata.get("is_personal", False)

            # Build archive path using RakSettings
            archive_dir = ArchiveManager._get_archive_dir(project_type, is_personal)
            archive_dir.mkdir(parents=True, exist_ok=True)

            archive_path = archive_dir / source_path.name

            # Check if archive path already exists
            if archive_path.exists():
                response = messagebox.askyesno(
                    "Archive Conflict",
                    f"Archive location already exists:\n{archive_path}\n\n"
                    "Do you want to overwrite it?"
                )
                if not response:
                    return False

                # Remove existing archive folder
                shutil.rmtree(archive_path)

            # Move folder to archive
            logger.info(f"Archiving: {source_path} -> {archive_path}")
            shutil.move(str(source_path), str(archive_path))

            # Update database
            db.archive_project(project["id"], str(archive_path))

            messagebox.showinfo(
                "Success",
                f"Project archived successfully to:\n{archive_path}"
            )

            logger.info(f"Successfully archived project: {project['id']}")
            return True

        except Exception as e:
            logger.error(f"Failed to archive project: {e}")
            messagebox.showerror(
                "Archive Failed",
                f"Failed to archive project:\n{str(e)}"
            )

            # Rollback: try to move folder back if it was moved
            try:
                if 'archive_path' in locals() and archive_path.exists() and not source_path.exists():
                    shutil.move(str(archive_path), str(source_path))
                    logger.info("Rolled back archive operation")
            except Exception as rollback_error:
                logger.error(f"Rollback failed: {rollback_error}")

            return False

    @staticmethod
    def unarchive_project(project: Dict, db: ProjectDatabase) -> bool:
        """
        Unarchive a project by moving it back to the active directory.

        The active path is computed from project type and personal status.

        Args:
            project: Project dictionary
            db: ProjectDatabase instance

        Returns:
            True if successful, False otherwise
        """
        try:
            source_path = Path(project["path"])

            if not source_path.exists():
                messagebox.showerror(
                    "Folder Not Found",
                    f"Archived folder does not exist:\n{source_path}"
                )
                return False

            # Compute the active path based on project type
            project_type = project.get("project_type", "")
            metadata = project.get("metadata", {})
            is_personal = metadata.get("is_personal", False)

            # Get the active directory for this project type
            active_dir = ArchiveManager._get_active_dir(project_type, is_personal)
            active_path = active_dir / source_path.name

            # Check if active path is already occupied
            if active_path.exists():
                response = messagebox.askyesnocancel(
                    "Path Conflict",
                    f"Active location is occupied:\n{active_path}\n\n"
                    "Yes: Rename and restore\n"
                    "No: Cancel"
                )

                if response is None or not response:
                    return False

                # Find available name with counter
                counter = 1
                base_name = active_path.name
                parent = active_path.parent

                while active_path.exists():
                    new_name = f"{base_name}_restored_{counter}"
                    active_path = parent / new_name
                    counter += 1

                logger.info(f"Using alternate path: {active_path}")

            # Ensure parent directory exists
            active_path.parent.mkdir(parents=True, exist_ok=True)

            # Move folder to active
            logger.info(f"Unarchiving: {source_path} -> {active_path}")
            shutil.move(str(source_path), str(active_path))

            # Update database
            db.unarchive_project(project["id"], str(active_path))

            messagebox.showinfo(
                "Success",
                f"Project restored successfully to:\n{active_path}"
            )

            logger.info(f"Successfully unarchived project: {project['id']}")
            return True

        except Exception as e:
            logger.error(f"Failed to unarchive project: {e}")
            messagebox.showerror(
                "Unarchive Failed",
                f"Failed to unarchive project:\n{str(e)}"
            )

            # Rollback: try to move folder back if it was moved
            try:
                if 'active_path' in locals() and active_path.exists() and not source_path.exists():
                    shutil.move(str(active_path), str(source_path))
                    logger.info("Rolled back unarchive operation")
            except Exception as rollback_error:
                logger.error(f"Rollback failed: {rollback_error}")

            return False


class ProjectImporter:
    """Handles importing existing projects from filesystem."""

    # Regex patterns for parsing folder names
    PATTERNS = {
        "GD": r'^(\d{4}-\d{2}-\d{2})_([^_]+)_(.+)$',
        "FX": r'^(\d{4}-\d{2}-\d{2})_(?:FX|CG)_([^_]+)_(.+)$',
        "Physical": r'^(\d{4}-\d{2}-\d{2})_3DPrint_([^_]+)_(.+)$',
        "Godot": r'^(\d{4}-\d{2}-\d{2})_Godot_([^_]+)_(.+)$',
        "TD": r'^(\d{4}-\d{2}-\d{2})_TD_([^_]+)_(.+)$',
        "Audio": r'^(\d{4}-\d{2}-\d{2})_([^_]+)_(.+)$',
        "Photo": r'^(\d{4}-\d{2}-\d{2})_([^_]+)_(.+)$'
    }

    # Active project directories (auto-converted for WSL)
    SCAN_DIRECTORIES_ACTIVE = {
        # Visual
        "Visual": _get_platform_path(r"D:\_work\Active\Visual"),
        "Visual_Personal": _get_platform_path(r"D:\_work\Active\Visual\_Personal"),
        # Audio
        "Audio_InProgress": _get_platform_path(r"D:\_work\Active\Audio\01_Prod\01_InProgress"),
        "Audio_Finished": _get_platform_path(r"D:\_work\Active\Audio\01_Prod\03_Finished"),
        # Physical
        "Physical": _get_platform_path(r"D:\_work\Active\Physical\Project"),
        "Physical_Personal": _get_platform_path(r"D:\_work\Active\Physical\_Personal"),
        # RealTime
        "RealTime": _get_platform_path(r"D:\_work\Active\RealTIme"),  # Note: folder has typo "RealTIme"
        "RealTime_Personal": _get_platform_path(r"D:\_work\Active\RealTIme\_Personal"),
        # Photo
        "Photo": _get_platform_path(r"D:\_work\Active\Photo"),
        "Photo_Personal": _get_platform_path(r"D:\_work\Active\Photo\_Personal"),
        # Web
        "Web": _get_platform_path(r"D:\_work\Active\Web"),
        "Web_Personal": _get_platform_path(r"D:\_work\Active\Web\_Personal"),
    }

    # Archive directories
    SCAN_DIRECTORIES_ARCHIVE = {
        # Visual
        "Visual": _get_platform_path(r"D:\_work\Archive\Visual"),
        "Visual_Personal": _get_platform_path(r"D:\_work\Archive\Visual\_Personal"),
        # Physical
        "Physical": _get_platform_path(r"D:\_work\Archive\Physical"),
        "Physical_Personal": _get_platform_path(r"D:\_work\Archive\Physical\_Personal"),
        # RealTime
        "RealTime": _get_platform_path(r"D:\_work\Archive\RealTime"),
        "RealTime_Personal": _get_platform_path(r"D:\_work\Archive\RealTime\_Personal"),
        # Photo
        "Photo": _get_platform_path(r"D:\_work\Archive\Photo"),
        "Photo_Personal": _get_platform_path(r"D:\_work\Archive\Photo\_Personal"),
        # Web
        "Web": _get_platform_path(r"D:\_work\Archive\Web"),
        "Web_Personal": _get_platform_path(r"D:\_work\Archive\Web\_Personal"),
    }

    @classmethod
    def scan_and_import(cls, db: ProjectDatabase, status_callback=None) -> Dict:
        """
        Scan filesystem and import existing projects from both active and archive.

        Args:
            db: ProjectDatabase instance
            status_callback: Optional callback function for status updates

        Returns:
            Dictionary with import statistics
        """
        stats = {"scanned": 0, "imported": 0, "skipped": 0, "errors": 0}

        # Get path config for converting active paths to work drive
        try:
            settings = get_rak_settings()
        except Exception:
            settings = None

        # First, collect all folders to import
        folders_to_process = []

        # Scan active directories
        for category, base_dir in cls.SCAN_DIRECTORIES_ACTIVE.items():
            if not base_dir.exists():
                continue

            if status_callback:
                status_callback(f"Scanning active {category}...")

            try:
                for item in base_dir.iterdir():
                    if not item.is_dir():
                        continue
                    if item.name.startswith('_') or item.name.startswith('.'):
                        continue

                    parsed = cls._parse_folder_name(item.name, category)
                    if parsed:
                        # Convert to work drive path for active projects
                        stored_path = str(item)
                        stored_base = str(base_dir)
                        if settings:
                            stored_path = settings.convert_to_work_drive_path(stored_path)
                            stored_base = settings.convert_to_work_drive_path(stored_base)

                        folders_to_process.append({
                            "path": stored_path,
                            "base_dir": stored_base,
                            "scanned_path": str(item),  # Keep original for duplicate check
                            "parsed": parsed,
                            "status": "active"
                        })
            except Exception:
                pass

        # Scan archive directories
        for category, base_dir in cls.SCAN_DIRECTORIES_ARCHIVE.items():
            if not base_dir.exists():
                continue

            if status_callback:
                status_callback(f"Scanning archive {category}...")

            try:
                for item in base_dir.iterdir():
                    if not item.is_dir():
                        continue
                    if item.name.startswith('_') or item.name.startswith('.'):
                        continue

                    parsed = cls._parse_folder_name(item.name, category)
                    if parsed:
                        folders_to_process.append({
                            "path": str(item),
                            "base_dir": str(base_dir),
                            "parsed": parsed,
                            "status": "archived"
                        })
            except Exception:
                pass

        # Now process collected folders
        if status_callback:
            status_callback(f"Importing {len(folders_to_process)} projects...")

        for folder_info in folders_to_process:
            stats["scanned"] += 1

            try:
                # Check if already exists (check both stored path and original scanned path)
                stored_path = folder_info["path"]
                scanned_path = folder_info.get("scanned_path", stored_path)

                if db.get_project_by_path(stored_path) or db.get_project_by_path(scanned_path):
                    stats["skipped"] += 1
                    continue

                # Register new project (don't save yet - batch at end)
                parsed = folder_info["parsed"]
                db.register_project({
                    "client_name": parsed["client"],
                    "project_name": parsed["project"],
                    "project_type": parsed["type"],
                    "date_created": parsed["date"],
                    "path": stored_path,
                    "base_directory": folder_info["base_dir"],
                    "status": folder_info.get("status", "active"),
                    "notes": "",
                    "metadata": {"is_personal": parsed.get("is_personal", False)}
                }, auto_save=False)
                stats["imported"] += 1

            except Exception:
                stats["errors"] += 1

        # Save once at the end
        if stats["imported"] > 0:
            db.save()

        return stats

    @classmethod
    def _parse_folder_name(cls, folder_name: str, category: str) -> Optional[Dict]:
        """
        Parse folder name to extract project information.

        Args:
            folder_name: Folder name to parse
            category: Category from SCAN_DIRECTORIES

        Returns:
            Dictionary with date, client, project, type or None if not parseable
        """
        # Check if this is a personal project
        is_personal = "_Personal" in category
        base_category = category.replace("_Personal", "")

        # Visual: Try VJ pattern first, then VFX (CG_), then GD pattern
        if base_category == "Visual":
            # VJ pattern with client: YYYY-MM-DD_VJ_Client_Project
            match = re.match(r'^(\d{4}-\d{2}-\d{2})_VJ_([^_]+)_(.+)$', folder_name)
            if match:
                return {
                    "date": match.group(1),
                    "client": "Personal" if is_personal else match.group(2),
                    "project": match.group(3),
                    "type": "VJ",
                    "is_personal": is_personal
                }
            # VJ pattern without client: YYYY-MM-DD_VJ_Project
            match = re.match(r'^(\d{4}-\d{2}-\d{2})_VJ_(.+)$', folder_name)
            if match:
                return {
                    "date": match.group(1),
                    "client": "Personal",
                    "project": match.group(2),
                    "type": "VJ",
                    "is_personal": True
                }
            # FX pattern: YYYY-MM-DD_FX_Client_Project (also matches legacy _CG_)
            match = re.match(cls.PATTERNS["FX"], folder_name)
            if match:
                return {
                    "date": match.group(1),
                    "client": "Personal" if is_personal else match.group(2),
                    "project": match.group(3),
                    "type": "FX",
                    "is_personal": is_personal
                }
            # FX/CG pattern without client: YYYY-MM-DD_FX_Project (for personal projects)
            match = re.match(r'^(\d{4}-\d{2}-\d{2})_(?:FX|CG)_(.+)$', folder_name)
            if match:
                return {
                    "date": match.group(1),
                    "client": "Personal",
                    "project": match.group(2),
                    "type": "FX",
                    "is_personal": True
                }
            # GD pattern: YYYY-MM-DD_Client_Project
            match = re.match(cls.PATTERNS["GD"], folder_name)
            if match:
                return {
                    "date": match.group(1),
                    "client": "Personal" if is_personal else match.group(2),
                    "project": match.group(3),
                    "type": "GD",
                    "is_personal": is_personal
                }

        # Physical: 3DPrint or Technical pattern
        elif base_category == "Physical":
            # 3DPrint pattern
            match = re.match(cls.PATTERNS["Physical"], folder_name)
            if match:
                return {
                    "date": match.group(1),
                    "client": "Personal" if is_personal else match.group(2),
                    "project": match.group(3),
                    "type": "Physical",
                    "is_personal": is_personal
                }
            # Technical pattern (older archive format)
            match = re.match(r'^(\d{4}-\d{2}-\d{2})_Technical_(.+)$', folder_name)
            if match:
                return {
                    "date": match.group(1),
                    "client": "Personal",
                    "project": match.group(2),
                    "type": "Physical",
                    "is_personal": True
                }

        # RealTime: Try various patterns
        elif base_category == "RealTime":
            # Full FX/CG pattern: YYYY-MM-DD_FX_Client_Project (also matches legacy _CG_)
            match = re.match(cls.PATTERNS["FX"], folder_name)
            if match:
                return {
                    "date": match.group(1),
                    "client": "Personal" if is_personal else match.group(2),
                    "project": match.group(3),
                    "type": "RealTime",
                    "is_personal": is_personal
                }
            # Simple FX/CG pattern: YYYY-MM-DD_FX_ProjectName (no client)
            match = re.match(r'^(\d{4}-\d{2}-\d{2})_(?:FX|CG)_(.+)$', folder_name)
            if match:
                return {
                    "date": match.group(1),
                    "client": "Personal",
                    "project": match.group(2),
                    "type": "RealTime",
                    "is_personal": True
                }
            # Godot_ pattern
            match = re.match(cls.PATTERNS["Godot"], folder_name)
            if match:
                return {
                    "date": match.group(1),
                    "client": "Personal" if is_personal else match.group(2),
                    "project": match.group(3),
                    "type": "Godot",
                    "is_personal": is_personal
                }
            # TD_ pattern
            match = re.match(cls.PATTERNS["TD"], folder_name)
            if match:
                return {
                    "date": match.group(1),
                    "client": "Personal" if is_personal else match.group(2),
                    "project": match.group(3),
                    "type": "TD",
                    "is_personal": is_personal
                }
            # Simple: YYYY-MM-DD_ProjectName (no client)
            match = re.match(r'^(\d{4}-\d{2}-\d{2})_(.+)$', folder_name)
            if match:
                return {
                    "date": match.group(1),
                    "client": "Personal",
                    "project": match.group(2),
                    "type": "RealTime",
                    "is_personal": True
                }

        # Audio: Date_ProjectName or Date_Client_Project
        elif base_category.startswith("Audio"):
            # Try with client first: YYYY-MM-DD_Client_Project
            match = re.match(r'^(\d{4}-\d{2}-\d{2})_([^_]+)_(.+)$', folder_name)
            if match:
                return {
                    "date": match.group(1),
                    "client": match.group(2),
                    "project": match.group(3),
                    "type": "Audio",
                    "is_personal": False
                }
            # Simple: YYYY-MM-DD_ProjectName
            match = re.match(r'^(\d{4}-\d{2}-\d{2})_(.+)$', folder_name)
            if match:
                return {
                    "date": match.group(1),
                    "client": "Personal",
                    "project": match.group(2),
                    "type": "Audio",
                    "is_personal": True
                }

        # Photo: Date_Location_Description
        elif base_category == "Photo":
            match = re.match(r'^(\d{4}-\d{2}-\d{2})_(.+)$', folder_name)
            if match:
                return {
                    "date": match.group(1),
                    "client": "Photo",
                    "project": match.group(2),
                    "type": "Photo",
                    "is_personal": False
                }

        # Web: Just project name (no date prefix typically)
        elif base_category == "Web":
            # Try date pattern first
            match = re.match(r'^(\d{4}-\d{2}-\d{2})_(.+)$', folder_name)
            if match:
                return {
                    "date": match.group(1),
                    "client": "Web",
                    "project": match.group(2),
                    "type": "Web",
                    "is_personal": False
                }
            # No date - use folder name as project, today as date
            from datetime import date
            return {
                "date": date.today().isoformat(),
                "client": "Web",
                "project": folder_name,
                "type": "Web",
                "is_personal": False
            }

        return None


class ProjectTrackerApp:
    """
    Project Tracker application.

    Can run as standalone window or be embedded in a parent frame.
    Use embedded=True when integrating into another application (like Pipeline Manager).
    """

    def __init__(self, root_or_frame, embedded=False, status_callback=None, hint_callback=None, creation_start_callback=None, creation_done_callback=None, creation_cancel_callback=None):
        """
        Initialize the Project Tracker.

        Args:
            root_or_frame: Either a Tk root window (standalone) or a Frame (embedded)
            embedded: If True, skip window configuration and header
            status_callback: Optional callback function for status messages (message, status_type)
            hint_callback: Optional callback function for showing keyboard hints (hint_text)
            creation_start_callback: Optional callback when project creation starts (FAB clicked)
            creation_done_callback: Optional callback when project creation completes successfully
            creation_cancel_callback: Optional callback when project creation is cancelled
        """
        self.embedded = embedded
        self.status_callback = status_callback
        self.hint_callback = hint_callback
        self.creation_start_callback = creation_start_callback
        self.creation_done_callback = creation_done_callback
        self.creation_cancel_callback = creation_cancel_callback

        if embedded:
            # Embedded mode: root_or_frame is the parent frame
            self.root = root_or_frame.winfo_toplevel()
            self.parent = root_or_frame
        else:
            # Standalone mode: root_or_frame is the Tk root
            self.root = root_or_frame
            self.parent = root_or_frame
            self.root.title("Project Tracker")
            self.root.geometry("1000x700")
            self.root.minsize(800, 600)

        # Initialize database
        self.db = ProjectDatabase()

        # Initialize settings
        self.settings = TrackerSettings()

        # Current selection
        self.selected_project = None
        self.selected_category = None  # Track selected category
        self.tree_item_to_project = {}  # Map tree items to project data

        # Path tracking for clipboard copy
        self._current_active_path = None
        self._current_raw_path = None

        # Column sorting and ordering (load from settings)
        self.sort_column = self.settings.get("sort_column", "date")
        self.sort_reverse = self.settings.get("sort_reverse", True)  # True = descending (newest first)
        self.column_order = self.settings.get("column_order", ["date", "client", "project"])

        # Column drag state
        self._drag_column = None
        self._drag_start_x = None

        # Grid view selection tracking
        self.grid_selected_index = -1
        self.grid_cards = []  # List of card frames for keyboard navigation
        self.grid_projects = []  # List of projects in grid order
        self.grid_cols = 1  # Current number of columns

        # Filter status (load from settings)
        self.filter_status = tk.StringVar(value=self.settings.get("filter_status", "active"))

        # Scope filter (all/personal/client)
        self.filter_scope = tk.StringVar(value=self.settings.get("filter_scope", "all"))
        self.scope_buttons = {}

        # Search query
        self.search_query = tk.StringVar()
        self.search_query.trace('w', self._on_search_changed)

        # Category buttons storage
        self.category_buttons = {}

        # Creation panel state management
        self.view_state = "PROJECT_LIST"  # "PROJECT_LIST", "SUBTYPE_SELECTION", "CREATION_FORM"
        self.creation_panel = None  # Frame for creation panel
        self.active_creator = None  # Current embedded creator instance
        self.fab_button = None  # Floating action button

        # Subtype selection state (for keyboard navigation)
        self.subtype_buttons = []
        self.subtype_selected_index = 0
        self.subtype_category = None

        # Build UI
        self._build_ui()

        # Apply saved settings after UI is built
        self._apply_saved_settings()

        # Load projects
        self.refresh_project_list()

        logger.info("Project Tracker initialized")

    def _build_ui(self):
        """Build the user interface."""
        if not self.embedded:
            # Header (only for standalone mode)
            self._build_header()

        # Main content area
        main_frame = tk.Frame(self.parent, bg="#0d1117", highlightthickness=0, bd=0)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Left panel (project list)
        self._build_left_panel(main_frame)

        # Right panel (details)
        self._build_right_panel(main_frame)

    def _build_header(self):
        """Build header section."""
        header_frame = tk.Frame(self.root, bg="#2c3e50", height=60)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        title_label = tk.Label(
            header_frame,
            text="📊 Project Tracker",
            font=("Arial", 16, "bold"),
            fg="white",
            bg="#2c3e50"
        )
        title_label.pack(side=tk.LEFT, padx=20, pady=15)

    def _build_left_panel(self, parent):
        """Build left panel with category buttons (standalone mode only)."""
        # When embedded, skip entirely - categories handled by main pipeline UI
        if self.embedded:
            return

        # Full left panel with category buttons (standalone mode)
        left_frame = tk.Frame(parent, width=200, bg="#0d1117")
        left_frame.pack(side=tk.LEFT, fill=tk.Y, pady=5, padx=(5, 0))
        left_frame.pack_propagate(False)

        # Title - clickable to show all projects
        title_label = tk.Label(left_frame, text="Categories", bg="#0d1117", fg="white",
                              font=("Arial", 12, "bold"), cursor="hand2")
        title_label.pack(pady=(10, 15), padx=10)
        title_label.bind('<Button-1>', lambda e: self._clear_category_selection())

        # Category buttons frame
        buttons_frame = tk.Frame(left_frame, bg="#0d1117")
        buttons_frame.pack(fill=tk.BOTH, expand=True, padx=10)

        # Define categories in unified order: Visual, RealTime, Audio, Physical, Photo, Web
        categories = [
            ("Visual", "🎬", CATEGORY_COLORS["Visual"]),
            ("RealTime", "⚡", CATEGORY_COLORS["RealTime"]),
            ("Audio", "🎵", CATEGORY_COLORS["Audio"]),
            ("Physical", "🔧", CATEGORY_COLORS["Physical"]),
            ("Photo", "📷", CATEGORY_COLORS["Photo"]),
            ("Web", "🌐", CATEGORY_COLORS["Web"]),
        ]

        # Create category buttons in grid (2 columns)
        for idx, (name, icon, color) in enumerate(categories):
            row = idx // 2
            col = idx % 2

            # Use highlightthickness for selection border (doesn't shift layout)
            btn_frame = tk.Frame(buttons_frame, bg=color, relief=tk.FLAT, cursor="hand2",
                                highlightthickness=3, highlightbackground="#0d1117")
            btn_frame.grid(row=row, column=col, padx=2, pady=5, sticky="nsew")

            # Store reference
            self.category_buttons[name] = {"frame": btn_frame, "color": color}

            # Icon and name
            icon_label = tk.Label(btn_frame, text=icon, bg=color, fg="white", font=("Arial", 24))
            icon_label.pack(pady=(10, 2))

            name_label = tk.Label(btn_frame, text=name, bg=color, fg="white", font=("Arial", 9, "bold"))
            name_label.pack(pady=(0, 2))

            # Count label
            count_label = tk.Label(btn_frame, text="(0)", bg=color, fg="white", font=("Arial", 8))
            count_label.pack(pady=(0, 10))

            # Store count label
            self.category_buttons[name]["count_label"] = count_label

            # Click handler
            def make_click_handler(cat_name):
                return lambda e: self._select_category(cat_name)

            click_handler = make_click_handler(name)

            for widget in (btn_frame, icon_label, name_label, count_label):
                widget.bind('<Button-1>', click_handler)

        # Configure grid weights
        buttons_frame.columnconfigure(0, weight=1)
        buttons_frame.columnconfigure(1, weight=1)

        # Spacer
        tk.Frame(left_frame, bg="#0d1117", height=20).pack()

        # Bottom buttons
        import_btn = tk.Button(
            left_frame,
            text="📥 Import",
            command=self._import_projects,
            bg="#238636",
            fg="white",
            font=("Arial", 9, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            pady=8
        )
        import_btn.pack(fill=tk.X, padx=10, pady=5)

        refresh_btn = tk.Button(
            left_frame,
            text="🔄 Refresh",
            command=self.refresh_project_list,
            bg="#1c2128",
            fg="white",
            font=("Arial", 9),
            relief=tk.FLAT,
            cursor="hand2",
            pady=6
        )
        refresh_btn.pack(fill=tk.X, padx=10, pady=5)

    def _build_right_panel(self, parent):
        """Build right panel with project list and details."""
        right_frame = tk.Frame(parent, bg="#0d1117", highlightthickness=0, bd=0)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(0, 5), pady=5)

        # Top: Search and filter
        controls_frame = tk.Frame(right_frame, bg="#0d1117")
        controls_frame.pack(fill=tk.X, padx=10, pady=10)

        # Search
        search_label = tk.Label(controls_frame, text="Search:", bg="#0d1117", fg="white", font=("Arial", 9))
        search_label.grid(row=0, column=0, sticky=tk.W, pady=5)

        self.search_entry = tk.Entry(controls_frame, textvariable=self.search_query, bg="#1c2128", fg="white",
                               insertbackground="white", font=("Arial", 10), width=30)
        self.search_entry.grid(row=0, column=1, sticky=tk.W, padx=(5, 15), pady=5)

        # Search hint on hover
        def on_search_enter(e):
            if self.hint_callback:
                self.hint_callback("Shortcut: Ctrl+F or /")

        def on_search_leave(e):
            if self.hint_callback:
                self.hint_callback("")

        search_label.bind("<Enter>", on_search_enter)
        search_label.bind("<Leave>", on_search_leave)
        self.search_entry.bind("<Enter>", on_search_enter)
        self.search_entry.bind("<Leave>", on_search_leave)

        # Filter buttons frame
        filter_frame = tk.Frame(controls_frame, bg="#0d1117")
        filter_frame.grid(row=0, column=2, columnspan=2, sticky=tk.W, padx=(15, 0), pady=5)

        # Store filter buttons for styling updates
        self.filter_buttons = {}

        def create_filter_button(parent, text, value, shortcut):
            """Create a filter toggle button."""
            btn = tk.Label(
                parent,
                text=text,
                font=("Arial", 9),
                fg="white",
                bg="#1c2128",
                padx=12,
                pady=4,
                cursor="hand2"
            )
            btn.pack(side=tk.LEFT, padx=(0, 2))

            def on_click(e):
                self.filter_status.set(value)
                self._on_filter_changed()

            def on_enter(e):
                if self.filter_status.get() != value:
                    btn.configure(bg="#2d333b")
                # Show shortcut hint
                if self.hint_callback:
                    self.hint_callback(f"Shortcut: {shortcut}")

            def on_leave(e):
                if self.filter_status.get() != value:
                    btn.configure(bg="#1c2128")
                # Clear shortcut hint
                if self.hint_callback:
                    self.hint_callback("")

            btn.bind("<Button-1>", on_click)
            btn.bind("<Enter>", on_enter)
            btn.bind("<Leave>", on_leave)

            self.filter_buttons[value] = btn
            return btn

        create_filter_button(filter_frame, "Active", "active", "4")
        create_filter_button(filter_frame, "Archive", "archived", "5")
        create_filter_button(filter_frame, "All", "all", "6")

        # Update initial button styling
        self._update_filter_button_styles()

        # Project count
        self.count_label = tk.Label(controls_frame, text="Projects (0)", bg="#0d1117", fg="#8b949e",
                                    font=("Arial", 9))
        self.count_label.grid(row=0, column=4, sticky=tk.E, padx=(15, 0), pady=5)

        controls_frame.columnconfigure(4, weight=1)

        # Middle: Project list header with view toggle
        list_header = tk.Frame(right_frame, bg="#0d1117")
        list_header.pack(fill=tk.X, padx=10, pady=(5, 5))

        list_label = tk.Label(list_header, text="Projects", bg="#0d1117", fg="white",
                            font=("Arial", 10, "bold"))
        list_label.pack(side=tk.LEFT)

        # View toggle buttons
        self.view_mode = tk.StringVar(value="list")

        grid_btn = tk.Radiobutton(list_header, text="⊞", variable=self.view_mode, value="grid",
                                  bg="#0d1117", fg="white", selectcolor="#1c2128",
                                  indicatoron=False, padx=8, pady=2, font=("Arial", 12),
                                  command=self._switch_view)
        grid_btn.pack(side=tk.RIGHT, padx=2)

        list_btn = tk.Radiobutton(list_header, text="≡", variable=self.view_mode, value="list",
                                  bg="#0d1117", fg="white", selectcolor="#1c2128",
                                  indicatoron=False, padx=8, pady=2, font=("Arial", 12),
                                  command=self._switch_view)
        list_btn.pack(side=tk.RIGHT, padx=2)

        # Separate scale sliders for list and grid views
        self.list_scale_value = tk.IntVar(value=100)
        self.grid_scale_value = tk.IntVar(value=100)

        # List scale slider (shown when list view active)
        self.list_scale_frame = tk.Frame(list_header, bg="#0d1117")
        list_scale_label = tk.Label(self.list_scale_frame, text="Size:", bg="#0d1117", fg="#8b949e",
                                   font=("Arial", 8))
        list_scale_label.pack(side=tk.LEFT, padx=(0, 2))
        self.list_scale_slider = tk.Scale(self.list_scale_frame, from_=50, to=150, orient=tk.HORIZONTAL,
                                         variable=self.list_scale_value, command=self._on_list_scale_changed,
                                         bg="#0d1117", fg="white", highlightthickness=0,
                                         troughcolor="#1c2128", activebackground="#58a6ff",
                                         length=80, showvalue=False, sliderlength=15)
        self.list_scale_slider.pack(side=tk.LEFT)
        self.list_scale_frame.pack(side=tk.RIGHT, padx=(10, 2))

        # Grid scale slider (shown when grid view active)
        self.grid_scale_frame = tk.Frame(list_header, bg="#0d1117")
        grid_scale_label = tk.Label(self.grid_scale_frame, text="Size:", bg="#0d1117", fg="#8b949e",
                                   font=("Arial", 8))
        grid_scale_label.pack(side=tk.LEFT, padx=(0, 2))
        self.grid_scale_slider = tk.Scale(self.grid_scale_frame, from_=100, to=225, orient=tk.HORIZONTAL,
                                         variable=self.grid_scale_value, command=self._on_grid_scale_changed,
                                         bg="#0d1117", fg="white", highlightthickness=0,
                                         troughcolor="#1c2128", activebackground="#58a6ff",
                                         length=80, showvalue=False, sliderlength=15)
        self.grid_scale_slider.pack(side=tk.LEFT)
        # Grid slider hidden by default (list view is default)

        # Container for both views
        self.view_container = tk.Frame(right_frame, bg="#0d1117", highlightthickness=0, bd=0)
        self.view_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # === LIST VIEW ===
        self.list_frame = tk.Frame(self.view_container, bg="#0d1117", highlightthickness=0, bd=0)

        # Wrapper frame to hide any white edges from treeview
        tree_wrapper = tk.Frame(self.list_frame, bg="#0d1117", highlightthickness=0, bd=0)
        tree_wrapper.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(tree_wrapper)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Treeview styling - dark theme to match container
        self.tree_style = ttk.Style()
        # Use 'clam' theme for better control over colors
        try:
            self.tree_style.theme_use('clam')
        except:
            pass

        # Style scrollbars to be dark
        self.tree_style.configure("Vertical.TScrollbar",
                       background="#1c2128",
                       troughcolor="#0d1117",
                       bordercolor="#0d1117",
                       arrowcolor="#8b949e")

        # Base row height (scaled later)
        self.base_row_height = 32

        self.tree_style.configure("Dark.Treeview",
                       background="#0d1117",
                       foreground="white",
                       fieldbackground="#0d1117",
                       borderwidth=0,
                       rowheight=self.base_row_height)
        self.tree_style.configure("Dark.Treeview.Heading",
                       background="#1c2128",
                       foreground="white",
                       font=("Arial", 10, "bold"))
        self.tree_style.map("Dark.Treeview",
                 background=[("selected", "#2d333b")],
                 foreground=[("selected", "white")])
        # Remove the border/focus highlight
        self.tree_style.layout("Dark.Treeview", [('Dark.Treeview.treearea', {'sticky': 'nswe'})])

        self.project_tree = ttk.Treeview(
            tree_wrapper,
            columns=("date", "client", "project"),
            displaycolumns=self.column_order,
            show="headings",
            yscrollcommand=scrollbar.set,
            selectmode="browse",
            style="Dark.Treeview"
        )

        # Column display names
        self.column_names = {"date": "Date", "client": "Client", "project": "Project"}

        # Configure columns with sort click handlers - equal widths, all stretch equally
        for col in ["date", "client", "project"]:
            self.project_tree.heading(col, text=self._get_column_header(col), anchor=tk.W,
                                      command=lambda c=col: self._on_column_click(c))
            self.project_tree.column(col, width=150, minwidth=80, stretch=True)

        self.project_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.project_tree.yview)

        # Bind column header drag events
        self.project_tree.bind('<Button-1>', self._on_tree_click)
        self.project_tree.bind('<B1-Motion>', self._on_tree_drag)
        self.project_tree.bind('<ButtonRelease-1>', self._on_tree_release)

        # Store project IDs mapped to tree items
        self.tree_item_to_project = {}
        self.project_tree.bind('<<TreeviewSelect>>', self._on_project_selected)
        self.project_tree.bind('<Return>', self._on_enter_key)
        self.project_tree.bind('<Double-1>', self._on_enter_key)

        # === GRID VIEW ===
        self.grid_frame = tk.Frame(self.view_container, bg="#0d1117", highlightthickness=0, bd=0)

        # Canvas with scrollbar for grid
        self.grid_canvas = tk.Canvas(self.grid_frame, bg="#0d1117", highlightthickness=0, bd=0, takefocus=True)
        grid_scrollbar = ttk.Scrollbar(self.grid_frame, orient=tk.VERTICAL, command=self.grid_canvas.yview)
        self.grid_inner = tk.Frame(self.grid_canvas, bg="#0d1117", highlightthickness=0, bd=0)

        self.grid_canvas.configure(yscrollcommand=grid_scrollbar.set)
        grid_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.grid_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.grid_window = self.grid_canvas.create_window((0, 0), window=self.grid_inner, anchor="nw")

        # Bind resize and scroll events
        self.grid_inner.bind("<Configure>", lambda e: self.grid_canvas.configure(scrollregion=self.grid_canvas.bbox("all")))
        self.grid_canvas.bind("<Configure>", self._on_grid_canvas_resize)

        # Keyboard navigation for grid view
        self.grid_canvas.bind('<Left>', self._on_grid_left)
        self.grid_canvas.bind('<Right>', self._on_grid_right)
        self.grid_canvas.bind('<Up>', self._on_grid_up)
        self.grid_canvas.bind('<Down>', self._on_grid_down)
        self.grid_canvas.bind('<Return>', self._on_enter_key)
        # Mousewheel binding - different on Windows vs Linux
        self.grid_canvas.bind_all("<MouseWheel>", self._on_grid_mousewheel)
        self.grid_canvas.bind_all("<Button-4>", self._on_grid_mousewheel)  # Linux scroll up
        self.grid_canvas.bind_all("<Button-5>", self._on_grid_mousewheel)  # Linux scroll down

        # Show list view by default
        self.list_frame.pack(fill=tk.BOTH, expand=True)

        # Bottom: Project details (store reference for hiding during creation)
        self.details_frame = tk.Frame(right_frame, bg="#1c2128")
        self.details_frame.pack(fill=tk.X, padx=10, pady=10)

        details_title = tk.Label(self.details_frame, text="Selected Project", bg="#1c2128", fg="white",
                                font=("Arial", 10, "bold"))
        details_title.pack(anchor=tk.W, padx=10, pady=(10, 5))

        # Detail labels
        self.detail_labels = {}
        detail_fields = [
            ("Client", "client_name"),
            ("Project", "project_name"),
            ("Type", "project_type"),
            ("Date", "date_created"),
        ]

        details_grid = tk.Frame(self.details_frame, bg="#1c2128")
        details_grid.pack(fill=tk.X, padx=10, pady=5)

        for i, (label, key) in enumerate(detail_fields):
            tk.Label(details_grid, text=f"{label}:", bg="#1c2128", fg="#8b949e",
                    font=("Arial", 8)).grid(row=i, column=0, sticky=tk.W, pady=2)

            value_label = tk.Label(details_grid, text="-", bg="#1c2128", fg="white",
                                  font=("Arial", 9))
            value_label.grid(row=i, column=1, sticky=tk.W, pady=2, padx=(10, 0))

            self.detail_labels[key] = value_label

        # Path section with clickable copy-to-clipboard
        path_section = tk.Frame(self.details_frame, bg="#1c2128")
        path_section.pack(fill=tk.X, padx=10, pady=(5, 0))

        # Active Path (only shown for active projects)
        self.active_path_frame = tk.Frame(path_section, bg="#1c2128")
        self.active_path_frame.pack(fill=tk.X, pady=2)

        tk.Label(self.active_path_frame, text="Active Path:", bg="#1c2128", fg="#8b949e",
                font=("Arial", 8), width=10, anchor="w").pack(side=tk.LEFT)

        self.active_path_label = tk.Label(
            self.active_path_frame, text="-", bg="#1c2128", fg="#58a6ff",
            font=("Arial", 9), cursor="hand2", anchor="w"
        )
        self.active_path_label.pack(side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True)
        self.active_path_label.bind("<Button-1>", lambda e: self._copy_path_to_clipboard("active"))
        self.active_path_label.bind("<Enter>", lambda e: self.active_path_label.configure(fg="#79c0ff"))
        self.active_path_label.bind("<Leave>", lambda e: self.active_path_label.configure(fg="#58a6ff"))

        # RAW Path (always shown)
        raw_path_frame = tk.Frame(path_section, bg="#1c2128")
        raw_path_frame.pack(fill=tk.X, pady=2)

        tk.Label(raw_path_frame, text="RAW Path:", bg="#1c2128", fg="#8b949e",
                font=("Arial", 8), width=10, anchor="w").pack(side=tk.LEFT)

        self.raw_path_label = tk.Label(
            raw_path_frame, text="-", bg="#1c2128", fg="#58a6ff",
            font=("Arial", 9), cursor="hand2", anchor="w"
        )
        self.raw_path_label.pack(side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True)
        self.raw_path_label.bind("<Button-1>", lambda e: self._copy_path_to_clipboard("raw"))
        self.raw_path_label.bind("<Enter>", lambda e: self.raw_path_label.configure(fg="#79c0ff"))
        self.raw_path_label.bind("<Leave>", lambda e: self.raw_path_label.configure(fg="#58a6ff"))

        # Action buttons
        button_frame = tk.Frame(self.details_frame, bg="#1c2128")
        button_frame.pack(fill=tk.X, padx=10, pady=(10, 10))

        self.open_btn = tk.Button(
            button_frame,
            text="📂 Open Folder",
            command=self._open_folder,
            bg="#238636",
            fg="white",
            font=("Arial", 9),
            relief=tk.FLAT,
            cursor="hand2",
            state=tk.DISABLED,
            padx=15,
            pady=6
        )
        self.open_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.archive_btn = tk.Button(
            button_frame,
            text="📦 Archive",
            command=self._archive_project,
            bg="#1c2128",
            fg="white",
            font=("Arial", 9),
            relief=tk.FLAT,
            cursor="hand2",
            state=tk.DISABLED,
            padx=15,
            pady=6
        )
        self.archive_btn.pack(side=tk.LEFT, padx=5)

        self.unarchive_btn = tk.Button(
            button_frame,
            text="📤 Un-Archive",
            command=self._unarchive_project,
            bg="#1c2128",
            fg="white",
            font=("Arial", 9),
            relief=tk.FLAT,
            cursor="hand2",
            state=tk.DISABLED,
            padx=15,
            pady=6
        )
        self.unarchive_btn.pack(side=tk.LEFT, padx=5)

        # Store reference to right frame for FAB positioning
        self.right_frame = right_frame

        # Create the Floating Action Button (FAB) - positioned over view_container
        self._create_fab_button()

    def _create_fab_button(self):
        """Create the floating action button for project creation."""
        # Create FAB as a fixed-size frame with label for precise control
        fab_size = 44  # Square size in pixels

        self.fab_button = tk.Frame(
            self.view_container,
            width=fab_size,
            height=fab_size,
            bg="#3fb950",
            cursor="hand2"
        )
        self.fab_button.pack_propagate(False)  # Prevent resizing based on content

        # Label with big plus sign centered in the frame
        self.fab_label = tk.Label(
            self.fab_button,
            text="+",
            font=("Arial", 34, "bold"),
            bg="#3fb950",
            fg="white",
            cursor="hand2"
        )
        self.fab_label.place(relx=0.5, rely=0.5, anchor="center")

        # Bind click events to both frame and label (use ButtonRelease for reliability)
        self.fab_button.bind("<ButtonRelease-1>", lambda e: self._on_fab_clicked())
        self.fab_label.bind("<ButtonRelease-1>", lambda e: self._on_fab_clicked())

        # Hover effects
        def on_enter(e):
            self.fab_button.configure(bg="#2ea043")
            self.fab_label.configure(bg="#2ea043")
            if self.hint_callback:
                self.hint_callback("Shortcut: Ctrl+N")

        def on_leave(e):
            self.fab_button.configure(bg="#3fb950")
            self.fab_label.configure(bg="#3fb950")
            if self.hint_callback:
                self.hint_callback("")

        self.fab_button.bind("<Enter>", on_enter)
        self.fab_button.bind("<Leave>", on_leave)
        self.fab_label.bind("<Enter>", on_enter)
        self.fab_label.bind("<Leave>", on_leave)

        # Position in bottom-right corner of view_container (above details panel)
        self.fab_button.place(relx=0.97, rely=0.97, anchor="se")

        # Update FAB visibility based on current category
        self._update_fab_visibility()

    def _update_fab_visibility(self):
        """Show/hide FAB based on current category and view state."""
        if self.fab_button is None:
            return

        # Hide FAB when in creation mode
        if self.view_state != "PROJECT_LIST":
            self.fab_button.place_forget()
            return

        # Show FAB only for creative categories (not Business/Global)
        if self.selected_category and is_creative_category(self.selected_category):
            # Position in bottom-right corner of view_container (above details panel)
            self.fab_button.place(relx=0.97, rely=0.97, anchor="se")
            self.fab_button.lift()  # Ensure FAB stays on top
            self.fab_label.lift()   # Also lift the label
        elif self.selected_category is None:
            # When no category selected (showing all), hide FAB
            self.fab_button.place_forget()
        else:
            self.fab_button.place_forget()

    def _on_fab_clicked(self):
        """Handle FAB button click."""
        # Prevent opening multiple panels - only allow one structure panel at a time
        if self.view_state != "PROJECT_LIST":
            return

        if not self.selected_category:
            messagebox.showinfo("Select Category", "Please select a category first.")
            return

        if not is_creative_category(self.selected_category):
            return

        # Notify parent that creation is starting
        if self.creation_start_callback:
            self.creation_start_callback()

        # Check if category has multiple subtypes
        if has_multiple_subtypes(self.selected_category):
            self._show_subtype_selection(self.selected_category)
        else:
            # Single subtype - open form directly
            subtypes = get_subtypes_for_category(self.selected_category)
            if subtypes:
                self._open_creation_form(self.selected_category, subtypes[0])

    def _show_subtype_selection(self, category):
        """Show panel with subtype selection buttons."""
        self.view_state = "SUBTYPE_SELECTION"
        self._update_fab_visibility()

        # Hide the view container (list/grid views) and details panel
        self.view_container.pack_forget()
        self.details_frame.pack_forget()

        # Create selection panel
        self.creation_panel = tk.Frame(self.right_frame, bg="#1c2128")
        self.creation_panel.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Header with back button and category color
        header_color = CATEGORY_COLORS.get(category, "#1c2128")
        header = tk.Frame(self.creation_panel, bg=header_color, height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        back_btn = tk.Button(
            header,
            text="< Back",
            font=("Arial", 10),
            bg=header_color,
            fg="white",
            activebackground=header_color,
            activeforeground="#cccccc",
            relief=tk.FLAT,
            cursor="hand2",
            command=self._close_creation_panel
        )
        back_btn.pack(side=tk.LEFT, padx=10, pady=10)

        header_label = tk.Label(
            header,
            text=f"Create New {category} Project",
            font=("Arial", 14, "bold"),
            fg="white",
            bg=header_color
        )
        header_label.pack(pady=15)

        # Buttons container - horizontal layout
        buttons_frame = tk.Frame(self.creation_panel, bg="#1c2128")
        buttons_frame.pack(expand=True, pady=30)

        # Store subtype buttons for keyboard navigation
        self.subtype_buttons = []
        self.subtype_selected_index = 0
        self.subtype_category = category

        # Create buttons for each subtype - horizontally spaced
        subtypes = get_subtypes_for_category(category)
        for idx, subtype in enumerate(subtypes):
            display_name = get_subtype_display_name(subtype)
            btn = tk.Button(
                buttons_frame,
                text=display_name,
                font=("Arial", 12),
                bg="#238636",
                fg="white",
                activebackground="#2ea043",
                activeforeground="white",
                relief=tk.FLAT,
                cursor="hand2",
                padx=20,
                pady=10,
                command=lambda s=subtype: self._open_creation_form(category, s)
            )
            btn.pack(side=tk.LEFT, padx=10)
            self.subtype_buttons.append({"button": btn, "subtype": subtype})

        # Highlight first button by default
        self._update_subtype_selection()

        # Bind keyboard navigation to the creation panel
        self.creation_panel.bind('<Left>', self._on_subtype_left)
        self.creation_panel.bind('<Right>', self._on_subtype_right)
        self.creation_panel.bind('<Return>', self._on_subtype_enter)
        self.creation_panel.focus_set()

    def _update_subtype_selection(self):
        """Update visual highlighting for subtype selection."""
        for idx, item in enumerate(self.subtype_buttons):
            if idx == self.subtype_selected_index:
                # Highlighted - darker green with border
                item["button"].configure(bg="#2ea043", highlightbackground="white", highlightthickness=2)
            else:
                # Normal green
                item["button"].configure(bg="#238636", highlightthickness=0)

    def _on_subtype_left(self, event):
        """Navigate left in subtype selection."""
        if self.subtype_buttons and self.subtype_selected_index > 0:
            self.subtype_selected_index -= 1
            self._update_subtype_selection()
        return "break"  # Stop event propagation

    def _on_subtype_right(self, event):
        """Navigate right in subtype selection."""
        if self.subtype_buttons and self.subtype_selected_index < len(self.subtype_buttons) - 1:
            self.subtype_selected_index += 1
            self._update_subtype_selection()
        return "break"  # Stop event propagation

    def _on_subtype_enter(self, event):
        """Select current subtype and open creation form."""
        if self.subtype_buttons and 0 <= self.subtype_selected_index < len(self.subtype_buttons):
            subtype = self.subtype_buttons[self.subtype_selected_index]["subtype"]
            self._open_creation_form(self.subtype_category, subtype)
        return "break"  # Stop event propagation

    def _open_creation_form(self, category, subtype):
        """Open the embedded creation form for a specific subtype."""
        self.view_state = "CREATION_FORM"
        self._update_fab_visibility()

        # Clear any existing creation panel (subtype selection)
        if self.creation_panel:
            self.creation_panel.destroy()
            self.creation_panel = None

        # Hide the view container (list/grid views) and details panel
        self.view_container.pack_forget()
        self.details_frame.pack_forget()

        # Create form panel
        self.creation_panel = tk.Frame(self.right_frame, bg="#1c2128")
        self.creation_panel.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Header with back button
        header_color = CATEGORY_COLORS.get(category, "#1c2128")
        header = tk.Frame(self.creation_panel, bg=header_color, height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        back_btn = tk.Button(
            header,
            text="< Back",
            font=("Arial", 10),
            bg=header_color,
            fg="white",
            activebackground=header_color,
            activeforeground="#cccccc",
            relief=tk.FLAT,
            cursor="hand2",
            command=self._close_creation_panel
        )
        back_btn.pack(side=tk.LEFT, padx=10, pady=10)

        display_name = get_subtype_display_name(subtype)
        header_label = tk.Label(
            header,
            text=f"New {display_name} Project",
            font=("Arial", 14, "bold"),
            fg="white",
            bg=header_color
        )
        header_label.pack(pady=15)

        # Form container frame
        form_container = tk.Frame(self.creation_panel, bg="#0d1117")
        form_container.pack(fill=tk.BOTH, expand=True)

        # Get the creator class and instantiate it in embedded mode
        creator_class = get_creator_class(category, subtype)
        if creator_class:
            try:
                self.active_creator = creator_class(
                    form_container,
                    embedded=True,
                    on_project_created=self._on_project_created,
                    on_cancel=self._close_creation_panel,
                    project_db=self.db
                )
            except Exception as e:
                logger.error(f"Failed to create embedded form: {e}")
                messagebox.showerror("Error", f"Failed to open creation form: {e}")
                self._close_creation_panel()
        else:
            logger.error(f"Creator class not found for {category}/{subtype}")
            messagebox.showerror("Error", f"Creator not found for {category}/{subtype}")
            self._close_creation_panel()

    def _on_project_created(self, project_data):
        """Handle successful project creation from embedded form."""
        logger.info(f"Project created: {project_data.get('project_name')}")

        # Close creation panel without notifying cancel
        self._close_creation_panel(notify_cancel=False)

        # Show success message
        self._update_status(f"Created project: {project_data.get('project_name')}")

        # Register project in database (centralized for all categories)
        if self.db and project_data:
            try:
                project_id = self.db.register_project(project_data)
                logger.info(f"Registered project in database: {project_id}")
            except Exception as e:
                logger.error(f"Failed to register project in database: {e}")

        # Notify parent that creation is done — parent handles
        # filter switching, refresh, and project selection
        if self.creation_done_callback:
            self.creation_done_callback(project_data)

    def _get_category_for_type(self, project_type: str) -> Optional[str]:
        """Map a project_type string to its tracker category."""
        if project_type in ("GD", "FX", "VFX", "VJ") or project_type.startswith("Visual-"):
            return "Visual"
        elif project_type == "Audio":
            return "Audio"
        elif project_type == "Physical":
            return "Physical"
        elif project_type in ("Godot", "TD", "RealTime"):
            return "RealTime"
        elif project_type == "Photo":
            return "Photo"
        elif project_type == "Web":
            return "Web"
        return None

    def _select_project_by_path(self, path: str):
        """Select a project by its path in whichever view is active.

        Matches by folder name (basename) since paths may differ in format
        between WSL (/mnt/d/...) and Windows (D:\\...) representations.
        """
        if not path:
            return
        # Match by folder name to avoid WSL vs Windows path format issues
        target_basename = os.path.basename(path.replace('\\', '/').rstrip('/'))
        logger.debug(f"_select_project_by_path: looking for basename '{target_basename}'")

        if self.view_mode.get() == "grid":
            for idx, project in enumerate(self.grid_projects):
                project_path = project.get('path', '').replace('\\', '/')
                if os.path.basename(project_path.rstrip('/')) == target_basename:
                    logger.debug(f"_select_project_by_path: found at grid index {idx}")
                    self.grid_selected_index = idx
                    self._select_grid_card(idx)
                    return
            logger.debug(f"_select_project_by_path: not found in {len(self.grid_projects)} grid projects")
        else:
            for item_id, project in self.tree_item_to_project.items():
                project_path = project.get('path', '').replace('\\', '/')
                if os.path.basename(project_path.rstrip('/')) == target_basename:
                    self.project_tree.selection_set(item_id)
                    self.project_tree.see(item_id)
                    self.selected_project = project
                    self._display_project_details(project)
                    return

    def _close_creation_panel(self, notify_cancel=True):
        """Close the creation panel and return to project list.

        Args:
            notify_cancel: If True, notify parent that creation was cancelled.
                          Set to False when called after successful creation.
        """
        # Clean up creator
        self.active_creator = None

        # Clean up subtype selection state
        self.subtype_buttons = []
        self.subtype_selected_index = 0
        self.subtype_category = None

        # Destroy creation panel
        if self.creation_panel:
            self.creation_panel.destroy()
            self.creation_panel = None

        # Reset state
        self.view_state = "PROJECT_LIST"

        # Show the view container and details panel again (in correct order)
        self.view_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.details_frame.pack(fill=tk.X, padx=10, pady=10)

        # Update FAB visibility
        self._update_fab_visibility()

        # Notify parent of cancellation
        if notify_cancel and self.creation_cancel_callback:
            self.creation_cancel_callback()

    def set_category(self, category_name: Optional[str]):
        """
        Set the selected category (public method for external use).

        Args:
            category_name: Category name or None to show all
        """
        # If in creation mode, close it first
        if self.view_state != "PROJECT_LIST":
            self._close_creation_panel(notify_cancel=False)

        self.selected_category = category_name

        # Update category button styles if in standalone mode
        for name, btn_info in self.category_buttons.items():
            self._update_category_card_style(btn_info, name)

        # Update FAB visibility based on new category
        self._update_fab_visibility()

        # Refresh project list for this category
        self.refresh_project_list()

    def _apply_saved_settings(self):
        """Apply saved settings after UI is built."""
        # Apply scale values
        saved_list_scale = self.settings.get("list_scale", 100)
        saved_grid_scale = self.settings.get("grid_scale", 100)

        self.list_scale_value.set(saved_list_scale)
        self.grid_scale_value.set(saved_grid_scale)

        # Apply list scale to treeview
        scale = saved_list_scale / 100.0
        new_row_height = int(self.base_row_height * scale)
        self.tree_style.configure("Dark.Treeview", rowheight=new_row_height)

        # Apply view mode
        saved_view_mode = self.settings.get("view_mode", "list")
        self.view_mode.set(saved_view_mode)

        # Switch to the saved view (without saving again)
        if saved_view_mode == "grid":
            self.list_frame.pack_forget()
            self.list_scale_frame.pack_forget()
            self.grid_frame.pack(fill=tk.BOTH, expand=True)
            self.grid_scale_frame.pack(side=tk.RIGHT, padx=(10, 2))

        # Update filter button styles based on saved filter
        self._update_filter_button_styles()

        logger.debug(f"Applied saved settings: view={saved_view_mode}, list_scale={saved_list_scale}, grid_scale={saved_grid_scale}")

    def _update_status(self, message: str, status_type: str = "info"):
        """Log status message to GUI and file logger."""
        logger.info(message)
        if self.status_callback:
            self.status_callback(message, status_type)

    def _select_category(self, category_name):
        """Handle category button selection."""
        # If in creation mode, close it first
        if self.view_state != "PROJECT_LIST":
            self._close_creation_panel(notify_cancel=False)

        self.selected_category = category_name

        # Update all button styles
        for name, btn_info in self.category_buttons.items():
            self._update_category_card_style(btn_info, name)

        # Update FAB visibility based on new category
        self._update_fab_visibility()

        # Refresh project list for this category
        self.refresh_project_list()

    def _update_category_card_style(self, btn_info, name):
        """Update category button styling based on selection state."""
        frame = btn_info["frame"]

        if name == self.selected_category:
            # Selected style - white highlight border
            frame.configure(highlightbackground="white")
        else:
            # Unselected style - blend with background
            frame.configure(highlightbackground="#0d1117")

    def _clear_category_selection(self):
        """Clear category selection to show all projects."""
        # If in creation mode, close it first
        if self.view_state != "PROJECT_LIST":
            self._close_creation_panel(notify_cancel=False)

        self.selected_category = None

        # Update all button styles
        for name, btn_info in self.category_buttons.items():
            self._update_category_card_style(btn_info, name)

        # Update FAB visibility (hidden when no category selected)
        self._update_fab_visibility()

        # Refresh project list to show all
        self.refresh_project_list()

    def refresh_project_list(self):
        """Refresh the project list from database based on selected category."""
        # Clear tree
        for item in self.project_tree.get_children():
            self.project_tree.delete(item)

        # Get filter status
        status = self.filter_status.get()

        # Get search query
        query = self.search_query.get().strip()

        # Get all projects first
        if query:
            projects = self.db.search_projects(query, include_archived=(status != "active"))
            if status == "archived":
                projects = [p for p in projects if p.get("status") == "archived"]
        else:
            if status == "all":
                projects = self.db.get_all_projects(status="all")
            else:
                projects = self.db.get_all_projects(status=status)

        # Filter by scope (personal/client) based on client name or is_personal metadata
        scope = self.filter_scope.get()
        if scope == "personal":
            projects = [p for p in projects if
                        p.get("client_name", "").lower() == "personal" or
                        p.get("metadata", {}).get("is_personal", False)]
        elif scope == "client":
            projects = [p for p in projects if
                        p.get("client_name", "").lower() != "personal" and
                        not p.get("metadata", {}).get("is_personal", False)]

        # Group projects by category
        categories = {
            "Visual": {"icon": "🎬", "projects": [], "color": CATEGORY_COLORS["Visual"]},
            "Audio": {"icon": "🎵", "projects": [], "color": CATEGORY_COLORS["Audio"]},
            "Physical": {"icon": "🔧", "projects": [], "color": CATEGORY_COLORS["Physical"]},
            "RealTime": {"icon": "⚡", "projects": [], "color": CATEGORY_COLORS["RealTime"]},
            "Photo": {"icon": "📷", "projects": [], "color": CATEGORY_COLORS["Photo"]},
            "Web": {"icon": "🌐", "projects": [], "color": CATEGORY_COLORS["Web"]},
        }

        # Categorize all projects
        for project in projects:
            project_type = project.get("project_type", "")

            # Map project types to categories
            if project_type in ["GD", "FX", "VFX", "VJ"] or project_type.startswith("Visual-"):
                categories["Visual"]["projects"].append(project)
            elif project_type == "Audio":
                categories["Audio"]["projects"].append(project)
            elif project_type == "Physical":
                categories["Physical"]["projects"].append(project)
            elif project_type in ["Godot", "TD", "RealTime"]:
                categories["RealTime"]["projects"].append(project)
            elif project_type == "Photo":
                categories["Photo"]["projects"].append(project)
            elif project_type == "Web":
                categories["Web"]["projects"].append(project)

        # Update category button counts
        for cat_name, cat_info in categories.items():
            if cat_name in self.category_buttons:
                btn_info = self.category_buttons[cat_name]
                count = len(cat_info["projects"])
                btn_info["count_label"].config(text=f"({count})")

        # Filter by selected category if one is selected
        if self.selected_category:
            category_projects = categories.get(self.selected_category, {}).get("projects", [])
        else:
            # No category selected - show all
            category_projects = []
            for cat_info in categories.values():
                category_projects.extend(cat_info["projects"])

        # Sort by selected column
        sort_key_map = {
            "date": lambda p: p.get("date_created", ""),
            "client": lambda p: p.get("client_name", "").lower(),
            "project": lambda p: p.get("project_name", "").lower()
        }
        sort_key = sort_key_map.get(self.sort_column, sort_key_map["date"])
        category_projects.sort(key=sort_key, reverse=self.sort_reverse)

        # Clear the project ID mapping
        self.tree_item_to_project = {}

        # Populate tree with flat list
        for project in category_projects:
            project_type = project.get("project_type", "")
            type_info = PROJECT_TYPES.get(project_type, {"icon": "📁", "name": project_type})

            # Get display values
            date_str = project.get("date_created", "")
            client_name = project.get("client_name", "")
            project_name = project.get('project_name', '')

            # Insert into tree
            item_id = self.project_tree.insert(
                "",
                tk.END,
                values=(date_str, client_name, project_name),
                tags=(project.get("status"),)
            )

            # Store mapping from tree item to project
            self.tree_item_to_project[item_id] = project

        # Update count label
        count = len(category_projects)
        if self.selected_category:
            self.count_label.config(text=f"({count})")
        else:
            self.count_label.config(text=f"({count})")

        logger.debug(f"Refreshed project list: {count} projects" +
                    (f" in {self.selected_category}" if self.selected_category else ""))

        # Also refresh grid view if it's currently visible
        if self.view_mode.get() == "grid":
            self._populate_grid()

    def _switch_view(self):
        """Switch between list and grid view."""
        view = self.view_mode.get()

        # Save view mode preference
        self.settings.set("view_mode", view)

        if view == "list":
            self.grid_frame.pack_forget()
            self.grid_scale_frame.pack_forget()
            self.list_frame.pack(fill=tk.BOTH, expand=True)
            self.list_scale_frame.pack(side=tk.RIGHT, padx=(10, 2))
            self.project_tree.focus_set()
            # Restore selection from selected_project
            if self.selected_project:
                for item_id, project in self.tree_item_to_project.items():
                    if project.get("id") == self.selected_project.get("id"):
                        self.project_tree.selection_set(item_id)
                        self.project_tree.see(item_id)
                        break
        else:
            self.list_frame.pack_forget()
            self.list_scale_frame.pack_forget()
            self.grid_frame.pack(fill=tk.BOTH, expand=True)
            self.grid_scale_frame.pack(side=tk.RIGHT, padx=(10, 2))
            self._populate_grid()
            # Set focus for keyboard navigation
            self.grid_canvas.focus_set()
            # Restore selection from selected_project
            if self.selected_project:
                for idx, project in enumerate(self.grid_projects):
                    if project.get("id") == self.selected_project.get("id"):
                        self.grid_selected_index = idx
                        self._select_grid_card(idx)
                        break
            elif self.grid_projects:
                # No selection, select first
                self.grid_selected_index = 0
                self._select_grid_card(0)

    def _on_list_scale_changed(self, value):
        """Handle list scale slider change - update row height."""
        scale = int(value) / 100.0  # Convert to multiplier (0.5 - 1.5)
        new_row_height = int(self.base_row_height * scale)
        self.tree_style.configure("Dark.Treeview", rowheight=new_row_height)
        # Save scale preference
        self.settings.set("list_scale", int(value))

    def _on_grid_scale_changed(self, value):
        """Handle grid scale slider change - repopulate grid."""
        # Save scale preference
        self.settings.set("grid_scale", int(value))
        if self.view_mode.get() == "grid":
            self._populate_grid()

    def _get_scaled_card_size(self) -> int:
        """Get card size based on current grid scale value."""
        base_card_size = 120
        scale = self.grid_scale_value.get() / 100.0
        return int(base_card_size * scale)

    def _on_grid_canvas_resize(self, event):
        """Handle grid canvas resize to adjust inner frame width and repopulate."""
        self.grid_canvas.itemconfig(self.grid_window, width=event.width)
        # Repopulate grid when resized to adjust number of columns
        if self.view_mode.get() == "grid" and self.tree_item_to_project:
            self._populate_grid()

    def _on_grid_mousewheel(self, event):
        """Handle mousewheel scrolling for grid view."""
        if self.view_mode.get() != "grid":
            return

        # Check if there's content to scroll
        try:
            bbox = self.grid_canvas.bbox("all")
            if bbox is None:
                return "break"

            # Get view and content dimensions
            view_height = self.grid_canvas.winfo_height()
            content_height = bbox[3] - bbox[1]

            # Only scroll if content is larger than view
            if content_height <= view_height:
                return "break"

            # Handle both Windows (MouseWheel) and Linux (Button-4/5) events
            if event.num == 4 or (hasattr(event, 'delta') and event.delta > 0):
                # Scroll up
                self.grid_canvas.yview_scroll(-1, "units")
            elif event.num == 5 or (hasattr(event, 'delta') and event.delta < 0):
                # Scroll down
                self.grid_canvas.yview_scroll(1, "units")

            return "break"
        except:
            return "break"

    def _populate_grid(self):
        """Populate the grid view with project cards."""
        # Reset grid tracking BEFORE destroying widgets
        self.grid_cards = []
        self.grid_projects = []

        # Clear existing grid items
        for widget in self.grid_inner.winfo_children():
            widget.destroy()

        # Get current projects (use the same data as list view)
        projects = list(self.tree_item_to_project.values())

        if not projects:
            no_projects = tk.Label(self.grid_inner, text="No projects found",
                                  bg="#0d1117", fg="#8b949e", font=("Arial", 11))
            no_projects.pack(pady=20)
            self.grid_selected_index = -1
            return

        # Calculate number of columns based on canvas width and scaled card size
        canvas_width = self.grid_canvas.winfo_width()
        card_size = self._get_scaled_card_size()
        padding = 16  # Total padding between cards
        self.grid_cols = max(1, canvas_width // (card_size + padding))

        # Create grid of project cards - use constant spacing (no weight distribution)
        for idx, project in enumerate(projects):
            row = idx // self.grid_cols
            col = idx % self.grid_cols

            card = self._create_project_card(project, row, col, card_size)
            self.grid_cards.append(card)
            self.grid_projects.append(project)

        # Restore selection if valid, otherwise select first
        if self.grid_selected_index >= len(self.grid_projects):
            self.grid_selected_index = 0 if self.grid_projects else -1

        # Highlight current selection
        if self.grid_selected_index >= 0:
            self._highlight_grid_card(self.grid_selected_index)

        # Ensure FAB stays on top after grid population
        if self.fab_button and self.view_state == "PROJECT_LIST":
            self.fab_button.lift()
            self.fab_label.lift()

    def _create_project_card(self, project: Dict, row: int, col: int, card_size: int = 120):
        """Create a single square project card for grid view."""
        project_type = project.get("project_type", "")
        type_info = PROJECT_TYPES.get(project_type, {"icon": "📁", "color": "#1c2128"})
        status = project.get("status", "active")

        # Scale factor for fonts based on card size (120 is base)
        font_scale = card_size / 120.0
        icon_size = max(16, int(24 * font_scale))
        name_size = max(7, int(8 * font_scale))
        small_size = max(6, int(7 * font_scale))

        # Truncation lengths scale with size
        name_max = max(8, int(12 * font_scale))
        client_max = max(6, int(10 * font_scale))

        # Card frame - fixed square size
        card = tk.Frame(self.grid_inner, bg="#1c2128", relief=tk.FLAT,
                       width=card_size, height=card_size, cursor="hand2")
        card.grid(row=row, column=col, padx=8, pady=8)
        card.grid_propagate(False)  # Keep fixed size
        card.pack_propagate(False)  # Keep fixed size

        # Add border for archived projects
        if status == "archived":
            card.configure(highlightbackground="#8b949e", highlightthickness=1)

        # Icon - scales with card size (folder icon for all types)
        icon_label = tk.Label(card, text="📁", bg="#1c2128", fg="white",
                             font=("Arial", icon_size))
        icon_label.pack(pady=(int(15 * font_scale), int(5 * font_scale)))

        # Project name - truncate based on card size
        project_name = project.get("project_name", "")[:name_max]
        if len(project.get("project_name", "")) > name_max:
            project_name += "..."
        name_label = tk.Label(card, text=project_name, bg="#1c2128", fg="white",
                             font=("Arial", name_size, "bold"), wraplength=card_size-10)
        name_label.pack(pady=(0, 2))

        # Client name - smaller
        client_name = project.get("client_name", "")[:client_max]
        if len(project.get("client_name", "")) > client_max:
            client_name += "..."
        client_label = tk.Label(card, text=client_name, bg="#1c2128", fg="#8b949e",
                               font=("Arial", small_size))
        client_label.pack(pady=(0, 2))

        # Date - compact format
        date_str = project.get("date_created", "")
        if len(date_str) > 7:
            date_str = date_str[2:]  # Remove century: 2025-12-29 -> 25-12-29
        date_label = tk.Label(card, text=date_str, bg="#1c2128",
                             fg="#8b949e", font=("Arial", small_size))
        date_label.pack()

        # Bind click event to all card elements
        # Store index in closure for click handler
        card_index = len(self.grid_cards)  # Current index (before this card is added)

        def on_card_click(e, p=project, idx=card_index):
            self.grid_selected_index = idx
            self.selected_project = p
            self._display_project_details(p)
            self._highlight_grid_card(idx)
            # Set focus to canvas for keyboard navigation
            self.grid_canvas.focus_set()

        def on_card_double_click(e, p=project, idx=card_index):
            self.grid_selected_index = idx
            self.selected_project = p
            self._open_folder()

        card.bind("<Button-1>", on_card_click)
        card.bind("<Double-1>", on_card_double_click)
        for child in card.winfo_children():
            child.bind("<Button-1>", on_card_click)
            child.bind("<Double-1>", on_card_double_click)

        return card

    def _highlight_grid_card(self, index: int):
        """Highlight the card at given index and unhighlight others."""
        for i, card in enumerate(self.grid_cards):
            # Check if card still exists
            if not card.winfo_exists():
                continue
            try:
                if i == index:
                    card.configure(bg="#2d333b")
                    for child in card.winfo_children():
                        child.configure(bg="#2d333b")
                else:
                    card.configure(bg="#1c2128")
                    for child in card.winfo_children():
                        child.configure(bg="#1c2128")
            except tk.TclError:
                continue

        # Scroll to make selected card visible
        if index >= 0 and index < len(self.grid_cards):
            card = self.grid_cards[index]
            # Check if card still exists
            if not card.winfo_exists():
                return
            try:
                # Get card position relative to canvas
                self.grid_canvas.update_idletasks()
                card_y = card.winfo_y()
                card_height = card.winfo_height()
                canvas_height = self.grid_canvas.winfo_height()

                # Get current scroll position
                bbox = self.grid_canvas.bbox("all")
                if bbox:
                    content_height = bbox[3] - bbox[1]
                    if content_height > canvas_height:
                        # Calculate visible region
                        scroll_top = self.grid_canvas.yview()[0] * content_height
                        scroll_bottom = scroll_top + canvas_height

                        # Scroll if card is outside visible region
                        if card_y < scroll_top:
                            self.grid_canvas.yview_moveto(card_y / content_height)
                        elif card_y + card_height > scroll_bottom:
                            self.grid_canvas.yview_moveto((card_y + card_height - canvas_height) / content_height)
            except tk.TclError:
                pass

    def _on_grid_left(self, event):
        """Navigate left in grid."""
        if not self.grid_projects:
            return "break"
        if self.grid_selected_index > 0:
            self.grid_selected_index -= 1
            self._select_grid_card(self.grid_selected_index)
        return "break"

    def _on_grid_right(self, event):
        """Navigate right in grid."""
        if not self.grid_projects:
            return "break"
        if self.grid_selected_index < len(self.grid_projects) - 1:
            self.grid_selected_index += 1
            self._select_grid_card(self.grid_selected_index)
        return "break"

    def _on_grid_up(self, event):
        """Navigate up in grid (previous row)."""
        if not self.grid_projects:
            return "break"
        new_index = self.grid_selected_index - self.grid_cols
        if new_index >= 0:
            self.grid_selected_index = new_index
            self._select_grid_card(self.grid_selected_index)
        return "break"

    def _on_grid_down(self, event):
        """Navigate down in grid (next row)."""
        if not self.grid_projects:
            return "break"
        new_index = self.grid_selected_index + self.grid_cols
        if new_index < len(self.grid_projects):
            self.grid_selected_index = new_index
            self._select_grid_card(self.grid_selected_index)
        return "break"

    def _select_grid_card(self, index: int):
        """Select card at index and update details."""
        if 0 <= index < len(self.grid_projects):
            self.selected_project = self.grid_projects[index]
            self._display_project_details(self.selected_project)
            self._highlight_grid_card(index)

    def _on_enter_key(self, event):
        """Handle Enter key to open selected project folder."""
        if self.selected_project:
            self._open_folder()
        return "break"

    def _on_search_changed(self, *args):
        """Handle search query change."""
        self.refresh_project_list()

    def _on_filter_changed(self, event=None):
        """Handle filter status change."""
        # Save filter preference
        self.settings.set("filter_status", self.filter_status.get())
        # Update button styles
        self._update_filter_button_styles()
        self.refresh_project_list()

    def _update_filter_button_styles(self):
        """Update filter button visual states based on current selection."""
        if not hasattr(self, 'filter_buttons'):
            return
        current = self.filter_status.get()
        for value, btn in self.filter_buttons.items():
            if value == current:
                # Selected state - highlighted
                btn.configure(bg="#58a6ff", fg="white")
            else:
                # Unselected state
                btn.configure(bg="#1c2128", fg="white")

    def set_scope(self, scope: str):
        """Set the scope filter (called from external UI like pipeline)."""
        self.filter_scope.set(scope)
        self._on_scope_changed()

    def _on_scope_changed(self, event=None):
        """Handle scope filter change."""
        # Save scope preference
        self.settings.set("filter_scope", self.filter_scope.get())
        # Update button styles (if buttons exist in this UI)
        self._update_scope_button_styles()
        self.refresh_project_list()

    def _update_scope_button_styles(self):
        """Update scope button visual states based on current selection."""
        if not hasattr(self, 'scope_buttons') or not self.scope_buttons:
            return
        current = self.filter_scope.get()
        for value, btn in self.scope_buttons.items():
            if value == current:
                # Selected state - highlighted
                btn.configure(bg="#58a6ff", fg="white")
            else:
                # Unselected state
                btn.configure(bg="#1c2128", fg="white")

    def _get_column_header(self, col: str) -> str:
        """Get column header text with sort indicator if applicable."""
        name = self.column_names.get(col, col)
        if col == self.sort_column:
            indicator = " ▼" if self.sort_reverse else " ▲"
            return name + indicator
        return name

    def _update_column_headers(self):
        """Update all column headers to reflect current sort state."""
        for col in ["date", "client", "project"]:
            self.project_tree.heading(col, text=self._get_column_header(col))

    def _on_column_click(self, col: str):
        """Handle column header click for sorting."""
        if col == self.sort_column:
            # Toggle sort direction
            self.sort_reverse = not self.sort_reverse
        else:
            # New column, default to descending for date, ascending for others
            self.sort_column = col
            self.sort_reverse = (col == "date")

        # Save settings
        self.settings.set("sort_column", self.sort_column)
        self.settings.set("sort_reverse", self.sort_reverse)

        # Update headers and refresh
        self._update_column_headers()
        self.refresh_project_list()

    def _get_column_at_x(self, x: int) -> str:
        """Get the column ID at the given x coordinate."""
        # Get column widths in display order
        total = 0
        for col in self.column_order:
            width = self.project_tree.column(col, "width")
            if x < total + width:
                return col
            total += width
        return None

    def _on_tree_click(self, event):
        """Handle click on treeview - detect header clicks for dragging."""
        region = self.project_tree.identify_region(event.x, event.y)
        if region == "heading":
            col = self._get_column_at_x(event.x)
            if col:
                self._drag_column = col
                self._drag_start_x = event.x

    def _on_tree_drag(self, event):
        """Handle dragging on treeview header."""
        if self._drag_column and self._drag_start_x is not None:
            # Check if we've moved enough to consider it a drag
            if abs(event.x - self._drag_start_x) > 20:
                # Change cursor to indicate dragging
                self.project_tree.configure(cursor="fleur")

    def _on_tree_release(self, event):
        """Handle mouse release - complete column reorder if dragging."""
        if self._drag_column and self._drag_start_x is not None:
            drag_distance = event.x - self._drag_start_x

            # Only reorder if we dragged far enough
            if abs(drag_distance) > 20:
                target_col = self._get_column_at_x(event.x)
                if target_col and target_col != self._drag_column:
                    # Reorder columns
                    new_order = self.column_order.copy()
                    old_idx = new_order.index(self._drag_column)
                    new_idx = new_order.index(target_col)

                    # Move the column
                    new_order.pop(old_idx)
                    new_order.insert(new_idx, self._drag_column)

                    self.column_order = new_order
                    self.project_tree["displaycolumns"] = self.column_order

                    # Save settings
                    self.settings.set("column_order", self.column_order)

        # Reset drag state
        self._drag_column = None
        self._drag_start_x = None
        self.project_tree.configure(cursor="")

    def _on_project_selected(self, event):
        """Handle project selection."""
        selection = self.project_tree.selection()

        if not selection:
            self.selected_project = None
            self._clear_details()
            return

        # Get project from our mapping
        item = selection[0]
        project = self.tree_item_to_project.get(item)

        if not project:
            return

        self.selected_project = project
        self._display_project_details(project)

    def _clear_details(self):
        """Clear detail panel."""
        for label in self.detail_labels.values():
            label.config(text="-")

        # Clear path labels and tracking variables
        self.active_path_label.config(text="-")
        self.raw_path_label.config(text="-")
        self._current_active_path = None
        self._current_raw_path = None
        self.active_path_frame.pack(fill=tk.X, pady=2)  # Show by default

        self.open_btn.config(state=tk.DISABLED)
        self.archive_btn.config(state=tk.DISABLED)
        self.unarchive_btn.config(state=tk.DISABLED)

    def _display_project_details(self, project: Dict):
        """Display project details in right panel."""
        # Update detail labels
        for key, label in self.detail_labels.items():
            value = project.get(key, "")

            # Format type with icon
            if key == "project_type":
                type_info = PROJECT_TYPES.get(value, {"name": value})
                value = type_info["name"]

            label.config(text=str(value))

        # Get status and stored path
        status = project.get("status", "active")
        stored_path = project.get("path", "")

        # Store paths for clipboard copy
        self._current_raw_path = stored_path
        self._current_active_path = None

        # Handle paths based on project status
        if status == "active":
            # Show Active Path frame
            self.active_path_frame.pack(fill=tk.X, pady=2)

            # Get the active path (work drive version)
            try:
                settings = get_rak_settings()
                active_path = settings.convert_to_work_drive_path(stored_path)
                self._current_active_path = active_path
                self.active_path_label.config(text=active_path)
            except Exception:
                self.active_path_label.config(text=stored_path)
                self._current_active_path = stored_path

            # RAW path is the stored D:\ path or derive it from active path
            # If stored path is already the work drive path, convert back to D:\ path
            if stored_path.upper().startswith("I:"):
                raw_path = stored_path.replace("I:", "D:\\_work\\Active", 1).replace("I:\\", "D:\\_work\\Active\\")
            else:
                raw_path = stored_path
            self._current_raw_path = raw_path
            self.raw_path_label.config(text=raw_path)
        else:
            # Archived: Keep Active Path frame visible but blank
            self.active_path_frame.pack(fill=tk.X, pady=2)
            self.active_path_label.config(text="-")
            self._current_active_path = None
            self.raw_path_label.config(text=stored_path)
            self._current_raw_path = stored_path

        # Enable buttons
        self.open_btn.config(state=tk.NORMAL)

        # Enable archive/unarchive based on status
        if status == "active":
            self.archive_btn.config(state=tk.NORMAL)
            self.unarchive_btn.config(state=tk.DISABLED)
        elif status == "archived":
            self.archive_btn.config(state=tk.DISABLED)
            self.unarchive_btn.config(state=tk.NORMAL)

    def _copy_path_to_clipboard(self, path_type: str):
        """Copy the specified path to clipboard."""
        if path_type == "active" and self._current_active_path:
            path = self._current_active_path
        elif path_type == "raw" and self._current_raw_path:
            path = self._current_raw_path
        else:
            return

        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(path)
            self._update_status(f"Copied: {path}")
            logger.debug(f"Copied path to clipboard: {path}")
        except Exception as e:
            logger.error(f"Failed to copy to clipboard: {e}")

    def _open_folder(self):
        """Open project folder in file explorer."""
        if not self.selected_project:
            return

        # Get path from project
        stored_path = self.selected_project["path"]
        status = self.selected_project.get("status", "active")

        # For active projects, convert to configured work drive path
        if status == "active":
            try:
                settings = get_rak_settings()
                open_path = settings.convert_to_work_drive_path(stored_path)
                path = Path(open_path)

                # If converted path doesn't exist, fall back to stored path
                if not path.exists():
                    logger.debug(f"Work drive path not found, using stored path: {stored_path}")
                    path = Path(stored_path)
            except Exception as e:
                logger.warning(f"Path conversion failed, using stored path: {e}")
                path = Path(stored_path)
        else:
            # Archived projects use stored path directly
            path = Path(stored_path)

        if not path.exists():
            messagebox.showerror(
                "Folder Not Found",
                f"Project folder does not exist:\n{path}"
            )
            return

        try:
            # Check for custom file manager setting
            custom_file_manager = self.settings.get("file_manager", "")

            if custom_file_manager:
                # Use custom file manager
                import subprocess
                open_path = str(path)

                # If running in WSL with a Windows file manager, convert path to Windows format
                if sys.platform != "win32" and custom_file_manager.lower().endswith(".exe"):
                    # Convert /mnt/d/... to D:\...
                    if open_path.startswith("/mnt/"):
                        parts = open_path.split("/")
                        if len(parts) >= 3:
                            drive_letter = parts[2].upper()
                            rest = "/".join(parts[3:])
                            open_path = f"{drive_letter}:\\{rest}".replace("/", "\\")

                subprocess.Popen([custom_file_manager, open_path])
            elif sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                os.system(f'open "{path}"')
            else:
                os.system(f'xdg-open "{path}"')

            logger.info(f"Opened folder: {path}")

        except Exception as e:
            logger.error(f"Failed to open folder: {e}")
            messagebox.showerror("Error", f"Failed to open folder:\n{str(e)}")

    def _archive_project(self):
        """Archive the selected project."""
        if not self.selected_project:
            return

        # Confirm
        response = messagebox.askyesno(
            "Confirm Archive",
            f"Archive this project?\n\n"
            f"Client: {self.selected_project.get('client_name')}\n"
            f"Project: {self.selected_project.get('project_name')}\n\n"
            f"The folder will be moved to D:\\_work\\Archive"
        )

        if not response:
            return

        # Archive
        self._update_status("Archiving project...")
        success = ArchiveManager.archive_project(self.selected_project, self.db)

        if success:
            self._update_status("Project archived successfully")
            self.refresh_project_list()
            self._clear_details()
        else:
            self._update_status("Archive failed")

    def _unarchive_project(self):
        """Un-archive the selected project."""
        if not self.selected_project:
            return

        # Confirm
        response = messagebox.askyesno(
            "Confirm Un-Archive",
            f"Restore this project from archive?\n\n"
            f"Client: {self.selected_project.get('client_name')}\n"
            f"Project: {self.selected_project.get('project_name')}\n\n"
            f"The folder will be moved back to its original location."
        )

        if not response:
            return

        # Un-archive
        self._update_status("Un-archiving project...")
        success = ArchiveManager.unarchive_project(self.selected_project, self.db)

        if success:
            self._update_status("Project restored successfully")
            self.refresh_project_list()
            self._clear_details()
        else:
            self._update_status("Un-archive failed")

    def _save_notes(self):
        """Save project notes."""
        if not self.selected_project:
            return

        notes = self.notes_text.get(1.0, tk.END).strip()

        try:
            self.db.update_project_notes(self.selected_project["id"], notes)
            self._update_status("Notes saved")
            logger.info(f"Saved notes for project: {self.selected_project['id']}")

            # Update selected project
            self.selected_project["notes"] = notes

        except Exception as e:
            logger.error(f"Failed to save notes: {e}")
            messagebox.showerror("Error", f"Failed to save notes:\n{str(e)}")

    def refresh_and_import(self, silent: bool = False):
        """
        Delete database and perform fresh import of all projects.

        Args:
            silent: If True, skip confirmation/result dialogs (used for F5 refresh)
        """
        if not silent:
            response = messagebox.askyesno(
                "Import Projects",
                "This will delete the existing database and perform a fresh import\n"
                "of all projects from your project directories.\n\n"
                "Continue?"
            )
            if not response:
                return

        self._update_status("Refreshing projects...")
        self.root.update_idletasks()

        try:
            # Delete existing database file
            if self.db.db_path.exists():
                os.remove(self.db.db_path)
                logger.info(f"Deleted old database: {self.db.db_path}")

            # Reinitialize database (creates fresh empty database)
            self.db = ProjectDatabase()

            # Run fresh import
            stats = ProjectImporter.scan_and_import(self.db, None)

            # Refresh list
            self.refresh_project_list()
            self._update_status(f"Imported {stats['imported']} projects", "success")

            # Show results dialog only if not silent
            if not silent:
                messagebox.showinfo(
                    "Import Complete",
                    f"Fresh import completed:\n\n"
                    f"Scanned: {stats['scanned']} folders\n"
                    f"Imported: {stats['imported']} projects\n"
                    f"Errors: {stats['errors']}"
                )

        except Exception as e:
            logger.error(f"Failed to import projects: {e}")
            if not silent:
                messagebox.showerror("Import Failed", f"Failed to import projects:\n{str(e)}")
            else:
                self._update_status(f"Import failed: {str(e)}", "error")

    def _import_projects(self):
        """Import existing projects from filesystem (with dialogs)."""
        self.refresh_and_import(silent=False)


def main():
    """Main entry point."""
    # Initialize logging first! Use MODULE_NAME to match get_logger() call
    setup_logging(MODULE_NAME)
    logger.info("Starting Project Tracker")

    root = tk.Tk()
    app = ProjectTrackerApp(root)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        logger.info("Project Tracker closed by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise


if __name__ == "__main__":
    main()
