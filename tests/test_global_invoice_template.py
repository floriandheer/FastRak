"""Template engine tests — uses a minimal hand-crafted .ott to verify
placeholder substitution and line-item row cloning without depending on
the real company templates."""

import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "modules"))

from invoice_manager.core.template_engine import (  # noqa: E402
    NS, TABLE_ROW_TAG, render_odt,
)


MIN_MIMETYPE = "application/vnd.oasis.opendocument.text-template"
MANIFEST_XML = """<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0">
  <manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.text-template"/>
  <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
</manifest:manifest>
"""


def _build_minimal_ott(path: Path, content_xml: str):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", MIN_MIMETYPE)
        z.writestr("META-INF/manifest.xml", MANIFEST_XML)
        z.writestr("content.xml", content_xml)


CONTENT_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
    xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
    xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
    xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0">
  <office:body>
    <office:text>
      <text:p>Invoice <text:span>{{invoice_number}}</text:span> for <text:span>{{customer_name}}</text:span></text:p>
      <table:table>
        <table:table-row>
          <table:table-cell><text:p>{{line_item_row}}{{desc}}</text:p></table:table-cell>
          <table:table-cell><text:p>{{qty}}</text:p></table:table-cell>
          <table:table-cell><text:p>{{line_total}}</text:p></table:table-cell>
        </table:table-row>
      </table:table>
      <text:p>Total: <text:span>{{total}}</text:span></text:p>
    </office:text>
  </office:body>
</office:document-content>
"""


def _read_content_xml(odt_path: Path) -> str:
    with zipfile.ZipFile(odt_path, "r") as z:
        return z.read("content.xml").decode("utf-8")


def test_scalar_substitution(tmp_path):
    template = tmp_path / "tpl.ott"
    output = tmp_path / "out.odt"
    _build_minimal_ott(template, CONTENT_TEMPLATE)
    render_odt(
        template, output,
        context={
            "invoice_number": "007",
            "customer_name": "ACME Ltd",
            "total": "€ 121,00",
        },
        line_items=[
            {"desc": "Widget", "qty": "2", "line_total": "20,00"},
        ],
    )
    xml = _read_content_xml(output)
    assert "{{invoice_number}}" not in xml
    assert "{{customer_name}}" not in xml
    assert "{{total}}" not in xml
    assert "007" in xml
    assert "ACME Ltd" in xml
    assert "€ 121,00" in xml


def test_row_cloning_creates_one_row_per_item(tmp_path):
    template = tmp_path / "tpl.ott"
    output = tmp_path / "out.odt"
    _build_minimal_ott(template, CONTENT_TEMPLATE)
    items = [
        {"desc": "Widget", "qty": "1", "line_total": "10,00"},
        {"desc": "Gadget", "qty": "3", "line_total": "30,00"},
        {"desc": "Sprocket", "qty": "2", "line_total": "20,00"},
    ]
    render_odt(template, output, context={"invoice_number": "1",
               "customer_name": "X", "total": "60,00"}, line_items=items)
    xml = _read_content_xml(output)
    root = ET.fromstring(xml)
    rows = list(root.iter(TABLE_ROW_TAG))
    assert len(rows) == len(items), (
        f"Expected one row per item, got {len(rows)} for {len(items)} items"
    )
    assert "{{line_item_row}}" not in xml
    assert "{{desc}}" not in xml
    for item in items:
        assert item["desc"] in xml


def test_unknown_placeholder_left_intact(tmp_path):
    template = tmp_path / "tpl.ott"
    output = tmp_path / "out.odt"
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"'
        ' xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
        '<office:body><office:text>'
        '<text:p>Hello {{unknown_field}} world</text:p>'
        '</office:text></office:body></office:document-content>'
    )
    _build_minimal_ott(template, content)
    render_odt(template, output, context={}, line_items=[])
    xml = _read_content_xml(output)
    # The placeholder should pass through so the user notices the typo
    assert "{{unknown_field}}" in xml
