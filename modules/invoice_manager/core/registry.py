"""SQLite-backed invoice registry — single source of truth for invoice numbers.

Guarantees:
  - Per-year sequential numbering (resets each calendar year).
  - Atomic reservation under concurrent access (BEGIN IMMEDIATE + UNIQUE).
  - Gapless: voided invoices keep their number; rows are never deleted.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import threading
import time
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from shared_logging import get_logger

from .models import Invoice, LineItem

logger = get_logger(__name__)


class RegistryConflictError(Exception):
    """Raised when an import would clash with an existing row."""


SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS invoices (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    year            INTEGER NOT NULL,
    sequence        INTEGER NOT NULL,
    company_key     TEXT    NOT NULL,
    invoice_date    TEXT    NOT NULL,
    customer_name   TEXT    NOT NULL,
    customer_vat    TEXT    NOT NULL DEFAULT '',
    customer_address TEXT   NOT NULL DEFAULT '',
    customer_email  TEXT    NOT NULL DEFAULT '',
    line_items_json TEXT    NOT NULL,
    subtotal_cents  INTEGER NOT NULL,
    vat_cents       INTEGER NOT NULL,
    total_cents     INTEGER NOT NULL,
    currency        TEXT    NOT NULL DEFAULT 'EUR',
    status          TEXT    NOT NULL DEFAULT 'draft',
    void_reason     TEXT,
    pdf_path        TEXT,
    source          TEXT    NOT NULL,
    source_ref      TEXT,
    notes           TEXT    NOT NULL DEFAULT '',
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL,
    UNIQUE(year, sequence)
);
CREATE INDEX IF NOT EXISTS idx_invoices_year ON invoices(year);
CREATE INDEX IF NOT EXISTS idx_invoices_company ON invoices(company_key);
CREATE INDEX IF NOT EXISTS idx_invoices_source_ref ON invoices(source, source_ref);

CREATE TABLE IF NOT EXISTS wc_push_queue (
    invoice_id      INTEGER PRIMARY KEY,
    order_id        TEXT    NOT NULL,
    attempts        INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT,
    next_retry_at   TEXT,
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL,
    FOREIGN KEY(invoice_id) REFERENCES invoices(id)
);

CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);
"""


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class InvoiceRegistry:
    """SQLite registry. Safe for multi-thread use; opens a fresh connection
    per logical transaction so the WC poll thread and the Tk main thread
    don't share connection state."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_lock = threading.Lock()
        self._initialised = False
        self._ensure_schema()

    # ---------- connection management ----------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=30.0,
            isolation_level=None,           # autocommit; we manage txns explicitly
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _ensure_schema(self):
        with self._init_lock:
            if self._initialised:
                return
            conn = self._connect()
            try:
                conn.execute("PRAGMA journal_mode = WAL;")
                conn.executescript(SCHEMA_SQL)
                cur = conn.execute("SELECT version FROM schema_version LIMIT 1;")
                row = cur.fetchone()
                if row is None:
                    conn.execute("INSERT INTO schema_version (version) VALUES (?)",
                                 (SCHEMA_VERSION,))
                # Idempotent migrations — add columns that may not exist yet.
                try:
                    conn.execute(
                        "ALTER TABLE invoices ADD COLUMN "
                        "expense_items_json TEXT NOT NULL DEFAULT '[]'"
                    )
                except Exception:
                    pass  # column already exists
                self._initialised = True
            finally:
                conn.close()

    # ---------- read helpers ----------

    def get_next_preview(self, year: int) -> int:
        """Read-only hint; NOT authoritative — may be stale by the time you reserve."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM invoices WHERE year = ?",
                (year,),
            ).fetchone()
            return int(row[0])
        finally:
            conn.close()

    def get_invoice(self, year: int, sequence: int) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM invoices WHERE year=? AND sequence=?",
                (year, sequence),
            ).fetchone()
            return _row_to_dict(row) if row else None
        finally:
            conn.close()

    def get_by_id(self, invoice_id: int) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM invoices WHERE id=?", (invoice_id,)
            ).fetchone()
            return _row_to_dict(row) if row else None
        finally:
            conn.close()

    def get_by_source_ref(self, source: str, ref: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM invoices WHERE source=? AND source_ref=?",
                (source, ref),
            ).fetchone()
            return _row_to_dict(row) if row else None
        finally:
            conn.close()

    def list_invoices(
        self,
        year: Optional[int] = None,
        company_key: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        clauses = []
        params: List[Any] = []
        if year is not None:
            clauses.append("year = ?")
            params.append(year)
        if company_key:
            clauses.append("company_key = ?")
            params.append(company_key)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if search:
            clauses.append("(customer_name LIKE ? OR notes LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = (
            f"SELECT * FROM invoices {where} "
            f"ORDER BY year DESC, sequence DESC LIMIT ?"
        )
        params.append(limit)
        conn = self._connect()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [_row_to_dict(r) for r in rows]
        finally:
            conn.close()

    def list_years(self) -> List[int]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT DISTINCT year FROM invoices ORDER BY year DESC"
            ).fetchall()
            return [int(r[0]) for r in rows]
        finally:
            conn.close()

    def distinct_customer_names(self) -> List[str]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT DISTINCT customer_name FROM invoices ORDER BY customer_name"
            ).fetchall()
            return [r[0] for r in rows]
        finally:
            conn.close()

    # ---------- write operations ----------

    def reserve_next_number(self, year: int, draft: Dict[str, Any]) -> int:
        """Atomically reserve the next sequence for `year` and persist a draft row.

        `draft` must contain: company_key, invoice_date (ISO YYYY-MM-DD),
        customer_name, line_items (list[LineItem] or list[dict]), source.

        Returns the assigned sequence. Status of the new row is 'draft' —
        call finalize_invoice(id, pdf_path) once rendering succeeds.
        """
        max_retries = 5
        for attempt in range(max_retries):
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE;")
                row = conn.execute(
                    "SELECT COALESCE(MAX(sequence), 0) + 1 FROM invoices WHERE year=?",
                    (year,),
                ).fetchone()
                next_seq = int(row[0])

                payload = _draft_to_row(draft, year=year, sequence=next_seq)
                conn.execute(
                    """
                    INSERT INTO invoices
                      (year, sequence, company_key, invoice_date,
                       customer_name, customer_vat, customer_address, customer_email,
                       line_items_json, expense_items_json,
                       subtotal_cents, vat_cents, total_cents,
                       currency, status, source, source_ref, notes,
                       created_at, updated_at)
                    VALUES
                      (:year, :sequence, :company_key, :invoice_date,
                       :customer_name, :customer_vat, :customer_address, :customer_email,
                       :line_items_json, :expense_items_json,
                       :subtotal_cents, :vat_cents, :total_cents,
                       :currency, 'draft', :source, :source_ref, :notes,
                       :created_at, :updated_at)
                    """,
                    payload,
                )
                conn.execute("COMMIT;")
                logger.info(
                    f"Reserved invoice #{next_seq} for {year} "
                    f"({payload['company_key']}, source={payload['source']})"
                )
                return next_seq
            except sqlite3.IntegrityError as e:
                # UNIQUE(year, sequence) collision — another thread won. Retry.
                try:
                    conn.execute("ROLLBACK;")
                except sqlite3.OperationalError:
                    pass
                logger.warning(
                    f"reserve_next_number race (attempt {attempt + 1}): {e}"
                )
                time.sleep(0.01 * (attempt + 1))
            except Exception:
                try:
                    conn.execute("ROLLBACK;")
                except sqlite3.OperationalError:
                    pass
                raise
            finally:
                conn.close()
        raise RuntimeError(
            f"Failed to reserve invoice number for year {year} after {max_retries} attempts"
        )

    def reserve_and_return_row(self, year: int, draft: Dict[str, Any]) -> Dict[str, Any]:
        """Convenience: reserve and return the full inserted row."""
        seq = self.reserve_next_number(year, draft)
        return self.get_invoice(year, seq)

    def import_existing_invoice(
        self,
        year: int,
        sequence: int,
        draft: Dict[str, Any],
        pdf_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Insert a row at a specific (year, sequence) — used to import
        invoices that were issued elsewhere (e.g. WooCommerce PDF plugin)
        before the registry existed.

        Idempotent on (source, source_ref): if a row already exists for the
        same external identifier, it is returned unchanged. If a different
        invoice already occupies the slot, raises RegistryConflictError so
        the caller can surface it for manual resolution.

        Inserts with status='issued' (the invoice has already been delivered).
        """
        source = draft.get("source", "manual")
        source_ref = draft.get("source_ref")

        if source_ref:
            existing_by_ref = self.get_by_source_ref(source, str(source_ref))
            if existing_by_ref:
                if (existing_by_ref["year"] != year
                        or existing_by_ref["sequence"] != sequence):
                    raise RegistryConflictError(
                        f"{source} ref {source_ref!r} is already registered as "
                        f"#{existing_by_ref['sequence']:03d} ({existing_by_ref['year']}), "
                        f"but the import requested #{sequence:03d} ({year})."
                    )
                return existing_by_ref

        existing_at_slot = self.get_invoice(year, sequence)
        if existing_at_slot:
            raise RegistryConflictError(
                f"Slot #{sequence:03d} ({year}) is already occupied by "
                f"{existing_at_slot['source']} ref "
                f"{existing_at_slot.get('source_ref')!r} "
                f"(customer: {existing_at_slot['customer_name']!r})."
            )

        payload = _draft_to_row(draft, year=year, sequence=sequence)
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            conn.execute(
                """
                INSERT INTO invoices
                  (year, sequence, company_key, invoice_date,
                   customer_name, customer_vat, customer_address, customer_email,
                   line_items_json, expense_items_json,
                   subtotal_cents, vat_cents, total_cents,
                   currency, status, pdf_path, source, source_ref, notes,
                   created_at, updated_at)
                VALUES
                  (:year, :sequence, :company_key, :invoice_date,
                   :customer_name, :customer_vat, :customer_address, :customer_email,
                   :line_items_json, :expense_items_json,
                   :subtotal_cents, :vat_cents, :total_cents,
                   :currency, 'issued', :pdf_path, :source, :source_ref, :notes,
                   :created_at, :updated_at)
                """,
                {**payload, "pdf_path": pdf_path},
            )
            conn.execute("COMMIT;")
        except sqlite3.IntegrityError as e:
            try:
                conn.execute("ROLLBACK;")
            except sqlite3.OperationalError:
                pass
            raise RegistryConflictError(
                f"UNIQUE conflict importing #{sequence:03d} ({year}): {e}"
            ) from e
        except Exception:
            try:
                conn.execute("ROLLBACK;")
            except sqlite3.OperationalError:
                pass
            raise
        finally:
            conn.close()

        logger.info(
            f"Imported invoice #{sequence:03d} ({year}) "
            f"from {source} ref={source_ref}"
        )
        return self.get_invoice(year, sequence)

    def finalize_invoice(self, invoice_id: int, pdf_path: str) -> None:
        """Mark a draft invoice as issued, with the rendered PDF location."""
        now = _now_iso()
        conn = self._connect()
        try:
            cur = conn.execute(
                "UPDATE invoices SET status='issued', pdf_path=?, updated_at=? "
                "WHERE id=? AND status='draft'",
                (pdf_path, now, invoice_id),
            )
            if cur.rowcount == 0:
                logger.warning(
                    f"finalize_invoice({invoice_id}) affected 0 rows "
                    f"(not draft or not found)"
                )
        finally:
            conn.close()

    def void_invoice(self, invoice_id: int, reason: str) -> None:
        """Mark an invoice as voided. Keeps the number (gapless requirement)."""
        if not reason or not reason.strip():
            raise ValueError("void_invoice requires a non-empty reason")
        now = _now_iso()
        conn = self._connect()
        try:
            cur = conn.execute(
                "UPDATE invoices SET status='voided', void_reason=?, updated_at=? "
                "WHERE id=? AND status != 'voided'",
                (reason.strip(), now, invoice_id),
            )
            if cur.rowcount == 0:
                logger.warning(f"void_invoice({invoice_id}) affected 0 rows")
        finally:
            conn.close()

    def update_draft(self, invoice_id: int, fields: Dict[str, Any]) -> None:
        """Update editable fields on a draft invoice. Issued/voided rows are immutable."""
        allowed = {
            "customer_name", "customer_vat", "customer_address", "customer_email",
            "invoice_date", "line_items_json", "subtotal_cents", "vat_cents",
            "total_cents", "currency", "notes",
        }
        bad = set(fields) - allowed
        if bad:
            raise ValueError(f"update_draft: disallowed fields {bad}")
        if not fields:
            return
        sets = ", ".join(f"{k} = :{k}" for k in fields)
        params = dict(fields)
        params["id"] = invoice_id
        params["updated_at"] = _now_iso()
        conn = self._connect()
        try:
            cur = conn.execute(
                f"UPDATE invoices SET {sets}, updated_at=:updated_at "
                f"WHERE id=:id AND status='draft'",
                params,
            )
            if cur.rowcount == 0:
                raise RuntimeError(
                    f"update_draft({invoice_id}) affected 0 rows — "
                    f"row missing or no longer in 'draft' status"
                )
        finally:
            conn.close()

    def set_pdf_path(self, invoice_id: int, pdf_path: str) -> None:
        """Update only pdf_path (used when re-filing without changing status)."""
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE invoices SET pdf_path=?, updated_at=? WHERE id=?",
                (pdf_path, _now_iso(), invoice_id),
            )
        finally:
            conn.close()

    # ---------- WC push queue ----------

    def enqueue_wc_push(self, invoice_id: int, order_id: str, error: str) -> None:
        now = _now_iso()
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO wc_push_queue
                  (invoice_id, order_id, attempts, last_error, next_retry_at,
                   created_at, updated_at)
                VALUES (?, ?, 1, ?, NULL, ?, ?)
                ON CONFLICT(invoice_id) DO UPDATE SET
                  attempts = attempts + 1,
                  last_error = excluded.last_error,
                  updated_at = excluded.updated_at
                """,
                (invoice_id, order_id, error, now, now),
            )
        finally:
            conn.close()

    def clear_wc_push(self, invoice_id: int) -> None:
        conn = self._connect()
        try:
            conn.execute("DELETE FROM wc_push_queue WHERE invoice_id=?", (invoice_id,))
        finally:
            conn.close()

    def pending_wc_pushes(self) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM wc_push_queue ORDER BY created_at"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ---------- backup / restore (debug mode) ----------

    _SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")

    def checkpoint(self) -> None:
        """Flush WAL into the main DB file so a plain file copy is a complete snapshot."""
        conn = self._connect()
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        finally:
            conn.close()

    def backup_db(self, dest: Path) -> Path:
        """Copy the DB file (and any WAL/SHM sidecars) to `dest`. Returns `dest`."""
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        self.checkpoint()
        shutil.copy2(str(self.db_path), str(dest))
        for suffix in self._SIDECAR_SUFFIXES:
            sidecar = Path(str(self.db_path) + suffix)
            if sidecar.exists():
                shutil.copy2(str(sidecar), str(dest) + suffix)
        logger.info(f"Backed up DB {self.db_path} -> {dest}")
        return dest

    def restore_db(self, src: Path) -> None:
        """Replace the DB file (and sidecars) with the backup at `src`.

        Safe because connections are opened per call — there are no long-lived
        handles to invalidate. Removes existing sidecars first so a clean copy
        of the snapshot is restored.
        """
        src = Path(src)
        if not src.exists():
            raise FileNotFoundError(f"DB backup not found: {src}")
        for suffix in ("",) + self._SIDECAR_SUFFIXES:
            target = Path(str(self.db_path) + suffix)
            if suffix and target.exists():
                target.unlink()
        shutil.copy2(str(src), str(self.db_path))
        for suffix in self._SIDECAR_SUFFIXES:
            sidecar = Path(str(src) + suffix)
            if sidecar.exists():
                shutil.copy2(str(sidecar), str(self.db_path) + suffix)
        logger.info(f"Restored DB {self.db_path} from {src}")

    # ---------- diagnostics ----------

    def health_check(self) -> List[str]:
        """Return a list of warnings. Empty list = healthy.

        Belgian law: gapless sequential numbering. We detect:
          - gaps within a year
          - duplicate (year, sequence) — should be impossible via UNIQUE but verify
        """
        warnings: List[str] = []
        conn = self._connect()
        try:
            years = [int(r[0]) for r in conn.execute(
                "SELECT DISTINCT year FROM invoices ORDER BY year").fetchall()]
            for year in years:
                seqs = [int(r[0]) for r in conn.execute(
                    "SELECT sequence FROM invoices WHERE year=? ORDER BY sequence",
                    (year,)).fetchall()]
                expected = list(range(1, len(seqs) + 1))
                if seqs != expected:
                    missing = set(expected) - set(seqs)
                    extra = set(seqs) - set(expected)
                    warnings.append(
                        f"Year {year}: gap detected. "
                        f"missing={sorted(missing)} extra={sorted(extra)}"
                    )
            dupes = conn.execute(
                "SELECT year, sequence, COUNT(*) FROM invoices "
                "GROUP BY year, sequence HAVING COUNT(*) > 1"
            ).fetchall()
            for y, s, c in dupes:
                warnings.append(f"Duplicate (year={y}, sequence={s}) count={c}")
        finally:
            conn.close()
        return warnings


# ---------- helpers ----------

def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    for key, dest in [("line_items_json", "line_items"),
                      ("expense_items_json", "expense_items")]:
        if d.get(key):
            try:
                d[dest] = json.loads(d[key])
            except json.JSONDecodeError:
                d[dest] = []
        else:
            d[dest] = []
    return d


def _serialize_items(items) -> tuple[List[dict], int, int]:
    """Serialize a list of LineItem or dict items; return (serialised, subtotal, vat)."""
    serialised: List[dict] = []
    subtotal = 0
    vat = 0
    for li in items:
        if isinstance(li, LineItem):
            serialised.append(li.to_dict())
            subtotal += li.line_subtotal_cents
            vat += li.line_vat_cents
        else:
            obj = LineItem.from_dict(li)
            serialised.append(obj.to_dict())
            subtotal += obj.line_subtotal_cents
            vat += obj.line_vat_cents
    return serialised, subtotal, vat


def _draft_to_row(draft: Dict[str, Any], year: int, sequence: int) -> Dict[str, Any]:
    work_ser, work_sub, work_vat = _serialize_items(draft.get("line_items", []))
    exp_ser, exp_sub, exp_vat   = _serialize_items(draft.get("expense_items", []))
    subtotal = work_sub + exp_sub
    vat      = work_vat + exp_vat
    total    = subtotal + vat

    inv_date = draft["invoice_date"]
    if isinstance(inv_date, (datetime, date)):
        inv_date = inv_date.strftime("%Y-%m-%d")

    now = _now_iso()
    return {
        "year": year,
        "sequence": sequence,
        "company_key": draft["company_key"],
        "invoice_date": inv_date,
        "customer_name": draft["customer_name"],
        "customer_vat": draft.get("customer_vat", "") or "",
        "customer_address": draft.get("customer_address", "") or "",
        "customer_email": draft.get("customer_email", "") or "",
        "line_items_json": json.dumps(work_ser, ensure_ascii=False),
        "expense_items_json": json.dumps(exp_ser, ensure_ascii=False),
        "subtotal_cents": subtotal,
        "vat_cents": vat,
        "total_cents": total,
        "currency": draft.get("currency", "EUR"),
        "source": draft.get("source", "manual"),
        "source_ref": draft.get("source_ref"),
        "notes": draft.get("notes", "") or "",
        "created_at": now,
        "updated_at": now,
    }
