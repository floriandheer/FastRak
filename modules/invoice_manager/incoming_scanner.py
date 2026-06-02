"""Incoming invoice scanner — filesystem scanning and PDF extraction logic.

Contains no UI code; everything here is pure logic imported by incoming_tab.py.
"""

import os
import re
import sys
from pathlib import Path

import yaml

from shared_logging import get_logger

logger = get_logger("invoice_manager.incoming")

# --- invoice2data optional dependency ----------------------------------------

try:
    from invoice2data import extract_data as i2d_extract
    from invoice2data.extract.loader import read_templates as i2d_read_templates
    INVOICE2DATA_AVAILABLE = True
    try:
        from invoice2data.input import pdfplumber as i2d_input_module
    except Exception:
        try:
            from invoice2data.input import pdfminer as i2d_input_module
        except Exception:
            i2d_input_module = None
except Exception as e:
    INVOICE2DATA_AVAILABLE = False
    i2d_input_module = None
    logger.debug(f"invoice2data not available: {e}")


# --- Template loading ---------------------------------------------------------

def _load_i2d_templates():
    if not INVOICE2DATA_AVAILABLE:
        return None
    tpl_dir = Path(__file__).resolve().parent.parent.parent / "templates" / "invoice_templates"
    if not tpl_dir.is_dir():
        return None
    try:
        templates = i2d_read_templates(str(tpl_dir))
        logger.info(f"Loaded {len(templates)} invoice2data templates from {tpl_dir}")
        return templates
    except Exception as e:
        logger.warning(f"Failed to load invoice2data templates: {e}")
        return None


_cached_i2d_templates = None
_i2d_templates_loaded = False


def _get_i2d_templates():
    global _cached_i2d_templates, _i2d_templates_loaded
    if not _i2d_templates_loaded:
        _cached_i2d_templates = _load_i2d_templates()
        _i2d_templates_loaded = True
    return _cached_i2d_templates


def _load_keyword_map():
    tpl_dir = Path(__file__).resolve().parent.parent.parent / "templates" / "invoice_templates"
    keyword_map = {}
    if not tpl_dir.is_dir():
        return keyword_map
    for yml_path in tpl_dir.glob("*.yml"):
        try:
            with open(yml_path, "r", encoding="utf-8") as f:
                tpl = yaml.safe_load(f)
            issuer = tpl.get("issuer")
            keywords = tpl.get("keywords", [])
            if issuer and keywords:
                keyword_map[issuer] = [kw.lower() for kw in keywords]
        except Exception:
            pass
    return keyword_map


_cached_keyword_map = None


def _get_keyword_map():
    global _cached_keyword_map
    if _cached_keyword_map is None:
        _cached_keyword_map = _load_keyword_map()
    return _cached_keyword_map


# --- PDF text extraction ------------------------------------------------------

def _clean_dotted_text(text):
    """Remove decorative dots between characters in PDF text."""
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        dot_count = line.count('.')
        if dot_count > 5 and dot_count > len(line) / 15:
            line = re.sub(r'\.{2,}', '', line)
            line = re.sub(r'(?<=[a-zA-Z])\.(?=[a-zA-Z])', '', line)
            line = re.sub(r'(?<!\d)\.(?!\d)', ' ', line)
            line = re.sub(r'(?<=\d) (?=\d)', '', line)
            line = re.sub(r'\s{2,}', ' ', line)
            line = line.strip()
        cleaned.append(line)
    return "\n".join(cleaned)


def _extract_text_from_pdf(pdf_path):
    text = ""
    try:
        import pdfplumber
        with pdfplumber.open(str(pdf_path)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception:
        try:
            from pdfminer.high_level import extract_text
            text = extract_text(str(pdf_path))
        except Exception:
            return ""
    return _clean_dotted_text(text)


def _match_vendor_by_keywords(text):
    keyword_map = _get_keyword_map()
    text_lower = text.lower()
    for issuer, keywords in keyword_map.items():
        if all(kw in text_lower for kw in keywords):
            return issuer
    return None


# --- Date extraction ----------------------------------------------------------

DATE_PATTERNS = [
    (re.compile(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})"), "dmy"),
    (re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})"), "ymd"),
    (re.compile(r"(\w+)\s+(\d{1,2}),?\s+(\d{4})"), "mdy_word"),
    (re.compile(r"(\d{1,2})\s+(\w+)\s+(\d{4})"), "dmy_word"),
]

MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    # Dutch
    "januari": 1, "februari": 2, "maart": 3, "mrt": 3, "mei": 5,
    "juni": 6, "juli": 7, "augustus": 8,
    "oktober": 10, "okt": 10,
    # French
    "janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5,
    "juin": 6, "juillet": 7, "août": 8, "septembre": 9,
    "octobre": 10, "novembre": 11, "décembre": 12,
}


def _parse_month_word(word):
    return MONTH_NAMES.get(word.lower())


_LABEL_DATE_PATTERNS = [
    re.compile(
        r'(?:Invoice\s*date|Factuurdatum)[:\s.]*'
        r'(\w+)\s+(\d{1,2}),?\s+(\d{4})',
        re.IGNORECASE,
    ),
    re.compile(
        r'(?:Datum|Date)[:\s]+(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})',
        re.IGNORECASE,
    ),
]


def _extract_date_from_text(text):
    import datetime as dt

    for pattern in _LABEL_DATE_PATTERNS:
        m = pattern.search(text)
        if m:
            groups = m.groups()
            try:
                if len(groups) == 3 and groups[0].isalpha():
                    mo = _parse_month_word(groups[0])
                    d = int(groups[1])
                    y = int(groups[2])
                    if mo and 2020 <= y <= 2030 and 1 <= d <= 31:
                        return dt.date(y, mo, d)
                elif len(groups) == 3:
                    d = int(groups[0])
                    mo = int(groups[1])
                    y = int(groups[2])
                    if 2020 <= y <= 2030 and 1 <= mo <= 12 and 1 <= d <= 31:
                        return dt.date(y, mo, d)
            except (ValueError, IndexError):
                pass

    for pattern, fmt in DATE_PATTERNS:
        for m in pattern.finditer(text):
            try:
                if fmt == "dmy":
                    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                elif fmt == "ymd":
                    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                elif fmt == "mdy_word":
                    mo = _parse_month_word(m.group(1))
                    if not mo:
                        continue
                    d, y = int(m.group(2)), int(m.group(3))
                elif fmt == "dmy_word":
                    d = int(m.group(1))
                    mo = _parse_month_word(m.group(2))
                    if not mo:
                        continue
                    y = int(m.group(3))
                else:
                    continue

                if 2020 <= y <= 2030 and 1 <= mo <= 12 and 1 <= d <= 31:
                    return dt.date(y, mo, d)
            except (ValueError, IndexError):
                continue
    return None


# --- Subprocess extraction (avoids GIL deadlock with stuck regex in C) --------

def _extract_in_subprocess(pdf_path_str, result_queue):
    import datetime as dt
    from pathlib import Path

    pdf_path = Path(pdf_path_str)
    try:
        text = _extract_text_from_pdf(pdf_path)
        if not text.strip():
            result_queue.put((None, "No readable text"))
            return

        i2d_templates = _get_i2d_templates()
        if i2d_templates:
            try:
                kwargs = {"templates": i2d_templates}
                if i2d_input_module:
                    kwargs["input_module"] = i2d_input_module
                result = i2d_extract(str(pdf_path), **kwargs)
                if result:
                    issuer = result.get("issuer")
                    inv_date = result.get("date")
                    if isinstance(inv_date, dt.datetime):
                        inv_date = inv_date.date()
                    if issuer and inv_date:
                        new_name = _generate_filename(inv_date, issuer)
                        info = f"{inv_date.strftime('%d/%m/%Y')} | {issuer}"
                        result_queue.put((new_name, info))
                        return
            except Exception:
                pass

        issuer = _match_vendor_by_keywords(text)
        if not issuer:
            result_queue.put((None, "No template matched"))
            return

        inv_date = _extract_date_from_text(text)
        if inv_date:
            new_name = _generate_filename(inv_date, issuer)
            info = f"{inv_date.strftime('%d/%m/%Y')} | {issuer} (fallback)"
            result_queue.put((new_name, info))
        else:
            result_queue.put((None, f"? | {issuer} (no date found)"))
    except Exception as e:
        result_queue.put((None, f"Error: {e}"))


def _extract_vendor_from_pdf(pdf_path):
    templates = _get_i2d_templates()
    if templates:
        try:
            kwargs = {"templates": templates}
            if i2d_input_module:
                kwargs["input_module"] = i2d_input_module
            result = i2d_extract(str(pdf_path), **kwargs)
            if result and result.get("issuer"):
                return result.get("issuer")
        except Exception as e:
            logger.debug(f"invoice2data failed for {pdf_path.name}: {e}")

    text = _extract_text_from_pdf(pdf_path)
    if text:
        issuer = _match_vendor_by_keywords(text)
        if issuer:
            logger.debug(f"Keyword fallback matched {pdf_path.name} -> {issuer}")
            return issuer

    return None


# --- Configuration ------------------------------------------------------------

def _resolve_boekhouding_root() -> Path:
    """Read the canonical bookkeeping root from the global_invoice config,
    falling back to the historical hardcoded path if that module isn't
    available or hasn't been configured.
    """
    try:
        from global_invoice.config import load_config
        return load_config().resolve_boekhouding_base()
    except Exception:
        return Path(r"D:\_work\Active\_LIBRARY\Boekhouding")


BOEKHOUDING_ROOT = _resolve_boekhouding_root()


def _generate_filename(date_obj, company_name, extension=".pdf"):
    """Generate standardised incoming invoice filename: FAC_YY-MM-DD_CompanyName.ext"""
    date_str = date_obj.strftime("%y-%m-%d")
    company_clean = re.sub(r"[^\w\-]", "", company_name)
    return f"FAC_{date_str}_{company_clean}{extension}"


# Expected recurring invoices grouped by category.
# frequency: "monthly" (3 per Q), "quarterly" (1 per Q), "yearly" (1+ per year)
# expected_quarter: for yearly invoices, which quarter they typically arrive in
# expected_yearly: for yearly invoices, how many per year (default 1)
# optional: True means missing = warning instead of error
EXPECTED_INVOICES = {
    "Abonnementen (Online)": {
        "Microsoft":  {"frequency": "yearly"},
        "OVHcloud":   {"frequency": "yearly", "expected_yearly": 3},
        "Google":     {"frequency": "monthly"},
        "Combell":    {"frequency": "yearly", "expected_yearly": 2},
        "Houdini":    {"frequency": "yearly", "expected_quarter": 2},
        "Doccle":     {"frequency": "yearly"},
        "Cloudflare": {"frequency": "yearly", "optional": True},
        "AmazonS3":   {"frequency": "yearly", "optional": True},
    },
    "Domiciliering": {
        "Orange":         {"frequency": "monthly"},
        "KBC":            {"frequency": "yearly", "expected_quarter": 4},
        "Anthropic":      {"frequency": "monthly"},
        "YoutubePremium": {"frequency": "monthly"},
        "DeWatergroep":   {"frequency": "quarterly"},
        "Eneco":          {"frequency": "quarterly"},
    },
    "Boekhouder": {
        "PietPas": {"frequency": "quarterly"},
    },
}


# --- Filesystem scanning -----------------------------------------------------

def _get_quarter_folder(year: int, quarter: int):
    return BOEKHOUDING_ROOT / str(year) / f"Q{quarter}" / "Binnenkomend"


def _get_quarter_files(year: int, quarter: int):
    folder = _get_quarter_folder(year, quarter)
    if folder.exists():
        return [f.name for f in folder.iterdir() if f.is_file()]
    return []


def scan_quarter(year: int, quarter: int) -> dict:
    """Scan a quarter folder and return status for each expected monthly/quarterly invoice."""
    files = _get_quarter_files(year, quarter)
    files_lower = [f.lower() for f in files]

    results = {}
    for category, vendors in EXPECTED_INVOICES.items():
        cat_results = {}
        for vendor, config in vendors.items():
            freq = config["frequency"]
            if freq == "yearly":
                continue

            optional = config.get("optional", False)
            expected_count = 3 if freq == "monthly" else 1

            vendor_lower = vendor.lower()
            matches = [
                files[i] for i, f in enumerate(files_lower)
                if vendor_lower in f
            ]

            if len(matches) >= expected_count:
                status = "ok"
            elif len(matches) > 0:
                status = "partial"
            elif optional:
                status = "optional_missing"
            else:
                status = "missing"

            cat_results[vendor] = {
                "config": config,
                "matches": matches,
                "status": status,
                "expected_count": expected_count,
            }

        if cat_results:
            results[category] = cat_results

    return results


def scan_year(year: int) -> dict:
    """Scan all quarters for yearly invoices."""
    quarter_files = {q: _get_quarter_files(year, q) for q in range(1, 5)}

    results = {}
    for category, vendors in EXPECTED_INVOICES.items():
        cat_results = {}
        for vendor, config in vendors.items():
            freq = config["frequency"]
            if freq != "yearly":
                continue

            optional = config.get("optional", False)
            expected_count = config.get("expected_yearly", 1)
            vendor_lower = vendor.lower()

            matches_per_q = {}
            total_matches = 0
            for q in range(1, 5):
                files = quarter_files[q]
                files_lower = [f.lower() for f in files]
                q_matches = [
                    files[i] for i, f in enumerate(files_lower)
                    if vendor_lower in f
                ]
                if q_matches:
                    matches_per_q[q] = q_matches
                    total_matches += len(q_matches)

            if total_matches >= expected_count:
                status = "ok"
            elif total_matches > 0:
                status = "partial"
            elif optional:
                status = "optional_missing"
            else:
                status = "missing"

            cat_results[vendor] = {
                "config": config,
                "matches": matches_per_q,
                "status": status,
                "expected_count": expected_count,
                "total_found": total_matches,
            }

        if cat_results:
            results[category] = cat_results

    return results


def _quarter_for_month(month: int) -> int:
    return (month - 1) // 3 + 1


VALID_PREFIXES = ("FAC", "CRE", "TIC")
NAMING_PATTERN = re.compile(
    r"^(FAC|CRE|TIC)_(\d{2})-(\d{2})-(\d{2})_(.+)\.(pdf|jpg|jpeg|png)$",
    re.IGNORECASE,
)


def validate_filenames(year: int) -> list:
    """Check all filenames in a year for naming issues.

    Returns list of (quarter, filename, [issues], issue_type).
    issue_type is "no_match" or "has_errors".
    """
    issues_list = []

    for q in range(1, 5):
        files = _get_quarter_files(year, q)
        for fname in files:
            issues = []

            double_ext = re.search(r"\.(pdf|jpg|jpeg|png)\.\1$", fname, re.IGNORECASE)
            if double_ext:
                issues.append("Double extension")

            if " " in fname:
                issues.append("Spaces in filename")

            m = NAMING_PATTERN.match(fname)
            if m is None:
                cleaned = re.sub(
                    r"\.(pdf|jpg|jpeg|png)\.(pdf|jpg|jpeg|png)$",
                    lambda x: "." + x.group(2),
                    fname, flags=re.IGNORECASE,
                )
                m_cleaned = NAMING_PATTERN.match(cleaned)
                if m_cleaned is None:
                    issues.append("Does not match naming convention, please rename")
                    issues_list.append((q, fname, issues, "no_match"))
                    continue
                else:
                    m = m_cleaned

            prefix, yy, mm, dd = m.group(1), m.group(2), m.group(3), m.group(4)
            vendor_part = m.group(5)
            ext = m.group(6)

            actual_ext = fname.rsplit(".", 1)[-1]
            if actual_ext != actual_ext.lower():
                issues.append(f"Extension not lowercase: .{actual_ext}")

            actual_prefix = fname.split("_")[0]
            if actual_prefix != actual_prefix.upper():
                issues.append(f"Prefix not uppercase: {actual_prefix}")

            if vendor_part and not vendor_part[0].isupper() and not vendor_part[0].isdigit():
                issues.append(f"Name starts with lowercase: {vendor_part}")

            try:
                file_month = int(mm)
                file_year = int(yy) + 2000
                file_day = int(dd)
                if not (1 <= file_month <= 12 and 1 <= file_day <= 31):
                    issues.append(f"Invalid date: {yy}-{mm}-{dd}")
                else:
                    file_q = _quarter_for_month(file_month)
                    if file_year == year and file_q != q:
                        issues.append(f"Date is Q{file_q} but filed in Q{q}")
                    elif file_year != year:
                        issues.append(f"Date is {file_year} but filed in {year}")
            except ValueError:
                issues.append(f"Invalid date: {yy}-{mm}-{dd}")

            if issues:
                issues_list.append((q, fname, issues, "has_errors"))

    return issues_list


def find_duplicates(year: int) -> list:
    """Find files that appear in multiple quarters.

    Returns list of (filename, [(q, full_name), ...]) for cross-quarter duplicates.
    """
    all_files = {}
    for q in range(1, 5):
        for fname in _get_quarter_files(year, q):
            key = fname.lower().strip()
            all_files.setdefault(key, []).append((q, fname))

    duplicates = []
    for key, locations in sorted(all_files.items()):
        if len(set(q for q, _ in locations)) > 1:
            duplicates.append((locations[0][1], locations))

    return duplicates
