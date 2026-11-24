from unittest import TestCase

import mistune
from tests.perf_utils import assert_near_linear


class TestAutoseIssue1Fr001(TestCase):
    def test_ac_fr_001_1_missing_cell(self):
        """AC-FR-001-1: Table row with fewer cells than header gets padded with empty cells."""
        text = "| Name | Role |\n|---|---|\n| Ana |"
        md = mistune.create_markdown(plugins=["table"])
        expected = (
            "<table>\n"
            "<thead>\n"
            "<tr>\n"
            "  <th>Name</th>\n"
            "  <th>Role</th>\n"
            "</tr>\n"
            "</thead>\n"
            "<tbody>\n"
            "<tr>\n"
            "  <td>Ana</td>\n"
            "  <td></td>\n"
            "</tr>\n"
            "</tbody>\n"
            "</table>\n"
        )
        self.assertEqual(md(text), expected)

    def test_ac_fr_002_1_extra_cell(self):
        """AC-FR-002-1: Table row with more cells than header gets truncated to header length."""
        text = "| Name | Role |\n|---|---|\n| Ana | Dev | extra |"
        md = mistune.create_markdown(plugins=["table"])
        expected = (
            "<table>\n"
            "<thead>\n"
            "<tr>\n"
            "  <th>Name</th>\n"
            "  <th>Role</th>\n"
            "</tr>\n"
            "</thead>\n"
            "<tbody>\n"
            "<tr>\n"
            "  <td>Ana</td>\n"
            "  <td>Dev</td>\n"
            "</tr>\n"
            "</tbody>\n"
            "</table>\n"
        )
        self.assertEqual(md(text), expected)

    def test_ac_nfr_001_1_table_benchmark_performance(self):
        """AC-NFR-001-1: Table parsing time shows no measurable regression / scales near-linear on benchmark inputs."""
        md = mistune.create_markdown(plugins=["table"])

        def render(size):
            rows = "\n".join([f"| Col1 {i} | Col2 {i} |" for i in range(size)])
            text = "| Header 1 | Header 2 |\n| --- | --- |\n" + rows + "\n"
            return md(text)

        _small, html = assert_near_linear(self, render, 500, 1000, warmup_size=100)
        self.assertIn("Col1 999", html)
