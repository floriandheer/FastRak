"""LibreOffice (.ott / .odt) template renderer.

Approach: open the template as a zip, edit content.xml in place, write a
new .odt zip. No python-uno or external libs required. Substitution
walks every text-bearing node (text:p, text:span, text:h) and updates
both .text and .tail — LibreOffice splits runs unpredictably, so a naive
//text() approach corrupts the document.

Placeholders:
  Scalar:  {{key}}     anywhere in the document
  Row repeat: a table row containing the literal marker {{line_item_row}}
              is cloned once per line item, then the marker is stripped.
"""

from __future__ import annotations

import io
import re
import shutil
import zipfile
from pathlib import Path
from typing import Dict, List, Optional
from xml.etree import ElementTree as ET

from shared_logging import get_logger

logger = get_logger(__name__)


# ODF namespaces. ElementTree uses {url}tag syntax for namespaced elements.
NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "table":  "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text":   "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
}
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)
# Common extra prefixes ODF files declare — register so they round-trip.
for prefix, uri in {
    "style":  "urn:oasis:names:tc:opendocument:xmlns:style:1.0",
    "fo":     "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0",
    "draw":   "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0",
    "svg":    "urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0",
    "xlink":  "http://www.w3.org/1999/xlink",
    "meta":   "urn:oasis:names:tc:opendocument:xmlns:meta:1.0",
    "number": "urn:oasis:names:tc:opendocument:xmlns:datastyle:1.0",
    "form":   "urn:oasis:names:tc:opendocument:xmlns:form:1.0",
    "script": "urn:oasis:names:tc:opendocument:xmlns:script:1.0",
    "config": "urn:oasis:names:tc:opendocument:xmlns:config:1.0",
    "manifest": "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0",
}.items():
    ET.register_namespace(prefix, uri)


TABLE_ROW_TAG = f"{{{NS['table']}}}table-row"
ROW_MARKER          = "{{line_item_row}}"
EXPENSE_ROW_MARKER  = "{{expense_item_row}}"
EXPENSE_SEC_MARKER  = "{{expense_section_row}}"
PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


class TemplateError(Exception):
    pass


def render_odt(
    template_path: Path,
    output_path: Path,
    context: Dict[str, str],
    line_items: List[Dict[str, str]],
    expense_items: Optional[List[Dict[str, str]]] = None,
) -> Path:
    """Render `template_path` to `output_path` with the given context.

    Args:
        template_path: A .ott or .odt file containing placeholders.
        output_path: Destination .odt file (parent dir must exist).
        context: Scalar {{key}} replacements. Values are stringified.
        line_items: Per-row dicts for rows tagged {{line_item_row}}.
        expense_items: Per-row dicts for rows tagged {{expense_item_row}}.
            Rows tagged {{expense_section_row}} are kept (once) when this
            list is non-empty, removed when it is empty or None.

    Returns:
        output_path on success.

    Raises:
        TemplateError on a malformed template or substitution failure.
    """
    template_path = Path(template_path)
    output_path = Path(output_path)
    if not template_path.exists():
        raise TemplateError(f"Template not found: {template_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(template_path, "r") as zin:
        members = zin.namelist()
        if "content.xml" not in members:
            raise TemplateError(
                f"Template {template_path} has no content.xml — not a valid ODF file"
            )
        content_xml = zin.read("content.xml")

    # Parse, transform, serialise
    try:
        tree = ET.ElementTree(ET.fromstring(content_xml))
    except ET.ParseError as e:
        raise TemplateError(f"content.xml is not valid XML: {e}") from e

    root = tree.getroot()
    _expand_row_groups(root, line_items, expense_items or [])
    _substitute_scalars(root, {k: str(v) for k, v in context.items()})
    new_content = ET.tostring(root, xml_declaration=True, encoding="UTF-8")

    # Repack the zip — zipfile can't update members in place, so we copy
    # everything else byte-for-byte and substitute content.xml.
    with zipfile.ZipFile(template_path, "r") as zin:
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename == "content.xml":
                    zout.writestr(item, new_content)
                else:
                    zout.writestr(item, zin.read(item.filename))

    logger.info(f"Rendered ODT: {output_path.name} from {template_path.name}")
    return output_path


# ---------- internals ----------

def _expand_row_groups(
    root: ET.Element,
    work_items: List[Dict[str, str]],
    expense_items: List[Dict[str, str]],
) -> None:
    """Process all special row markers in document order.

    - {{line_item_row}}      → cloned once per work item, marker stripped
    - {{expense_item_row}}   → cloned once per expense item, marker stripped
    - {{expense_section_row}}→ kept once (marker stripped) if expense_items
                               is non-empty; entire row removed if empty
    """
    work_rows: List[ET.Element] = []
    expense_rows: List[ET.Element] = []
    section_rows: List[ET.Element] = []

    for row in root.iter(TABLE_ROW_TAG):
        if _row_contains_text(row, ROW_MARKER):
            work_rows.append(row)
        elif _row_contains_text(row, EXPENSE_ROW_MARKER):
            expense_rows.append(row)
        elif _row_contains_text(row, EXPENSE_SEC_MARKER):
            section_rows.append(row)

    if not work_rows and work_items:
        logger.warning(
            f"Template has no {{line_item_row}} marker but {len(work_items)} "
            f"work items provided — they will be omitted from the PDF"
        )

    for marker_row in work_rows:
        _expand_repeating_row(root, marker_row, work_items, ROW_MARKER)

    for marker_row in expense_rows:
        _expand_repeating_row(root, marker_row, expense_items, EXPENSE_ROW_MARKER)

    for sec_row in section_rows:
        _handle_section_row(root, sec_row, bool(expense_items), EXPENSE_SEC_MARKER)


def _expand_repeating_row(
    root: ET.Element,
    marker_row: ET.Element,
    items: List[Dict[str, str]],
    marker_text: str,
) -> None:
    parent = _find_parent(root, marker_row)
    if parent is None:
        logger.warning("Marker row has no parent — skipping")
        return
    idx = list(parent).index(marker_row)
    clones: List[ET.Element] = []
    for item in items:
        cloned = _deep_clone(marker_row)
        _strip_text(cloned, marker_text)
        _substitute_scalars(cloned, {k: str(v) for k, v in item.items()})
        clones.append(cloned)
    parent.remove(marker_row)
    for offset, c in enumerate(clones):
        parent.insert(idx + offset, c)


def _handle_section_row(
    root: ET.Element,
    sec_row: ET.Element,
    keep: bool,
    marker_text: str,
) -> None:
    if keep:
        _strip_text(sec_row, marker_text)
    else:
        parent = _find_parent(root, sec_row)
        if parent is not None:
            parent.remove(sec_row)


# Keep old name as alias so external callers aren't broken.
def _expand_line_item_rows(root: ET.Element, items: List[Dict[str, str]]) -> None:
    _expand_row_groups(root, items, [])


def _row_contains_text(row: ET.Element, text: str) -> bool:
    for el in row.iter():
        if el.text and text in el.text:
            return True
        if el.tail and text in el.tail:
            return True
    return False


# Keep old names as aliases for external callers.
def _row_contains_marker(row: ET.Element) -> bool:
    return _row_contains_text(row, ROW_MARKER)


def _strip_marker(row: ET.Element) -> None:
    _strip_text(row, ROW_MARKER)


def _strip_text(el: ET.Element, text: str) -> None:
    for node in el.iter():
        if node.text and text in node.text:
            node.text = node.text.replace(text, "")
        if node.tail and text in node.tail:
            node.tail = node.tail.replace(text, "")


def _deep_clone(el: ET.Element) -> ET.Element:
    # ElementTree doesn't expose a clone API; round-trip via tostring/fromstring
    # is reliable and preserves attribute ordering / xmlns.
    return ET.fromstring(ET.tostring(el))


def _find_parent(root: ET.Element, target: ET.Element):
    for parent in root.iter():
        for child in list(parent):
            if child is target:
                return parent
    return None


def _substitute_scalars(root: ET.Element, ctx: Dict[str, str]) -> None:
    """Replace every {{key}} occurrence in .text and .tail of every node.

    LibreOffice splits text runs unpredictably (italic/bold/spell-checked
    fragments become separate text:span children), so a placeholder like
    {{customer_name}} might be split across multiple spans. We can't fully
    reconstruct that here, but we can substitute within each contiguous
    text fragment. Templates should keep placeholders as one un-formatted
    span (see README).
    """
    def repl(match: re.Match) -> str:
        key = match.group(1)
        if key in ctx:
            return ctx[key]
        # Unknown placeholder — leave intact so it's visible in the PDF
        # (and the user notices the typo).
        return match.group(0)

    for el in root.iter():
        if el.text and "{{" in el.text:
            el.text = PLACEHOLDER_RE.sub(repl, el.text)
        if el.tail and "{{" in el.tail:
            el.tail = PLACEHOLDER_RE.sub(repl, el.tail)
