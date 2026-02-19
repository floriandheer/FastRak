#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PipelineScript_Web_PublishStatic.py
Author: Florian Dheer
Version: 1.0.0
Description: Upload Staatic exports to FTP via WinSCP, sync DokuWiki, and create dated archives
"""

import os
import sys
import json
import shutil
import zipfile
import threading
import subprocess
import tempfile
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List
from urllib.parse import quote

# Setup logging using shared utility
from shared_logging import get_logger, setup_logging as setup_shared_logging
from rak_settings import get_rak_settings

# Get logger reference (configured in main())
logger = get_logger("web_publish_static")


# ====================================
# CONFIGURATION
# ====================================

class WebPublishConfig:
    """Configuration manager for static site publishing."""

    def __init__(self):
        app_data = Path.home() / "AppData" / "Local" / "PipelineManager"
        app_data.mkdir(parents=True, exist_ok=True)
        self.config_file = app_data / "web_publish_config.json"
        self.config = self._load_config()

    def _default_config(self) -> Dict:
        work = get_rak_settings().get_work_drive()
        return {
            "sites": {
                "floriandheer": {
                    "label": "floriandheer.com",
                    "export_dir": f"{work}\\Web\\_Personal\\floriandheer\\03_publish\\floriandheer",
                    "has_wiki": True,
                    "wiki_latest_dir": f"{work}\\Web\\_Personal\\floriandheer\\_wiki_latest",
                    "wiki_remote_path": "/wiki",
                    "ftp": {
                        "protocol": "ftp",
                        "host": "",
                        "port": 21,
                        "username": "",
                        "password": "",
                        "remote_path": "/"
                    }
                },
                "hyphen-v": {
                    "label": "hyphen-v.com",
                    "export_dir": f"{work}\\Web\\_Personal\\hyphen-v\\03_publish\\hyphen-v",
                    "has_wiki": False,
                    "wiki_latest_dir": "",
                    "wiki_remote_path": "",
                    "ftp": {
                        "protocol": "ftp",
                        "host": "",
                        "port": 21,
                        "username": "",
                        "password": "",
                        "remote_path": "/"
                    }
                }
            },
            "winscp_path": ""
        }

    def _load_config(self) -> Dict:
        default = self._default_config()
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                self._merge(default, loaded)
                return default
            except Exception as e:
                logger.error(f"Error loading config: {e}")
                return default
        else:
            self._save(default)
            return default

    def _merge(self, default: Dict, loaded: Dict):
        for key, value in loaded.items():
            if key in default and isinstance(value, dict) and isinstance(default[key], dict):
                self._merge(default[key], value)
            else:
                default[key] = value

    def _save(self, config: Optional[Dict] = None):
        if config is None:
            config = self.config
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def save(self):
        self._save()

    def get_site_config(self, site_key: str) -> Dict:
        return self.config.get("sites", {}).get(site_key, {})

    def get_site_keys(self) -> List[str]:
        return list(self.config.get("sites", {}).keys())

    def get_winscp_path(self) -> str:
        return self.config.get("winscp_path", "")

    def set_winscp_path(self, path: str):
        self.config["winscp_path"] = path
        self._save()


# ====================================
# WINSCP MANAGER
# ====================================

class WinSCPManager:
    """Manages WinSCP binary detection and script execution."""

    COMMON_PATHS = [
        r"C:\Program Files (x86)\WinSCP\winscp.com",
        r"C:\Program Files\WinSCP\winscp.com",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "WinSCP", "winscp.com"),
    ]

    def __init__(self, config: WebPublishConfig):
        self.config = config

    def find_winscp(self) -> Optional[str]:
        """Find winscp.com binary. Returns path or None."""
        # Check configured path first
        configured = self.config.get_winscp_path()
        if configured and os.path.isfile(configured):
            return configured

        # Check common install locations
        for path in self.COMMON_PATHS:
            if os.path.isfile(path):
                self.config.set_winscp_path(path)
                return path

        # Check PATH
        for dir_path in os.environ.get("PATH", "").split(os.pathsep):
            candidate = os.path.join(dir_path, "winscp.com")
            if os.path.isfile(candidate):
                self.config.set_winscp_path(candidate)
                return candidate

        return None

    def _build_open_command(self, ftp_cfg: Dict) -> str:
        """Build the WinSCP open command string with URL-encoded password."""
        protocol = ftp_cfg.get("protocol", "ftp")
        host = ftp_cfg["host"]
        port = ftp_cfg.get("port", 21)
        user = ftp_cfg["username"]
        password = quote(ftp_cfg["password"], safe="")
        url = f"{protocol}://{user}:{password}@{host}:{port}"
        return f'open "{url}" -passive=on -timeout=30'

    def build_upload_script(self, ftp_cfg: Dict, local_dir: str, remote_path: str,
                            exclude_wiki: bool = False) -> str:
        """Build WinSCP script for uploading (synchronize remote)."""
        lines = [
            "option batch abort",
            "option confirm off",
            "option reconnecttime 15",
            self._build_open_command(ftp_cfg),
        ]
        excludes = ""
        if exclude_wiki:
            excludes = ' -filemask="|wiki/"'
        lines.append(f'synchronize remote "{local_dir}" "{remote_path}"{excludes}')
        lines.append("exit")
        return "\n".join(lines)

    def build_wiki_download_script(self, ftp_cfg: Dict, remote_wiki_path: str,
                                   local_wiki_dir: str) -> str:
        """Build WinSCP script for downloading wiki (synchronize local)."""
        lines = [
            "option batch abort",
            "option confirm off",
            "option reconnecttime 15",
            self._build_open_command(ftp_cfg),
            f'synchronize local -delete "{local_wiki_dir}" "{remote_wiki_path}"',
            "exit",
        ]
        return "\n".join(lines)

    def execute_script(self, winscp_path: str, script_content: str,
                       on_output=None) -> int:
        """Execute a WinSCP script. Returns exit code."""
        # Write script to temp file
        script_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.txt', delete=False, encoding='utf-8'
        )
        try:
            script_file.write(script_content)
            script_file.close()

            cmd = [winscp_path, "/ini=nul", f"/script={script_file.name}"]
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            for line in iter(process.stdout.readline, ''):
                if on_output:
                    on_output(line.rstrip('\n'))

            return process.wait()
        finally:
            try:
                os.unlink(script_file.name)
            except OSError:
                pass


# ====================================
# PUBLISH WORKFLOW
# ====================================

class PublishWorkflow:
    """Orchestrates the publish pipeline in a background thread."""

    def __init__(self, config: WebPublishConfig, winscp_mgr: WinSCPManager,
                 site_key: str, root: tk.Tk, callbacks: Dict):
        self.config = config
        self.winscp_mgr = winscp_mgr
        self.site_key = site_key
        self.root = root
        self.site_cfg = config.get_site_config(site_key)
        self.has_wiki = self.site_cfg.get("has_wiki", False)

        # Callbacks: on_step_start(idx, name), on_step_done(idx, success),
        #            on_output(msg), on_complete(success, msg),
        #            prompt_user(title, message, choices) -> str
        self.cb = callbacks

        self._cancel = threading.Event()

    def get_steps(self) -> List[str]:
        if self.has_wiki:
            return [
                "Validate",
                "FTP Upload (excl. wiki)",
                "Copy wiki from _wiki_latest",
                "Sync wiki from online",
                "Update _wiki_latest",
                "Archive",
            ]
        else:
            return [
                "Validate",
                "FTP Upload",
                "Archive",
            ]

    def cancel(self):
        self._cancel.set()

    def _cancelled(self) -> bool:
        return self._cancel.is_set()

    def _output(self, msg: str):
        self.root.after(0, lambda: self.cb["on_output"](msg))

    def _step_start(self, idx: int, name: str):
        self.root.after(0, lambda: self.cb["on_step_start"](idx, name))

    def _step_done(self, idx: int, success: bool):
        self.root.after(0, lambda: self.cb["on_step_done"](idx, success))

    def _complete(self, success: bool, msg: str):
        self.root.after(0, lambda: self.cb["on_complete"](success, msg))

    def _prompt_user_sync(self, title: str, message: str, choices: List[str]) -> str:
        """Thread-safe user prompt. Blocks until user responds."""
        result_event = threading.Event()
        result_holder = [None]

        def show_dialog():
            dialog = tk.Toplevel(self.root)
            dialog.title(title)
            dialog.transient(self.root)
            dialog.grab_set()
            dialog.resizable(False, False)

            tk.Label(dialog, text=message, wraplength=400, justify=tk.LEFT,
                     padx=20, pady=15).pack()

            btn_frame = tk.Frame(dialog)
            btn_frame.pack(pady=(0, 15))

            def on_choice(choice):
                result_holder[0] = choice
                dialog.destroy()
                result_event.set()

            for choice in choices:
                tk.Button(btn_frame, text=choice, width=20,
                          command=lambda c=choice: on_choice(c)).pack(side=tk.LEFT, padx=5)

            dialog.protocol("WM_DELETE_WINDOW", lambda: on_choice("Cancel"))
            dialog.update_idletasks()
            # Center on parent
            x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
            y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
            dialog.geometry(f"+{x}+{y}")

        self.root.after(0, show_dialog)
        result_event.wait()
        return result_holder[0]

    def run(self):
        """Main workflow entry point. Call from a thread."""
        try:
            if self.has_wiki:
                self._run_with_wiki()
            else:
                self._run_without_wiki()
        except Exception as e:
            logger.exception("Publish workflow failed")
            self._complete(False, f"Error: {e}")

    def _run_without_wiki(self):
        steps = self.get_steps()
        step = 0

        # Step 0: Validate
        self._step_start(step, steps[step])
        ok = self._validate()
        self._step_done(step, ok)
        if not ok or self._cancelled():
            return
        step += 1

        # Step 1: FTP Upload
        self._step_start(step, steps[step])
        ok = self._ftp_upload(exclude_wiki=False)
        self._step_done(step, ok)
        if not ok or self._cancelled():
            return
        step += 1

        # Step 2: Archive
        self._step_start(step, steps[step])
        ok = self._archive()
        self._step_done(step, ok)
        if not ok:
            return

        self._complete(True, "Publish completed successfully!")

    def _run_with_wiki(self):
        steps = self.get_steps()
        step = 0

        # Step 0: Validate
        self._step_start(step, steps[step])
        ok = self._validate()
        self._step_done(step, ok)
        if not ok or self._cancelled():
            return
        step += 1

        # Step 1: FTP Upload (excl. wiki)
        self._step_start(step, steps[step])
        ok = self._ftp_upload(exclude_wiki=True)
        self._step_done(step, ok)
        if not ok or self._cancelled():
            return
        step += 1

        # Step 2: Copy wiki from _wiki_latest
        self._step_start(step, steps[step])
        ok = self._copy_wiki_to_export()
        self._step_done(step, ok)
        if not ok or self._cancelled():
            return
        step += 1

        # Step 3: Sync wiki from online
        self._step_start(step, steps[step])
        ok = self._sync_wiki_from_online()
        self._step_done(step, ok)
        if not ok or self._cancelled():
            return
        step += 1

        # Step 4: Update _wiki_latest
        self._step_start(step, steps[step])
        ok = self._update_wiki_latest()
        self._step_done(step, ok)
        if not ok or self._cancelled():
            return
        step += 1

        # Step 5: Archive
        self._step_start(step, steps[step])
        ok = self._archive()
        self._step_done(step, ok)
        if not ok:
            return

        self._complete(True, "Publish completed successfully!")

    # ---- Individual Steps ----

    def _validate(self) -> bool:
        export_dir = self.site_cfg.get("export_dir", "")
        ftp_cfg = self.site_cfg.get("ftp", {})

        if not os.path.isdir(export_dir):
            self._output(f"Export directory not found: {export_dir}")
            self._complete(False, "Validation failed: export directory missing")
            return False

        if not ftp_cfg.get("host") or not ftp_cfg.get("username"):
            self._output("FTP credentials not configured. Open Settings to configure.")
            self._complete(False, "Validation failed: FTP not configured")
            return False

        winscp = self.winscp_mgr.find_winscp()
        if not winscp:
            self._output("WinSCP not found. Install WinSCP or set the path in Settings.")
            self._complete(False, "Validation failed: WinSCP not found")
            return False

        self._output(f"Export dir: {export_dir}")
        self._output(f"WinSCP: {winscp}")
        self._output(f"FTP host: {ftp_cfg['host']}")
        self._output("Validation passed")
        return True

    def _ftp_upload(self, exclude_wiki: bool) -> bool:
        export_dir = self.site_cfg["export_dir"]
        ftp_cfg = self.site_cfg["ftp"]
        remote_path = ftp_cfg.get("remote_path", "/")
        winscp_path = self.winscp_mgr.find_winscp()

        script = self.winscp_mgr.build_upload_script(ftp_cfg, export_dir, remote_path, exclude_wiki)
        self._output(f"Uploading to {ftp_cfg['host']}:{remote_path} ...")
        if exclude_wiki:
            self._output("(excluding /wiki/ directory)")

        exit_code = self.winscp_mgr.execute_script(
            winscp_path, script, on_output=self._output
        )

        if exit_code != 0:
            self._output(f"FTP upload failed (exit code {exit_code})")
            self._complete(False, f"FTP upload failed (exit code {exit_code})")
            return False

        self._output("FTP upload completed")
        return True

    def _copy_wiki_to_export(self) -> bool:
        wiki_latest = self.site_cfg.get("wiki_latest_dir", "")
        export_dir = self.site_cfg["export_dir"]
        wiki_dest = os.path.join(export_dir, "wiki")

        if not os.path.isdir(wiki_latest):
            # _wiki_latest doesn't exist yet - prompt user
            self._output(f"_wiki_latest not found: {wiki_latest}")
            choice = self._prompt_user_sync(
                "Wiki Not Found",
                f"The wiki latest folder does not exist:\n{wiki_latest}\n\n"
                "How would you like to proceed?",
                ["Download from server", "Browse folder", "Cancel"]
            )

            if choice == "Download from server":
                self._output("Will download wiki from server in the next step")
                os.makedirs(wiki_latest, exist_ok=True)
                # Don't copy anything, the sync step will populate it
                return True
            elif choice == "Browse folder":
                # Use a thread-safe file dialog
                result_event = threading.Event()
                result_holder = [None]

                def browse():
                    path = filedialog.askdirectory(
                        title="Select existing wiki folder",
                        parent=self.root
                    )
                    result_holder[0] = path
                    result_event.set()

                self.root.after(0, browse)
                result_event.wait()

                selected = result_holder[0]
                if not selected or not os.path.isdir(selected):
                    self._output("No valid folder selected")
                    self._complete(False, "Wiki setup cancelled")
                    return False

                # Copy selected folder to _wiki_latest
                self._output(f"Copying selected wiki to {wiki_latest} ...")
                shutil.copytree(selected, wiki_latest)
                self._output("Wiki folder copied to _wiki_latest")
            else:
                self._complete(False, "Cancelled by user")
                return False

        # Now copy _wiki_latest into export_dir/wiki
        if os.path.isdir(wiki_dest):
            self._output("Removing existing wiki/ in export dir ...")
            shutil.rmtree(wiki_dest)

        self._output(f"Copying wiki from _wiki_latest to export dir ...")
        shutil.copytree(wiki_latest, wiki_dest)
        self._output("Wiki copied to export directory")
        return True

    def _sync_wiki_from_online(self) -> bool:
        export_dir = self.site_cfg["export_dir"]
        wiki_local = os.path.join(export_dir, "wiki")
        ftp_cfg = self.site_cfg["ftp"]
        wiki_remote = self.site_cfg.get("wiki_remote_path", "/wiki")
        winscp_path = self.winscp_mgr.find_winscp()

        self._output(f"Syncing wiki from server ({wiki_remote}) ...")

        script = self.winscp_mgr.build_wiki_download_script(
            ftp_cfg, wiki_remote, wiki_local
        )
        exit_code = self.winscp_mgr.execute_script(
            winscp_path, script, on_output=self._output
        )

        if exit_code != 0:
            self._output(f"Wiki sync failed (exit code {exit_code})")
            self._complete(False, f"Wiki sync failed (exit code {exit_code})")
            return False

        self._output("Wiki synced from online")
        return True

    def _update_wiki_latest(self) -> bool:
        export_dir = self.site_cfg["export_dir"]
        wiki_source = os.path.join(export_dir, "wiki")
        wiki_latest = self.site_cfg.get("wiki_latest_dir", "")

        if not wiki_latest:
            self._output("No _wiki_latest path configured, skipping update")
            return True

        if not os.path.isdir(wiki_source):
            self._output("No wiki/ folder in export dir to copy back")
            return True

        self._output(f"Updating _wiki_latest ...")
        if os.path.isdir(wiki_latest):
            shutil.rmtree(wiki_latest)
        shutil.copytree(wiki_source, wiki_latest)
        self._output("_wiki_latest updated")
        return True

    def _archive(self) -> bool:
        export_dir = self.site_cfg["export_dir"]
        archive_base = get_rak_settings().get_archive_path("Web")
        site_archive_dir = os.path.join(archive_base, self.site_key)
        os.makedirs(site_archive_dir, exist_ok=True)

        date_str = datetime.now().strftime("%Y-%m-%d")
        zip_name = f"{self.site_key}_{date_str}.zip"
        zip_path = os.path.join(site_archive_dir, zip_name)

        self._output(f"Creating archive: {zip_path}")

        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for dirpath, dirnames, filenames in os.walk(export_dir):
                    for filename in filenames:
                        file_path = os.path.join(dirpath, filename)
                        arcname = os.path.relpath(file_path, export_dir)
                        zf.write(file_path, arcname)

            size_mb = os.path.getsize(zip_path) / (1024 * 1024)
            self._output(f"Archive created: {zip_name} ({size_mb:.1f} MB)")
            return True
        except Exception as e:
            self._output(f"Archive failed: {e}")
            self._complete(False, f"Archive failed: {e}")
            return False


# ====================================
# FTP SETTINGS DIALOG
# ====================================

class FTPSettingsDialog:
    """Modal dialog for configuring FTP settings."""

    def __init__(self, parent: tk.Tk, config: WebPublishConfig, winscp_mgr: WinSCPManager):
        self.config = config
        self.winscp_mgr = winscp_mgr
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Publish Settings")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.resizable(False, False)
        self.dialog.geometry("550x555")

        self._build_ui()
        self._load_site(self.config.get_site_keys()[0])

        # Center on parent
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.dialog.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.dialog.winfo_height()) // 2
        self.dialog.geometry(f"+{x}+{y}")

    def _build_ui(self):
        pad = {"padx": 10, "pady": 4}

        # Site selector
        top = tk.Frame(self.dialog)
        top.pack(fill=tk.X, **pad)
        tk.Label(top, text="Site:").pack(side=tk.LEFT)
        self.site_var = tk.StringVar()
        site_keys = self.config.get_site_keys()
        labels = {k: self.config.get_site_config(k).get("label", k) for k in site_keys}
        self.site_combo = ttk.Combobox(
            top, textvariable=self.site_var,
            values=[labels[k] for k in site_keys],
            state="readonly", width=30
        )
        self.site_combo.pack(side=tk.LEFT, padx=5)
        self.site_combo.bind("<<ComboboxSelected>>", self._on_site_changed)
        self._site_labels = labels
        self._site_keys = site_keys

        # FTP frame
        ftp_frame = ttk.LabelFrame(self.dialog, text="FTP Connection")
        ftp_frame.pack(fill=tk.X, **pad)
        ftp_frame.columnconfigure(1, weight=1)

        row = 0
        tk.Label(ftp_frame, text="Protocol:").grid(row=row, column=0, sticky="w", padx=10, pady=4)
        self.protocol_var = tk.StringVar(value="ftp")
        ttk.Combobox(ftp_frame, textvariable=self.protocol_var,
                      values=["ftp", "sftp"], state="readonly", width=10
                      ).grid(row=row, column=1, sticky="w", padx=5, pady=4)

        row += 1
        tk.Label(ftp_frame, text="Host:").grid(row=row, column=0, sticky="w", padx=10, pady=4)
        self.host_var = tk.StringVar()
        tk.Entry(ftp_frame, textvariable=self.host_var, width=35).grid(
            row=row, column=1, sticky="ew", padx=5, pady=4)

        row += 1
        tk.Label(ftp_frame, text="Port:").grid(row=row, column=0, sticky="w", padx=10, pady=4)
        self.port_var = tk.StringVar(value="21")
        tk.Entry(ftp_frame, textvariable=self.port_var, width=8).grid(
            row=row, column=1, sticky="w", padx=5, pady=4)

        row += 1
        tk.Label(ftp_frame, text="Username:").grid(row=row, column=0, sticky="w", padx=10, pady=4)
        self.user_var = tk.StringVar()
        tk.Entry(ftp_frame, textvariable=self.user_var, width=35).grid(
            row=row, column=1, sticky="ew", padx=5, pady=4)

        row += 1
        tk.Label(ftp_frame, text="Password:").grid(row=row, column=0, sticky="w", padx=10, pady=4)
        self.pass_var = tk.StringVar()
        tk.Entry(ftp_frame, textvariable=self.pass_var, show="*", width=35).grid(
            row=row, column=1, sticky="ew", padx=5, pady=4)

        row += 1
        tk.Label(ftp_frame, text="Remote Path:").grid(row=row, column=0, sticky="w", padx=10, pady=4)
        self.remote_var = tk.StringVar(value="/")
        tk.Entry(ftp_frame, textvariable=self.remote_var, width=35).grid(
            row=row, column=1, sticky="ew", padx=5, pady=4)

        # Paths frame
        paths_frame = ttk.LabelFrame(self.dialog, text="Paths")
        paths_frame.pack(fill=tk.X, **pad)
        paths_frame.columnconfigure(1, weight=1)

        tk.Label(paths_frame, text="Export Dir:").grid(row=0, column=0, sticky="w", padx=10, pady=4)
        self.export_var = tk.StringVar()
        tk.Entry(paths_frame, textvariable=self.export_var, width=45).grid(
            row=0, column=1, sticky="ew", padx=5, pady=4)
        tk.Button(paths_frame, text="...", width=3,
                  command=self._browse_export).grid(row=0, column=2, padx=5, pady=4)

        tk.Label(paths_frame, text="Wiki Latest:").grid(row=1, column=0, sticky="w", padx=10, pady=4)
        self.wiki_var = tk.StringVar()
        self.wiki_entry = tk.Entry(paths_frame, textvariable=self.wiki_var, width=45)
        self.wiki_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=4)
        self.wiki_browse_btn = tk.Button(paths_frame, text="...", width=3,
                                         command=self._browse_wiki)
        self.wiki_browse_btn.grid(row=1, column=2, padx=5, pady=4)

        tk.Label(paths_frame, text="Wiki Remote:").grid(row=2, column=0, sticky="w", padx=10, pady=4)
        self.wiki_remote_var = tk.StringVar()
        self.wiki_remote_entry = tk.Entry(paths_frame, textvariable=self.wiki_remote_var, width=45)
        self.wiki_remote_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=4)

        # WinSCP frame
        winscp_frame = ttk.LabelFrame(self.dialog, text="WinSCP")
        winscp_frame.pack(fill=tk.X, **pad)
        winscp_frame.columnconfigure(1, weight=1)

        tk.Label(winscp_frame, text="winscp.com:").grid(row=0, column=0, sticky="w", padx=10, pady=4)
        self.winscp_var = tk.StringVar(value=self.config.get_winscp_path())
        tk.Entry(winscp_frame, textvariable=self.winscp_var, width=45).grid(
            row=0, column=1, sticky="ew", padx=5, pady=4)
        tk.Button(winscp_frame, text="...", width=3,
                  command=self._browse_winscp).grid(row=0, column=2, padx=5, pady=4)

        # Buttons
        btn_frame = tk.Frame(self.dialog)
        btn_frame.pack(fill=tk.X, pady=10, padx=10)

        tk.Button(btn_frame, text="Test Connection", command=self._test_connection).pack(side=tk.LEFT)
        tk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
        tk.Button(btn_frame, text="Save", command=self._save).pack(side=tk.RIGHT)

    def _on_site_changed(self, event=None):
        label = self.site_var.get()
        for key in self._site_keys:
            if self._site_labels[key] == label:
                self._save_current_to_memory()
                self._load_site(key)
                return

    def _load_site(self, site_key: str):
        self._current_key = site_key
        cfg = self.config.get_site_config(site_key)
        ftp = cfg.get("ftp", {})

        self.site_var.set(self._site_labels.get(site_key, site_key))
        self.protocol_var.set(ftp.get("protocol", "ftp"))
        self.host_var.set(ftp.get("host", ""))
        self.port_var.set(str(ftp.get("port", 21)))
        self.user_var.set(ftp.get("username", ""))
        self.pass_var.set(ftp.get("password", ""))
        self.remote_var.set(ftp.get("remote_path", "/"))
        self.export_var.set(cfg.get("export_dir", ""))
        self.wiki_var.set(cfg.get("wiki_latest_dir", ""))
        self.wiki_remote_var.set(cfg.get("wiki_remote_path", "/wiki"))

        has_wiki = cfg.get("has_wiki", False)
        state = tk.NORMAL if has_wiki else tk.DISABLED
        self.wiki_entry.config(state=state)
        self.wiki_browse_btn.config(state=state)
        self.wiki_remote_entry.config(state=state)

    def _save_current_to_memory(self):
        """Save current form values back to config dict (in memory)."""
        key = self._current_key
        site = self.config.config["sites"][key]
        site["export_dir"] = self.export_var.get()
        site["wiki_latest_dir"] = self.wiki_var.get()
        site["wiki_remote_path"] = self.wiki_remote_var.get()
        ftp = site.setdefault("ftp", {})
        ftp["protocol"] = self.protocol_var.get()
        ftp["host"] = self.host_var.get()
        try:
            ftp["port"] = int(self.port_var.get())
        except ValueError:
            ftp["port"] = 21
        ftp["username"] = self.user_var.get()
        ftp["password"] = self.pass_var.get()
        ftp["remote_path"] = self.remote_var.get()

    def _save(self):
        self._save_current_to_memory()
        self.config.config["winscp_path"] = self.winscp_var.get()
        self.config.save()
        self.dialog.destroy()

    def _browse_export(self):
        path = filedialog.askdirectory(title="Select Export Directory", parent=self.dialog)
        if path:
            self.export_var.set(path)

    def _browse_wiki(self):
        path = filedialog.askdirectory(title="Select Wiki Latest Directory", parent=self.dialog)
        if path:
            self.wiki_var.set(path)

    def _browse_winscp(self):
        path = filedialog.askopenfilename(
            title="Select winscp.com",
            filetypes=[("WinSCP Console", "winscp.com"), ("All Files", "*.*")],
            parent=self.dialog
        )
        if path:
            self.winscp_var.set(path)

    def _test_connection(self):
        self._save_current_to_memory()
        ftp_cfg = self.config.get_site_config(self._current_key).get("ftp", {})
        winscp_path = self.winscp_var.get() or self.winscp_mgr.find_winscp()

        if not winscp_path or not os.path.isfile(winscp_path):
            messagebox.showerror("Error", "WinSCP not found", parent=self.dialog)
            return

        if not ftp_cfg.get("host") or not ftp_cfg.get("username"):
            messagebox.showerror("Error", "Host and username are required", parent=self.dialog)
            return

        # Build a simple test script
        open_cmd = self.winscp_mgr._build_open_command(ftp_cfg)
        script = f"option batch abort\noption confirm off\n{open_cmd}\nls\nexit\n"

        try:
            exit_code = self.winscp_mgr.execute_script(winscp_path, script)
            if exit_code == 0:
                messagebox.showinfo("Success", "Connection successful!", parent=self.dialog)
            else:
                messagebox.showerror("Failed",
                                     f"Connection failed (exit code {exit_code})",
                                     parent=self.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Connection test failed: {e}", parent=self.dialog)


# ====================================
# MAIN UI
# ====================================

FORM_COLORS = {
    "bg": "#1a1a2e",
    "bg_card": "#16213e",
    "fg": "#e0e0e0",
    "fg_dim": "#8888aa",
    "accent": "#0f3460",
    "highlight": "#533483",
    "success": "#2ecc71",
    "warning": "#f39c12",
    "error": "#e74c3c",
    "info": "#3498db",
    "border": "#2a2a4a",
}


class PublishStaticUI:
    """Tkinter GUI for the static site publisher."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Publish Static Site")
        self.root.geometry("800x650")
        self.root.minsize(700, 550)
        self.root.configure(bg=FORM_COLORS["bg"])

        self.config = WebPublishConfig()
        self.winscp_mgr = WinSCPManager(self.config)
        self.workflow = None
        self.publish_running = False
        self.step_labels = []

        self._build_ui()
        self._on_site_changed()

    def _build_ui(self):
        colors = FORM_COLORS

        # Header
        header = tk.Frame(self.root, bg="#2c3e50", height=55)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="Publish Static Site", font=("Arial", 15, "bold"),
                 fg="white", bg="#2c3e50").place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # Controls frame
        ctrl = tk.Frame(self.root, bg=colors["bg"])
        ctrl.pack(fill=tk.X, padx=12, pady=(10, 5))

        tk.Label(ctrl, text="Site:", bg=colors["bg"], fg=colors["fg"],
                 font=("Arial", 10)).pack(side=tk.LEFT)

        site_keys = self.config.get_site_keys()
        self.site_labels_map = {}
        combo_values = []
        for k in site_keys:
            label = self.config.get_site_config(k).get("label", k)
            self.site_labels_map[label] = k
            combo_values.append(label)

        self.site_var = tk.StringVar(value=combo_values[0] if combo_values else "")
        self.site_combo = ttk.Combobox(ctrl, textvariable=self.site_var,
                                       values=combo_values, state="readonly", width=25)
        self.site_combo.pack(side=tk.LEFT, padx=8)
        self.site_combo.bind("<<ComboboxSelected>>", lambda e: self._on_site_changed())

        self.settings_btn = tk.Button(ctrl, text="Settings", command=self._open_settings,
                                      bg=colors["accent"], fg=colors["fg"], relief=tk.FLAT)
        self.settings_btn.pack(side=tk.RIGHT)

        self.start_btn = tk.Button(ctrl, text="Start Publish", command=self._start_publish,
                                   bg="#27ae60", fg="white", font=("Arial", 10, "bold"),
                                   relief=tk.FLAT, padx=15)
        self.start_btn.pack(side=tk.RIGHT, padx=8)

        # Path info
        info_frame = tk.Frame(self.root, bg=colors["bg"])
        info_frame.pack(fill=tk.X, padx=12, pady=(0, 5))

        self.export_label = tk.Label(info_frame, text="Export: -", bg=colors["bg"],
                                     fg=colors["fg_dim"], font=("Arial", 9), anchor="w")
        self.export_label.pack(fill=tk.X)

        self.archive_label = tk.Label(info_frame, text="Archive: -", bg=colors["bg"],
                                      fg=colors["fg_dim"], font=("Arial", 9), anchor="w")
        self.archive_label.pack(fill=tk.X)

        # Steps frame
        steps_outer = tk.LabelFrame(self.root, text="Progress", bg=colors["bg"],
                                    fg=colors["fg_dim"], font=("Arial", 9))
        steps_outer.pack(fill=tk.X, padx=12, pady=(5, 5))

        self.steps_frame = tk.Frame(steps_outer, bg=colors["bg"])
        self.steps_frame.pack(fill=tk.X, padx=8, pady=6)

        # Output text
        output_frame = tk.Frame(self.root, bg=colors["bg"])
        output_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 5))

        self.output_text = scrolledtext.ScrolledText(
            output_frame, wrap=tk.WORD, bg="#0d1117", fg=colors["fg"],
            font=("Consolas", 9), insertbackground=colors["fg"],
            relief=tk.FLAT, state=tk.DISABLED
        )
        self.output_text.pack(fill=tk.BOTH, expand=True)
        self.output_text.tag_configure("error", foreground=colors["error"])
        self.output_text.tag_configure("success", foreground=colors["success"])
        self.output_text.tag_configure("info", foreground=colors["info"])

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = tk.Label(self.root, textvariable=self.status_var, bg=colors["border"],
                              fg=colors["fg_dim"], anchor=tk.W, padx=10, font=("Arial", 9))
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def _get_current_site_key(self) -> str:
        return self.site_labels_map.get(self.site_var.get(), "")

    def _on_site_changed(self):
        site_key = self._get_current_site_key()
        if not site_key:
            return
        cfg = self.config.get_site_config(site_key)
        self.export_label.config(text=f"Export: {cfg.get('export_dir', '-')}")
        archive_base = get_rak_settings().get_archive_path("Web")
        self.archive_label.config(text=f"Archive: {os.path.join(archive_base, site_key)}")
        self._build_steps(site_key)

    def _build_steps(self, site_key: str):
        for w in self.steps_frame.winfo_children():
            w.destroy()
        self.step_labels = []

        cfg = self.config.get_site_config(site_key)
        has_wiki = cfg.get("has_wiki", False)

        if has_wiki:
            steps = [
                "Validate",
                "FTP Upload (excl. wiki)",
                "Copy wiki from _wiki_latest",
                "Sync wiki from online",
                "Update _wiki_latest",
                "Archive",
            ]
        else:
            steps = ["Validate", "FTP Upload", "Archive"]

        colors = FORM_COLORS
        for i, step in enumerate(steps):
            frame = tk.Frame(self.steps_frame, bg=colors["bg"])
            frame.pack(fill=tk.X, pady=1)

            icon = tk.Label(frame, text="  ", bg=colors["bg"], fg=colors["fg_dim"],
                            font=("Arial", 9), width=3)
            icon.pack(side=tk.LEFT)

            label = tk.Label(frame, text=f"{i + 1}. {step}", bg=colors["bg"],
                             fg=colors["fg_dim"], font=("Arial", 9), anchor="w")
            label.pack(side=tk.LEFT, fill=tk.X)

            self.step_labels.append((icon, label))

    def _append_output(self, msg: str, tag: str = None):
        self.output_text.config(state=tk.NORMAL)
        if tag:
            self.output_text.insert(tk.END, msg + "\n", tag)
        else:
            self.output_text.insert(tk.END, msg + "\n")
        self.output_text.see(tk.END)
        self.output_text.config(state=tk.DISABLED)

    def _open_settings(self):
        dialog = FTPSettingsDialog(self.root, self.config, self.winscp_mgr)
        self.root.wait_window(dialog.dialog)
        # Reload after settings close
        self.config = WebPublishConfig()
        self.winscp_mgr = WinSCPManager(self.config)
        self._on_site_changed()

    def _start_publish(self):
        if self.publish_running:
            return

        site_key = self._get_current_site_key()
        if not site_key:
            return

        self.publish_running = True
        self.start_btn.config(state=tk.DISABLED)
        self.settings_btn.config(state=tk.DISABLED)
        self.site_combo.config(state=tk.DISABLED)

        # Clear output
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete(1.0, tk.END)
        self.output_text.config(state=tk.DISABLED)

        # Reset step icons
        for icon, label in self.step_labels:
            icon.config(text="  ", fg=FORM_COLORS["fg_dim"])
            label.config(fg=FORM_COLORS["fg_dim"])

        callbacks = {
            "on_step_start": self._on_step_start,
            "on_step_done": self._on_step_done,
            "on_output": lambda msg: self._append_output(msg),
            "on_complete": self._on_complete,
        }

        self.workflow = PublishWorkflow(
            self.config, self.winscp_mgr, site_key, self.root, callbacks
        )

        thread = threading.Thread(target=self.workflow.run, daemon=True)
        thread.start()

    def _on_step_start(self, idx: int, name: str):
        if idx < len(self.step_labels):
            icon, label = self.step_labels[idx]
            icon.config(text="...", fg=FORM_COLORS["warning"])
            label.config(fg=FORM_COLORS["fg"])
        self.status_var.set(f"Step {idx + 1}: {name}")

    def _on_step_done(self, idx: int, success: bool):
        if idx < len(self.step_labels):
            icon, label = self.step_labels[idx]
            if success:
                icon.config(text=" ok", fg=FORM_COLORS["success"])
                label.config(fg=FORM_COLORS["success"])
            else:
                icon.config(text=" !", fg=FORM_COLORS["error"])
                label.config(fg=FORM_COLORS["error"])

    def _on_complete(self, success: bool, msg: str):
        self.publish_running = False
        self.start_btn.config(state=tk.NORMAL)
        self.settings_btn.config(state=tk.NORMAL)
        self.site_combo.config(state="readonly")

        if success:
            self._append_output(f"\n{msg}", "success")
            self.status_var.set(msg)
        else:
            self._append_output(f"\n{msg}", "error")
            self.status_var.set(msg)


# ====================================
# MAIN
# ====================================

def main():
    setup_shared_logging("web_publish_static")

    root = tk.Tk()
    PublishStaticUI(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
