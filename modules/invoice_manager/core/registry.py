"""SQLite-backed invoice registry — single source of truth for invoice numbers.

Guarantees:
  - Globally continuous sequential numbering (does NOT reset on Jan 1 —
    sequence 1 was the first non-legacy invoice and it counts up forever).
  - Atomic reservation under concurrent access (BEGIN IMMEDIATE serializes
    writers so the global MAX read inside the txn stays valid).
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

CREATE TABLE IF NOT EXISTS contacts (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    display_name         TEXT    NOT NULL,
    abbreviation         TEXT,
    vat                  TEXT    NOT NULL DEFAULT '',
    address              TEXT    NOT NULL DEFAULT '',
    email                TEXT    NOT NULL DEFAULT '',
    notes                TEXT    NOT NULL DEFAULT '',
    project_client_name  TEXT,
    project_categories   TEXT    NOT NULL DEFAULT '[]',
    created_at           TEXT    NOT NULL,
    updated_at           TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_contacts_name ON contacts(display_name);
-- abbreviation / project_client_name indices are created after
-- the migration block adds those columns on older DBs (see
-- _ensure_schema). Keeping the index DDL out of SCHEMA_SQL means
-- executescript() doesn't abort if an old DB has the contacts
-- table without those columns yet.

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
                try:
                    conn.execute(
                        "ALTER TABLE contacts ADD COLUMN project_client_name TEXT"
                    )
                except Exception:
                    pass  # column already exists
                # The partial index here is also covered by SCHEMA_SQL above
                # for fresh DBs; the ALTER path needs it created explicitly.
                try:
                    conn.execute(
                        "CREATE UNIQUE INDEX IF NOT EXISTS "
                        "idx_contacts_project_client "
                        "ON contacts(project_client_name) "
                        "WHERE project_client_name IS NOT NULL"
                    )
                except Exception:
                    pass
                try:
                    conn.execute(
                        "ALTER TABLE contacts ADD COLUMN abbreviation TEXT"
                    )
                except Exception:
                    pass  # column already exists
                try:
                    conn.execute(
                        "ALTER TABLE contacts ADD COLUMN "
                        "project_categories TEXT NOT NULL DEFAULT '[]'"
                    )
                except Exception:
                    pass  # column already exists
                try:
                    conn.execute(
                        "CREATE UNIQUE INDEX IF NOT EXISTS "
                        "idx_contacts_abbreviation "
                        "ON contacts(abbreviation) "
                        "WHERE abbreviation IS NOT NULL"
                    )
                except Exception:
                    pass
                # Retire the wc_customer_id column. SQLite 3.35+ supports
                # DROP COLUMN; on older versions the ALTER silently fails
                # and the column lingers as dead data — harmless because
                # no code paths reference it anymore.
                try:
                    conn.execute("DROP INDEX IF EXISTS idx_contacts_wc_customer")
                except Exception:
                    pass
                try:
                    conn.execute(
                        "ALTER TABLE contacts DROP COLUMN wc_customer_id"
                    )
                except Exception:
                    pass  # old SQLite or column already absent
                self._initialised = True
            finally:
                conn.close()

    # ---------- read helpers ----------

    def get_next_preview(self, year: int) -> int:
        """Read-only hint; NOT authoritative — may be stale by the time you reserve.

        Numbering is globally continuous (does not reset per calendar year);
        `year` is accepted for API symmetry with `reserve_next_number` but
        does not affect the result.
        """
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM invoices",
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
        """Atomically reserve the next sequence and persist a draft row.

        Sequences are globally continuous — they do NOT reset on Jan 1.
        `year` is recorded on the row (and pairs with sequence for the
        UNIQUE constraint) but is NOT used to pick the next number.

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
                    "SELECT COALESCE(MAX(sequence), 0) + 1 FROM invoices",
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

    def delete_invoice(self, invoice_id: int) -> Dict[str, Any]:
        """Permanently remove an invoice row and reclaim its number.

        Unlike `void_invoice` (which keeps the number — the normal,
        legally-correct way to retract an issued invoice), this actually
        deletes the row. It exists for the "oops, test invoice" case:
        something was generated by mistake (e.g. forgot to enable debug
        mode) and should never have existed at all.

        The one rule that's still enforced — because relaxing it *would*
        corrupt the registry — is that the row must be the most recently
        reserved number (its sequence == the current global MAX(sequence)).
        Deleting anything earlier would leave a gap that every invoice
        after it would then have to explain.

        Returns the deleted row (including `pdf_path`, if any, so the
        caller can also remove the file from disk) and raises ValueError
        if the invoice isn't the most recent one.
        """
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            row = conn.execute(
                "SELECT * FROM invoices WHERE id=?", (invoice_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Invoice {invoice_id} not found")
            max_seq = conn.execute(
                "SELECT COALESCE(MAX(sequence), 0) FROM invoices"
            ).fetchone()[0]
            if row["sequence"] != max_seq:
                raise ValueError(
                    "Only the most recently reserved invoice number can be "
                    "deleted — removing an earlier one would leave a gap"
                )
            conn.execute("DELETE FROM invoices WHERE id=?", (invoice_id,))
            conn.execute("COMMIT;")
            deleted = _row_to_dict(row)
        except Exception:
            try:
                conn.execute("ROLLBACK;")
            except sqlite3.OperationalError:
                pass
            raise
        finally:
            conn.close()

        logger.info(
            f"Deleted invoice id={invoice_id} status={deleted['status']} — "
            f"reclaimed #{deleted['sequence']:03d}"
        )
        return deleted

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

    # ---------- contacts ----------

    def list_contacts(self) -> List[Dict[str, Any]]:
        """All contacts, ordered alphabetically by display_name."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM contacts ORDER BY display_name COLLATE NOCASE"
            ).fetchall()
            return [_contact_row_to_dict(r) for r in rows]
        finally:
            conn.close()

    def get_contact(self, contact_id: int) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM contacts WHERE id=?", (contact_id,),
            ).fetchone()
            return _contact_row_to_dict(row) if row else None
        finally:
            conn.close()

    def create_contact(self, data: Dict[str, Any]) -> int:
        """Insert a contact. Returns the new row id.

        `data` may contain: display_name, abbreviation, vat, address,
        email, notes, project_client_name, project_categories. Missing
        string fields default to ''. Empty strings for `abbreviation` and
        `project_client_name` are normalised to NULL so the partial
        unique indices don't conflict. `project_categories` is a
        list[str] of category keys (e.g. ["Visual", "Physical"]) — the
        ones the contact should appear under when creating new project
        folders; an empty list means "show everywhere" (the legacy
        behaviour for contacts that haven't opted into the checkboxes).

        ``display_name`` is allowed to be blank: bulk-importing from the
        project list leaves it empty so the user can fill in real names
        later from the form.
        """
        now = _now_iso()
        project_client = data.get("project_client_name")
        if isinstance(project_client, str):
            project_client = project_client.strip() or None
        abbreviation = data.get("abbreviation")
        if isinstance(abbreviation, str):
            abbreviation = abbreviation.strip() or None
        payload = {
            "display_name": (data.get("display_name") or "").strip(),
            "abbreviation": abbreviation,
            "vat": (data.get("vat") or "").strip(),
            "address": (data.get("address") or "").strip(),
            "email": (data.get("email") or "").strip(),
            "notes": (data.get("notes") or "").strip(),
            "project_client_name": project_client,
            "project_categories": _encode_categories(data.get("project_categories")),
            "created_at": now,
            "updated_at": now,
        }
        conn = self._connect()
        try:
            cur = conn.execute(
                """
                INSERT INTO contacts
                  (display_name, abbreviation, vat, address, email, notes,
                   project_client_name, project_categories, created_at, updated_at)
                VALUES
                  (:display_name, :abbreviation, :vat, :address, :email, :notes,
                   :project_client_name, :project_categories, :created_at, :updated_at)
                """,
                payload,
            )
            new_id = int(cur.lastrowid)
            logger.info(f"Created contact #{new_id}: {payload['display_name']!r}")
            return new_id
        finally:
            conn.close()

    def get_contact_by_project_client(self, project_client_name: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM contacts WHERE project_client_name=?",
                (project_client_name,),
            ).fetchone()
            return _contact_row_to_dict(row) if row else None
        finally:
            conn.close()

    def get_contact_by_abbreviation(self, abbreviation: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM contacts WHERE abbreviation=?",
                (abbreviation,),
            ).fetchone()
            return _contact_row_to_dict(row) if row else None
        finally:
            conn.close()

    def update_contact(self, contact_id: int, data: Dict[str, Any]) -> None:
        """Patch a contact. Keys not present in `data` are left alone.

        `abbreviation` and `project_client_name` get the same blank-to-NULL
        normalisation as ``create_contact`` so partial unique indices stay
        consistent. `project_categories` (a list[str]) is JSON-encoded the
        same way as on insert.
        """
        allowed = {"display_name", "abbreviation", "vat", "address", "email",
                   "notes", "project_client_name", "project_categories"}
        nullable_when_blank = {"abbreviation", "project_client_name"}
        sets = []
        values: List[Any] = []
        for key in allowed:
            if key in data:
                value = data[key]
                if key == "project_categories":
                    value = _encode_categories(value)
                elif isinstance(value, str):
                    value = value.strip()
                    if not value and key in nullable_when_blank:
                        value = None
                sets.append(f"{key}=?")
                values.append(value)
        if not sets:
            return
        sets.append("updated_at=?")
        values.append(_now_iso())
        values.append(int(contact_id))
        conn = self._connect()
        try:
            conn.execute(
                f"UPDATE contacts SET {', '.join(sets)} WHERE id=?",
                tuple(values),
            )
        finally:
            conn.close()

    def delete_contact(self, contact_id: int) -> None:
        conn = self._connect()
        try:
            conn.execute("DELETE FROM contacts WHERE id=?", (int(contact_id),))
        finally:
            conn.close()

    # ---------- diagnostics ----------

    def health_check(self) -> List[str]:
        """Return a list of warnings. Empty list = healthy.

        Belgian law: gapless sequential numbering. Sequences run as a
        single continuous series across years (not reset on Jan 1), so
        we detect:
          - any missing number in 1..MAX(sequence)
          - the same sequence used by more than one row (regardless of year)
        """
        warnings: List[str] = []
        conn = self._connect()
        try:
            seqs = [int(r[0]) for r in conn.execute(
                "SELECT sequence FROM invoices ORDER BY sequence").fetchall()]
            if seqs:
                expected = set(range(1, max(seqs) + 1))
                missing = sorted(expected - set(seqs))
                # `extra` would be sequences outside 1..MAX, which the
                # UNIQUE constraint and positive-int convention rule out;
                # we surface them anyway so corruption is visible.
                extra = sorted(s for s in seqs if s < 1)
                if missing or extra:
                    parts = []
                    if missing:
                        parts.append(f"missing={missing}")
                    if extra:
                        parts.append(f"extra={extra}")
                    warnings.append("Gap in sequence: " + " ".join(parts))
            dupes = conn.execute(
                "SELECT sequence, COUNT(*) FROM invoices "
                "GROUP BY sequence HAVING COUNT(*) > 1"
            ).fetchall()
            for s, c in dupes:
                warnings.append(f"Duplicate sequence #{s:03d} used by {c} rows")
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


def _contact_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Decode a contact row, turning `project_categories` from its stored
    JSON string into a list[str] (the form/autocomplete code wants to
    work with the list, not the encoding)."""
    d = dict(row)
    try:
        d["project_categories"] = json.loads(d.get("project_categories") or "[]")
    except json.JSONDecodeError:
        d["project_categories"] = []
    return d


def _encode_categories(value: Any) -> str:
    """Normalise a category list/iterable into the JSON string we store.

    Silently drops non-string entries — the UI only ever sends checkbox
    keys, so anything else would be a programming error upstream, not
    something to surface to the user.
    """
    if not value:
        return "[]"
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return "[]"
    cats = [str(c) for c in value if isinstance(c, str) and c.strip()]
    return json.dumps(cats)


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
