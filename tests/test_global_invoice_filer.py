"""Filer tests — primarily verifying filename format matches the legacy
WooCommerce monitor format so existing Boekhouding files stay consistent."""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "modules"))

from global_invoice.filer import (  # noqa: E402
    build_invoice_filename, clean_client_name, file_pdf, quarter_dir_for, quarter_for,
)


def test_quarter_for():
    assert quarter_for(1) == 1
    assert quarter_for(3) == 1
    assert quarter_for(4) == 2
    assert quarter_for(7) == 3
    assert quarter_for(12) == 4


def test_clean_client_name_strips_unsafe_chars():
    assert clean_client_name("Mike Morraye") == "MikeMorraye"
    assert clean_client_name("Some / Co. <test>") == "SomeCo.test"
    assert clean_client_name("Foo_Bar") == "FooBar"


def test_invoice_filename_matches_legacy_format():
    # Legacy from WooCommerceOrderMonitor: 3D_YYMMDD_Factuur{n:03d}_{Clean}.pdf
    assert (
        build_invoice_filename("3D", "2026-05-04", 5, "Mike Morraye")
        == "3D_260504_Factuur005_MikeMorraye.pdf"
    )
    assert (
        build_invoice_filename("FD", "2026-05-18", 12, "ACME Corp.")
        == "FD_260518_Factuur012_ACMECorp..pdf"
    )


def test_quarter_dir_for():
    base = Path("/tmp/Boekhouding")
    assert quarter_dir_for(base, "2026-02-15") == base / "2026" / "Q1" / "Uitgaand"
    assert quarter_dir_for(base, "2026-04-01") == base / "2026" / "Q2" / "Uitgaand"
    assert quarter_dir_for(base, "2026-12-31") == base / "2026" / "Q4" / "Uitgaand"


def test_file_pdf_moves_and_renames(tmp_path):
    src = tmp_path / "rendered.pdf"
    src.write_bytes(b"%PDF-1.4 fake")
    boek = tmp_path / "Boekhouding"
    out = file_pdf(src, boek, "FD", "2026-05-18", 7, "Test Customer", move=True)
    assert out.exists()
    assert not src.exists(), "source should have been moved, not copied"
    assert out.parent == boek / "2026" / "Q2" / "Uitgaand"
    assert out.name == "FD_260518_Factuur007_TestCustomer.pdf"


def test_file_pdf_refuses_overwrite(tmp_path):
    src = tmp_path / "rendered.pdf"
    src.write_bytes(b"fake")
    boek = tmp_path / "Boekhouding"
    file_pdf(src, boek, "FD", "2026-05-18", 1, "Test", move=True)
    # Second invocation with the same numbers should error
    src2 = tmp_path / "rendered2.pdf"
    src2.write_bytes(b"fake2")
    from global_invoice.filer import FilerError
    with pytest.raises(FilerError):
        file_pdf(src2, boek, "FD", "2026-05-18", 1, "Test", move=True)
