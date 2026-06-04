"""Tests for invoice_manager.core.registry — focused on the atomic numbering
contract and the gapless / void-preserving invariants."""

import os
import sqlite3
import sys
import tempfile
import threading
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "modules"))

from invoice_manager.core.models import LineItem  # noqa: E402
from invoice_manager.core.registry import InvoiceRegistry  # noqa: E402


@pytest.fixture
def tmp_db(tmp_path):
    return tmp_path / "invoices.sqlite"


@pytest.fixture
def registry(tmp_db):
    return InvoiceRegistry(tmp_db)


def _draft(company="FD", date_str="2026-05-18", customer="Test Customer"):
    return {
        "company_key": company,
        "invoice_date": date_str,
        "customer_name": customer,
        "line_items": [LineItem("Test item", 1, 10000, 21.0)],
        "source": "manual",
        "source_ref": None,
    }


def test_first_invoice_is_one(registry):
    seq = registry.reserve_next_number(2026, _draft())
    assert seq == 1


def test_reserve_increments(registry):
    assert registry.reserve_next_number(2026, _draft()) == 1
    assert registry.reserve_next_number(2026, _draft()) == 2
    assert registry.reserve_next_number(2026, _draft()) == 3


def test_sequence_does_not_reset_across_years(registry):
    """Sequence is globally continuous — year boundaries don't reset it."""
    assert registry.reserve_next_number(2026, _draft(date_str="2026-12-31")) == 1
    assert registry.reserve_next_number(2026, _draft(date_str="2026-12-31")) == 2
    assert registry.reserve_next_number(2027, _draft(date_str="2027-01-02")) == 3
    assert registry.reserve_next_number(2027, _draft(date_str="2027-01-02")) == 4
    assert registry.reserve_next_number(2026, _draft(date_str="2026-12-31")) == 5


def test_void_preserves_number(registry):
    seq1 = registry.reserve_next_number(2026, _draft())
    seq2 = registry.reserve_next_number(2026, _draft())
    inv = registry.get_invoice(2026, seq1)
    registry.void_invoice(inv["id"], "test cancellation")
    voided = registry.get_invoice(2026, seq1)
    assert voided["status"] == "voided"
    assert voided["void_reason"] == "test cancellation"
    # Next reservation continues from max, ignoring void
    seq3 = registry.reserve_next_number(2026, _draft())
    assert seq3 == 3
    assert seq2 == 2


def test_void_requires_reason(registry):
    seq = registry.reserve_next_number(2026, _draft())
    inv = registry.get_invoice(2026, seq)
    with pytest.raises(ValueError):
        registry.void_invoice(inv["id"], "")


def test_unique_year_sequence_enforced_at_schema_level(registry, tmp_db):
    registry.reserve_next_number(2026, _draft())
    conn = sqlite3.connect(str(tmp_db))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO invoices "
                "(year, sequence, company_key, invoice_date, customer_name,"
                " line_items_json, subtotal_cents, vat_cents, total_cents,"
                " source, created_at, updated_at) "
                "VALUES (2026, 1, 'FD', '2026-05-18', 'X', '[]', 0, 0, 0, "
                "'manual', '2026-05-18T00:00:00', '2026-05-18T00:00:00')"
            )
    finally:
        conn.close()


def test_concurrent_reservation_is_atomic(tmp_db):
    """20 threads each reserve a number; result must be exactly {1..20}."""
    registry = InvoiceRegistry(tmp_db)
    n = 20
    results: list[int] = []
    results_lock = threading.Lock()
    errors: list[Exception] = []

    def worker():
        try:
            seq = registry.reserve_next_number(2026, _draft())
            with results_lock:
                results.append(seq)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert errors == [], f"Errors during concurrent reservation: {errors}"
    assert sorted(results) == list(range(1, n + 1)), (
        f"Expected exactly {{1..{n}}}, got {sorted(results)}"
    )


def test_get_by_source_ref(registry):
    draft = _draft()
    draft["source"] = "woocommerce"
    draft["source_ref"] = "1234"
    seq = registry.reserve_next_number(2026, draft)
    found = registry.get_by_source_ref("woocommerce", "1234")
    assert found is not None
    assert found["sequence"] == seq
    assert registry.get_by_source_ref("woocommerce", "9999") is None


def test_finalize_invoice(registry):
    seq = registry.reserve_next_number(2026, _draft())
    inv = registry.get_invoice(2026, seq)
    registry.finalize_invoice(inv["id"], "/tmp/some.pdf")
    issued = registry.get_invoice(2026, seq)
    assert issued["status"] == "issued"
    assert issued["pdf_path"] == "/tmp/some.pdf"


def test_health_check_passes_when_gapless(registry):
    for _ in range(5):
        registry.reserve_next_number(2026, _draft())
    assert registry.health_check() == []


def test_health_check_passes_across_year_boundary(registry):
    """A continuous run that crosses Jan 1 must not be flagged as a gap."""
    registry.reserve_next_number(2026, _draft(date_str="2026-12-30"))
    registry.reserve_next_number(2026, _draft(date_str="2026-12-31"))
    registry.reserve_next_number(2027, _draft(date_str="2027-01-02"))
    registry.reserve_next_number(2027, _draft(date_str="2027-01-03"))
    assert registry.health_check() == []


def test_health_check_flags_real_gap(registry):
    """A missing number anywhere in the global sequence should warn."""
    registry.import_existing_invoice(2026, 1, _draft())
    registry.import_existing_invoice(2026, 2, _draft())
    # Skip 3 — leave a real gap.
    registry.import_existing_invoice(2027, 4, _draft(date_str="2027-01-05"))
    warnings = registry.health_check()
    assert any("missing=[3]" in w for w in warnings), warnings


def test_list_invoices_filters(registry):
    registry.reserve_next_number(2026, _draft(company="FD"))
    registry.reserve_next_number(2026, _draft(company="HV"))
    registry.reserve_next_number(2026, _draft(company="3D"))
    fd_only = registry.list_invoices(company_key="FD")
    assert len(fd_only) == 1
    assert fd_only[0]["company_key"] == "FD"


def test_contacts_crud_roundtrip(registry):
    new_id = registry.create_contact({
        "display_name": "ACME Corp",
        "abbreviation": "ACME",
        "vat": "BE0123456789",
        "email": "hello@acme.example",
        "address": "Acme Street 1\n1000 Brussels",
    })
    assert new_id > 0

    fetched = registry.get_contact(new_id)
    assert fetched["display_name"] == "ACME Corp"
    assert fetched["abbreviation"] == "ACME"
    assert fetched["vat"] == "BE0123456789"

    by_abbr = registry.get_contact_by_abbreviation("ACME")
    assert by_abbr is not None and by_abbr["id"] == new_id

    registry.update_contact(new_id, {"email": "billing@acme.example"})
    assert registry.get_contact(new_id)["email"] == "billing@acme.example"
    # Other fields untouched
    assert registry.get_contact(new_id)["vat"] == "BE0123456789"

    listed = registry.list_contacts()
    assert any(c["id"] == new_id for c in listed)

    registry.delete_contact(new_id)
    assert registry.get_contact(new_id) is None


def test_contacts_allow_blank_name(registry):
    """Bulk-imported contacts start with no display_name; the user fills
    it in from the form later. The registry accepts the blank state.
    """
    cid = registry.create_contact({
        "display_name": "",
        "abbreviation": "MikeMorraye",
        "project_client_name": "MikeMorraye",
    })
    row = registry.get_contact(cid)
    assert row["display_name"] == ""
    assert row["abbreviation"] == "MikeMorraye"


def test_contacts_abbreviation_unique(registry):
    registry.create_contact({"display_name": "First", "abbreviation": "DUP"})
    with pytest.raises(sqlite3.IntegrityError):
        registry.create_contact({"display_name": "Second", "abbreviation": "DUP"})


def test_contacts_abbreviation_blank_becomes_null(registry):
    """Two contacts with no abbreviation must not collide on the unique index."""
    registry.create_contact({"display_name": "A", "abbreviation": ""})
    registry.create_contact({"display_name": "B", "abbreviation": "   "})
    # Both succeed; both normalise to NULL.
    rows = registry.list_contacts()
    assert all(r["abbreviation"] is None for r in rows)

    # Updating an existing abbreviation to blank also nulls it (and frees
    # the index slot for someone else to take that string later).
    cid = registry.create_contact({"display_name": "C", "abbreviation": "TEMP"})
    registry.update_contact(cid, {"abbreviation": "  "})
    assert registry.get_contact(cid)["abbreviation"] is None
    registry.create_contact({"display_name": "D", "abbreviation": "TEMP"})  # OK


def test_contacts_project_link_roundtrip(registry):
    cid = registry.create_contact({
        "display_name": "Mike Morraye",
        "project_client_name": "MikeMorraye",
    })
    by_proj = registry.get_contact_by_project_client("MikeMorraye")
    assert by_proj is not None and by_proj["id"] == cid
    # Re-link to a different project client
    registry.update_contact(cid, {"project_client_name": "MorrayeMike"})
    assert registry.get_contact_by_project_client("MikeMorraye") is None
    assert registry.get_contact_by_project_client("MorrayeMike")["id"] == cid


def test_contacts_project_link_unique(registry):
    registry.create_contact({
        "display_name": "A", "project_client_name": "ProjectFoo",
    })
    with pytest.raises(sqlite3.IntegrityError):
        registry.create_contact({
            "display_name": "B", "project_client_name": "ProjectFoo",
        })
