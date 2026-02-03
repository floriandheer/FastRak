"""
Rak Settings Module

Centralized settings for FastRak Pipeline Manager.
Handles paths, software defaults, and other configuration.
"""

import json
import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple

from shared_logging import get_logger

logger = get_logger(__name__)


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


class RakSettings:
    """
    Manages settings for FastRak Pipeline Manager.

    Provides centralized access to paths, software defaults, and settings,
    with support for drive validation and per-category configuration.

    Default configuration:
    - Work drive: I:\\ (mapped via VisualSubst)
    - Archive base: D:\\_work\\Archive

    Categories and their default subpaths:
    - Visual: Visual/ (includes GD, CG, VJ subcategories)
    - RealTime: RealTime/ (includes Godot, TouchDesigner subcategories)
    - Audio: Audio/
    - Physical: Physical/
    - Photo: Photo/
    - Web: Web/
    """

    # Default configuration
    DEFAULT_CONFIG = {
        "version": "1.1.0",
        "drives": {
            "work": "I:",
            "active_base": "D:\\_work\\Active",
            "archive_base": "D:\\_work\\Archive"
        },
        "categories": {
            "Visual": {
                "work_subpath": "Visual",
                "archive_subpath": "Visual",
                "subcategories": ["GD", "CG", "VJ"]
            },
            "RealTime": {
                "work_subpath": "RealTime",
                "archive_subpath": "RealTime",
                "subcategories": ["Godot", "TD"]
            },
            "Audio": {
                "work_subpath": "Audio",
                "archive_subpath": "Audio",
                "subcategories": []
            },
            "Physical": {
                "work_subpath": "Physical",
                "archive_subpath": "Physical",
                "subcategories": []
            },
            "Photo": {
                "work_subpath": "Photo",
                "archive_subpath": "Photo",
                "subcategories": []
            },
            "Web": {
                "work_subpath": "Web",
                "archive_subpath": "Web",
                "subcategories": []
            }
        },
        # UI preferences
        "ui": {
            "start_fullscreen": False
        },
        # Global software version defaults (one version per software, used everywhere)
        "software_defaults": {
            "houdini": "20.5",
            "blender": "4.4",
            "fusion": "19",
            "resolume": "Arena 7",
            "after_effects": "2024",
            "touchdesigner": "2023.11760",
            "godot": "4.3",
            "ableton": "12",
            "reaper": "7",
            "traktor": "",
            "freecad": "",
            "alibre": "",
            "affinity": "",
            "python": "3.11",
            "slicer": "Bambu Studio",
            "printer": "Bambu Lab X1 Carbon",
            "platform": "PC/Desktop",
            "renderer": "Forward+",
            "resolution": "1920x1080"
        },
        "software_sync": {
            "nas_software_path": "D:\\_work\\_PIPELINE\\Software",
            "mapped_software_path": "P:\\Software",
            "launchers_base_path": "D:\\_work\\_PIPELINE\\Launchers"
        }
    }

    # Ordered list of categories for consistent UI display
    CATEGORY_ORDER = ["Visual", "RealTime", "Audio", "Physical", "Photo", "Web"]

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the pipeline configuration.

        Args:
            config_path: Path to config file. If None, uses default location.
        """
        if config_path is None:
            app_data = _get_appdata_path()
            app_data.mkdir(parents=True, exist_ok=True)
            self.config_path = app_data / "rak_config.json"
        else:
            self.config_path = Path(config_path)

        self.config = self._load_or_create()
        logger.info(f"Configuration loaded: {self.config_path}")

    def _load_or_create(self) -> Dict:
        """Load configuration from file or create default."""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # Merge with defaults to handle new fields
                    return self._merge_with_defaults(loaded)
            else:
                logger.info("Config not found, creating default")
                self._save(self.DEFAULT_CONFIG)
                return self.DEFAULT_CONFIG.copy()
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return self.DEFAULT_CONFIG.copy()

    def _merge_with_defaults(self, loaded: Dict) -> Dict:
        """Merge loaded config with defaults to ensure all keys exist."""
        import copy
        result = copy.deepcopy(self.DEFAULT_CONFIG)

        # Update drives
        if "drives" in loaded:
            result["drives"].update(loaded["drives"])

        # Update categories (preserve user customizations)
        if "categories" in loaded:
            for cat, cat_config in loaded["categories"].items():
                if cat in result["categories"]:
                    result["categories"][cat].update(cat_config)
                else:
                    result["categories"][cat] = cat_config

        # Update software_defaults (preserve user customizations)
        if "software_defaults" in loaded:
            loaded_sw = loaded["software_defaults"]
            # Handle flat structure (current format)
            if loaded_sw and not any(isinstance(v, dict) for v in loaded_sw.values()):
                result["software_defaults"].update(loaded_sw)
            else:
                # Legacy nested format: extract values and flatten
                for key, value in loaded_sw.items():
                    if isinstance(value, dict):
                        # Could be a category with subcategories or a flat category
                        for subkey, subvalue in value.items():
                            if isinstance(subvalue, dict):
                                # Nested subcategory - extract software versions
                                result["software_defaults"].update(subvalue)
                            else:
                                result["software_defaults"][subkey] = subvalue
                    else:
                        result["software_defaults"][key] = value

        # Update UI preferences
        if "ui" in loaded:
            result["ui"].update(loaded["ui"])

        # Preserve version from loaded if newer
        if "version" in loaded:
            result["version"] = loaded["version"]

        return result

    def _save(self, config: Optional[Dict] = None):
        """Save configuration to file."""
        if config is None:
            config = self.config

        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            logger.debug("Configuration saved")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            raise

    def save(self):
        """Public method to save current configuration."""
        self._save()

    # ==================== GETTERS ====================

    def get_start_fullscreen(self) -> bool:
        """Get whether the app should start in borderless fullscreen."""
        return self.config.get("ui", {}).get("start_fullscreen", False)

    def set_start_fullscreen(self, value: bool):
        """Set whether the app should start in borderless fullscreen."""
        if "ui" not in self.config:
            self.config["ui"] = {}
        self.config["ui"]["start_fullscreen"] = value
        self._save()

    def get_work_drive(self) -> str:
        """Get the work drive letter (e.g., 'I:')."""
        return self.config["drives"]["work"]

    def get_active_base(self) -> str:
        """Get the active base path (e.g., 'D:\\_work\\Active')."""
        return self.config["drives"].get("active_base", "D:\\_work\\Active")

    def get_archive_base(self) -> str:
        """Get the archive base path (e.g., 'D:\\_work\\Archive')."""
        return self.config["drives"]["archive_base"]

    def get_mapped_software_path(self) -> str:
        """Get the mapped drive path for software sync (e.g., 'P:\\Software')."""
        return self.config.get("software_sync", {}).get(
            "mapped_software_path", "P:\\Software")

    def get_launchers_base_path(self) -> str:
        """Get the base path for software launchers (e.g., 'D:\\_work\\_PIPELINE\\Launchers')."""
        return self.config.get("software_sync", {}).get(
            "launchers_base_path", "D:\\_work\\_PIPELINE\\Launchers")

    def get_work_path(self, category: str) -> str:
        """
        Get the full work path for a category.

        Args:
            category: Category name (e.g., 'Visual', 'Audio')

        Returns:
            Full path like 'I:\\Visual'
        """
        work_drive = self.get_work_drive()
        cat_config = self.config["categories"].get(category, {})
        subpath = cat_config.get("work_subpath", category)

        return f"{work_drive}\\{subpath}"

    def get_active_path(self, category: str) -> str:
        """
        Get the full active base path for a category (real path, not drive letter).

        Args:
            category: Category name (e.g., 'Visual', 'Audio')

        Returns:
            Full path like 'D:\\_work\\Active\\Visual'
        """
        active_base = self.get_active_base()
        cat_config = self.config["categories"].get(category, {})
        subpath = cat_config.get("work_subpath", category)

        return f"{active_base}\\{subpath}"

    def get_archive_path(self, category: str) -> str:
        """
        Get the full archive path for a category.

        Args:
            category: Category name (e.g., 'Visual', 'Audio')

        Returns:
            Full path like 'D:\\_work\\Archive\\Visual'
        """
        archive_base = self.get_archive_base()
        cat_config = self.config["categories"].get(category, {})
        subpath = cat_config.get("archive_subpath", category)

        return f"{archive_base}\\{subpath}"

    def get_category_config(self, category: str) -> Dict:
        """Get the full configuration for a category."""
        return self.config["categories"].get(category, {})

    def get_all_categories(self) -> Dict:
        """Get all category configurations."""
        return self.config["categories"]

    def get_ordered_categories(self) -> list:
        """Get categories in the defined display order."""
        return self.CATEGORY_ORDER.copy()

    def get_software_defaults(self, category: str = None, subcategory: str = None) -> Dict[str, str]:
        """
        Get software version defaults.

        The category and subcategory parameters are accepted for backwards
        compatibility but ignored - all software versions are global.

        Returns:
            Dict of software names to default versions
        """
        return self.config.get("software_defaults", {})

    # ==================== SETTERS ====================

    def set_work_drive(self, drive: str):
        """
        Set the work drive letter.

        Args:
            drive: Drive letter (e.g., 'I:' or 'I')
        """
        # Normalize to include colon
        if not drive.endswith(':'):
            drive = f"{drive}:"
        drive = drive.upper()

        self.config["drives"]["work"] = drive
        self._save()
        logger.info(f"Work drive set to: {drive}")

    def set_active_base(self, path: str):
        """
        Set the active base path.

        Args:
            path: Active base path (e.g., 'D:\\_work\\Active')
        """
        path = path.replace('/', '\\')

        self.config["drives"]["active_base"] = path
        self._save()
        logger.info(f"Active base set to: {path}")

    def set_archive_base(self, path: str):
        """
        Set the archive base path.

        Args:
            path: Archive base path (e.g., 'D:\\_work\\Archive')
        """
        # Normalize path separators
        path = path.replace('/', '\\')

        self.config["drives"]["archive_base"] = path
        self._save()
        logger.info(f"Archive base set to: {path}")

    def set_mapped_software_path(self, path: str):
        """Set the mapped drive path for software sync."""
        path = path.replace('/', '\\')
        if "software_sync" not in self.config:
            self.config["software_sync"] = {}
        self.config["software_sync"]["mapped_software_path"] = path
        self._save()
        logger.info(f"Mapped software path set to: {path}")

    def set_launchers_base_path(self, path: str):
        """Set the base path for software launchers."""
        path = path.replace('/', '\\')
        if "software_sync" not in self.config:
            self.config["software_sync"] = {}
        self.config["software_sync"]["launchers_base_path"] = path
        self._save()
        logger.info(f"Launchers base path set to: {path}")

    def set_category_paths(self, category: str, work_subpath: str = None,
                          archive_subpath: str = None):
        """
        Set custom subpaths for a category.

        Args:
            category: Category name
            work_subpath: Custom work subdirectory (relative to work drive)
            archive_subpath: Custom archive subdirectory (relative to archive base)
        """
        if category not in self.config["categories"]:
            self.config["categories"][category] = {}

        if work_subpath is not None:
            self.config["categories"][category]["work_subpath"] = work_subpath

        if archive_subpath is not None:
            self.config["categories"][category]["archive_subpath"] = archive_subpath

        self._save()
        logger.info(f"Updated paths for category: {category}")

    def set_software_defaults(self, **software_versions):
        """
        Set software version defaults.

        Args:
            **software_versions: Software name=version pairs (e.g., houdini="20.5")
        """
        if "software_defaults" not in self.config:
            self.config["software_defaults"] = {}

        self.config["software_defaults"].update(software_versions)
        self._save()
        logger.info(f"Updated software defaults: {list(software_versions.keys())}")

    # ==================== VALIDATION ====================

    def validate_drive(self, drive_or_path: str) -> Tuple[bool, str]:
        """
        Validate if a drive/path is accessible.

        Handles:
        - Regular drives (C:, D:)
        - Mapped drives via VisualSubst (I:, P:)
        - Network paths

        Args:
            drive_or_path: Drive letter (e.g., 'I:') or full path

        Returns:
            Tuple of (is_valid, status_message)
        """
        # Extract drive letter if full path given
        if len(drive_or_path) >= 2 and drive_or_path[1] == ':':
            drive = drive_or_path[:2].upper()
            check_path = drive_or_path
        else:
            drive = drive_or_path.upper()
            if not drive.endswith(':'):
                drive = f"{drive}:"
            check_path = f"{drive}\\"

        # Convert for WSL if needed
        if sys.platform != "win32":
            check_path = self._to_wsl_path(check_path)

        # Check if path exists
        try:
            path = Path(check_path)
            if path.exists():
                # Additional check: try to list directory to verify access
                try:
                    list(path.iterdir())
                    return True, "Mounted and accessible"
                except PermissionError:
                    return False, "Permission denied"
                except Exception as e:
                    return False, f"Access error: {e}"
            else:
                # Check if it's a subst/mapped drive that might not be mounted
                is_subst = self._is_subst_drive(drive)
                if is_subst:
                    return False, "Mapped drive not mounted (VisualSubst)"
                else:
                    return False, "Drive/path not found"
        except Exception as e:
            return False, f"Validation error: {e}"

    def _is_subst_drive(self, drive: str) -> bool:
        """
        Check if a drive letter is a substituted drive (via subst or VisualSubst).

        Args:
            drive: Drive letter (e.g., 'I:')

        Returns:
            True if it's a subst drive, False otherwise
        """
        if sys.platform != "win32":
            # Can't check subst from WSL directly
            return False

        try:
            result = subprocess.run(
                ['subst'],
                capture_output=True,
                text=True,
                timeout=5
            )
            # Output format: "I:\: => D:\_work\Active"
            drive_upper = drive.upper()
            for line in result.stdout.splitlines():
                if line.startswith(f"{drive_upper}\\:"):
                    return True
            return False
        except Exception:
            return False

    def _to_wsl_path(self, windows_path: str) -> str:
        """Convert Windows path to WSL path."""
        path = windows_path.replace('\\', '/')
        if len(path) >= 2 and path[1] == ':':
            drive = path[0].lower()
            rest = path[2:]
            if rest.startswith('/'):
                rest = rest[1:]
            return f"/mnt/{drive}/{rest}"
        return path

    def validate_work_drive(self) -> Tuple[bool, str]:
        """Validate the configured work drive."""
        return self.validate_drive(self.get_work_drive())

    def validate_archive_base(self) -> Tuple[bool, str]:
        """Validate the configured archive base path."""
        return self.validate_drive(self.get_archive_base())

    def validate_all(self) -> Dict[str, Tuple[bool, str]]:
        """
        Validate all configured paths.

        Returns:
            Dictionary with path names as keys and (is_valid, message) tuples as values
        """
        results = {
            "work_drive": self.validate_work_drive(),
            "archive_base": self.validate_archive_base()
        }

        # Validate each category's work path
        for category in self.CATEGORY_ORDER:
            work_path = self.get_work_path(category)
            results[f"{category}_work"] = self.validate_drive(work_path)

        return results

    # ==================== UTILITIES ====================

    def convert_to_work_drive_path(self, stored_path: str) -> str:
        """
        Convert a stored D:\\_work\\Active path to the configured work drive path.

        This is useful for opening active project folders when the work drive
        is mapped via VisualSubst to D:\\_work\\Active.

        Args:
            stored_path: Path stored in database (e.g., 'D:\\_work\\Active\\Visual\\Project')

        Returns:
            Path with work drive (e.g., 'I:\\Visual\\Project') or original if not applicable
        """
        # The active base path that gets mapped
        active_base = self.get_active_base()

        # Normalize path separators for comparison
        normalized_path = stored_path.replace('/', '\\')
        normalized_base = active_base.replace('/', '\\')

        # Check if this is an active project path
        if normalized_path.lower().startswith(normalized_base.lower()):
            # Extract the relative path after D:\_work\Active
            relative = normalized_path[len(normalized_base):]
            if relative.startswith('\\'):
                relative = relative[1:]

            # Build new path with work drive
            work_drive = self.get_work_drive()
            if relative:
                return f"{work_drive}\\{relative}"
            else:
                return work_drive

        # Not an active path - return unchanged
        return stored_path

    def reset_to_defaults(self):
        """Reset configuration to defaults."""
        self.config = self.DEFAULT_CONFIG.copy()
        self._save()
        logger.info("Configuration reset to defaults")

    def get_platform_path(self, windows_path: str) -> Path:
        """
        Convert Windows path to appropriate platform path.

        Args:
            windows_path: Path in Windows format (e.g., 'I:\\Visual')

        Returns:
            Path object appropriate for current platform
        """
        if sys.platform == "win32":
            return Path(windows_path)
        else:
            return Path(self._to_wsl_path(windows_path))

    def to_display_path(self, path: str) -> str:
        """
        Convert internal path to display format.
        Uses forward slashes for cleaner display.

        Args:
            path: Path string

        Returns:
            Display-friendly path string
        """
        return path.replace('\\', '/')


# Singleton instance for easy access
_instance: Optional[RakSettings] = None


def get_rak_settings() -> RakSettings:
    """
    Get the singleton RakSettings instance.

    This provides a convenient way for modules to access settings
    without needing to create their own instance.

    Returns:
        RakSettings singleton instance
    """
    global _instance
    if _instance is None:
        _instance = RakSettings()
    return _instance


# Backwards compatibility aliases
get_path_config = get_rak_settings
get_config = get_rak_settings
PathConfig = RakSettings
PipelineConfig = RakSettings


# Example usage and testing
if __name__ == "__main__":
    settings = RakSettings()

    print("=== Rak Settings ===")
    print(f"Work Drive: {settings.get_work_drive()}")
    print(f"Archive Base: {settings.get_archive_base()}")
    print()

    print("=== Category Paths ===")
    for category in settings.get_ordered_categories():
        work = settings.get_work_path(category)
        archive = settings.get_archive_path(category)
        print(f"{category}:")
        print(f"  Work: {work}")
        print(f"  Archive: {archive}")
    print()

    print("=== Validation ===")
    work_valid, work_msg = settings.validate_work_drive()
    archive_valid, archive_msg = settings.validate_archive_base()
    print(f"Work Drive: {'OK' if work_valid else 'FAIL'} - {work_msg}")
    print(f"Archive Base: {'OK' if archive_valid else 'FAIL'} - {archive_msg}")
