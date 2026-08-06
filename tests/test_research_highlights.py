"""Guards for the highlighted-research section on the research_ui overview page.

The failure mode this holds shut: the shop window quietly becoming a hand-kept list
(which rots), or showcasing superseded/retracted nodes as if they were live leads.
"""
import os
import re
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (REPO, os.path.join(REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ctx  # noqa: E402
import tools.research_ui as ru  # noqa: E402


class HighlightedResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = ru.corpus()
        cls.html = ru.highlighted_research(cls.c)
        cls.card_ids = re.findall(r'href="/node/([A-Z]\d+)"', cls.html)

    def test_the_overview_page_carries_the_section(self):
        code, body, _ct = ru.route("/", {}, {})
        self.assertEqual(code, 200)
        self.assertIn("Highlighted research", body)
        self.assertIn("New leads", body)
        self.assertIn("Load-bearing", body)

    def test_every_highlighted_node_exists_and_is_current(self):
        self.assertTrue(self.card_ids)
        for nid in self.card_ids:
            self.assertIn(nid, self.c.nodes)
            self.assertEqual(ctx._node_meta(self.c.nodes[nid])["status"], "current",
                             "{} is not current — a stale shop window".format(nid))

    def test_the_most_cited_current_node_is_showcased(self):
        current = [n for n, node in self.c.nodes.items()
                   if ctx._node_meta(node)["status"] == "current"]
        top = max(current, key=lambda n: len(self.c.rev.get(n, [])))
        self.assertIn(top, self.card_ids)

    def test_the_newest_current_node_is_showcased(self):
        number = lambda nid: int(re.sub(r"\D", "", nid) or 0)
        current = [n for n, node in self.c.nodes.items()
                   if ctx._node_meta(node)["status"] == "current"]
        self.assertIn(max(current, key=number), self.card_ids)

    def test_selection_is_measured_not_hand_kept(self):
        """No literal node-id list feeds the section — grep its source for one."""
        import inspect
        src = inspect.getsource(ru.highlighted_research)
        self.assertFalse(re.search(r"['\"][FHED]\d+['\"]", src),
                         "highlighted_research hard-codes node ids")


if __name__ == "__main__":
    unittest.main()
