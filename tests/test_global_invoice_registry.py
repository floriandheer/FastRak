"""Tests for global_invoice.registry — focused on the atomic numbering
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

from global_invoice.models import LineItem  # noqa: E402
from global_invoice.registry import InvoiceRegistry  # noqa: E402


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


def test_first_invoice_of_year_is_one(registry):
    seq = registry.reserve_next_number(2026, _draft())
    assert seq == 1


def test_reserve_increments_within_year(registry):
    assert registry.reserve_next_number(2026, _draft()) == 1
    assert registry.reserve_next_number(2026, _draft()) == 2
    assert registry.reserve_next_number(2026, _draft()) == 3


def test_yearly_reset(registry):
    assert registry.reserve_next_number(2026, _draft(date_str="2026-12-31")) == 1
    assert registry.reserve_next_number(2026, _draft(date_str="2026-12-31")) == 2
    assert registry.reserve_next_number(2027, _draft(date_str="2027-01-02")) == 1
    assert registry.reserve_next_number(2027, _draft(date_str="2027-01-02")) == 2
    assert registry.reserve_next_number(2026, _draft(date_str="2026-12-31")) == 3


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


def test_list_invoices_filters(registry):
    registry.reserve_next_number(2026, _draft(company="FD"))
    registry.reserve_next_number(2026, _draft(company="HV"))
    registry.reserve_next_number(2026, _draft(company="3D"))
    fd_only = registry.list_invoices(company_key="FD")
    assert len(fd_only) == 1
    assert fd_only[0]["company_key"] == "FD"
