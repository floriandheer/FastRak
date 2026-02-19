"""
Inside Tracker - UI
Tracks politician stock trades (US Congress PTR filings) and corporate insider
transactions (EU/Benelux AFM PDMR register).
"""

import os
import sys
import json
import time
import zipfile
import io
import xml.etree.ElementTree as ET
import tkinter as tk
import tkinter.ttk as ttk
import threading
import subprocess
import webbrowser
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from pathlib import Path

# Add parent dir so shared modules can be imported when run standalone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shared_form_keyboard import FORM_COLORS
from shared_logging import setup_logging

# --- CONFIGURATION -----------------------------------------------------------

DOWNLOAD_DIR = Path(r"C:\Users\flori\Desktop\InsideTracker\downloads")
STATE_FILE = Path(r"C:\Users\flori\Desktop\InsideTracker\tracker_state.json")

TRACKED_POLITICIANS = [
    "Pelosi",
    "Greene",
    "Green",
    "Gottheimer",
    "McCaul",
    "Khanna",
    "Crenshaw",
    "Tuberville",
]

YEARS = [2024, 2025, 2026]

HOUSE_ZIP_URL = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{}FD.zip"
HOUSE_PTR_URL = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{}/{}.pdf"

# --- EU / AFM CONFIGURATION -------------------------------------------------

STATE_FILE_EU = Path(r"C:\Users\flori\Desktop\InsideTracker\tracker_state_eu.json")

AFM_XML_URL = (
    "https://www.afm.nl/export.aspx"
    "?type=0ee836dc-5520-459d-bcf4-a4a689de6614&format=xml"
)
AFM_DETAIL_URL = (
    "https://www.afm.nl/en/sector/registers/meldingenregisters/"
    "transacties-leidinggevenden-mar19-/details?id={}"
)

TRACKED_EU_COMPANIES = [
    "ASML",
    "Shell",
    "Philips",
    "Adyen",
    "ING",
    "AB InBev",
    "KBC",
    "Ahold Delhaize",
]

# Color palette for EU companies (mapped by index)
_EU_COMPANY_COLORS = [
    "#c084fc",  # ASML - purple
    "#fb923c",  # Shell - orange
    "#34d399",  # Philips - green
    "#60a5fa",  # Adyen - blue
    "#fbbf24",  # ING - yellow
    "#f472b6",  # AB InBev - pink
    "#a78bfa",  # KBC - violet
    "#2dd4bf",  # Ahold Delhaize - teal
]

# Time range presets: (label, days_back or special key)
# "YTD" is computed dynamically; others are simple day offsets.
TIME_RANGES = [
    ("1D", 1),
    ("5D", 5),
    ("1M", 30),
    ("3M", 90),
    ("6M", 180),
    ("YTD", "ytd"),
    ("1Y", 365),
    ("2Y", 730),
    ("All", None),
]


def _time_range_cutoff(range_value) -> datetime:
    """Return the cutoff datetime for a given time range value."""
    if range_value is None:
        return datetime.min
    if range_value == "ytd":
        return datetime(datetime.now().year, 1, 1)
    return datetime.now() - timedelta(days=range_value)

# --- STATE MANAGEMENT --------------------------------------------------------

def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"downloaded": [], "last_fetch": None}

def save_state(state: dict):
    state["last_fetch"] = datetime.now().isoformat()
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

# --- CORE LOGIC --------------------------------------------------------------

def fetch_url(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "InsiderTracker/1.0"})
    with urlopen(req, timeout=30) as resp:
        return resp.read()

def get_ptr_filings(year: int, log_fn=None) -> list[dict]:
    """Download the FD zip for a year and extract PTR filings from the XML index."""
    url = HOUSE_ZIP_URL.format(year)
    if log_fn:
        log_fn(f"Fetching index for {year}...")

    try:
        data = fetch_url(url)
    except Exception as e:
        if log_fn:
            log_fn(f"Skipped {year}: {e}")
        return []

    zf = zipfile.ZipFile(io.BytesIO(data))
    xml_name = next((n for n in zf.namelist() if n.endswith(".xml")), None)
    if not xml_name:
        if log_fn:
            log_fn(f"No XML found for {year}")
        return []

    xml_bytes = zf.read(xml_name)
    xml_text = xml_bytes.decode("utf-8-sig")
    root = ET.fromstring(xml_text)

    filings = []
    tracked_lower = {name.lower() for name in TRACKED_POLITICIANS}

    for member in root.findall("Member"):
        filing_type = (member.findtext("FilingType") or "").strip()
        if filing_type != "P":
            continue

        last_name = (member.findtext("Last") or "").strip()
        if last_name.lower() not in tracked_lower:
            continue

        filings.append({
            "last_name": last_name,
            "first_name": (member.findtext("First") or "").strip(),
            "prefix": (member.findtext("Prefix") or "").strip(),
            "district": (member.findtext("StateDst") or "").strip(),
            "filing_date": (member.findtext("FilingDate") or "").strip(),
            "doc_id": (member.findtext("DocID") or "").strip(),
            "year": year,
        })

    if log_fn:
        log_fn(f"{year}: {len(filings)} PTR filings found")
    return filings

def download_pdf(filing: dict, download_dir: Path) -> bool:
    """Download a single PTR PDF. Returns True if newly downloaded."""
    doc_id = filing["doc_id"]
    year = filing["year"]
    url = HOUSE_PTR_URL.format(year, doc_id)

    safe_date = filing["filing_date"].replace("/", "-")
    filename = f"{filing['last_name']}_{filing['first_name']}_{safe_date}_{doc_id}.pdf"
    filepath = download_dir / filename

    if filepath.exists():
        return False

    data = fetch_url(url)
    filepath.write_bytes(data)
    return True

def parse_filing_date(date_str: str) -> datetime:
    """Parse M/D/YYYY or M-D-YYYY filing date."""
    for fmt in ("%m/%d/%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return datetime.min


# --- EU / AFM LOGIC ----------------------------------------------------------

def load_state_eu() -> dict:
    if STATE_FILE_EU.exists():
        with open(STATE_FILE_EU) as f:
            return json.load(f)
    return {"seen_ids": [], "last_fetch": None}


def save_state_eu(state: dict):
    state["last_fetch"] = datetime.now().isoformat()
    STATE_FILE_EU.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE_EU, "w") as f:
        json.dump(state, f, indent=2)


def fetch_afm_xml(log_fn=None) -> list[dict]:
    """Download the AFM PDMR XML register and return parsed rows."""
    if log_fn:
        log_fn("Fetching AFM PDMR register (XML)...")

    data = fetch_url(AFM_XML_URL)
    xml_text = data.decode("utf-8-sig")
    root = ET.fromstring(xml_text)

    tracked_lower = {c.lower() for c in TRACKED_EU_COMPANIES}
    rows = []

    for entry in root.findall("vermelding"):
        issuer = (entry.findtext("uitgevendeinstelling") or "").strip()
        # Case-insensitive partial match on tracked companies
        issuer_lower = issuer.lower()
        if not any(tracked in issuer_lower for tracked in tracked_lower):
            continue

        # Parse transaction date — format: "M/D/YYYY H:MM:SS AM/PM"
        raw_date = (entry.findtext("transactiedatum") or "").strip()
        parsed_date = datetime.min
        for fmt in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                parsed_date = datetime.strptime(raw_date, fmt)
                break
            except ValueError:
                continue

        date_display = parsed_date.strftime("%Y-%m-%d") if parsed_date != datetime.min else raw_date

        row_id = (entry.findtext("meldingid") or "").strip()
        if not row_id:
            person = (entry.findtext("meldingsplichtige") or "").strip()
            row_id = f"{issuer}_{raw_date}_{person}"

        rows.append({
            "id": row_id,
            "date": date_display,
            "_parsed_date": parsed_date,
            "company": issuer,
            "person": (entry.findtext("meldingsplichtige") or "").strip(),
            "position": (entry.findtext("functie") or "").strip(),
            "lei": (entry.findtext("lei") or "").strip(),
        })

    if log_fn:
        log_fn(f"AFM: {len(rows)} transactions for tracked companies")

    rows.sort(key=lambda r: r["_parsed_date"], reverse=True)
    return rows


# --- GUI ----------------------------------------------------------------------

class InsideTrackerGUI:
    def __init__(self, root, on_back=None):
        self.root = root
        self.root.title("Inside Tracker - Politician Stock Trade Monitor")
        self.root.geometry("960x640")
        self.root.minsize(800, 500)
        self.root.configure(bg=FORM_COLORS["bg"])

        self.state = load_state()
        self.filings = []
        self._fetching = False
        self._on_back = on_back

        self._configure_styles()
        self._build_ui()
        self._load_cached_filings()

    # -- Styles ----------------------------------------------------------------

    def _configure_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Dark.Treeview",
                        background=FORM_COLORS["bg_input"],
                        foreground=FORM_COLORS["text"],
                        fieldbackground=FORM_COLORS["bg_input"],
                        borderwidth=0,
                        font=("Segoe UI", 10))
        style.configure("Dark.Treeview.Heading",
                        background=FORM_COLORS["border"],
                        foreground=FORM_COLORS["text"],
                        font=("Segoe UI", 10, "bold"))
        style.map("Dark.Treeview",
                  background=[("selected", FORM_COLORS["accent_dark"])],
                  foreground=[("selected", FORM_COLORS["text"])])

        style.configure("TScrollbar",
                        background=FORM_COLORS["border"],
                        troughcolor=FORM_COLORS["bg_input"],
                        borderwidth=0,
                        arrowcolor=FORM_COLORS["text_dim"])

    # -- UI Build --------------------------------------------------------------

    def _build_ui(self):
        # Header
        header = tk.Frame(self.root, bg=FORM_COLORS["bg"])
        header.pack(fill=tk.X, padx=16, pady=(16, 8))

        tk.Label(header, text="Inside Tracker",
                 bg=FORM_COLORS["bg"], fg=FORM_COLORS["text"],
                 font=("Segoe UI", 16, "bold")).pack(side=tk.LEFT)

        tk.Label(header, text="Politician Stock Trade Monitor",
                 bg=FORM_COLORS["bg"], fg=FORM_COLORS["text_dim"],
                 font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(12, 0), pady=(4, 0))

        # Toolbar
        toolbar = tk.Frame(self.root, bg=FORM_COLORS["bg"])
        toolbar.pack(fill=tk.X, padx=16, pady=(0, 8))

        self.fetch_btn = tk.Button(
            toolbar, text="Fetch New Filings",
            bg=FORM_COLORS["accent_dark"], fg="#ffffff",
            activebackground=FORM_COLORS["accent"], activeforeground="#ffffff",
            font=("Segoe UI", 10, "bold"), relief=tk.FLAT,
            padx=16, pady=6, cursor="hand2",
            command=self._on_fetch)
        self.fetch_btn.pack(side=tk.LEFT)

        tk.Button(
            toolbar, text="Open PDF",
            bg=FORM_COLORS["bg_input"], fg=FORM_COLORS["text"],
            activebackground=FORM_COLORS["bg_hover"], activeforeground=FORM_COLORS["text"],
            font=("Segoe UI", 10), relief=tk.FLAT,
            padx=12, pady=6, cursor="hand2",
            command=self._open_selected_pdf
        ).pack(side=tk.LEFT, padx=(8, 0))

        tk.Button(
            toolbar, text="Open Folder",
            bg=FORM_COLORS["bg_input"], fg=FORM_COLORS["text"],
            activebackground=FORM_COLORS["bg_hover"], activeforeground=FORM_COLORS["text"],
            font=("Segoe UI", 10), relief=tk.FLAT,
            padx=12, pady=6, cursor="hand2",
            command=self._open_folder
        ).pack(side=tk.LEFT, padx=(8, 0))

        tk.Button(
            toolbar, text="View on house.gov",
            bg=FORM_COLORS["bg_input"], fg=FORM_COLORS["text"],
            activebackground=FORM_COLORS["bg_hover"], activeforeground=FORM_COLORS["text"],
            font=("Segoe UI", 10), relief=tk.FLAT,
            padx=12, pady=6, cursor="hand2",
            command=self._open_on_web
        ).pack(side=tk.LEFT, padx=(8, 0))

        if self._on_back:
            tk.Button(
                toolbar, text="Back to Market Select",
                bg=FORM_COLORS["bg_input"], fg=FORM_COLORS["text"],
                activebackground=FORM_COLORS["bg_hover"], activeforeground=FORM_COLORS["text"],
                font=("Segoe UI", 10), relief=tk.FLAT,
                padx=12, pady=6, cursor="hand2",
                command=self._on_back
            ).pack(side=tk.RIGHT)

        # Filter bar
        filter_bar = tk.Frame(self.root, bg=FORM_COLORS["bg"])
        filter_bar.pack(fill=tk.X, padx=16, pady=(0, 8))

        tk.Label(filter_bar, text="Filter:",
                 bg=FORM_COLORS["bg"], fg=FORM_COLORS["text_dim"],
                 font=("Segoe UI", 10)).pack(side=tk.LEFT)

        self.filter_var = tk.StringVar(value="All")
        names = ["All"] + sorted(TRACKED_POLITICIANS)
        for name in names:
            rb = tk.Radiobutton(
                filter_bar, text=name, variable=self.filter_var, value=name,
                bg=FORM_COLORS["bg"], fg=FORM_COLORS["text_dim"],
                selectcolor=FORM_COLORS["bg_input"],
                activebackground=FORM_COLORS["bg"],
                activeforeground=FORM_COLORS["text"],
                font=("Segoe UI", 9), relief=tk.FLAT,
                indicatoron=False, padx=10, pady=3, cursor="hand2",
                command=self._apply_filter)
            rb.pack(side=tk.LEFT, padx=(6, 0))

        # Time range bar
        time_bar = tk.Frame(self.root, bg=FORM_COLORS["bg"])
        time_bar.pack(fill=tk.X, padx=16, pady=(0, 8))

        tk.Label(time_bar, text="Period:",
                 bg=FORM_COLORS["bg"], fg=FORM_COLORS["text_dim"],
                 font=("Segoe UI", 10)).pack(side=tk.LEFT)

        self.time_var = tk.StringVar(value="3M")
        for label, _ in TIME_RANGES:
            rb = tk.Radiobutton(
                time_bar, text=label, variable=self.time_var, value=label,
                bg=FORM_COLORS["bg"], fg=FORM_COLORS["text_dim"],
                selectcolor=FORM_COLORS["bg_input"],
                activebackground=FORM_COLORS["bg"],
                activeforeground=FORM_COLORS["text"],
                font=("Segoe UI", 9), relief=tk.FLAT,
                indicatoron=False, padx=10, pady=3, cursor="hand2",
                command=self._apply_filter)
            rb.pack(side=tk.LEFT, padx=(6, 0))

        # Treeview
        tree_frame = tk.Frame(self.root, bg=FORM_COLORS["bg"])
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 8))

        columns = ("date", "politician", "district", "doc_id", "year", "status")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                 selectmode="browse", style="Dark.Treeview")

        headings = {
            "date": "Filing Date",
            "politician": "Politician",
            "district": "State/District",
            "doc_id": "Doc ID",
            "year": "Year",
            "status": "Status",
        }
        widths = {
            "date": 120,
            "politician": 220,
            "district": 100,
            "doc_id": 110,
            "year": 60,
            "status": 110,
        }
        for col in columns:
            self.tree.heading(col, text=headings[col])
            anchor = tk.CENTER if col in ("year", "status") else tk.W
            self.tree.column(col, width=widths[col], minwidth=50, anchor=anchor)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # Row tags
        self.tree.tag_configure("downloaded", foreground=FORM_COLORS["text"])
        self.tree.tag_configure("new", foreground=FORM_COLORS["success"])
        self.tree.tag_configure("pelosi", foreground="#c084fc")
        self.tree.tag_configure("greene", foreground="#fb923c")
        self.tree.tag_configure("green", foreground="#34d399")
        self.tree.tag_configure("gottheimer", foreground="#60a5fa")
        self.tree.tag_configure("khanna", foreground="#fbbf24")
        self.tree.tag_configure("mccaul", foreground="#f472b6")
        self.tree.tag_configure("crenshaw", foreground="#a78bfa")
        self.tree.tag_configure("tuberville", foreground="#2dd4bf")

        # Double-click to open PDF
        self.tree.bind("<Double-1>", lambda e: self._open_selected_pdf())

        # Status bar
        status_bar = tk.Frame(self.root, bg=FORM_COLORS["border"])
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_label = tk.Label(
            status_bar, text="", bg=FORM_COLORS["border"],
            fg=FORM_COLORS["text_dim"], font=("Segoe UI", 9),
            anchor=tk.W, padx=12, pady=4)
        self.status_label.pack(fill=tk.X)

        self._update_status_bar()

    # -- Data ------------------------------------------------------------------

    def _load_cached_filings(self):
        """Build filing list from already-downloaded PDFs on disk."""
        self.filings = []
        downloaded_ids = set(self.state.get("downloaded", []))

        if not DOWNLOAD_DIR.exists():
            self._set_status("No downloads yet. Click 'Fetch New Filings' to start.")
            return

        for pdf in DOWNLOAD_DIR.glob("*.pdf"):
            parts = pdf.stem.split("_")
            if len(parts) < 4:
                continue
            last_name = parts[0]
            first_name = " ".join(parts[1:-2])
            date_str = parts[-2]
            doc_id = parts[-1]

            # Parse date for sorting
            parsed_date = parse_filing_date(date_str)

            # Infer year from date
            year = parsed_date.year if parsed_date != datetime.min else 0

            self.filings.append({
                "last_name": last_name,
                "first_name": first_name,
                "filing_date": date_str,
                "doc_id": doc_id,
                "year": year,
                "district": "",
                "prefix": "",
                "_parsed_date": parsed_date,
                "_status": "Downloaded",
            })

        self.filings.sort(key=lambda f: f["_parsed_date"], reverse=True)
        self._populate_tree()

    def _populate_tree(self, name_filter="All"):
        """Fill treeview with current filings."""
        self.tree.delete(*self.tree.get_children())

        # Resolve time range cutoff
        time_label = self.time_var.get()
        range_value = next((v for l, v in TIME_RANGES if l == time_label), None)
        cutoff = _time_range_cutoff(range_value)

        for f in self.filings:
            if name_filter != "All":
                if f["last_name"].lower() != name_filter.lower():
                    continue

            # Time range filter
            if f["_parsed_date"] != datetime.min and f["_parsed_date"] < cutoff:
                continue

            full_name = f"{f.get('prefix', '')} {f['first_name']} {f['last_name']}".strip()
            status = f.get("_status", "Downloaded")
            tag = f["last_name"].lower()

            self.tree.insert("", tk.END, values=(
                f["filing_date"],
                full_name,
                f.get("district", ""),
                f["doc_id"],
                f["year"],
                status,
            ), tags=(tag,))

        self._update_status_bar()

    def _apply_filter(self):
        self._populate_tree(self.filter_var.get())

    # -- Actions ---------------------------------------------------------------

    def _on_fetch(self):
        if self._fetching:
            return
        self._fetching = True
        self.fetch_btn.configure(state=tk.DISABLED, text="Fetching...")
        threading.Thread(target=self._fetch_worker, daemon=True).start()

    def _fetch_worker(self):
        try:
            downloaded_ids = set(self.state.get("downloaded", []))
            all_filings = []

            for year in YEARS:
                filings = get_ptr_filings(year, log_fn=lambda msg: self.root.after(
                    0, self._set_status, msg))
                all_filings.extend(filings)

            new_filings = [f for f in all_filings if f["doc_id"] not in downloaded_ids]

            DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

            new_count = 0
            for f in new_filings:
                name = f"{f['prefix']} {f['first_name']} {f['last_name']}".strip()
                self.root.after(0, self._set_status,
                                f"Downloading: {name} ({f['filing_date']})")
                try:
                    if download_pdf(f, DOWNLOAD_DIR):
                        new_count += 1
                    downloaded_ids.add(f["doc_id"])
                except Exception as e:
                    self.root.after(0, self._set_status,
                                    f"Failed: {f['doc_id']} - {e}")
                time.sleep(0.3)

            self.state["downloaded"] = sorted(downloaded_ids)
            save_state(self.state)

            # Rebuild filings from all fetched data (includes district info)
            enriched = []
            for f in all_filings:
                parsed = parse_filing_date(f["filing_date"])
                f["_parsed_date"] = parsed
                f["_status"] = "New" if f["doc_id"] in {
                    nf["doc_id"] for nf in new_filings} else "Downloaded"
                enriched.append(f)

            enriched.sort(key=lambda x: x["_parsed_date"], reverse=True)

            def _update_ui():
                self.filings = enriched
                self._populate_tree(self.filter_var.get())
                self._set_status(
                    f"Done. {new_count} new PDF(s) downloaded. "
                    f"{len(all_filings)} total filings across {len(YEARS)} years.")

            self.root.after(0, _update_ui)

        except Exception as e:
            self.root.after(0, self._set_status, f"Error: {e}")
        finally:
            self.root.after(0, self._fetch_done)

    def _fetch_done(self):
        self._fetching = False
        self.fetch_btn.configure(state=tk.NORMAL, text="Fetch New Filings")

    def _open_selected_pdf(self):
        sel = self.tree.selection()
        if not sel:
            self._set_status("Select a filing first.")
            return

        values = self.tree.item(sel[0], "values")
        doc_id = values[3]  # doc_id column
        date_str = values[0]

        # Find matching PDF
        for pdf in DOWNLOAD_DIR.glob(f"*_{doc_id}.pdf"):
            os.startfile(str(pdf))
            self._set_status(f"Opened: {pdf.name}")
            return

        self._set_status(f"PDF not found for DocID {doc_id}. Try fetching first.")

    def _open_on_web(self):
        sel = self.tree.selection()
        if not sel:
            self._set_status("Select a filing first.")
            return

        values = self.tree.item(sel[0], "values")
        doc_id = values[3]
        year = values[4]
        url = HOUSE_PTR_URL.format(year, doc_id)
        webbrowser.open(url)
        self._set_status(f"Opened in browser: DocID {doc_id}")

    def _open_folder(self):
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(str(DOWNLOAD_DIR))

    # -- Status ----------------------------------------------------------------

    def _set_status(self, msg):
        self.status_label.configure(text=msg)

    def _update_status_bar(self):
        last = self.state.get("last_fetch")
        n_downloaded = len(self.state.get("downloaded", []))
        n_shown = len(self.tree.get_children())

        parts = []
        if last:
            dt = datetime.fromisoformat(last)
            parts.append(f"Last fetch: {dt.strftime('%Y-%m-%d %H:%M')}")
        parts.append(f"{n_downloaded} PDFs on file")
        parts.append(f"{n_shown} shown")
        parts.append(f"Tracking: {', '.join(TRACKED_POLITICIANS)}")

        self._set_status("  |  ".join(parts))


# --- EUROPEAN INSIDE TRACKER GUI ---------------------------------------------

class EuropeanInsideTrackerGUI:
    def __init__(self, root, on_back=None):
        self.root = root
        self.root.title("Inside Tracker — EU/Benelux Corporate Insider Transactions")
        self.root.geometry("1100x640")
        self.root.minsize(900, 500)
        self.root.configure(bg=FORM_COLORS["bg"])

        self.state = load_state_eu()
        self.transactions = []
        self._fetching = False
        self._on_back = on_back

        # Build tag-name mapping for companies
        self._company_tags = {}
        for i, company in enumerate(TRACKED_EU_COMPANIES):
            tag = company.lower().replace(" ", "_")
            self._company_tags[company.lower()] = (tag, _EU_COMPANY_COLORS[i % len(_EU_COMPANY_COLORS)])

        self._configure_styles()
        self._build_ui()

    # -- Styles ----------------------------------------------------------------

    def _configure_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Dark.Treeview",
                        background=FORM_COLORS["bg_input"],
                        foreground=FORM_COLORS["text"],
                        fieldbackground=FORM_COLORS["bg_input"],
                        borderwidth=0,
                        font=("Segoe UI", 10))
        style.configure("Dark.Treeview.Heading",
                        background=FORM_COLORS["border"],
                        foreground=FORM_COLORS["text"],
                        font=("Segoe UI", 10, "bold"))
        style.map("Dark.Treeview",
                  background=[("selected", FORM_COLORS["accent_dark"])],
                  foreground=[("selected", FORM_COLORS["text"])])

        style.configure("TScrollbar",
                        background=FORM_COLORS["border"],
                        troughcolor=FORM_COLORS["bg_input"],
                        borderwidth=0,
                        arrowcolor=FORM_COLORS["text_dim"])

    # -- UI Build --------------------------------------------------------------

    def _build_ui(self):
        # Header
        header = tk.Frame(self.root, bg=FORM_COLORS["bg"])
        header.pack(fill=tk.X, padx=16, pady=(16, 8))

        tk.Label(header, text="Inside Tracker — EU/Benelux",
                 bg=FORM_COLORS["bg"], fg=FORM_COLORS["text"],
                 font=("Segoe UI", 16, "bold")).pack(side=tk.LEFT)

        tk.Label(header, text="Corporate Insider Transactions (AFM)",
                 bg=FORM_COLORS["bg"], fg=FORM_COLORS["text_dim"],
                 font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(12, 0), pady=(4, 0))

        # Toolbar
        toolbar = tk.Frame(self.root, bg=FORM_COLORS["bg"])
        toolbar.pack(fill=tk.X, padx=16, pady=(0, 8))

        self.fetch_btn = tk.Button(
            toolbar, text="Fetch Transactions",
            bg=FORM_COLORS["accent_dark"], fg="#ffffff",
            activebackground=FORM_COLORS["accent"], activeforeground="#ffffff",
            font=("Segoe UI", 10, "bold"), relief=tk.FLAT,
            padx=16, pady=6, cursor="hand2",
            command=self._on_fetch)
        self.fetch_btn.pack(side=tk.LEFT)

        tk.Button(
            toolbar, text="View on AFM",
            bg=FORM_COLORS["bg_input"], fg=FORM_COLORS["text"],
            activebackground=FORM_COLORS["bg_hover"], activeforeground=FORM_COLORS["text"],
            font=("Segoe UI", 10), relief=tk.FLAT,
            padx=12, pady=6, cursor="hand2",
            command=self._open_on_web
        ).pack(side=tk.LEFT, padx=(8, 0))

        if self._on_back:
            tk.Button(
                toolbar, text="Back to Market Select",
                bg=FORM_COLORS["bg_input"], fg=FORM_COLORS["text"],
                activebackground=FORM_COLORS["bg_hover"], activeforeground=FORM_COLORS["text"],
                font=("Segoe UI", 10), relief=tk.FLAT,
                padx=12, pady=6, cursor="hand2",
                command=self._on_back
            ).pack(side=tk.RIGHT)

        # Filter bar
        filter_bar = tk.Frame(self.root, bg=FORM_COLORS["bg"])
        filter_bar.pack(fill=tk.X, padx=16, pady=(0, 8))

        tk.Label(filter_bar, text="Filter:",
                 bg=FORM_COLORS["bg"], fg=FORM_COLORS["text_dim"],
                 font=("Segoe UI", 10)).pack(side=tk.LEFT)

        self.filter_var = tk.StringVar(value="All")
        names = ["All"] + sorted(TRACKED_EU_COMPANIES)
        for name in names:
            rb = tk.Radiobutton(
                filter_bar, text=name, variable=self.filter_var, value=name,
                bg=FORM_COLORS["bg"], fg=FORM_COLORS["text_dim"],
                selectcolor=FORM_COLORS["bg_input"],
                activebackground=FORM_COLORS["bg"],
                activeforeground=FORM_COLORS["text"],
                font=("Segoe UI", 9), relief=tk.FLAT,
                indicatoron=False, padx=10, pady=3, cursor="hand2",
                command=self._apply_filter)
            rb.pack(side=tk.LEFT, padx=(6, 0))

        # Time range bar
        time_bar = tk.Frame(self.root, bg=FORM_COLORS["bg"])
        time_bar.pack(fill=tk.X, padx=16, pady=(0, 8))

        tk.Label(time_bar, text="Period:",
                 bg=FORM_COLORS["bg"], fg=FORM_COLORS["text_dim"],
                 font=("Segoe UI", 10)).pack(side=tk.LEFT)

        self.time_var = tk.StringVar(value="3M")
        for label, _ in TIME_RANGES:
            rb = tk.Radiobutton(
                time_bar, text=label, variable=self.time_var, value=label,
                bg=FORM_COLORS["bg"], fg=FORM_COLORS["text_dim"],
                selectcolor=FORM_COLORS["bg_input"],
                activebackground=FORM_COLORS["bg"],
                activeforeground=FORM_COLORS["text"],
                font=("Segoe UI", 9), relief=tk.FLAT,
                indicatoron=False, padx=10, pady=3, cursor="hand2",
                command=self._apply_filter)
            rb.pack(side=tk.LEFT, padx=(6, 0))

        # Treeview
        tree_frame = tk.Frame(self.root, bg=FORM_COLORS["bg"])
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 8))

        columns = ("date", "company", "person", "position", "lei")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                 selectmode="browse", style="Dark.Treeview")

        headings = {
            "date": "Date",
            "company": "Company",
            "person": "Person",
            "position": "Position",
            "lei": "LEI",
        }
        widths = {
            "date": 100,
            "company": 200,
            "person": 180,
            "position": 240,
            "lei": 200,
        }
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], minwidth=50, anchor=tk.W)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # Row tags — per-company colors
        self.tree.tag_configure("new", foreground=FORM_COLORS["success"])
        for tag, color in self._company_tags.values():
            self.tree.tag_configure(tag, foreground=color)

        # Double-click to open detail page
        self.tree.bind("<Double-1>", lambda e: self._open_on_web())

        # Status bar
        status_bar = tk.Frame(self.root, bg=FORM_COLORS["border"])
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_label = tk.Label(
            status_bar, text="", bg=FORM_COLORS["border"],
            fg=FORM_COLORS["text_dim"], font=("Segoe UI", 9),
            anchor=tk.W, padx=12, pady=4)
        self.status_label.pack(fill=tk.X)

        self._update_status_bar()

    # -- Data ------------------------------------------------------------------

    def _populate_tree(self, company_filter="All"):
        self.tree.delete(*self.tree.get_children())
        seen_ids = set(self.state.get("seen_ids", []))

        # Resolve time range cutoff
        time_label = self.time_var.get()
        range_value = next((v for l, v in TIME_RANGES if l == time_label), None)
        cutoff = _time_range_cutoff(range_value)

        for t in self.transactions:
            if company_filter != "All":
                if company_filter.lower() not in t["company"].lower():
                    continue

            # Time range filter
            if t["_parsed_date"] != datetime.min and t["_parsed_date"] < cutoff:
                continue

            # Determine tag
            is_new = t["id"] not in seen_ids
            tag = "new" if is_new else ""
            if not is_new:
                for tracked, (company_tag, _) in self._company_tags.items():
                    if tracked in t["company"].lower():
                        tag = company_tag
                        break

            self.tree.insert("", tk.END, iid=t["id"], values=(
                t["date"],
                t["company"],
                t["person"],
                t["position"],
                t["lei"],
            ), tags=(tag,) if tag else ())

        self._update_status_bar()

    def _apply_filter(self):
        self._populate_tree(self.filter_var.get())

    # -- Actions ---------------------------------------------------------------

    def _on_fetch(self):
        if self._fetching:
            return
        self._fetching = True
        self.fetch_btn.configure(state=tk.DISABLED, text="Fetching...")
        threading.Thread(target=self._fetch_worker, daemon=True).start()

    def _fetch_worker(self):
        try:
            seen_ids = set(self.state.get("seen_ids", []))
            rows = fetch_afm_xml(log_fn=lambda msg: self.root.after(0, self._set_status, msg))

            new_count = sum(1 for r in rows if r["id"] not in seen_ids)

            # Update seen IDs with all current transaction IDs
            all_ids = seen_ids | {r["id"] for r in rows}
            self.state["seen_ids"] = sorted(all_ids)
            save_state_eu(self.state)

            def _update_ui():
                self.transactions = rows
                self._populate_tree(self.filter_var.get())
                self._set_status(
                    f"Done. {new_count} new transaction(s). "
                    f"{len(rows)} total for tracked companies.")

            self.root.after(0, _update_ui)

        except Exception as e:
            self.root.after(0, self._set_status, f"Error: {e}")
        finally:
            self.root.after(0, self._fetch_done)

    def _fetch_done(self):
        self._fetching = False
        self.fetch_btn.configure(state=tk.NORMAL, text="Fetch Transactions")

    def _open_on_web(self):
        sel = self.tree.selection()
        if not sel:
            self._set_status("Select a transaction first.")
            return

        tx_id = sel[0]
        url = AFM_DETAIL_URL.format(tx_id)
        webbrowser.open(url)
        self._set_status(f"Opened in browser: {tx_id}")

    # -- Status ----------------------------------------------------------------

    def _set_status(self, msg):
        self.status_label.configure(text=msg)

    def _update_status_bar(self):
        last = self.state.get("last_fetch")
        n_seen = len(self.state.get("seen_ids", []))
        n_shown = len(self.tree.get_children())

        parts = []
        if last:
            dt = datetime.fromisoformat(last)
            parts.append(f"Last fetch: {dt.strftime('%Y-%m-%d %H:%M')}")
        parts.append(f"{n_seen} transactions on record")
        parts.append(f"{n_shown} shown")
        parts.append(f"Tracking: {', '.join(TRACKED_EU_COMPANIES)}")

        self._set_status("  |  ".join(parts))


# --- MARKET SELECTOR ---------------------------------------------------------

def _clear_root(root):
    """Destroy all children of a root window."""
    for widget in root.winfo_children():
        widget.destroy()


class MarketSelectorDialog:
    def __init__(self, root):
        self.root = root
        self.root.title("Inside Tracker — Market Selection")
        self.root.geometry("480x300")
        self.root.minsize(400, 260)
        self.root.configure(bg=FORM_COLORS["bg"])

        self._build_ui()

    def _build_ui(self):
        # Title
        tk.Label(self.root, text="Inside Tracker",
                 bg=FORM_COLORS["bg"], fg=FORM_COLORS["text"],
                 font=("Segoe UI", 18, "bold")).pack(pady=(40, 4))

        tk.Label(self.root, text="Select a market to track",
                 bg=FORM_COLORS["bg"], fg=FORM_COLORS["text_dim"],
                 font=("Segoe UI", 11)).pack(pady=(0, 30))

        btn_frame = tk.Frame(self.root, bg=FORM_COLORS["bg"])
        btn_frame.pack()

        tk.Button(
            btn_frame,
            text="US Congress\nPolitician Stock Trades",
            bg=FORM_COLORS["accent_dark"], fg="#ffffff",
            activebackground=FORM_COLORS["accent"], activeforeground="#ffffff",
            font=("Segoe UI", 11, "bold"), relief=tk.FLAT,
            padx=24, pady=16, cursor="hand2", width=28,
            command=self._launch_us
        ).pack(pady=(0, 12))

        tk.Button(
            btn_frame,
            text="EU / Benelux\nCorporate Insider Transactions (AFM)",
            bg=FORM_COLORS["accent_dark"], fg="#ffffff",
            activebackground=FORM_COLORS["accent"], activeforeground="#ffffff",
            font=("Segoe UI", 11, "bold"), relief=tk.FLAT,
            padx=24, pady=16, cursor="hand2", width=28,
            command=self._launch_eu
        ).pack()

    def _launch_us(self):
        _clear_root(self.root)
        self.root.geometry("960x640")
        InsideTrackerGUI(self.root, on_back=self._back_to_selector)

    def _launch_eu(self):
        _clear_root(self.root)
        self.root.geometry("1100x640")
        EuropeanInsideTrackerGUI(self.root, on_back=self._back_to_selector)

    def _back_to_selector(self):
        _clear_root(self.root)
        self.root.geometry("480x300")
        MarketSelectorDialog(self.root)


# --- MAIN ---------------------------------------------------------------------

def main():
    setup_logging("inside_tracker")
    root = tk.Tk()
    MarketSelectorDialog(root)
    root.mainloop()
    return 0

if __name__ == "__main__":
    sys.exit(main())
