"""
Invoice Checker - Quarterly & Yearly Invoice Verification
Scans the bookkeeping folder to verify all expected recurring invoices
are present for a given quarter or year. Detects cross-quarter duplicates.
"""

import os
import re
import sys
import threading
import tkinter as tk
from tkinter import ttk
from datetime import datetime
from pathlib import Path
import yaml

# Add parent dir so shared modules can be imported when run standalone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shared_form_keyboard import FORM_COLORS
from shared_logging import setup_logging as setup_shared_logging, get_logger
try:
    from invoice2data import extract_data as i2d_extract
    from invoice2data.extract.loader import read_templates as i2d_read_templates
    INVOICE2DATA_AVAILABLE = True
    # Try pdfplumber input module; fall back to pdfminer or default
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
    print(f"[InvoiceChecker] invoice2data import failed: {e}")

logger = get_logger("invoice_checker")

# --- PDF CONTENT EXTRACTION --------------------------------------------------


def _load_i2d_templates():
    """Load invoice2data templates once and cache them."""
    if not INVOICE2DATA_AVAILABLE:
        return None
    tpl_dir = Path(__file__).resolve().parent.parent / "templates" / "invoice_templates"
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
    """Return cached invoice2data templates (loaded on first call)."""
    global _cached_i2d_templates, _i2d_templates_loaded
    if not _i2d_templates_loaded:
        _cached_i2d_templates = _load_i2d_templates()
        _i2d_templates_loaded = True
    return _cached_i2d_templates


def _load_keyword_map():
    """Load {issuer: [keywords]} from YAML template files."""
    tpl_dir = Path(__file__).resolve().parent.parent / "templates" / "invoice_templates"
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
    """Return cached keyword map (loaded on first call)."""
    global _cached_keyword_map
    if _cached_keyword_map is None:
        _cached_keyword_map = _load_keyword_map()
    return _cached_keyword_map


def _clean_dotted_text(text):
    """Remove decorative dots between characters in PDF text.

    Some PDFs (e.g. Google invoices) render text like
    '.Invoice. .dateOct. 3 1.,. .2 0.2 5'
    This collapses runs of dots and spaces to recover the actual text.
    """
    # Detect lines with dotted patterns (many single dots among characters)
    # and clean them more aggressively
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        # Count dots in the line
        dot_count = line.count('.')
        if dot_count > 5 and dot_count > len(line) / 15:
            # This line has dotted formatting — clean aggressively
            # Remove multi-dot sequences first
            line = re.sub(r'\.{2,}', '', line)
            # Remove dots between letters
            line = re.sub(r'(?<=[a-zA-Z])\.(?=[a-zA-Z])', '', line)
            # Remove remaining isolated dots not between digits
            line = re.sub(r'(?<!\d)\.(?!\d)', ' ', line)
            # Collapse "digit space digit" patterns: "3 0" -> "30"
            line = re.sub(r'(?<=\d) (?=\d)', '', line)
            # Collapse whitespace
            line = re.sub(r'\s{2,}', ' ', line)
            line = line.strip()
        cleaned.append(line)
    return "\n".join(cleaned)


def _extract_text_from_pdf(pdf_path):
    """Extract text from a PDF using pdfplumber."""
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
    """Match extracted PDF text against template keywords.

    Returns the issuer string or None.
    """
    keyword_map = _get_keyword_map()
    text_lower = text.lower()
    for issuer, keywords in keyword_map.items():
        if all(kw in text_lower for kw in keywords):
            return issuer
    return None


DATE_PATTERNS = [
    # DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
    (re.compile(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})"), "dmy"),
    # YYYY-MM-DD
    (re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})"), "ymd"),
    # "January 15, 2026" / "Jan 15, 2026"
    (re.compile(
        r"(\w+)\s+(\d{1,2}),?\s+(\d{4})"
    ), "mdy_word"),
    # "15 januari 2026" / "15 January 2026"
    (re.compile(
        r"(\d{1,2})\s+(\w+)\s+(\d{4})"
    ), "dmy_word"),
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
    "oktober": 10, "okt": 10, "december": 12,
    # French
    "janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5,
    "juin": 6, "juillet": 7, "août": 8, "septembre": 9,
    "octobre": 10, "novembre": 11, "décembre": 12,
}


def _parse_month_word(word):
    """Convert a month name to a number, or None."""
    return MONTH_NAMES.get(word.lower())


def _strip_dots_and_spaces(s):
    """Remove dots and spaces from a string to recover numbers/words."""
    return re.sub(r'[\s.]+', '', s)


# Patterns that look for an invoice date label followed by a date,
# tolerating dots and spaces mixed into the value (common in dotted PDFs).
_LABEL_DATE_PATTERNS = [
    # "Invoice date Oct 31, 2025" or "Factuurdatum 4 okt 2025"
    # Text is already cleaned by _clean_dotted_text, so no need for
    # permissive dot/space quantifiers (which cause catastrophic backtracking).
    re.compile(
        r'(?:Invoice\s*date|Factuurdatum)[:\s.]*'
        r'(\w+)\s+(\d{1,2}),?\s+(\d{4})',
        re.IGNORECASE,
    ),
    # "Datum:<spaces>24.11.2025"
    re.compile(
        r'(?:Datum|Date)[:\s]+(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})',
        re.IGNORECASE,
    ),
]


def _extract_date_from_text(text):
    """Try to find the invoice date in extracted text.

    First tries label-based patterns (Invoice date, Factuurdatum, Datum)
    which target the actual invoice date. Falls back to generic date patterns.
    Returns a date object or None.
    """
    import datetime as dt

    # First pass: look for labelled invoice dates
    for pattern in _LABEL_DATE_PATTERNS:
        m = pattern.search(text)
        if m:
            groups = m.groups()
            try:
                if len(groups) == 3 and groups[0].isalpha():
                    # Month-word pattern: "Oct 31 2025"
                    mo = _parse_month_word(groups[0])
                    d = int(groups[1])
                    y = int(groups[2])
                    if mo and 2020 <= y <= 2030 and 1 <= d <= 31:
                        return dt.date(y, mo, d)
                elif len(groups) == 3:
                    # Numeric pattern: DD.MM.YYYY
                    d = int(groups[0])
                    mo = int(groups[1])
                    y = int(groups[2])
                    if 2020 <= y <= 2030 and 1 <= mo <= 12 and 1 <= d <= 31:
                        return dt.date(y, mo, d)
            except (ValueError, IndexError):
                pass

    # Second pass: generic date patterns on cleaned text
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


def _extract_in_subprocess(pdf_path_str, result_queue):
    """Top-level function for multiprocessing: extract invoice data from a PDF.

    Must be top-level (not a closure) so it can be pickled by multiprocessing.
    Puts (new_filename_or_None, info_string) onto result_queue.
    """
    import datetime as dt
    from pathlib import Path

    pdf_path = Path(pdf_path_str)
    try:
        text = _extract_text_from_pdf(pdf_path)
        if not text.strip():
            result_queue.put((None, "No readable text"))
            return

        # Try invoice2data first
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

        # Fallback: keyword matching on already-extracted text
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
    """Extract the vendor/issuer from a PDF.

    Tries invoice2data first, falls back to pdfplumber keyword matching.
    Returns the issuer string or None.
    """
    # Try invoice2data first
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

    # Fallback: extract text and match keywords
    text = _extract_text_from_pdf(pdf_path)
    if text:
        issuer = _match_vendor_by_keywords(text)
        if issuer:
            logger.debug(f"Keyword fallback matched {pdf_path.name} -> {issuer}")
            return issuer

    return None



# --- CONFIGURATION -----------------------------------------------------------

BOEKHOUDING_ROOT = Path(r"D:\_work\Active\_LIBRARY\Boekhouding")

def _generate_filename(date_obj, company_name, extension=".pdf"):
    """Generate standardised invoice filename: FAC_YY-MM-DD_CompanyName.ext"""
    date_str = date_obj.strftime("%y-%m-%d")
    company_clean = re.sub(r"[^\w\-]", "", company_name)
    return f"FAC_{date_str}_{company_clean}{extension}"


# Expected recurring invoices grouped by category.
# frequency: "monthly" (3 per Q), "quarterly" (1 per Q), "yearly" (1+ per year)
# expected_quarter: for yearly invoices, which quarter they typically arrive in
# expected_yearly: for yearly invoices, how many per year (default 1)
# optional: True means missing = warning (grey) instead of error (red)
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

# --- SCANNER -----------------------------------------------------------------


def _get_quarter_folder(year: int, quarter: int):
    """Return the Path of a quarter's Binnenkomend folder."""
    return BOEKHOUDING_ROOT / str(year) / f"Q{quarter}" / "Binnenkomend"


def _get_quarter_files(year: int, quarter: int):
    """Return list of filenames in a quarter's Binnenkomend folder."""
    folder = _get_quarter_folder(year, quarter)
    if folder.exists():
        return [f.name for f in folder.iterdir() if f.is_file()]
    return []


def scan_quarter(year: int, quarter: int) -> dict:
    """Scan a quarter folder and return status for each expected invoice.

    Matches invoices by filename only (content extraction is used separately
    for the rename feature).

    Only includes monthly and quarterly vendors (yearly vendors are skipped).
    Returns dict: {category: {vendor: {config, matches, status, expected_count}}}
    """
    files = _get_quarter_files(year, quarter)
    files_lower = [f.lower() for f in files]

    results = {}
    for category, vendors in EXPECTED_INVOICES.items():
        cat_results = {}
        for vendor, config in vendors.items():
            freq = config["frequency"]

            # Skip yearly vendors — they belong in the year overview
            if freq == "yearly":
                continue

            optional = config.get("optional", False)

            if freq == "monthly":
                expected_count = 3
            else:  # quarterly
                expected_count = 1

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
    """Scan all quarters for yearly invoices.

    Matches invoices by filename only.

    Returns dict: {category: {vendor: {config, matches: {q: [files]}, status, expected_count}}}
    """
    # Collect files per quarter
    quarter_files = {}
    for q in range(1, 5):
        files = _get_quarter_files(year, q)
        quarter_files[q] = files

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
    """Return quarter number (1-4) for a given month."""
    return (month - 1) // 3 + 1


# Pattern: PREFIX_YY-MM-DD_VendorName[Suffix].ext
VALID_PREFIXES = ("FAC", "CRE", "TIC")
NAMING_PATTERN = re.compile(
    r"^(FAC|CRE|TIC)_(\d{2})-(\d{2})-(\d{2})_(.+)\.(pdf|jpg|jpeg|png)$",
    re.IGNORECASE,
)


def validate_filenames(year: int) -> list:
    """Check all filenames in a year for naming issues.

    Returns list of (quarter, filename, [issues], issue_type) where issue_type
    is "no_match" (file doesn't follow the naming convention at all) or
    "has_errors" (follows the convention but with issues).
    """
    issues_list = []

    for q in range(1, 5):
        files = _get_quarter_files(year, q)
        for fname in files:
            issues = []

            # Check for double extensions (.pdf.pdf, .jpg.jpg, etc.)
            double_ext = re.search(r"\.(pdf|jpg|jpeg|png)\.\1$", fname, re.IGNORECASE)
            if double_ext:
                issues.append("Double extension")

            # Check for spaces in filename
            if " " in fname:
                issues.append("Spaces in filename")

            # Try to match the expected pattern
            m = NAMING_PATTERN.match(fname)
            if m is None:
                # Check if it's a double-ext variant that would match after fix
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
                    # Use the cleaned match for further checks
                    m = m_cleaned

            prefix, yy, mm, dd = m.group(1), m.group(2), m.group(3), m.group(4)
            vendor_part = m.group(5)
            ext = m.group(6)

            # Extension should be lowercase
            actual_ext = fname.rsplit(".", 1)[-1]
            if actual_ext != actual_ext.lower():
                issues.append(f"Extension not lowercase: .{actual_ext}")

            # Prefix should be uppercase
            actual_prefix = fname.split("_")[0]
            if actual_prefix != actual_prefix.upper():
                issues.append(f"Prefix not uppercase: {actual_prefix}")

            # Vendor name should start with uppercase or digit
            if vendor_part and not vendor_part[0].isupper() and not vendor_part[0].isdigit():
                issues.append(f"Name starts with lowercase: {vendor_part}")

            # Validate date
            try:
                file_month = int(mm)
                file_year = int(yy) + 2000
                file_day = int(dd)
                # Basic range check
                if not (1 <= file_month <= 12 and 1 <= file_day <= 31):
                    issues.append(f"Invalid date: {yy}-{mm}-{dd}")
                else:
                    # Check if date matches the quarter it's filed in
                    file_q = _quarter_for_month(file_month)
                    if file_year == year and file_q != q:
                        issues.append(
                            f"Date is Q{file_q} but filed in Q{q}"
                        )
                    elif file_year != year:
                        issues.append(
                            f"Date is {file_year} but filed in {year}"
                        )
            except ValueError:
                issues.append(f"Invalid date: {yy}-{mm}-{dd}")

            if issues:
                issues_list.append((q, fname, issues, "has_errors"))

    return issues_list


def find_duplicates(year: int) -> list:
    """Find files that appear to be the same invoice filed in multiple quarters.

    Compares by stripping the filename down to a normalised key (date + vendor).
    Returns list of (filename, [(q, full_name), ...]) for files found in 2+ quarters.
    """
    # Collect all files per quarter
    all_files = {}  # key -> [(quarter, original_filename)]
    for q in range(1, 5):
        files = _get_quarter_files(year, q)
        for fname in files:
            key = fname.lower().strip()
            all_files.setdefault(key, []).append((q, fname))

    duplicates = []
    for key, locations in sorted(all_files.items()):
        quarters = set(q for q, _ in locations)
        if len(quarters) > 1:
            duplicates.append((locations[0][1], locations))

    return duplicates


# --- GUI ---------------------------------------------------------------------


class InvoiceCheckerGUI:
    """GUI for the Invoice Checker."""

    def __init__(self, root):
        self.root = root
        self.root.title("Invoice Checker")
        self.root.geometry("950x700")
        self.root.minsize(850, 550)
        self.root.configure(bg=FORM_COLORS["bg"])

        now = datetime.now()
        self.current_year = now.year
        self.current_quarter = (now.month - 1) // 3 + 1
        self.trees = {}  # tab_key -> treeview
        self.tab_folders = {}  # tab_key -> folder path

        self._build_ui()
        self._scan()

    # --- UI construction ---

    def _build_ui(self):
        C = FORM_COLORS

        # --- Header ---
        header = tk.Frame(self.root, bg=C["accent_dark"], height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text="Invoice Checker", font=("Arial", 15, "bold"),
            fg="white", bg=C["accent_dark"],
        ).pack(side="left", padx=16)

        # --- Controls ---
        ctrl = tk.Frame(self.root, bg=C["bg"], pady=10)
        ctrl.pack(fill="x", padx=16)

        tk.Label(ctrl, text="Year:", fg=C["text"], bg=C["bg"],
                 font=("Arial", 10)).pack(side="left")
        self.year_var = tk.StringVar(value=str(self.current_year))
        year_cb = ttk.Combobox(ctrl, textvariable=self.year_var, width=6,
                               values=[str(y) for y in range(2023, self.current_year + 1)],
                               state="readonly")
        year_cb.pack(side="left", padx=(4, 16))
        year_cb.bind("<<ComboboxSelected>>", lambda e: self._scan())

        reload_btn = tk.Button(
            ctrl, text="\u21bb  Reload", command=self._scan,
            bg=C["bg_input"], fg=C["text"], activebackground=C["bg_hover"],
            activeforeground=C["text"], relief=tk.FLAT, font=("Arial", 10),
            cursor="hand2", padx=12, pady=2,
        )
        reload_btn.pack(side="left", padx=(0, 8))
        reload_btn.bind("<Enter>", lambda e: e.widget.configure(bg=C["bg_hover"]))
        reload_btn.bind("<Leave>", lambda e: e.widget.configure(bg=C["bg_input"]))

        self.folder_label = tk.Label(ctrl, text="", fg=C["text_dim"], bg=C["bg"],
                                     font=("Arial", 9), cursor="hand2")
        self.folder_label.pack(side="left", padx=(16, 0))
        self.folder_label.bind("<Button-1>", self._copy_folder_path)
        self.folder_label.bind("<Enter>",
                               lambda e: e.widget.configure(fg=C["accent"]))
        self.folder_label.bind("<Leave>",
                               lambda e: e.widget.configure(fg=C["text_dim"]))

        # --- Shared treeview style ---
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Invoice.Treeview",
                        background=C["bg_input"],
                        foreground=C["text"],
                        fieldbackground=C["bg_input"],
                        rowheight=26,
                        font=("Arial", 10))
        style.configure("Invoice.Treeview.Heading",
                        background=C["border"],
                        foreground=C["text"],
                        font=("Arial", 10, "bold"))
        style.map("Invoice.Treeview",
                  background=[("selected", C["accent_dark"])],
                  foreground=[("selected", "white")])

        # Notebook tab style
        style.configure("Invoice.TNotebook", background=C["bg"])
        style.configure("Invoice.TNotebook.Tab",
                        background=C["bg_input"],
                        foreground=C["text"],
                        padding=[14, 6])
        style.map("Invoice.TNotebook.Tab",
                  background=[("selected", C["accent_dark"])],
                  foreground=[("selected", "#ffffff")])

        # --- Notebook ---
        self.notebook = ttk.Notebook(self.root, style="Invoice.TNotebook")
        self.notebook.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # Quarter tabs
        for q in range(1, 5):
            frame = tk.Frame(self.notebook, bg=C["bg"])
            tree = self._create_treeview(frame, ("vendor", "frequency", "status", "found", "files"))
            tree.heading("vendor", text="Vendor", anchor="w")
            tree.heading("frequency", text="Frequency", anchor="w")
            tree.heading("status", text="Status", anchor="w")
            tree.heading("found", text="Found", anchor="center")
            tree.heading("files", text="Files", anchor="w")
            tree.column("#0", width=30, stretch=False)
            tree.column("vendor", width=150, minwidth=100)
            tree.column("frequency", width=90, minwidth=70)
            tree.column("status", width=110, minwidth=80)
            tree.column("found", width=70, minwidth=50, anchor="center")
            tree.column("files", width=350, minwidth=150)
            self.notebook.add(frame, text=f"  Q{q}  ")
            self.trees[f"q{q}"] = tree

        # Year overview tab
        year_frame = tk.Frame(self.notebook, bg=C["bg"])
        year_tree = self._create_treeview(year_frame,
                                          ("vendor", "status", "found", "q1", "q2", "q3", "q4"))
        year_tree.heading("vendor", text="Vendor", anchor="w")
        year_tree.heading("status", text="Status", anchor="w")
        year_tree.heading("found", text="Total", anchor="center")
        year_tree.heading("q1", text="Q1", anchor="w")
        year_tree.heading("q2", text="Q2", anchor="w")
        year_tree.heading("q3", text="Q3", anchor="w")
        year_tree.heading("q4", text="Q4", anchor="w")
        year_tree.column("#0", width=30, stretch=False)
        year_tree.column("vendor", width=140, minwidth=100)
        year_tree.column("status", width=110, minwidth=80)
        year_tree.column("found", width=60, minwidth=40, anchor="center")
        year_tree.column("q1", width=140, minwidth=80)
        year_tree.column("q2", width=140, minwidth=80)
        year_tree.column("q3", width=140, minwidth=80)
        year_tree.column("q4", width=140, minwidth=80)
        self.notebook.add(year_frame, text="  Year Overview  ")
        self.trees["year"] = year_tree

        # Duplicates tab
        dup_frame = tk.Frame(self.notebook, bg=C["bg"])
        dup_tree = self._create_treeview(dup_frame,
                                         ("filename", "quarters", "details"))
        dup_tree.heading("filename", text="Filename", anchor="w")
        dup_tree.heading("quarters", text="Quarters", anchor="w")
        dup_tree.heading("details", text="Details", anchor="w")
        dup_tree.column("#0", width=30, stretch=False)
        dup_tree.column("filename", width=300, minwidth=200)
        dup_tree.column("quarters", width=150, minwidth=100)
        dup_tree.column("details", width=350, minwidth=200)
        self.notebook.add(dup_frame, text="  Duplicates  ")
        self.trees["dup"] = dup_tree

        # Naming validation tab
        naming_frame = tk.Frame(self.notebook, bg=C["bg"])

        # Rename button bar
        rename_bar = tk.Frame(naming_frame, bg=C["bg"])
        rename_bar.pack(fill="x", padx=4, pady=(4, 0))
        self._rename_pending = []  # stores (q, old_path, new_name) for confirm
        self._rename_mode = False

        self.rename_btn = tk.Button(
            rename_bar, text="Rename",
            command=self._on_rename_click,
            bg=C["bg_input"], fg=C["text"], activebackground=C["bg_hover"],
            activeforeground=C["text"], relief=tk.FLAT, font=("Arial", 10),
            cursor="hand2", padx=12, pady=4,
        )
        self.rename_btn.pack(side="left")
        self.rename_btn.bind("<Enter>", self._rename_btn_enter)
        self.rename_btn.bind("<Leave>", self._rename_btn_leave)

        self.cancel_btn = tk.Button(
            rename_bar, text="Cancel",
            command=self._cancel_rename,
            bg=C["bg_input"], fg=C["text"], activebackground=C["bg_hover"],
            activeforeground=C["text"], relief=tk.FLAT, font=("Arial", 10),
            cursor="hand2", padx=12, pady=4,
        )
        self.cancel_btn.bind("<Enter>", lambda e: e.widget.configure(bg=C["bg_hover"]))
        self.cancel_btn.bind("<Leave>", lambda e: e.widget.configure(bg=C["bg_input"]))

        self.rename_count_label = tk.Label(
            rename_bar, text="", fg=C["text_dim"], bg=C["bg"],
            font=("Arial", 9))
        self.rename_count_label.pack(side="left", padx=(12, 0))

        naming_tree = self._create_treeview(naming_frame,
                                            ("quarter", "filename", "issues"))
        naming_tree.heading("quarter", text="Quarter", anchor="w")
        naming_tree.heading("filename", text="Filename", anchor="w")
        naming_tree.heading("issues", text="Issues", anchor="w")
        naming_tree.column("#0", width=30, stretch=False)
        naming_tree.column("quarter", width=80, minwidth=60)
        naming_tree.column("filename", width=320, minwidth=200)
        naming_tree.column("issues", width=400, minwidth=250)
        self.notebook.add(naming_frame, text="  Naming  ")
        self.trees["naming"] = naming_tree

        # Apply tags to all trees
        for tree in self.trees.values():
            tree.tag_configure("ok", background="#1a2e1a", foreground=C["text"])
            tree.tag_configure("partial", background="#2e2a1a", foreground=C["text"])
            tree.tag_configure("missing", background="#2e1a1a", foreground=C["text"])
            tree.tag_configure("optional_missing",
                               background=C["bg_input"], foreground=C["text_dim"])
            tree.tag_configure("not_this_quarter",
                               background=C["bg_input"], foreground=C["text_dim"])
            tree.tag_configure("category", foreground=C["accent"],
                               font=("Arial", 10, "bold"))
            tree.tag_configure("duplicate", background="#2e1a1a", foreground=C["text"])
            tree.tag_configure("no_duplicates", foreground=C["text_dim"])
            tree.tag_configure("warning", background="#2e2a1a", foreground=C["text"])
            tree.tag_configure("error", background="#2e1a1a", foreground=C["text"])
            tree.tag_configure("no_match", background="#2e1a2e", foreground=C["text"])
            tree.tag_configure("no_issues", foreground=C["text_dim"])

        # --- Summary bar ---
        self.summary_var = tk.StringVar()
        summary = tk.Label(self.root, textvariable=self.summary_var,
                           fg=C["text"], bg=C["border"],
                           font=("Arial", 10), anchor="w", padx=12, pady=6)
        summary.pack(fill="x", side="bottom")

    def _create_treeview(self, parent, columns):
        """Create a treeview with scrollbar inside the parent frame."""
        C = FORM_COLORS
        tree_frame = tk.Frame(parent, bg=C["bg"])
        tree_frame.pack(fill="both", expand=True, padx=4, pady=4)

        tree = ttk.Treeview(tree_frame, columns=columns, show="tree headings",
                            style="Invoice.Treeview")
        tree.heading("#0", text="", anchor="w")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        tree.bind("<Double-1>", self._on_row_double_click)
        return tree

    # --- Scanning ---

    def _scan(self):
        year = int(self.year_var.get())
        self._scan_quarters(year)
        self._scan_year_overview(year)
        self._scan_duplicates(year)
        self._scan_naming(year)
        self._update_folder_label()
        self._update_summary()

    def _scan_quarters(self, year: int):
        for q in range(1, 5):
            tree = self.trees[f"q{q}"]
            for item in tree.get_children():
                tree.delete(item)

            folder = BOEKHOUDING_ROOT / str(year) / f"Q{q}" / "Binnenkomend"
            self.tab_folders[f"q{q}"] = folder

            results = scan_quarter(year, q)

            for category, vendors in results.items():
                cat_id = tree.insert("", "end", text="",
                                     values=(category, "", "", "", ""),
                                     tags=("category",))

                for vendor, info in vendors.items():
                    status = info["status"]
                    matches = info["matches"]
                    expected = info["expected_count"]

                    if status == "ok":
                        status_text = "\u2713  OK"
                        found_text = f"{len(matches)}/{expected}"
                    elif status == "partial":
                        status_text = "\u25b3  Incomplete"
                        found_text = f"{len(matches)}/{expected}"
                    elif status == "optional_missing":
                        status_text = "\u25cb  Optional"
                        found_text = f"0/{expected}"
                    else:  # missing
                        status_text = "\u2717  MISSING"
                        found_text = f"0/{expected}"

                    freq_labels = {
                        "monthly": "Monthly",
                        "quarterly": "Quarterly",
                    }
                    freq_text = freq_labels.get(info["config"]["frequency"], "")
                    files_text = ", ".join(matches) if matches else ""

                    tree.insert(cat_id, "end", text="",
                                values=(vendor, freq_text, status_text,
                                        found_text, files_text),
                                tags=(status,))

                tree.item(cat_id, open=True)

    def _scan_year_overview(self, year: int):
        tree = self.trees["year"]
        for item in tree.get_children():
            tree.delete(item)

        self.tab_folders["year"] = BOEKHOUDING_ROOT / str(year)
        results = scan_year(year)

        for category, vendors in results.items():
            cat_id = tree.insert("", "end", text="",
                                 values=(category, "", "", "", "", "", ""),
                                 tags=("category",))

            for vendor, info in vendors.items():
                status = info["status"]
                total = info["total_found"]
                expected = info["expected_count"]
                matches_per_q = info["matches"]

                if status == "ok":
                    status_text = "\u2713  OK"
                elif status == "partial":
                    status_text = "\u25b3  Incomplete"
                elif status == "optional_missing":
                    status_text = "\u25cb  Optional"
                else:
                    status_text = "\u2717  MISSING"

                found_text = f"{total}/{expected}"
                q_texts = []
                for q in range(1, 5):
                    q_files = matches_per_q.get(q, [])
                    q_texts.append(", ".join(q_files) if q_files else "")

                tree.insert(cat_id, "end", text="",
                            values=(vendor, status_text, found_text,
                                    q_texts[0], q_texts[1], q_texts[2], q_texts[3]),
                            tags=(status,))

            tree.item(cat_id, open=True)

    def _scan_duplicates(self, year: int):
        tree = self.trees["dup"]
        for item in tree.get_children():
            tree.delete(item)

        duplicates = find_duplicates(year)

        if not duplicates:
            tree.insert("", "end", text="",
                        values=("No duplicates found", "", ""),
                        tags=("no_duplicates",))
            return

        for filename, locations in duplicates:
            quarters = sorted(set(q for q, _ in locations))
            q_text = ", ".join(f"Q{q}" for q in quarters)
            details = " | ".join(f"Q{q}: {fn}" for q, fn in sorted(locations))
            tree.insert("", "end", text="",
                        values=(filename, q_text, details),
                        tags=("duplicate",))

    def _scan_naming(self, year: int):
        tree = self.trees["naming"]
        for item in tree.get_children():
            tree.delete(item)

        self.tab_folders["naming"] = BOEKHOUDING_ROOT / str(year)
        issues_list = validate_filenames(year)

        if not issues_list:
            tree.insert("", "end", text="",
                        values=("", "No naming issues found", ""),
                        tags=("no_issues",))
            self.rename_count_label.config(text="")
            return

        # Date-in-wrong-quarter is a warning, other issues are errors
        warning_only = {"Date is"}
        no_match_count = 0
        for q, fname, issues, issue_type in issues_list:
            issues_text = " | ".join(issues)
            if issue_type == "no_match":
                tag = "no_match"
                no_match_count += 1
            elif all(any(i.startswith(w) for w in warning_only) for i in issues):
                tag = "warning"
            else:
                tag = "error"
            tree.insert("", "end", text="",
                        values=(f"Q{q}", fname, issues_text),
                        tags=(tag,))

        if no_match_count > 0:
            pdf_count = sum(
                1 for _, fname, _, itype in issues_list
                if itype == "no_match" and fname.lower().endswith(".pdf")
            )
            label = f"{no_match_count} unmatched"
            if pdf_count < no_match_count:
                label += f" ({pdf_count} PDF renameable)"
            self.rename_count_label.config(text=label)
        else:
            self.rename_count_label.config(text="")

    # --- Tab / folder label ---

    def _on_tab_changed(self, event=None):
        self._update_folder_label()
        self._update_summary()

    def _get_active_tab_key(self):
        idx = self.notebook.index(self.notebook.select())
        if idx < 4:
            return f"q{idx + 1}"
        elif idx == 4:
            return "year"
        elif idx == 5:
            return "dup"
        else:
            return "naming"

    def _update_folder_label(self):
        key = self._get_active_tab_key()
        folder = self.tab_folders.get(key)
        if folder:
            self.folder_label.config(text=str(folder))
        else:
            self.folder_label.config(text="")

    def _update_summary(self):
        year = int(self.year_var.get())
        key = self._get_active_tab_key()

        if key.startswith("q"):
            q = int(key[1])
            tree = self.trees[key]
            total = 0
            found = 0
            missing = 0
            for cat_id in tree.get_children():
                for child in tree.get_children(cat_id):
                    tags = tree.item(child, "tags")
                    if "ok" in tags:
                        total += 1
                        found += 1
                    elif "partial" in tags or "missing" in tags:
                        total += 1
                        if "missing" in tags:
                            missing += 1
                        else:
                            missing += 1  # partial also counts as incomplete
            if missing > 0:
                self.summary_var.set(
                    f"Q{q} {year}:  {found} of {total} invoices found  |  "
                    f"{missing} missing or incomplete"
                )
            else:
                self.summary_var.set(
                    f"Q{q} {year}:  All {found} expected invoices found!"
                )

        elif key == "year":
            results = scan_year(year)
            total = 0
            found = 0
            for cat in results.values():
                for info in cat.values():
                    if info["config"].get("optional"):
                        continue
                    total += 1
                    if info["status"] == "ok":
                        found += 1
            self.summary_var.set(
                f"Year {year}:  {found} of {total} yearly invoices found"
            )

        elif key == "dup":
            duplicates = find_duplicates(year)
            if duplicates:
                self.summary_var.set(
                    f"Duplicates {year}:  {len(duplicates)} file(s) found "
                    f"in multiple quarters!"
                )
            else:
                self.summary_var.set(
                    f"Duplicates {year}:  No duplicates found"
                )

        elif key == "naming":
            issues_list = validate_filenames(year)
            if issues_list:
                no_match = sum(1 for *_, itype in issues_list
                               if itype == "no_match")
                has_errors = sum(1 for *_, itype in issues_list
                                 if itype == "has_errors")
                # Separate warnings (date-only) from real errors
                warnings = sum(
                    1 for _, _, issues, itype in issues_list
                    if itype == "has_errors" and all(
                        i.startswith("Date is")
                        for i in issues
                    )
                )
                real_errors = has_errors - warnings
                parts = []
                if no_match:
                    parts.append(f"{no_match} unnamed")
                if real_errors:
                    parts.append(f"{real_errors} error(s)")
                if warnings:
                    parts.append(f"{warnings} warning(s)")
                self.summary_var.set(
                    f"Naming {year}:  {', '.join(parts)}"
                )
            else:
                self.summary_var.set(
                    f"Naming {year}:  All filenames are correct!"
                )

    # --- Rename ---

    def _extract_rename_info(self, pdf_path, timeout=15):
        """Extract invoice data via invoice2data and return proposed filename.

        Runs extraction in a subprocess so that a stuck regex (which holds the
        GIL in C code) cannot block the main scan thread.
        Returns (new_filename_or_None, info_string).
        """
        import multiprocessing as mp

        result_queue = mp.Queue()
        proc = mp.Process(
            target=_extract_in_subprocess,
            args=(str(pdf_path), result_queue),
            daemon=True,
        )
        proc.start()
        proc.join(timeout=timeout)

        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=2)
            if proc.is_alive():
                proc.kill()
            logger.warning(f"Extraction timed out for {pdf_path.name} after {timeout}s")
            return None, f"Timed out ({timeout}s)"

        try:
            return result_queue.get_nowait()
        except Exception:
            logger.error(f"Extraction failed for {pdf_path.name} (no result)")
            return None, "Error: no result"

    def _rename_btn_enter(self, event):
        if self._rename_mode:
            event.widget.configure(bg="#2a5a2a")
        else:
            event.widget.configure(bg=FORM_COLORS["bg_hover"])

    def _rename_btn_leave(self, event):
        if self._rename_mode:
            event.widget.configure(bg="#1a4a1a")
        else:
            event.widget.configure(bg=FORM_COLORS["bg_input"])

    def _set_rename_mode(self, active):
        """Toggle between Rename and Confirm mode."""
        C = FORM_COLORS
        self._rename_mode = active
        if active:
            self.rename_btn.configure(text="Confirm", bg="#1a4a1a", fg="#90ee90")
            self.cancel_btn.pack(side="left", padx=(8, 0))
        else:
            self.rename_btn.configure(text="Rename", bg=C["bg_input"], fg=C["text"])
            self.cancel_btn.pack_forget()
            self._rename_pending = []

    def _cancel_rename(self):
        """Cancel rename preview and go back to normal view."""
        self._set_rename_mode(False)
        self._scan_naming(int(self.year_var.get()))
        self._update_summary()

    def _on_rename_click(self):
        """Handle rename button click — preview or confirm."""
        if self._rename_mode:
            self._confirm_rename()
        else:
            self._preview_rename()

    def _preview_rename(self):
        """Show proposed new names in the naming tree (runs extraction in background)."""
        year = int(self.year_var.get())
        issues_list = validate_filenames(year)

        to_rename = [
            (q, fname) for q, fname, _, itype in issues_list
            if itype == "no_match"
        ]

        logger.info(f"Rename preview: {len(to_rename)} files to rename")

        if not to_rename:
            self.summary_var.set("No files to rename.")
            return

        if not INVOICE2DATA_AVAILABLE:
            self.summary_var.set(
                "invoice2data is not installed. "
                "Install with: pip install invoice2data pdfplumber"
            )
            return

        # Disable button and show scanning status
        self.rename_btn.configure(state="disabled", text="Scanning...")
        self.summary_var.set(f"Scanning {len(to_rename)} file(s)...")
        self.root.update_idletasks()

        def _do_extract():
            """Run extraction in background thread."""
            results = []
            total = len(to_rename)
            try:
                for i, (q, fname) in enumerate(to_rename, 1):
                    try:
                        folder = BOEKHOUDING_ROOT / str(year) / f"Q{q}" / "Binnenkomend"
                        old_path = folder / fname

                        if fname.lower().endswith(".pdf"):
                            new_name, info = self._extract_rename_info(old_path)
                        else:
                            new_name = None
                            info = "Not a PDF"

                        # Fallback for unrecognised PDFs
                        if new_name is None and fname.lower().endswith(".pdf"):
                            ext = Path(fname).suffix
                            new_name = f"FAC_00-00-00_Onbekend{ext}"
                            info = "Unknown (fallback)"

                        logger.info(f"Scanned {i}/{total}: {fname} -> {new_name or '(skip)'}")
                        results.append((q, old_path, fname, new_name, info))
                    except Exception as e:
                        logger.error(f"Scan failed for {fname}: {e}", exc_info=True)
                        folder = BOEKHOUDING_ROOT / str(year) / f"Q{q}" / "Binnenkomend"
                        results.append((q, folder / fname, fname, None, f"Error: {e}"))
            except Exception as e:
                logger.error(f"Scan thread crashed: {e}", exc_info=True)
            finally:
                logger.info(f"Scan complete: {len(results)}/{total} files processed")
                self.root.after(0, lambda: self._show_preview_results(year, results))

        threading.Thread(target=_do_extract, daemon=True).start()

    def _show_preview_results(self, year, results):
        """Display extraction results in the naming tree (called on main thread)."""
        tree = self.trees["naming"]
        for item in tree.get_children():
            tree.delete(item)

        self._rename_pending = []
        skipped = 0

        for q, old_path, fname, new_name, info in results:
            if new_name:
                self._rename_pending.append((q, old_path, new_name))
                tree.insert("", "end", text="",
                            values=(f"Q{q}", fname,
                                    f"New name: {new_name}"),
                            tags=("ok",))
            else:
                skipped += 1
                tree.insert("", "end", text="",
                            values=(f"Q{q}", fname, info),
                            tags=("no_match",))

        self.rename_btn.configure(state="normal")
        count = len(self._rename_pending)
        if count > 0:
            self._set_rename_mode(True)
            msg = f"Naming {year}:  {count} file(s) to rename"
            if skipped:
                msg += f", {skipped} skipped"
            self.summary_var.set(msg)
        else:
            self.summary_var.set("No files could be automatically recognised.")

    def _confirm_rename(self):
        """Perform the pending renames synchronously (renames are instant)."""
        pending = list(self._rename_pending)
        self.rename_btn.configure(state="disabled", text="Renaming...")
        self.root.update_idletasks()

        # Do all renames first without logging (log file I/O can block on WSL)
        renamed_log = []
        errors = []
        for q, old_path, new_name in pending:
            try:
                if not old_path.exists():
                    raise FileNotFoundError(f"Source file not found: {old_path}")
                new_path = old_path.parent / new_name
                if new_path.exists():
                    stem = new_path.stem
                    ext = new_path.suffix
                    counter = 2
                    while new_path.exists():
                        new_path = old_path.parent / f"{stem}_{counter:02d}{ext}"
                        counter += 1
                old_path.rename(new_path)
                renamed_log.append(f"{old_path.name} -> {new_path.name}")
            except Exception as e:
                errors.append(f"{old_path.name}: {e}")

        # Log results in batch after all renames are done
        for entry in renamed_log:
            logger.info(f"Renamed: {entry}")
        for entry in errors:
            logger.error(f"Rename failed: {entry}")
        logger.info(
            f"Rename complete: {len(renamed_log)}/{len(pending)} renamed"
            + (f", {len(errors)} error(s)" if errors else "")
        )
        self._finish_rename(len(renamed_log), errors)

    def _finish_rename(self, renamed, errors):
        """Update UI after rename completes (called on main thread)."""
        self._set_rename_mode(False)

        msg = f"{renamed} file(s) renamed."
        if errors:
            msg += f" {len(errors)} error(s)."
        self.summary_var.set(msg)

        self._scan()

    # --- Clipboard ---

    def _copy_folder_path(self, event=None):
        """Copy the current folder path to clipboard."""
        path = self.folder_label.cget("text")
        if not path:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(path)
        prev = self.summary_var.get()
        self.summary_var.set(f"Copied: {path}")
        self.root.after(2000, lambda: self.summary_var.set(prev))

    def _on_row_double_click(self, event):
        """Copy the full file path to clipboard when double-clicking a row."""
        tree = event.widget
        item = tree.identify_row(event.y)
        if not item:
            return
        values = tree.item(item, "values")
        tags = tree.item(item, "tags")

        if "category" in tags or "no_duplicates" in tags or "no_issues" in tags or not values:
            return

        # Determine which tab we're on
        key = self._get_active_tab_key()

        if key.startswith("q"):
            # Quarter tab: files column is index 4
            files_text = values[4] if len(values) > 4 else ""
            if not files_text:
                return
            folder = self.tab_folders.get(key)
            filenames = [f.strip() for f in files_text.split(",")]
            full_paths = [str(folder / fn) for fn in filenames]

        elif key == "year":
            # Year overview: Q1-Q4 columns are indices 3-6
            year = int(self.year_var.get())
            full_paths = []
            for qi, col_idx in enumerate(range(3, 7), start=1):
                q_files = values[col_idx] if len(values) > col_idx else ""
                if q_files:
                    folder = BOEKHOUDING_ROOT / str(year) / f"Q{qi}" / "Binnenkomend"
                    for fn in q_files.split(","):
                        full_paths.append(str(folder / fn.strip()))
            if not full_paths:
                return

        elif key == "dup":
            # Duplicate tab: parse the details to extract paths
            filename = values[0] if values else ""
            if not filename:
                return
            year = int(self.year_var.get())
            quarters_text = values[1] if len(values) > 1 else ""
            q_nums = [int(s.strip().replace("Q", ""))
                      for s in quarters_text.split(",") if s.strip()]
            full_paths = []
            for q in q_nums:
                folder = BOEKHOUDING_ROOT / str(year) / f"Q{q}" / "Binnenkomend"
                full_paths.append(str(folder / filename))

        elif key == "naming":
            # Naming tab: quarter in col 0, filename in col 1
            q_text = values[0] if values else ""
            filename = values[1] if len(values) > 1 else ""
            if not q_text or not filename:
                return
            q = int(q_text.replace("Q", ""))
            year = int(self.year_var.get())
            folder = BOEKHOUDING_ROOT / str(year) / f"Q{q}" / "Binnenkomend"
            full_paths = [str(folder / filename)]
        else:
            return

        clip_text = "\n".join(full_paths)
        self.root.clipboard_clear()
        self.root.clipboard_append(clip_text)

        prev = self.summary_var.get()
        if len(full_paths) == 1:
            self.summary_var.set(f"Copied: {full_paths[0]}")
        else:
            self.summary_var.set(f"{len(full_paths)} paths copied to clipboard")
        self.root.after(2000, lambda: self.summary_var.set(prev))


# --- ENTRY POINT -------------------------------------------------------------


def main():
    setup_shared_logging("invoice_checker")
    root = tk.Tk()
    InvoiceCheckerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
