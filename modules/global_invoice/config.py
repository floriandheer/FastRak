"""Configuration loader for the Global Invoice module.

User-private data (config.json, invoices.sqlite) lives outside the repo
in the per-user PipelineManager AppData folder so it isn't synced to git.
Templates and the example config are bundled inside the package itself.

Falls back to sensible defaults for db_path / boekhouding_base / soffice_path.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional

from shared_logging import get_logger

from .models import Company

logger = get_logger(__name__)


# Path layout (post-migration):
#   <repo>/modules/global_invoice/config.py            ← this file
#   <repo>/modules/global_invoice/config.json.example  ← template (committed)
#   <repo>/modules/global_invoice/README.txt           ← docs (committed)
#   <appdata>/PipelineManager/global_invoice/config.json     ← user data
#   <appdata>/PipelineManager/global_invoice/invoices.sqlite ← user data
_PKG_DIR = Path(__file__).resolve().parent
_MODULES_DIR = _PKG_DIR.parent
REPO_ROOT = _MODULES_DIR.parent
CONFIG_EXAMPLE_PATH = _PKG_DIR / "config.json.example"

# Legacy (pre-migration) location — files here get moved to DATA_DIR on first run.
_LEGACY_DATA_DIR = _MODULES_DIR / "global_invoice_data"

_MIGRATABLE_FILENAMES = (
    "config.json",
    "invoices.sqlite",
    "invoices.sqlite-wal",
    "invoices.sqlite-shm",
)


def _get_user_data_dir() -> Path:
    """Per-user PipelineManager AppData dir, matching rak_settings convention."""
    if sys.platform == "win32":
        return Path.home() / "AppData" / "Local" / "PipelineManager" / "global_invoice"
    # WSL: prefer the Windows user's AppData so it stays in sync with native runs
    windows_users = Path("/mnt/c/Users")
    if windows_users.exists():
        username = os.environ.get("USER", "")
        user_path = windows_users / username
        if user_path.exists():
            return user_path / "AppData" / "Local" / "PipelineManager" / "global_invoice"
    return Path.home() / ".local" / "share" / "PipelineManager" / "global_invoice"


DATA_DIR = _get_user_data_dir()
CONFIG_PATH = DATA_DIR / "config.json"
DEFAULT_DB_PATH = DATA_DIR / "invoices.sqlite"


def _migrate_legacy_data() -> None:
    """One-shot migration: move legacy in-repo data files into the user data dir.

    Runs on every load_config() but is a no-op once the legacy files are gone.
    Never overwrites a file that already exists at the new location.
    """
    if not _LEGACY_DATA_DIR.exists():
        return
    moved: List[str] = []
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for filename in _MIGRATABLE_FILENAMES:
        src = _LEGACY_DATA_DIR / filename
        dst = DATA_DIR / filename
        if not src.exists():
            continue
        if dst.exists():
            logger.warning(
                f"Legacy file {src} exists but {dst} already does too — "
                f"leaving legacy in place; resolve manually."
            )
            continue
        try:
            shutil.move(str(src), str(dst))
            moved.append(filename)
        except Exception as e:
            logger.error(f"Failed to migrate {src} → {dst}: {e}")
    if moved:
        logger.info(
            f"Migrated global_invoice data files to {DATA_DIR}: {moved}. "
            f"Legacy folder {_LEGACY_DATA_DIR} can be removed."
        )


class ConfigError(Exception):
    pass


class GlobalInvoiceConfig:
    def __init__(self, raw: dict, source_path: Path):
        self._raw = raw
        self.source_path = source_path
        self.companies: List[Company] = []
        self._companies_by_key: Dict[str, Company] = {}
        self._parse()

    def _parse(self):
        companies = self._raw.get("companies") or []
        if not companies:
            raise ConfigError("config.json has no 'companies' entries")
        for entry in companies:
            try:
                c = Company(
                    key=entry["key"],
                    display_name=entry["display_name"],
                    legal_name=entry.get("legal_name", entry["display_name"]),
                    vat=entry.get("vat", ""),
                    address_lines=list(entry.get("address_lines") or []),
                    output_prefix=entry.get("output_prefix", entry["key"]),
                    default_vat_rate=float(entry.get("default_vat_rate", 21.0)),
                    email=entry.get("email", ""),
                    iban=entry.get("iban", ""),
                    bic=entry.get("bic", ""),
                    template_path=entry.get("template_path"),
                    wc_binding=entry.get("wc_binding"),
                )
            except KeyError as ke:
                raise ConfigError(f"Company entry missing required field: {ke}") from ke
            self.companies.append(c)
            self._companies_by_key[c.key] = c

    # --- accessors ---
    def get_company(self, key: str) -> Company:
        if key not in self._companies_by_key:
            raise KeyError(f"Unknown company key: {key!r}")
        return self._companies_by_key[key]

    def company_keys(self) -> List[str]:
        return [c.key for c in self.companies]

    @property
    def currency(self) -> str:
        return self._raw.get("behavior", {}).get("currency", "EUR")

    @property
    def year_change_confirm_threshold(self) -> int:
        return int(self._raw.get("behavior", {}).get("year_change_confirm_threshold", 1))

    @property
    def auto_open_pdf_after_generate(self) -> bool:
        return bool(self._raw.get("behavior", {}).get("auto_open_pdf_after_generate", True))

    # --- path resolution ---
    def resolve_template_path(self, company: Company) -> Optional[Path]:
        if not company.template_path:
            return None
        p = Path(company.template_path)
        if not p.is_absolute():
            p = REPO_ROOT / p
        return p

    def resolve_db_path(self) -> Path:
        raw = (self._raw.get("paths") or {}).get("db_path")
        if raw:
            p = Path(raw)
            if not p.is_absolute():
                p = REPO_ROOT / p
            return p
        return DEFAULT_DB_PATH

    def resolve_boekhouding_base(self) -> Path:
        raw = (self._raw.get("paths") or {}).get("boekhouding_base")
        if raw:
            return Path(raw)
        # Fall back to rak_settings.get_active_base()/_LIBRARY/Boekhouding
        from rak_settings import get_rak_settings
        return Path(get_rak_settings().get_active_base()) / "_LIBRARY" / "Boekhouding"

    def resolve_soffice_path(self) -> Optional[Path]:
        raw = (self._raw.get("paths") or {}).get("soffice_path")
        if raw:
            p = Path(raw)
            return p if p.exists() else None
        # Search PATH
        found = shutil.which("soffice") or shutil.which("soffice.exe")
        if found:
            return Path(found)
        # Common Windows install locations (works from WSL via /mnt/c too)
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

    # --- WC binding helper ---
    def get_wc_credentials_for_alles3d(self) -> Optional[dict]:
        """Return WC credentials dict for company '3D'.

        If wc_binding.use_monitor_config is true, read from the existing
        woocommerce_monitor_data/config.json so credentials live in one place.
        """
        try:
            company = self.get_company("3D")
        except KeyError:
            return None
        if not company.wc_binding:
            return None
        if company.wc_binding.get("use_monitor_config"):
            monitor_cfg = _MODULES_DIR / "woocommerce_monitor_data" / "config.json"
            if monitor_cfg.exists():
                try:
                    with open(monitor_cfg, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    return data.get("woocommerce")
                except Exception as e:
                    logger.warning(f"Failed to read WC monitor config: {e}")
                    return None
            else:
                logger.warning("WC monitor config.json not found; cannot load credentials")
                return None
        # Inline credentials
        binding = dict(company.wc_binding)
        binding.pop("use_monitor_config", None)
        return binding


def load_config(path: Optional[Path] = None) -> GlobalInvoiceConfig:
    """Load and parse config.json. Raises ConfigError if missing or invalid."""
    if path is None:
        _migrate_legacy_data()
    cfg_path = Path(path) if path else CONFIG_PATH
    if not cfg_path.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        raise ConfigError(
            f"Config not found: {cfg_path}\n\n"
            f"Copy the template into place:\n"
            f"    {CONFIG_EXAMPLE_PATH}\n"
            f"  → {cfg_path}\n\n"
            f"Then edit the company entries with your real legal name, VAT, "
            f"address, and bank details."
        )
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in {cfg_path}: {e}") from e
    return GlobalInvoiceConfig(raw, cfg_path)
