#!/usr/bin/env python3
"""web_merge_driver.py — a node-aware git merge driver for RESEARCH_WEB.md.

WHY NOT `merge=union`
    Union is the obvious choice for an append-mostly file and it is measurably
    wrong here. Two branches that each edit the SAME `### F2 — …` heading merge
    with exit 0 and produce a file containing two `### F2` lines. ctx's parser
    overwrites on duplicate ids, so one node silently wins and the other's
    metadata — including a `[SUPERSEDED by F9]` marker — disappears. Union
    manufactures exactly the duplicate-id corruption it is meant to prevent, and
    does it silently, which is worse than a conflict.

WHAT THIS DOES INSTEAD
    Splits all three inputs into a preamble plus node blocks keyed by id, then
    merges per node:

      * present on one side only        -> keep it (this is the append case, which
                                          is the overwhelming majority of research
                                          work and the reason union was tempting)
      * changed on one side only        -> take the changed side
      * changed on BOTH sides, same way -> take it once
      * changed on BOTH sides, differently -> CONFLICT, with markers

    The last case is the point. Two people editing one node's prose is a real
    disagreement about a research claim, and a merge driver must not resolve it by
    picking one. Everything else resolves cleanly without human attention.

    Ordering follows `theirs` (the branch being merged in) for blocks it knows,
    then appends any ours-only blocks, so a fast-forwarding deploy branch keeps
    its existing order.

INSTALL (per clone; git does not read driver definitions from a repo file):
    git config merge.researchweb.name "node-aware RESEARCH_WEB.md merge"
    git config merge.researchweb.driver "venv/bin/python tools/web_merge_driver.py %O %A %B"
  .gitattributes already routes RESEARCH_WEB.md to it. Without the config git
  falls back to the normal text merge, which is safe — just noisier.

Exit 0 = merged cleanly. Exit 1 = conflict markers written; git will say so.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HDR = re.compile(r"^### ([FHED]\d+)\b.*$", re.M)


def split_blocks(text: str) -> tuple[str, dict[str, str], list[str]]:
    """(preamble, {id: block_text}, id_order). A block runs to the next ### header."""
    marks = list(HDR.finditer(text))
    if not marks:
        return text, {}, []
    preamble = text[: marks[0].start()]
    blocks: dict[str, str] = {}
    order: list[str] = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        nid = m.group(1)
        # A duplicate id already in one input is a pre-existing corruption; keep the
        # first and let ctx web --lint report it rather than silently reconciling.
        if nid not in blocks:
            blocks[nid] = text[m.start():end]
            order.append(nid)
    return preamble, blocks, order


def merge_text(base: str, ours: str, theirs: str) -> tuple[str, bool]:
    pre_b, b, _ = split_blocks(base)
    pre_o, o, ord_o = split_blocks(ours)
    pre_t, t, ord_t = split_blocks(theirs)

    # Preamble: same three-way rule, at whole-text granularity.
    if pre_o == pre_t:
        preamble, pre_conflict = pre_o, False
    elif pre_o == pre_b:
        preamble, pre_conflict = pre_t, False
    elif pre_t == pre_b:
        preamble, pre_conflict = pre_o, False
    else:
        preamble = ("<<<<<<< ours\n" + pre_o + "=======\n" + pre_t + ">>>>>>> theirs\n")
        pre_conflict = True

    conflict = pre_conflict
    out: list[str] = []
    emitted: set[str] = set()

    def resolve(nid: str) -> str | None:
        nonlocal conflict
        ob, tb, bb = o.get(nid), t.get(nid), b.get(nid)
        if ob is not None and tb is None:
            return None if (bb is not None and ob == bb) else ob   # deleted by them
        if tb is not None and ob is None:
            return None if (bb is not None and tb == bb) else tb   # deleted by us
        if ob == tb:
            return ob
        if ob == bb:
            return tb
        if tb == bb:
            return ob
        conflict = True
        return ("<<<<<<< ours\n" + ob + "=======\n" + tb + ">>>>>>> theirs\n")

    for nid in ord_t + [n for n in ord_o if n not in t]:
        if nid in emitted:
            continue
        emitted.add(nid)
        blk = resolve(nid)
        if blk is not None:
            out.append(blk)

    return preamble + "".join(out), conflict


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 3:
        print("usage: web_merge_driver.py %O %A %B", file=sys.stderr)
        return 2
    o_path, a_path, b_path = Path(argv[0]), Path(argv[1]), Path(argv[2])
    try:
        base = o_path.read_text() if o_path.exists() else ""
        ours = a_path.read_text()
        theirs = b_path.read_text()
    except OSError as exc:
        print(f"web_merge_driver: {exc}", file=sys.stderr)
        return 2
    merged, conflict = merge_text(base, ours, theirs)
    a_path.write_text(merged)          # git takes the result from %A
    return 1 if conflict else 0


if __name__ == "__main__":
    sys.exit(main())
