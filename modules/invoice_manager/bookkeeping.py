"""Quarterly bookkeeping folder structure helpers.

Replaces the standalone ``PipelineScript_Bookkeeping_FolderStructure.py``
GUI by exposing the same logic as plain functions, so InvoiceManager can
create / inspect the ``{boekhouding}/{year}/Q{n}/{Binnenkomend,Uitgaand}``
hierarchy from inside its own Settings section.

The base directory is always ``state.config.resolve_boekhouding_base()``
— i.e. the same path the rest of the app reads — so quarter folders
land exactly where the Outgoing / Incoming sections look for invoices.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import List, Tuple

from shared_folder_tree_parser import parse_tree_file, create_structure

QUARTERS: Tuple[str, str, str, str] = ("Q1", "Q2", "Q3", "Q4")

QUARTER_MONTHS = {
    "Q1": (1, 2, 3),
    "Q2": (4, 5, 6),
    "Q3": (7, 8, 9),
    "Q4": (10, 11, 12),
}

INCOMING_FOLDER = "Binnenkomend"
OUTGOING_FOLDER = "Uitgaand"

_TEMPLATE_NAME = "bookkeeping_structure.txt"


def _templates_dir() -> Path:
    """Repo-level templates folder (where ``bookkeeping_structure.txt`` lives)."""
    return Path(__file__).resolve().parent.parent.parent / "templates"


def get_current_quarter(today: datetime.date | None = None) -> str:
    today = today or datetime.date.today()
    for q, months in QUARTER_MONTHS.items():
        if today.month in months:
            return q
    return "Q1"


def get_next_quarter(today: datetime.date | None = None) -> str:
    current = get_current_quarter(today)
    idx = QUARTERS.index(current)
    return QUARTERS[(idx + 1) % 4]


def quarter_dir(base_dir: Path | str, year: int | str, quarter: str) -> Path:
    return Path(base_dir) / str(year) / quarter


def quarter_status(base_dir: Path | str, year: int | str, quarter: str) -> str:
    """One of ``"complete"``, ``"incomplete"``, ``"missing"``."""
    qdir = quarter_dir(base_dir, year, quarter)
    if not qdir.exists():
        return "missing"
    incoming = qdir / INCOMING_FOLDER
    outgoing = qdir / OUTGOING_FOLDER
    if incoming.exists() and outgoing.exists():
        return "complete"
    return "incomplete"


def create_quarter_folders(
    base_dir: Path | str,
    year: int | str,
    quarter: str,
) -> Tuple[bool, str]:
    """Create the ``{base}/{year}/{quarter}/...`` structure.

    Returns ``(True, str(quarter_dir))`` on success, ``(False, error)``
    on failure. Idempotent — already-existing folders are left alone.
    """
    try:
        qdir = quarter_dir(base_dir, year, quarter)
        qdir.mkdir(parents=True, exist_ok=True)
        tree_file = _templates_dir() / _TEMPLATE_NAME
        tree = parse_tree_file(str(tree_file))
        create_structure(str(qdir), tree)
        return True, str(qdir)
    except Exception as e:
        return False, str(e)


def list_quarter_statuses(base_dir: Path | str, year: int | str) -> List[Tuple[str, str, Path]]:
    """Return ``[(quarter, status, full_path), ...]`` for all four
    quarters of ``year``."""
    return [
        (q, quarter_status(base_dir, year, q), quarter_dir(base_dir, year, q))
        for q in QUARTERS
    ]
