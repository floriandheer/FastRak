"""Debug-mode session for the Global Invoice GUI.

Lets the user try out invoice creation end-to-end without permanently
affecting numbering or the Boekhouding tree. While active:

  - Generated PDFs are filed into a *_DEBUG* subfolder of Boekhouding,
    not the real Q{n}/Uitgaand directory.
  - The session tracks every PDF written so it can clean them up later.
  - The SQLite DB is snapshotted on entry; on exit, the snapshot is
    restored so the numbering returns to exactly the pre-debug state.

State is persisted to ``DATA_DIR/debug_session.json`` so that if the
process crashes mid-session, the next run can still find the snapshot
and offer cleanup.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from shared_logging import get_logger

logger = get_logger(__name__)


DEBUG_SUBFOLDER_NAME = "_DEBUG"


class DebugSessionError(Exception):
    pass


class DebugSession:
    """Persistent record of an in-progress debug session."""

    def __init__(self, marker_path: Path):
        self.marker_path = Path(marker_path)
        self._data: Dict[str, Any] = {
            "active": False,
            "started_at": None,
            "db_backup_path": None,
            "created_pdfs": [],
        }
        if self.marker_path.exists():
            try:
                with open(self.marker_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    self._data.update(loaded)
            except Exception as e:
                logger.warning(f"Failed to read debug marker {self.marker_path}: {e}")

    # ---- state queries ----

    def is_active(self) -> bool:
        return bool(self._data.get("active"))

    @property
    def started_at(self) -> Optional[str]:
        return self._data.get("started_at")

    @property
    def db_backup_path(self) -> Optional[Path]:
        raw = self._data.get("db_backup_path")
        return Path(raw) if raw else None

    @property
    def created_pdfs(self) -> List[Path]:
        return [Path(p) for p in self._data.get("created_pdfs", [])]

    # ---- mutation ----

    def start(self, db_backup_path: Path) -> None:
        if self.is_active():
            raise DebugSessionError("Debug session is already active.")
        self._data = {
            "active": True,
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "db_backup_path": str(db_backup_path),
            "created_pdfs": [],
        }
        self._save()
        logger.info(f"Debug session started; DB backup at {db_backup_path}")

    def record_pdf(self, pdf_path: Path) -> None:
        if not self.is_active():
            raise DebugSessionError("Cannot record PDF — no active debug session.")
        self._data.setdefault("created_pdfs", []).append(str(pdf_path))
        self._save()

    def clear(self) -> None:
        """Forget the session and remove the marker file."""
        self._data = {
            "active": False,
            "started_at": None,
            "db_backup_path": None,
            "created_pdfs": [],
        }
        if self.marker_path.exists():
            try:
                self.marker_path.unlink()
            except OSError as e:
                logger.warning(f"Could not remove debug marker {self.marker_path}: {e}")

    # ---- persistence ----

    def _save(self) -> None:
        self.marker_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.marker_path.with_suffix(self.marker_path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)
        os.replace(tmp, self.marker_path)


def cleanup_debug_pdfs(pdfs: List[Path]) -> Dict[str, List[str]]:
    """Delete each PDF; return {'deleted': [...], 'missing': [...], 'failed': [...]}.

    Also tries to remove empty parent directories left behind (e.g. an empty
    _DEBUG quarter subfolder).
    """
    deleted: List[str] = []
    missing: List[str] = []
    failed: List[str] = []
    parents: set = set()
    for p in pdfs:
        if not p.exists():
            missing.append(str(p))
            continue
        try:
            p.unlink()
            deleted.append(str(p))
            parents.add(p.parent)
        except Exception as e:
            logger.warning(f"Could not delete debug PDF {p}: {e}")
            failed.append(f"{p}: {e}")
    # Best-effort prune of now-empty parent dirs (don't ascend past _DEBUG).
    for parent in sorted(parents, key=lambda p: len(str(p)), reverse=True):
        try:
            current = parent
            while current.exists() and DEBUG_SUBFOLDER_NAME in current.parts:
                if any(current.iterdir()):
                    break
                current.rmdir()
                current = current.parent
        except Exception as e:
            logger.debug(f"Could not prune empty debug dir {parent}: {e}")
    return {"deleted": deleted, "missing": missing, "failed": failed}


def debug_boekhouding_base(real_base: Path) -> Path:
    """The base path used while a debug session is active."""
    return Path(real_base) / DEBUG_SUBFOLDER_NAME
