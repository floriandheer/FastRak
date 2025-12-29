#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PipelineScript_Audio_MusicBeeBackup_Rclone.py
Description: Robust MusicBee library backup to OneDrive using rclone
Author: Florian Dheer
Version: 1.0.0

Features:
- Uses rclone for reliable, resumable file transfers
- Persistent settings for source and destination paths
- Dry-run preview before actual backup
- Real-time progress tracking
- Detailed logging and error handling
- OneDrive-optimized with chunked uploads
"""

import os
import sys
import json
import subprocess
import threading
import datetime
import logging
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

# ============================================================================
# CONSTANTS AND CONFIGURATION
# ============================================================================

APP_NAME = "MusicBee Backup"
APP_VERSION = "1.0.0"

# Default paths
DEFAULT_SOURCE_DIR = "M:\\"
DEFAULT_DEST_REMOTE = "onedrive:_Music"

# Configuration paths
APP_DATA_DIR = os.path.join(os.path.expanduser("~"), "AppData", "Local", "PipelineManager")
CONFIG_FILE = os.path.join(APP_DATA_DIR, "musicbee_backup_rclone_config.json")
LOG_DIR = os.path.join(APP_DATA_DIR, "logs")

# Header color
HEADER_COLOR = "#2c3e50"

# rclone default options for OneDrive
RCLONE_DEFAULT_OPTIONS = [
    "--verbose",
    "--stats=2s",
    "--transfers=4",
    "--checkers=8",
    "--onedrive-chunk-size=10M",
    "--ignore-case",
    "--exclude", ".DS_Store",
    "--exclude", "Thumbs.db",
    "--exclude", "desktop.ini",
    "--exclude", "*.tmp",
    "--exclude", "*.temp",
    "--exclude", "$RECYCLE.BIN/**",
    "--exclude", "System Volume Information/**",
]


# ============================================================================
# LOGGING SETUP
# ============================================================================

from shared_logging import get_logger, setup_logging as setup_shared_logging

# Get logger reference (configured in main())
logger = get_logger("musicbee_backup")


# ============================================================================
# DATA CLASSES AND ENUMS
# ============================================================================

class BackupStatus(Enum):
    """Backup operation status."""
    IDLE = "idle"
    CHECKING_RCLONE = "checking_rclone"
    ANALYZING = "analyzing"
    DRY_RUN = "dry_run"
    BACKING_UP = "backing_up"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class BackupSettings:
    """Backup configuration settings."""
    source_path: str = DEFAULT_SOURCE_DIR
    dest_remote: str = DEFAULT_DEST_REMOTE
    delete_excluded: bool = False
    dry_run_first: bool = True
    transfers: int = 4
    checkers: int = 8
    bandwidth_limit: str = ""  # e.g., "10M" for 10 MB/s

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BackupSettings':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class BackupStats:
    """Statistics from a backup operation."""
    files_transferred: int = 0
    files_checked: int = 0
    bytes_transferred: int = 0
    errors: int = 0
    elapsed_time: float = 0.0
    transfer_speed: str = ""


# ============================================================================
# CONFIGURATION MANAGER
# ============================================================================

class ConfigManager:
    """Manages persistent configuration settings."""

    def __init__(self, config_path: str = CONFIG_FILE):
        self.config_path = config_path
        self.settings = self._load_settings()

    def _load_settings(self) -> BackupSettings:
        """Load settings from file or create defaults."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"Loaded settings from {self.config_path}")
                    return BackupSettings.from_dict(data)
            except Exception as e:
                logger.warning(f"Failed to load settings: {e}, using defaults")

        return BackupSettings()

    def save_settings(self) -> bool:
        """Save current settings to file."""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings.to_dict(), f, indent=2)
            logger.info(f"Settings saved to {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            return False

    def update_settings(self, **kwargs) -> None:
        """Update specific settings."""
        for key, value in kwargs.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
        self.save_settings()


# ============================================================================
# RCLONE MANAGER
# ============================================================================

class RcloneManager:
    """Manages rclone operations."""

    def __init__(self):
        self.rclone_path: Optional[str] = None
        self.rclone_version: Optional[str] = None
        self.process: Optional[subprocess.Popen] = None
        self.cancelled = False

    def find_rclone(self) -> Tuple[bool, str]:
        """Find rclone executable and verify it works."""
        # Check common locations
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        possible_paths = [
            "rclone",  # In PATH
            os.path.join(script_dir, "tools", "rclone", "rclone.exe"),  # Pipeline tools folder
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "rclone", "rclone.exe"),
            os.path.join(os.environ.get("PROGRAMFILES", ""), "rclone", "rclone.exe"),
            os.path.join(os.path.expanduser("~"), "scoop", "apps", "rclone", "current", "rclone.exe"),
            r"C:\rclone\rclone.exe",
        ]

        for path in possible_paths:
            try:
                result = subprocess.run(
                    [path, "version"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )
                if result.returncode == 0:
                    self.rclone_path = path
                    # Extract version from output
                    version_match = re.search(r'rclone v(\d+\.\d+\.\d+)', result.stdout)
                    self.rclone_version = version_match.group(1) if version_match else "unknown"
                    logger.info(f"Found rclone v{self.rclone_version} at {path}")
                    return True, f"rclone v{self.rclone_version} found"
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                continue

        error_msg = (
            "rclone not found! Please install rclone:\n"
            "1. Download from https://rclone.org/downloads/\n"
            "2. Or install via: winget install Rclone.Rclone\n"
            "3. Or install via: scoop install rclone"
        )
        logger.error("rclone not found")
        return False, error_msg

    def check_remote(self, remote: str) -> Tuple[bool, str]:
        """Check if the remote is configured and accessible."""
        if not self.rclone_path:
            return False, "rclone not initialized"

        # Extract remote name (before the colon)
        remote_name = remote.split(":")[0]

        try:
            # List configured remotes
            result = subprocess.run(
                [self.rclone_path, "listremotes"],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )

            if result.returncode != 0:
                return False, f"Failed to list remotes: {result.stderr}"

            configured_remotes = [r.strip().rstrip(':') for r in result.stdout.strip().split('\n') if r.strip()]

            if remote_name not in configured_remotes:
                return False, (
                    f"Remote '{remote_name}' not configured.\n"
                    f"Configured remotes: {', '.join(configured_remotes) if configured_remotes else 'None'}\n\n"
                    f"Run 'rclone config' in terminal to set up your remote."
                )

            # Quick connectivity test
            result = subprocess.run(
                [self.rclone_path, "lsd", remote, "--max-depth", "0"],
                capture_output=True,
                text=True,
                timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )

            if result.returncode != 0:
                if "authError" in result.stderr.lower() or "token" in result.stderr.lower():
                    return False, f"Authentication failed for '{remote_name}'. Run 'rclone config reconnect {remote_name}:'"
                return False, f"Cannot access remote: {result.stderr[:200]}"

            return True, f"Remote '{remote_name}' is accessible"

        except subprocess.TimeoutExpired:
            return False, "Timeout checking remote. Check your internet connection."
        except Exception as e:
            return False, f"Error checking remote: {e}"

    def is_destination_empty(self, remote: str) -> Tuple[bool, bool, str]:
        """
        Check if the remote destination is empty or doesn't exist.

        Returns:
            Tuple of (success, is_empty, message)
            - success: Whether the check completed without errors
            - is_empty: True if destination is empty or doesn't exist
            - message: Status message
        """
        if not self.rclone_path:
            return False, False, "rclone not initialized"

        try:
            # Use lsf to list files (faster than lsjson for just checking existence)
            # --max-depth 1 limits to top level, --files-only counts only files
            result = subprocess.run(
                [self.rclone_path, "lsf", remote, "--max-depth", "1", "-R"],
                capture_output=True,
                text=True,
                timeout=120,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )

            if result.returncode != 0:
                # Check if it's a "directory not found" error (destination doesn't exist yet)
                if "directory not found" in result.stderr.lower() or "not found" in result.stderr.lower():
                    return True, True, "Destination folder doesn't exist yet - will be created"
                return False, False, f"Error checking destination: {result.stderr[:200]}"

            # Check if output is empty (no files/folders)
            files = [f for f in result.stdout.strip().split('\n') if f.strip()]

            if len(files) == 0:
                return True, True, "Destination is empty - initial copy mode available"
            else:
                return True, False, f"Destination contains {len(files)} items - using sync mode"

        except subprocess.TimeoutExpired:
            return False, False, "Timeout checking destination. Check your internet connection."
        except Exception as e:
            return False, False, f"Error checking destination: {e}"

    def run_sync(
        self,
        source: str,
        dest: str,
        dry_run: bool = False,
        delete: bool = False,
        settings: Optional[BackupSettings] = None,
        progress_callback: Optional[callable] = None,
        output_callback: Optional[callable] = None
    ) -> Tuple[bool, BackupStats]:
        """Run rclone sync operation."""
        if not self.rclone_path:
            return False, BackupStats(errors=1)

        self.cancelled = False
        stats = BackupStats()

        # Build command
        cmd = [self.rclone_path, "sync", source, dest]
        cmd.extend(RCLONE_DEFAULT_OPTIONS)

        if dry_run:
            cmd.append("--dry-run")

        if delete:
            cmd.append("--delete-excluded")

        if settings:
            if settings.transfers:
                cmd.extend(["--transfers", str(settings.transfers)])
            if settings.checkers:
                cmd.extend(["--checkers", str(settings.checkers)])
            if settings.bandwidth_limit:
                cmd.extend(["--bwlimit", settings.bandwidth_limit])

        logger.info(f"Running rclone command: {' '.join(cmd)}")

        try:
            start_time = datetime.datetime.now()

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',  # Replace undecodable characters instead of failing
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )

            # Process output line by line
            for line in iter(self.process.stdout.readline, ''):
                if self.cancelled:
                    self.process.terminate()
                    logger.info("Backup cancelled by user")
                    return False, stats

                line = line.strip()
                if not line:
                    continue

                # Count transferred files from verbose output (e.g., "INFO  : file.mp3: Copied")
                if ": Copied" in line or ": Moved" in line:
                    stats.files_transferred += 1

                # Parse "Transferred:" line for bytes and speed
                # Format: "Transferred:   1.234 GiB / 10.000 GiB, 12%, 50.000 MiB/s, ETA 2m30s"
                if "Transferred:" in line and "/" in line:
                    # Parse bytes transferred
                    bytes_match = re.search(r'Transferred:\s+([\d.]+)\s*(\w+)\s*/', line)
                    if bytes_match:
                        value = float(bytes_match.group(1))
                        unit = bytes_match.group(2).upper()
                        multipliers = {
                            "B": 1, "BYTES": 1,
                            "KIB": 1024, "KB": 1024,
                            "MIB": 1024**2, "MB": 1024**2,
                            "GIB": 1024**3, "GB": 1024**3,
                            "TIB": 1024**4, "TB": 1024**4
                        }
                        stats.bytes_transferred = int(value * multipliers.get(unit, 1))

                    # Parse speed (e.g., "50.000 MiB/s")
                    speed_match = re.search(r'([\d.]+)\s*(\w+)/s', line)
                    if speed_match:
                        stats.transfer_speed = f"{speed_match.group(1)} {speed_match.group(2)}/s"

                # Parse "Checks:" or "Transferred:" for file counts
                # Format: "Transferred:   5 / 50, 10%" or "Checks:  100 / 1000"
                checks_match = re.search(r'Checks:\s*(\d+)\s*/\s*(\d+)', line)
                if checks_match:
                    stats.files_checked = int(checks_match.group(2))

                # Parse errors
                if "Errors:" in line:
                    error_match = re.search(r'Errors:\s+(\d+)', line)
                    if error_match:
                        stats.errors = int(error_match.group(1))

                # Send to callbacks
                if output_callback:
                    output_callback(line)
                if progress_callback:
                    progress_callback(stats)

            self.process.wait()

            stats.elapsed_time = (datetime.datetime.now() - start_time).total_seconds()

            if self.process.returncode == 0:
                logger.info("Backup completed successfully")
                return True, stats
            else:
                logger.error(f"Backup failed with return code {self.process.returncode}")
                stats.errors = max(1, stats.errors)
                return False, stats

        except Exception as e:
            logger.error(f"Error during backup: {e}")
            stats.errors = max(1, stats.errors)
            return False, stats
        finally:
            self.process = None

    def run_copy(
        self,
        source: str,
        dest: str,
        skip_existing: bool = False,
        settings: Optional[BackupSettings] = None,
        progress_callback: Optional[callable] = None,
        output_callback: Optional[callable] = None
    ) -> Tuple[bool, BackupStats]:
        """
        Run rclone copy operation for initial full copy (faster than sync for empty destinations).

        This method is optimized for copying to an empty destination:
        - Uses 'copy' instead of 'sync' (no deletion logic)
        - Skips destination checking with --no-check-dest
        - Uses higher parallelism for faster bulk transfers
        """
        if not self.rclone_path:
            return False, BackupStats(errors=1)

        self.cancelled = False
        stats = BackupStats()

        # Build command with optimizations for copy
        cmd = [self.rclone_path, "copy", source, dest]

        # Base options
        cmd.extend([
            "--verbose",
            "--stats=2s",
            "--onedrive-chunk-size=10M",
            "--ignore-case",
            "--exclude", ".DS_Store",
            "--exclude", "Thumbs.db",
            "--exclude", "desktop.ini",
            "--exclude", "*.tmp",
            "--exclude", "*.temp",
            "--exclude", "$RECYCLE.BIN/**",
            "--exclude", "System Volume Information/**",
        ])

        # Handle existing files
        if skip_existing:
            cmd.append("--ignore-existing")  # Skip files that already exist on destination
        # Otherwise files will be overwritten if source is newer or different

        # Use higher parallelism for initial copy (can be more aggressive)
        transfers = settings.transfers if settings and settings.transfers else 8
        checkers = settings.checkers if settings and settings.checkers else 16
        cmd.extend(["--transfers", str(max(transfers, 8))])  # At least 8 for initial copy
        cmd.extend(["--checkers", str(max(checkers, 16))])   # At least 16 for initial copy

        if settings and settings.bandwidth_limit:
            cmd.extend(["--bwlimit", settings.bandwidth_limit])

        logger.info(f"Running rclone copy (initial copy mode): {' '.join(cmd)}")

        try:
            start_time = datetime.datetime.now()

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',  # Replace undecodable characters instead of failing
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )

            # Process output line by line
            for line in iter(self.process.stdout.readline, ''):
                if self.cancelled:
                    self.process.terminate()
                    logger.info("Initial copy cancelled by user")
                    return False, stats

                line = line.strip()
                if not line:
                    continue

                # Count transferred files from verbose output
                if ": Copied" in line:
                    stats.files_transferred += 1

                # Parse transfer stats (same as sync)
                if "Transferred:" in line and "/" in line:
                    bytes_match = re.search(r'Transferred:\s+([\d.]+)\s*(\w+)\s*/', line)
                    if bytes_match:
                        value = float(bytes_match.group(1))
                        unit = bytes_match.group(2).upper()
                        multipliers = {
                            "B": 1, "BYTES": 1,
                            "KIB": 1024, "KB": 1024,
                            "MIB": 1024**2, "MB": 1024**2,
                            "GIB": 1024**3, "GB": 1024**3,
                            "TIB": 1024**4, "TB": 1024**4
                        }
                        stats.bytes_transferred = int(value * multipliers.get(unit, 1))

                    speed_match = re.search(r'([\d.]+)\s*(\w+)/s', line)
                    if speed_match:
                        stats.transfer_speed = f"{speed_match.group(1)} {speed_match.group(2)}/s"

                # Parse file counts
                checks_match = re.search(r'Transferred:\s*(\d+)\s*/\s*(\d+)', line)
                if checks_match:
                    stats.files_checked = int(checks_match.group(2))

                if "Errors:" in line:
                    error_match = re.search(r'Errors:\s+(\d+)', line)
                    if error_match:
                        stats.errors = int(error_match.group(1))

                if output_callback:
                    output_callback(line)
                if progress_callback:
                    progress_callback(stats)

            self.process.wait()

            stats.elapsed_time = (datetime.datetime.now() - start_time).total_seconds()

            if self.process.returncode == 0:
                logger.info("Initial copy completed successfully")
                return True, stats
            else:
                logger.error(f"Initial copy failed with return code {self.process.returncode}")
                stats.errors = max(1, stats.errors)
                return False, stats

        except Exception as e:
            logger.error(f"Error during initial copy: {e}")
            stats.errors = max(1, stats.errors)
            return False, stats
        finally:
            self.process = None

    def cancel(self) -> None:
        """Cancel the current operation."""
        self.cancelled = True
        if self.process:
            try:
                self.process.terminate()
            except:
                pass


# ============================================================================
# GUI APPLICATION
# ============================================================================

class MusicBeeBackupApp:
    """Main application GUI."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"MusicBee to OneDrive Backup")
        self.root.geometry("750x700")
        self.root.minsize(750, 600)

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        # Initialize managers
        self.config_manager = ConfigManager()
        self.rclone = RcloneManager()

        # State variables
        self.status = BackupStatus.IDLE
        self.current_stats = BackupStats()

        # Create UI
        self._create_header()
        self._create_main_frame()
        self._create_status_bar()

        # Load settings into UI
        self._load_settings_to_ui()

        # Check rclone on startup
        self.root.after(500, self._check_rclone)

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _create_header(self) -> None:
        """Create the header section."""
        header_frame = tk.Frame(self.root, bg=HEADER_COLOR, height=60)
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.grid_propagate(False)

        title_label = tk.Label(
            header_frame,
            text="MusicBee to OneDrive Backup",
            font=("Arial", 16, "bold"),
            fg="white",
            bg=HEADER_COLOR
        )
        title_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    def _create_main_frame(self) -> None:
        """Create the main content area."""
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)

        # Configuration section
        self._create_config_frame(main_frame)

        # Options section
        self._create_options_frame(main_frame)

        # Results section
        self._create_results_frame(main_frame)

    def _create_config_frame(self, parent) -> None:
        """Create the configuration section."""
        config_frame = ttk.LabelFrame(parent, text="Backup Configuration")
        config_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        config_frame.columnconfigure(1, weight=1)

        # Source directory
        ttk.Label(config_frame, text="MusicBee Library:").grid(
            row=0, column=0, sticky="w", padx=10, pady=10
        )
        self.source_var = tk.StringVar()
        ttk.Entry(config_frame, textvariable=self.source_var, width=50).grid(
            row=0, column=1, sticky="ew", padx=5, pady=10
        )
        ttk.Button(
            config_frame,
            text="Browse",
            command=lambda: self._browse_directory(self.source_var, "Select MusicBee Library")
        ).grid(row=0, column=2, padx=5, pady=10)

        # Destination remote
        ttk.Label(config_frame, text="OneDrive Remote:").grid(
            row=1, column=0, sticky="w", padx=10, pady=10
        )
        self.dest_var = tk.StringVar()
        ttk.Entry(config_frame, textvariable=self.dest_var, width=50).grid(
            row=1, column=1, sticky="ew", padx=5, pady=10
        )

        # Button frame for Test and Configure
        remote_btn_frame = ttk.Frame(config_frame)
        remote_btn_frame.grid(row=1, column=2, padx=5, pady=10)

        ttk.Button(
            remote_btn_frame,
            text="Test",
            command=self._test_remote,
            width=8
        ).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(
            remote_btn_frame,
            text="Configure",
            command=self._configure_rclone,
            width=8
        ).pack(side=tk.LEFT)

        # Help text
        help_label = ttk.Label(
            config_frame,
            text="Format: remotename:path (e.g., 'onedrive:_Music') - Click 'Configure' to set up rclone",
            font=("Arial", 8)
        )
        help_label.grid(row=2, column=1, sticky="w", padx=5, pady=(0, 10))

    def _create_options_frame(self, parent) -> None:
        """Create the options section."""
        options_frame = ttk.LabelFrame(parent, text="Options")
        options_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)

        # Checkboxes row
        checkbox_frame = ttk.Frame(options_frame)
        checkbox_frame.pack(fill=tk.X, padx=10, pady=10)

        self.dry_run_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            checkbox_frame,
            text="Preview changes before backup",
            variable=self.dry_run_var
        ).pack(side=tk.LEFT, padx=(0, 20))

        self.delete_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            checkbox_frame,
            text="Delete orphaned files (CAUTION)",
            variable=self.delete_var
        ).pack(side=tk.LEFT, padx=(0, 20))

        # Advanced options row
        adv_frame = ttk.Frame(options_frame)
        adv_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(adv_frame, text="Parallel transfers:").pack(side=tk.LEFT)
        self.transfers_var = tk.StringVar(value="4")
        ttk.Spinbox(
            adv_frame,
            from_=1,
            to=16,
            width=5,
            textvariable=self.transfers_var
        ).pack(side=tk.LEFT, padx=(5, 20))

        ttk.Label(adv_frame, text="Bandwidth limit:").pack(side=tk.LEFT)
        self.bwlimit_var = tk.StringVar(value="")
        ttk.Entry(
            adv_frame,
            textvariable=self.bwlimit_var,
            width=10
        ).pack(side=tk.LEFT, padx=(5, 5))
        ttk.Label(adv_frame, text="(e.g., 10M or empty)").pack(side=tk.LEFT)

        # Buttons row
        btn_frame = ttk.Frame(options_frame)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        btn_frame.columnconfigure(1, weight=1)

        self.preview_btn = tk.Button(
            btn_frame,
            text="Preview Changes",
            command=self._run_preview,
            bg="#3498db",
            fg="white",
            font=("Arial", 10, "bold"),
            padx=15,
            pady=5,
            cursor="hand2"
        )
        self.preview_btn.grid(row=0, column=0, padx=5)

        self.copy_btn = tk.Button(
            btn_frame,
            text="Copy",
            command=self._run_copy,
            bg="#9b59b6",
            fg="white",
            font=("Arial", 10, "bold"),
            padx=15,
            pady=5,
            cursor="hand2"
        )
        self.copy_btn.grid(row=0, column=1, padx=5)

        self.backup_btn = tk.Button(
            btn_frame,
            text="Start Backup",
            command=self._run_backup,
            bg="#27ae60",
            fg="white",
            font=("Arial", 10, "bold"),
            padx=15,
            pady=5,
            cursor="hand2"
        )
        self.backup_btn.grid(row=0, column=2, padx=5)

        self.cancel_btn = tk.Button(
            btn_frame,
            text="Cancel",
            command=self._cancel_operation,
            bg="#e74c3c",
            fg="white",
            font=("Arial", 10, "bold"),
            padx=15,
            pady=5,
            state=tk.DISABLED,
            cursor="hand2"
        )
        self.cancel_btn.grid(row=0, column=3, padx=5)

        self.save_btn = ttk.Button(
            btn_frame,
            text="Save Settings",
            command=self._save_settings
        )
        self.save_btn.grid(row=0, column=4, padx=5)

    def _create_results_frame(self, parent) -> None:
        """Create the results display section."""
        results_frame = ttk.LabelFrame(parent, text="Backup Progress and Results")
        results_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)

        # Notebook for tabs
        self.notebook = ttk.Notebook(results_frame)
        self.notebook.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # Progress tab
        progress_frame = ttk.Frame(self.notebook)
        self.notebook.add(progress_frame, text="Progress")
        progress_frame.columnconfigure(0, weight=1)
        progress_frame.rowconfigure(1, weight=1)

        # Progress bar and stats
        stats_frame = ttk.Frame(progress_frame)
        stats_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            stats_frame,
            variable=self.progress_var,
            maximum=100,
            mode="determinate"
        )
        self.progress_bar.pack(fill=tk.X, pady=(0, 10))

        stats_info = ttk.Frame(stats_frame)
        stats_info.pack(fill=tk.X)

        self.stats_labels = {}
        for i, (key, label) in enumerate([
            ("files", "Files:"),
            ("size", "Size:"),
            ("speed", "Speed:"),
            ("errors", "Errors:")
        ]):
            ttk.Label(stats_info, text=label).grid(row=0, column=i*2, padx=(0, 5))
            lbl = ttk.Label(stats_info, text="--")
            lbl.grid(row=0, column=i*2+1, padx=(0, 20))
            self.stats_labels[key] = lbl

        # Log text
        self.log_text = tk.Text(progress_frame, wrap=tk.WORD, height=15)
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        log_scrollbar = ttk.Scrollbar(progress_frame, command=self.log_text.yview)
        log_scrollbar.grid(row=1, column=1, sticky="ns")
        self.log_text.config(yscrollcommand=log_scrollbar.set)

        # Configure text tags
        self.log_text.tag_configure("info", foreground="black")
        self.log_text.tag_configure("success", foreground="#27ae60")
        self.log_text.tag_configure("warning", foreground="#f39c12")
        self.log_text.tag_configure("error", foreground="#e74c3c")
        self.log_text.tag_configure("highlight", foreground="#3498db")

    def _create_status_bar(self) -> None:
        """Create status bar at bottom."""
        status_frame = tk.Frame(self.root, bd=1, relief=tk.SUNKEN)
        status_frame.grid(row=2, column=0, sticky="ew")

        self.status_label = tk.Label(status_frame, text="Ready", anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, padx=5)

        self.rclone_label = tk.Label(status_frame, text="Checking rclone...", anchor=tk.E)
        self.rclone_label.pack(side=tk.RIGHT, padx=5)

    def _load_settings_to_ui(self) -> None:
        """Load settings from config into UI elements."""
        settings = self.config_manager.settings

        self.source_var.set(settings.source_path)
        self.dest_var.set(settings.dest_remote)
        self.dry_run_var.set(settings.dry_run_first)
        self.delete_var.set(settings.delete_excluded)
        self.transfers_var.set(str(settings.transfers))
        self.bwlimit_var.set(settings.bandwidth_limit)

    def _save_settings(self) -> None:
        """Save current UI settings to config."""
        self.config_manager.update_settings(
            source_path=self.source_var.get(),
            dest_remote=self.dest_var.get(),
            dry_run_first=self.dry_run_var.get(),
            delete_excluded=self.delete_var.get(),
            transfers=int(self.transfers_var.get()),
            bandwidth_limit=self.bwlimit_var.get()
        )
        self._log("Settings saved successfully", "success")
        self._update_status("Settings saved")

    def _browse_directory(self, var: tk.StringVar, title: str) -> None:
        """Open directory browser dialog."""
        current = var.get()
        initial_dir = current if os.path.isdir(current) else os.path.expanduser("~")

        directory = filedialog.askdirectory(title=title, initialdir=initial_dir)
        if directory:
            var.set(directory)

    def _log(self, message: str, tag: str = "info") -> None:
        """Add message to log with timestamp."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")

        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n", tag)
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def _clear_log(self) -> None:
        """Clear the log display."""
        self.log_text.delete(1.0, tk.END)

    def _update_status(self, message: str) -> None:
        """Update status bar message."""
        self.status_label.configure(text=message)
        self.root.update_idletasks()

    def _update_progress(self, stats: BackupStats) -> None:
        """Update progress display from stats."""
        self.stats_labels["files"].configure(
            text=f"{stats.files_transferred}/{stats.files_checked}"
        )
        self.stats_labels["size"].configure(
            text=self._format_size(stats.bytes_transferred)
        )
        self.stats_labels["speed"].configure(text=stats.transfer_speed or "--")
        self.stats_labels["errors"].configure(text=str(stats.errors))

        # Update progress bar
        if stats.files_checked > 0:
            progress = (stats.files_transferred / stats.files_checked) * 100
            self.progress_var.set(min(progress, 100))

        self.root.update_idletasks()

    def _reset_progress(self) -> None:
        """Reset progress display."""
        self.progress_var.set(0)
        for label in self.stats_labels.values():
            label.configure(text="--")

    def _set_buttons_state(self, running: bool) -> None:
        """Enable/disable buttons based on running state."""
        state = tk.DISABLED if running else tk.NORMAL
        self.preview_btn.configure(state=state)
        self.copy_btn.configure(state=state)
        self.backup_btn.configure(state=state)
        self.save_btn.configure(state=state)
        self.cancel_btn.configure(state=tk.NORMAL if running else tk.DISABLED)

    def _check_rclone(self) -> None:
        """Check if rclone is available."""
        self._update_status("Checking rclone installation...")

        success, message = self.rclone.find_rclone()

        if success:
            self.rclone_label.configure(text=message, fg="#27ae60")
            self._log(message, "success")
            self._update_status("Ready")
        else:
            self.rclone_label.configure(text="rclone not found", fg="#e74c3c")
            self._log(message, "error")
            self._update_status("rclone not available")

            # Disable action buttons
            self.preview_btn.configure(state=tk.DISABLED)
            self.copy_btn.configure(state=tk.DISABLED)
            self.backup_btn.configure(state=tk.DISABLED)

    def _test_remote(self) -> None:
        """Test the configured remote."""
        remote = self.dest_var.get().strip()

        if not remote:
            messagebox.showwarning("Warning", "Please enter a remote destination first.")
            return

        if not self.rclone.rclone_path:
            messagebox.showerror("Error", "rclone is not available.")
            return

        self._update_status(f"Testing remote '{remote}'...")
        self._log(f"Testing remote: {remote}", "info")

        def test_thread():
            success, message = self.rclone.check_remote(remote)

            self.root.after(0, lambda: self._log(message, "success" if success else "error"))
            self.root.after(0, lambda: self._update_status("Ready"))

            if success:
                self.root.after(0, lambda: messagebox.showinfo("Success", message))
            else:
                self.root.after(0, lambda: messagebox.showerror("Remote Test Failed", message))

        threading.Thread(target=test_thread, daemon=True).start()

    def _configure_rclone(self) -> None:
        """Open rclone config in a terminal window."""
        if not self.rclone.rclone_path:
            messagebox.showerror(
                "Error",
                "rclone is not available. Please ensure rclone.exe is installed."
            )
            return

        self._log("Opening rclone configuration in terminal...", "highlight")

        try:
            # Open rclone config in a new terminal window
            if sys.platform == "win32":
                # Use start cmd to open a new terminal window
                subprocess.Popen(
                    f'start cmd /k "{self.rclone.rclone_path}" config',
                    shell=True
                )
            else:
                # For Linux/Mac
                subprocess.Popen(
                    [self.rclone.rclone_path, "config"],
                    start_new_session=True
                )

            self._update_status("rclone config opened in terminal")

        except Exception as e:
            self._log(f"Error opening rclone config: {e}", "error")
            messagebox.showerror("Error", f"Failed to open rclone config:\n{e}")

    def _validate_inputs(self) -> bool:
        """Validate user inputs before running."""
        source = self.source_var.get().strip()
        dest = self.dest_var.get().strip()

        if not source:
            messagebox.showwarning("Warning", "Please specify a source directory.")
            return False

        if not os.path.isdir(source):
            messagebox.showerror("Error", f"Source directory does not exist:\n{source}")
            return False

        if not dest:
            messagebox.showwarning("Warning", "Please specify a destination remote.")
            return False

        if ":" not in dest:
            messagebox.showwarning(
                "Warning",
                "Destination should be in format 'remote:path'\n"
                "Example: onedrive:_Music"
            )
            return False

        if not self.rclone.rclone_path:
            messagebox.showerror("Error", "rclone is not available. Please install rclone first.")
            return False

        return True

    def _get_current_settings(self) -> BackupSettings:
        """Get current settings from UI."""
        return BackupSettings(
            source_path=self.source_var.get().strip(),
            dest_remote=self.dest_var.get().strip(),
            delete_excluded=self.delete_var.get(),
            dry_run_first=self.dry_run_var.get(),
            transfers=int(self.transfers_var.get()),
            bandwidth_limit=self.bwlimit_var.get().strip()
        )

    def _run_preview(self) -> None:
        """Run dry-run preview."""
        if not self._validate_inputs():
            return

        self._clear_log()
        self._reset_progress()
        self._set_buttons_state(True)
        self.status = BackupStatus.DRY_RUN

        settings = self._get_current_settings()

        self._log("Starting dry-run preview...", "highlight")
        self._log(f"Source: {settings.source_path}", "info")
        self._log(f"Destination: {settings.dest_remote}", "info")
        self._log("No files will be modified during preview.\n", "info")

        def preview_thread():
            try:
                success, stats = self.rclone.run_sync(
                    settings.source_path,
                    settings.dest_remote,
                    dry_run=True,
                    delete=settings.delete_excluded,
                    settings=settings,
                    progress_callback=lambda s: self.root.after(0, lambda: self._update_progress(s)),
                    output_callback=lambda msg: self.root.after(0, lambda m=msg: self._log(m, "info"))
                )

                if success:
                    self.root.after(0, lambda: self._log("\nPreview completed successfully!", "success"))
                    self.root.after(0, lambda: self._log(
                        f"Files that would be transferred: {stats.files_transferred}", "highlight"))
                    if stats.errors > 0:
                        self.root.after(0, lambda: self._log(
                            f"Potential errors: {stats.errors}", "warning"))
                else:
                    self.root.after(0, lambda: self._log("\nPreview completed with issues.", "warning"))

            except Exception as e:
                self.root.after(0, lambda: self._log(f"Error during preview: {e}", "error"))
            finally:
                self.root.after(0, lambda: self._set_buttons_state(False))
                self.root.after(0, lambda: self._update_status("Preview completed"))
                self.status = BackupStatus.IDLE

        threading.Thread(target=preview_thread, daemon=True).start()

    def _run_backup(self) -> None:
        """Run actual backup."""
        if not self._validate_inputs():
            return

        settings = self._get_current_settings()

        # Check if destination is empty (for initial copy mode)
        self._update_status("Checking destination...")
        self._log("Checking if destination is empty...", "info")

        check_success, is_empty, check_msg = self.rclone.is_destination_empty(settings.dest_remote)

        if not check_success:
            self._log(f"Warning: {check_msg}", "warning")
            self._log("Proceeding with standard sync mode.", "info")
            is_empty = False  # Fall back to sync if check fails

        use_initial_copy = is_empty

        # Show confirmation with mode information
        if use_initial_copy:
            confirm_msg = (
                f"INITIAL COPY MODE\n\n"
                f"Destination is empty - using fast copy mode.\n"
                f"This skips file comparison for faster transfers.\n\n"
                f"From: {settings.source_path}\n"
                f"To: {settings.dest_remote}\n\n"
                f"Do you want to proceed with the initial copy?"
            )
            title = "Confirm Initial Copy"
        else:
            confirm_msg = (
                f"SYNC MODE\n\n"
                f"From: {settings.source_path}\n"
                f"To: {settings.dest_remote}\n\n"
            )

            if settings.delete_excluded:
                confirm_msg += (
                    "WARNING: Files in destination that don't exist in source WILL BE DELETED!\n\n"
                )

            confirm_msg += "Do you want to proceed with the backup?"
            title = "Confirm Backup"

        if not messagebox.askyesno(title, confirm_msg):
            self._update_status("Ready")
            return

        self._clear_log()
        self._reset_progress()
        self._set_buttons_state(True)
        self.status = BackupStatus.BACKING_UP

        if use_initial_copy:
            self._log("=" * 50, "highlight")
            self._log("INITIAL COPY MODE - Fast bulk transfer", "highlight")
            self._log("=" * 50, "highlight")
            self._log("Skipping file comparison (destination is empty)", "info")
            self._log(f"Using {max(settings.transfers, 8)} parallel transfers", "info")
        else:
            self._log("Starting backup (sync mode)...", "highlight")

        self._log(f"Source: {settings.source_path}", "info")
        self._log(f"Destination: {settings.dest_remote}", "info")
        if not use_initial_copy and settings.delete_excluded:
            self._log("Delete mode: ENABLED - orphaned files will be removed", "warning")
        self._log("", "info")

        def backup_thread():
            try:
                start_time = datetime.datetime.now()

                if use_initial_copy:
                    # Use fast copy for empty destination
                    success, stats = self.rclone.run_copy(
                        settings.source_path,
                        settings.dest_remote,
                        settings=settings,
                        progress_callback=lambda s: self.root.after(0, lambda: self._update_progress(s)),
                        output_callback=lambda msg: self.root.after(0, lambda m=msg: self._log(m, "info"))
                    )
                    mode_name = "Initial copy"
                else:
                    # Use sync for existing destination
                    success, stats = self.rclone.run_sync(
                        settings.source_path,
                        settings.dest_remote,
                        dry_run=False,
                        delete=settings.delete_excluded,
                        settings=settings,
                        progress_callback=lambda s: self.root.after(0, lambda: self._update_progress(s)),
                        output_callback=lambda msg: self.root.after(0, lambda m=msg: self._log(m, "info"))
                    )
                    mode_name = "Backup"

                elapsed = (datetime.datetime.now() - start_time).total_seconds()

                if success:
                    self.root.after(0, lambda: self._log("\n" + "="*50, "success"))
                    self.root.after(0, lambda: self._log(f"{mode_name.upper()} COMPLETED SUCCESSFULLY!", "success"))
                    self.root.after(0, lambda: self._log("="*50, "success"))
                    self.root.after(0, lambda: self._log(
                        f"Files transferred: {stats.files_transferred}", "success"))
                    self.root.after(0, lambda: self._log(
                        f"Data transferred: {self._format_size(stats.bytes_transferred)}", "success"))
                    self.root.after(0, lambda: self._log(
                        f"Time elapsed: {self._format_time(elapsed)}", "success"))

                    if stats.errors > 0:
                        self.root.after(0, lambda: self._log(
                            f"Errors encountered: {stats.errors}", "warning"))

                    self.root.after(0, lambda: messagebox.showinfo(
                        f"{mode_name} Complete",
                        f"{mode_name} completed successfully!\n\n"
                        f"Files transferred: {stats.files_transferred}\n"
                        f"Data transferred: {self._format_size(stats.bytes_transferred)}\n"
                        f"Time elapsed: {self._format_time(elapsed)}"
                    ))
                else:
                    self.root.after(0, lambda: self._log(f"\n{mode_name} completed with errors.", "error"))
                    self.root.after(0, lambda: messagebox.showwarning(
                        f"{mode_name} Completed with Errors",
                        f"{mode_name} completed but encountered {stats.errors} error(s).\n"
                        "Check the log for details."
                    ))

            except Exception as e:
                self.root.after(0, lambda: self._log(f"\nBackup failed: {e}", "error"))
                self.root.after(0, lambda: messagebox.showerror("Backup Failed", str(e)))
            finally:
                self.root.after(0, lambda: self._set_buttons_state(False))
                self.root.after(0, lambda: self._update_status("Backup completed"))
                self.status = BackupStatus.IDLE
                self.root.after(0, lambda: self.progress_var.set(100))

        threading.Thread(target=backup_thread, daemon=True).start()

    def _run_copy(self) -> None:
        """Run copy operation with user choice for existing files."""
        if not self._validate_inputs():
            return

        settings = self._get_current_settings()

        # Ask user how to handle existing files
        dialog = tk.Toplevel(self.root)
        dialog.title("Copy Mode - Handle Existing Files")
        dialog.geometry("450x200")
        dialog.transient(self.root)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

        user_choice = {"skip": None}

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame,
            text="How should existing files be handled?",
            font=("Arial", 11, "bold")
        ).pack(pady=(0, 10))

        ttk.Label(
            frame,
            text="This will copy all files from source to destination.\n"
                 "Choose how to handle files that already exist:",
            wraplength=400
        ).pack(pady=(0, 20))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=10)

        def on_skip():
            user_choice["skip"] = True
            dialog.destroy()

        def on_overwrite():
            user_choice["skip"] = False
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        tk.Button(
            btn_frame,
            text="Skip Existing Files",
            command=on_skip,
            bg="#3498db",
            fg="white",
            font=("Arial", 10, "bold"),
            padx=10,
            pady=5,
            cursor="hand2",
            width=18
        ).grid(row=0, column=0, padx=5)

        tk.Button(
            btn_frame,
            text="Overwrite Existing",
            command=on_overwrite,
            bg="#e67e22",
            fg="white",
            font=("Arial", 10, "bold"),
            padx=10,
            pady=5,
            cursor="hand2",
            width=18
        ).grid(row=0, column=1, padx=5)

        ttk.Button(
            frame,
            text="Cancel",
            command=on_cancel
        ).pack(pady=(10, 0))

        # Wait for dialog to close
        self.root.wait_window(dialog)

        # Check if user made a choice
        if user_choice["skip"] is None:
            self._update_status("Copy cancelled")
            return

        skip_existing = user_choice["skip"]

        # Show confirmation
        mode_text = "skip existing files" if skip_existing else "overwrite existing files"
        confirm_msg = (
            f"COPY MODE\n\n"
            f"From: {settings.source_path}\n"
            f"To: {settings.dest_remote}\n\n"
            f"Mode: Will {mode_text}\n\n"
            f"Do you want to proceed with the copy?"
        )

        if not messagebox.askyesno("Confirm Copy", confirm_msg):
            self._update_status("Ready")
            return

        self._clear_log()
        self._reset_progress()
        self._set_buttons_state(True)
        self.status = BackupStatus.BACKING_UP

        mode_desc = "Skipping existing files" if skip_existing else "Overwriting existing files"
        self._log("=" * 50, "highlight")
        self._log(f"COPY MODE - {mode_desc}", "highlight")
        self._log("=" * 50, "highlight")
        self._log(f"Source: {settings.source_path}", "info")
        self._log(f"Destination: {settings.dest_remote}", "info")
        self._log(f"Mode: {mode_desc}", "info")
        self._log("", "info")

        def copy_thread():
            try:
                start_time = datetime.datetime.now()

                success, stats = self.rclone.run_copy(
                    settings.source_path,
                    settings.dest_remote,
                    skip_existing=skip_existing,
                    settings=settings,
                    progress_callback=lambda s: self.root.after(0, lambda: self._update_progress(s)),
                    output_callback=lambda msg: self.root.after(0, lambda m=msg: self._log(m, "info"))
                )

                elapsed = (datetime.datetime.now() - start_time).total_seconds()

                if success:
                    self.root.after(0, lambda: self._log("\n" + "="*50, "success"))
                    self.root.after(0, lambda: self._log("COPY COMPLETED SUCCESSFULLY!", "success"))
                    self.root.after(0, lambda: self._log("="*50, "success"))
                    self.root.after(0, lambda: self._log(
                        f"Files copied: {stats.files_transferred}", "success"))
                    self.root.after(0, lambda: self._log(
                        f"Data transferred: {self._format_size(stats.bytes_transferred)}", "success"))
                    self.root.after(0, lambda: self._log(
                        f"Time elapsed: {self._format_time(elapsed)}", "success"))

                    if stats.errors > 0:
                        self.root.after(0, lambda: self._log(
                            f"Errors encountered: {stats.errors}", "warning"))

                    self.root.after(0, lambda: messagebox.showinfo(
                        "Copy Complete",
                        f"Copy completed successfully!\n\n"
                        f"Files copied: {stats.files_transferred}\n"
                        f"Data transferred: {self._format_size(stats.bytes_transferred)}\n"
                        f"Time elapsed: {self._format_time(elapsed)}"
                    ))
                else:
                    self.root.after(0, lambda: self._log("\nCopy completed with errors.", "error"))
                    self.root.after(0, lambda: messagebox.showwarning(
                        "Copy Completed with Errors",
                        f"Copy completed but encountered {stats.errors} error(s).\n"
                        "Check the log for details."
                    ))

            except Exception as e:
                self.root.after(0, lambda: self._log(f"\nCopy failed: {e}", "error"))
                self.root.after(0, lambda: messagebox.showerror("Copy Failed", str(e)))
            finally:
                self.root.after(0, lambda: self._set_buttons_state(False))
                self.root.after(0, lambda: self._update_status("Copy completed"))
                self.status = BackupStatus.IDLE
                self.root.after(0, lambda: self.progress_var.set(100))

        threading.Thread(target=copy_thread, daemon=True).start()

    def _cancel_operation(self) -> None:
        """Cancel the current operation."""
        if self.status in [BackupStatus.DRY_RUN, BackupStatus.BACKING_UP]:
            if messagebox.askyesno("Cancel", "Are you sure you want to cancel the current operation?"):
                self.rclone.cancel()
                self._log("Operation cancelled by user", "warning")
                self._update_status("Cancelled")
                self._set_buttons_state(False)
                self.status = BackupStatus.CANCELLED

    def _on_closing(self) -> None:
        """Handle window close event."""
        if self.status in [BackupStatus.DRY_RUN, BackupStatus.BACKING_UP]:
            if not messagebox.askyesno(
                "Quit",
                "An operation is in progress. Are you sure you want to quit?"
            ):
                return
            self.rclone.cancel()

        self.root.destroy()

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format bytes to human-readable size."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 ** 2:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 ** 3:
            return f"{size_bytes / (1024 ** 2):.1f} MB"
        else:
            return f"{size_bytes / (1024 ** 3):.2f} GB"

    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format seconds to human-readable time."""
        if seconds < 60:
            return f"{seconds:.1f} seconds"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main application entry point."""
    # Setup logging when the app actually runs (not at import time)
    setup_shared_logging("musicbee_backup")

    root = tk.Tk()
    app = MusicBeeBackupApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
