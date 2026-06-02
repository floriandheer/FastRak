"""Scan the Boekhouding Uitgaand tree for legacy and current invoice PDFs.

Four filename patterns have been used over the years:

  canonical        {PREFIX}_{YYMMDD}_Factuur{seq}_{client}.pdf
                   Prefix matches a known company output_prefix (e.g. '3D').

  prefixed_legacy  {CLIENT_CODE}_{YYMMDD}_Factuur{seq}_{project}.pdf
                   Prefix is a client abbreviation (e.g. 'SW' = Skermwest).
                   Company is always 'FD'.  Used 2024.

  long_date_legacy Factuur{seq:05d}_{YYYYMMDD}_{description}.pdf
                   No company prefix; company is always 'FD'.  Used 2021-2023.

Files that match none of the above are tagged 'unrecognised'.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set

# ── pattern constants ────────────────────────────────────────────────────────

PATTERN_CANONICAL = "canonical"
PATTERN_PREFIXED_LEGACY = "prefixed_legacy"
PATTERN_LONG_DATE_LEGACY = "long_date_legacy"
PATTERN_UNRECOGNISED = "unrecognised"

# {PREFIX}_{YYMMDD}_Factuur{seq}_{desc}.pdf
_RE_PREFIXED = re.compile(
    r"^(?P<prefix>[A-Z0-9]{2,4})_(?P<yymmdd>\d{6})_Factuur(?P<seq>\d+)_(?P<desc>.+)\.pdf$",
    re.IGNORECASE,
)

# Factuur{seq}_{YYYYMMDD}_{desc}.pdf
_RE_LONG_DATE = re.compile(
    r"^Factuur(?P<seq>\d+)_(?P<yyyymmdd>\d{8})_(?P<desc>.+)\.pdf$",
    re.IGNORECASE,
)


# ── result dataclass ─────────────────────────────────────────────────────────

@dataclass
class ScannedInvoice:
    path: Path
    year: int
    quarter: int
    pattern: str
    sequence: Optional[int]
    invoice_date: Optional[str]  # ISO YYYY-MM-DD, or None
    company_key: Optional[str]   # e.g. '3D', 'FD', 'HV', or None
    client_code: Optional[str]   # prefixed_legacy only: the client prefix (e.g. 'SW')
    description: str             # human-readable description / project
    notes: str = field(default="")  # warnings set post-scan (e.g. duplicate seq)

    @property
    def can_import(self) -> bool:
        """True if enough metadata is present to create a registry stub."""
        return (
            self.pattern != PATTERN_UNRECOGNISED
            and self.sequence is not None
            and self.invoice_date is not None
            and self.company_key is not None
        )

    @property
    def import_customer_name(self) -> str:
        """Best-effort customer name for registry import."""
        if self.pattern == PATTERN_PREFIXED_LEGACY and self.client_code:
            return f"{self.client_code} — {self.description.split(' — ', 1)[-1]}"
        return self.description


# ── helpers ──────────────────────────────────────────────────────────────────

def _parse_yymmdd(s: str) -> Optional[str]:
    try:
        return datetime.strptime(s, "%y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_yyyymmdd(s: str) -> Optional[str]:
    try:
        return datetime.strptime(s, "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        return None


def _classify(path: Path, year: int, quarter: int,
               known_prefixes: Set[str]) -> ScannedInvoice:
    name = path.name

    m = _RE_PREFIXED.match(name)
    if m:
        prefix = m.group("prefix").upper()
        seq = int(m.group("seq"))
        inv_date = _parse_yymmdd(m.group("yymmdd"))
        desc = m.group("desc")
        if prefix in known_prefixes:
            return ScannedInvoice(
                path=path, year=year, quarter=quarter,
                pattern=PATTERN_CANONICAL,
                sequence=seq, invoice_date=inv_date,
                company_key=prefix, client_code=None,
                description=desc,
            )
        return ScannedInvoice(
            path=path, year=year, quarter=quarter,
            pattern=PATTERN_PREFIXED_LEGACY,
            sequence=seq, invoice_date=inv_date,
            company_key="FD", client_code=prefix,
            description=f"{prefix} — {desc}",
        )

    m = _RE_LONG_DATE.match(name)
    if m:
        return ScannedInvoice(
            path=path, year=year, quarter=quarter,
            pattern=PATTERN_LONG_DATE_LEGACY,
            sequence=int(m.group("seq")),
            invoice_date=_parse_yyyymmdd(m.group("yyyymmdd")),
            company_key="FD", client_code=None,
            description=m.group("desc"),
        )

    return ScannedInvoice(
        path=path, year=year, quarter=quarter,
        pattern=PATTERN_UNRECOGNISED,
        sequence=None, invoice_date=None,
        company_key=None, client_code=None,
        description=path.stem,
    )


def _flag_duplicates(invoices: List[ScannedInvoice]) -> None:
    """Annotate invoices that share (year, company_key, sequence)."""
    counts: Counter = Counter()
    for inv in invoices:
        if inv.sequence is not None and inv.company_key:
            counts[(inv.year, inv.company_key, inv.sequence)] += 1
    for inv in invoices:
        if inv.sequence is not None and inv.company_key:
            k = (inv.year, inv.company_key, inv.sequence)
            if counts[k] > 1:
                inv.notes = (
                    f"Duplicate: #{inv.sequence} appears {counts[k]}x in {inv.year}"
                )


# ── public API ────────────────────────────────────────────────────────────────

def scan_boekhouding(
    boekhouding_base: Path,
    known_company_prefixes: Set[str],
) -> List[ScannedInvoice]:
    """Walk {base}/{YYYY}/Q{n}/Uitgaand/ and classify every PDF found.

    Args:
        boekhouding_base: root of the Boekhouding tree.
        known_company_prefixes: uppercase set of output_prefix values from
            config (e.g. {'3D', 'FD', 'HV'}).  Prefixed filenames whose
            prefix is in this set are tagged canonical; others are tagged
            prefixed_legacy and assigned to company 'FD'.

    Returns a flat list sorted by (year, quarter, filename).
    Duplicate (year, company, sequence) combinations are annotated.
    """
    results: List[ScannedInvoice] = []
    base = Path(boekhouding_base)
    if not base.exists():
        return results

    for year_dir in sorted(base.iterdir()):
        if not year_dir.is_dir():
            continue
        try:
            year = int(year_dir.name)
        except ValueError:
            continue

        for quarter_dir in sorted(year_dir.iterdir()):
            if not quarter_dir.is_dir():
                continue
            qm = re.match(r"^Q(\d)$", quarter_dir.name, re.IGNORECASE)
            if not qm:
                continue
            quarter = int(qm.group(1))

            for child in quarter_dir.iterdir():
                if child.is_dir() and child.name.lower() == "uitgaand":
                    for pdf in sorted(child.iterdir()):
                        if pdf.suffix.lower() == ".pdf":
                            results.append(
                                _classify(pdf, year, quarter,
                                          known_company_prefixes)
                            )
                    break

    _flag_duplicates(results)
    return results
