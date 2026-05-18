"""Headless LibreOffice PDF exporter.

Runs `soffice --headless --convert-to pdf <odt>` with an isolated
UserInstallation so concurrent invocations don't fight over the profile lock.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from shared_logging import get_logger

logger = get_logger(__name__)


class PdfExportError(Exception):
    pass


def odt_to_pdf(
    odt_path: Path,
    output_dir: Path,
    soffice_path: Optional[Path] = None,
    timeout: int = 90,
) -> Path:
    """Convert an .odt file to .pdf in `output_dir`. Returns the produced PDF path.

    Args:
        odt_path: Source .odt file.
        output_dir: Directory where the PDF is written (created if missing).
        soffice_path: Explicit soffice binary path. If None, falls back to PATH
            search and known install locations.
        timeout: Subprocess timeout in seconds.
    """
    odt_path = Path(odt_path)
    output_dir = Path(output_dir)
    if not odt_path.exists():
        raise PdfExportError(f"ODT not found: {odt_path}")
    output_dir.mkdir(parents=True, exist_ok=True)

    binary = Path(soffice_path) if soffice_path else _autodetect_soffice()
    if not binary or not binary.exists():
        raise PdfExportError(
            "soffice binary not found. Install LibreOffice or set "
            "paths.soffice_path in global_invoice_data/config.json."
        )

    # Isolated user profile per invocation — avoids profile lock contention
    # when two renders run in parallel.
    with tempfile.TemporaryDirectory(prefix="soffice_profile_") as profile_dir:
        # The user-installation URI must be a file:// URL
        profile_uri = Path(profile_dir).as_uri()
        cmd = [
            str(binary),
            "--headless",
            "--nologo",
            "--nodefault",
            "--nofirststartwizard",
            f"-env:UserInstallation={profile_uri}",
            "--convert-to", "pdf",
            "--outdir", str(output_dir),
            str(odt_path),
        ]
        logger.info(f"Running soffice: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout, check=False
            )
        except subprocess.TimeoutExpired as e:
            raise PdfExportError(
                f"soffice timed out after {timeout}s converting {odt_path.name}"
            ) from e

        if result.returncode != 0:
            raise PdfExportError(
                f"soffice failed (exit {result.returncode}). "
                f"stdout={result.stdout.strip()} stderr={result.stderr.strip()}"
            )

    # soffice writes <basename>.pdf to outdir
    pdf_path = output_dir / f"{odt_path.stem}.pdf"
    if not pdf_path.exists():
        raise PdfExportError(
            f"soffice succeeded but expected output not found: {pdf_path}"
        )
    logger.info(f"Exported PDF: {pdf_path}")
    return pdf_path


def _autodetect_soffice() -> Optional[Path]:
    found = shutil.which("soffice") or shutil.which("soffice.exe")
    if found:
        return Path(found)
    candidates = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "/mnt/c/Program Files/LibreOffice/program/soffice.exe",
        "/mnt/c/Program Files (x86)/LibreOffice/program/soffice.exe",
        "/usr/bin/soffice",
        "/usr/bin/libreoffice",
    ]
    for c in candidates:
        p = Path(c)
        if p.exists():
            return p
    return None
