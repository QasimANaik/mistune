from unittest import TestCase

import mistune


class TestAutoseIssue1E2E(TestCase):
    def test_e2e_table_ac_missing_and_extra_cells(self):
        # AC-FR-001-1: Given Markdown text with fewer cells than header, padded with empty cell
        text_missing = "| Name | Role |\n|---|---|\n| Ana |"
        md = mistune.create_markdown(plugins=["table"])
        expected_missing = (
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
        self.assertEqual(md(text_missing), expected_missing)

        # AC-FR-002-1: Given Markdown text with more cells than header, truncated to header length
        text_extra = "| Name | Role |\n|---|---|\n| Ana | Dev | extra |"
        expected_extra = (
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
        self.assertEqual(md(text_extra), expected_extra)

        # AC-FR-003-1: Given Markdown text with exact matching cells
        text_match = "| Name | Role |\n|---|---|\n| Ana | Dev |"
        self.assertEqual(md(text_match), expected_extra)

    def test_e2e_table_ac_invalid_delimiter(self):
        # AC-FR-004-1: Given Markdown text with invalid delimiter count, falls back to paragraph
        text = "| Name | Role |\n|---|"
        md = mistune.create_markdown(plugins=["table"])
        expected = "<p>| Name | Role |\n|---|</p>\n"
        self.assertEqual(md(text), expected)

    def test_e2e_table_combined_plugins_and_options(self):
        # Combining table plugin, speedup plugin, and escape=False with cell formatting
        text = "| Item | Price |\n| :--- | ---: |\n| **Apple** | $1.50 |"
        md = mistune.create_markdown(escape=False, plugins=["table", "speedup"])
        expected = (
            "<table>\n"
            "<thead>\n"
            "<tr>\n"
            "  <th style=\"text-align:left\">Item</th>\n"
            "  <th style=\"text-align:right\">Price</th>\n"
            "</tr>\n"
            "</thead>\n"
            "<tbody>\n"
            "<tr>\n"
            "  <td style=\"text-align:left\"><strong>Apple</strong></td>\n"
            "  <td style=\"text-align:right\">$1.50</td>\n"
            "</tr>\n"
            "</tbody>\n"
            "</table>\n"
        )
        self.assertEqual(md(text), expected)

    def test_e2e_regression_standard_table_with_formatting(self):
        # Regression test 1: Standard table with explicit alignments and inline formatting
        text = (
            "| Left | Center | Right |\n"
            "| :--- | :---: | ---: |\n"
            "| *a* | b | c |\n"
            "| d | e | f |\n"
        )
        md = mistune.create_markdown(plugins=["table"])
        expected = (
            "<table>\n"
            "<thead>\n"
            "<tr>\n"
            "  <th style=\"text-align:left\">Left</th>\n"
            "  <th style=\"text-align:center\">Center</th>\n"
            "  <th style=\"text-align:right\">Right</th>\n"
            "</tr>\n"
            "</thead>\n"
            "<tbody>\n"
            "<tr>\n"
            "  <td style=\"text-align:left\"><em>a</em></td>\n"
            "  <td style=\"text-align:center\">b</td>\n"
            "  <td style=\"text-align:right\">c</td>\n"
            "</tr>\n"
            "<tr>\n"
            "  <td style=\"text-align:left\">d</td>\n"
            "  <td style=\"text-align:center\">e</td>\n"
            "  <td style=\"text-align:right\">f</td>\n"
            "</tr>\n"
            "</tbody>\n"
            "</table>\n"
        )
        self.assertEqual(md(text), expected)

    def test_e2e_regression_table_missing_cells_multiline(self):
        # Regression test 2: Table with 3 columns where data row has fewer cells
        text = (
            "A | B | C\n"
            "- | - | -\n"
            "a | b\n"
        )
        md = mistune.create_markdown(plugins=["table"])
        expected = (
            "<table>\n"
            "<thead>\n"
            "<tr>\n"
            "  <th>A</th>\n"
            "  <th>B</th>\n"
            "  <th>C</th>\n"
            "</tr>\n"
            "</thead>\n"
            "<tbody>\n"
            "<tr>\n"
            "  <td>a</td>\n"
            "  <td>b</td>\n"
            "  <td></td>\n"
            "</tr>\n"
            "</tbody>\n"
            "</table>\n"
        )
        self.assertEqual(md(text), expected)
