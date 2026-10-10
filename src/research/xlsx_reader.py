"""
MONAD Quant — read one sheet of an .xlsx workbook with the standard library only.

An .xlsx file is a zip of XML parts: the workbook lists sheets by name and relationship
id, the relationships map ids to sheet parts, and cells hold either numbers or indexes
into a shared-string table. This reader returns a sheet as {row number: {column letters:
value}}, enough for a validation cross-check against a published table (the World Bank
"Pink Sheet", docs/research/MINER_TILT_PREPERIOD.md) without adding a dependency.
"""
from __future__ import annotations

import io
import re
import zipfile
import xml.etree.ElementTree as ET

_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_REF = re.compile(r"([A-Z]+)(\d+)")


class WorkbookError(ValueError):
    """The workbook does not have the expected structure."""


def _shared_strings(z: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    return ["".join(t.text or "" for t in si.iter(f"{_MAIN}t")) for si in root.iter(f"{_MAIN}si")]


def _sheet_part(z: zipfile.ZipFile, name: str) -> str:
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rid = next((s.get(f"{_REL}id") for s in wb.iter(f"{_MAIN}sheet") if s.get("name") == name), None)
    if rid is None:
        names = [s.get("name") for s in wb.iter(f"{_MAIN}sheet")]
        raise WorkbookError(f"no sheet {name!r} (sheets: {names})")
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    target = next((r.get("Target") for r in rels.iter(f"{_PKG}Relationship") if r.get("Id") == rid), None)
    if target is None:
        raise WorkbookError(f"sheet {name!r} has no part")
    target = target.lstrip("/")
    return target if target.startswith("xl/") else f"xl/{target}"


def read_sheet(data: bytes, name: str) -> dict[int, dict[str, object]]:
    """{row: {column: value}}: numbers as float, text as str, empty cells left out."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        strings = _shared_strings(z)
        root = ET.fromstring(z.read(_sheet_part(z, name)))
    rows: dict[int, dict[str, object]] = {}
    for c in root.iter(f"{_MAIN}c"):
        m = _REF.fullmatch(c.get("r") or "")
        if not m:
            continue
        col, row = m.group(1), int(m.group(2))
        kind = c.get("t")
        if kind == "inlineStr":
            value = "".join(t.text or "" for t in c.iter(f"{_MAIN}t"))
        else:
            v = c.find(f"{_MAIN}v")
            if v is None or v.text is None:
                continue
            if kind == "s":
                value = strings[int(v.text)]
            elif kind in ("str", "e", "b"):
                value = v.text
            else:
                try:
                    value = float(v.text)
                except ValueError:
                    value = v.text
        rows.setdefault(row, {})[col] = value
    return rows
