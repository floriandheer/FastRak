"""Places generated PDFs into the Boekhouding folder structure.

Pattern (matches existing Alles3D format from PipelineScript_Physical_
WooCommerceOrderMonitor.py InvoiceFiler._build_invoice_filename):
  {boekhouding_base}/{YYYY}/Q{n}/Uitgaand/{prefix}_{YYMMDD}_Factuur{seq:03d}_{ClientName}.pdf
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from shared_logging import get_logger

logger = get_logger(__name__)


class FilerError(Exception):
    pass


def quarter_for(month: int) -> int:
    return (month - 1) // 3 + 1


def clean_client_name(name: str) -> str:
    """Strip filesystem-unfriendly chars and spaces. Matches WC monitor logic."""
    cleaned = name.replace(" ", "").replace("_", "")
    for ch in '<>:"/\\|?*':
        cleaned = cleaned.replace(ch, "")
    return cleaned


def build_invoice_filename(
    output_prefix: str,
    invoice_date: str,
    sequence: int,
    customer_name: str,
) -> str:
    """Build the canonical invoice filename.

    Args:
        output_prefix: e.g. 'FD' / 'HV' / '3D'.
        invoice_date: ISO YYYY-MM-DD.
        sequence: invoice number within its year (1-based).
        customer_name: raw customer name; will be cleaned.
    """
    dt = datetime.strptime(invoice_date[:10], "%Y-%m-%d")
    date_part = dt.strftime("%y%m%d")
    return (
        f"{output_prefix}_{date_part}_Factuur{int(sequence):03d}_"
        f"{clean_client_name(customer_name)}.pdf"
    )


def quarter_dir_for(boekhouding_base: Path, invoice_date: str) -> Path:
    """Return {base}/YYYY/Q{n}/Uitgaand. Does NOT mkdir; caller decides."""
    dt = datetime.strptime(invoice_date[:10], "%Y-%m-%d")
    return Path(boekhouding_base) / str(dt.year) / f"Q{quarter_for(dt.month)}" / "Uitgaand"


def file_pdf(
    pdf_src: Path,
    boekhouding_base: Path,
    output_prefix: str,
    invoice_date: str,
    sequence: int,
    customer_name: str,
    move: bool = True,
) -> Path:
    """Move (or copy) the rendered PDF into the Boekhouding tree.

    Returns the final filed path. Creates parent directories as needed.
    """
    pdf_src = Path(pdf_src)
    if not pdf_src.exists():
        raise FilerError(f"Source PDF does not exist: {pdf_src}")
    dest_dir = quarter_dir_for(boekhouding_base, invoice_date)
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = build_invoice_filename(
        output_prefix, invoice_date, sequence, customer_name
    )
    dest_path = dest_dir / filename
    # Refuse to overwrite an existing filed invoice — it should never happen
    # under the gapless-numbering guarantee, so if it does we want to know.
    if dest_path.exists():
        raise FilerError(
            f"Destination already exists, refusing to overwrite: {dest_path}"
        )
    if move:
        shutil.move(str(pdf_src), str(dest_path))
    else:
        shutil.copy2(str(pdf_src), str(dest_path))
    logger.info(f"Filed invoice PDF: {dest_path}")
    return dest_path


def create_shortcut(shortcut_path: Path, target_path: Path) -> Optional[Path]:
    """Create a Windows .lnk pointing at target_path. No-op on non-Windows."""
    try:
        import win32com.client
    except ImportError:
        logger.debug("pywin32 not available — skipping shortcut creation")
        return None
    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        sc = shell.CreateShortCut(str(shortcut_path))
        sc.TargetPath = str(target_path)
        sc.WorkingDirectory = str(target_path.parent)
        sc.save()
        logger.info(f"Created shortcut: {shortcut_path}")
        return shortcut_path
    except Exception as e:
        logger.error(f"Failed to create shortcut at {shortcut_path}: {e}")
        return None
