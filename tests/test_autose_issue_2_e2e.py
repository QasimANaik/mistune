from time import perf_counter
from unittest import TestCase

import mistune


class TestAutoseIssue2E2E(TestCase):
    def test_url_plugin_acceptance_criteria_parentheses_and_punctuation(self):
        # AC-FR-001-1, AC-FR-002-1, AC-FR-002-2, AC-FR-003-1, AC-FR-003-2
        md = mistune.create_markdown(escape=False, plugins=["url"])

        # AC-FR-001-1
        text1 = "see https://en.wikipedia.org/wiki/Python_(programming_language) for details"
        res1 = md(text1)
        self.assertIn(
            '<a href="https://en.wikipedia.org/wiki/Python_(programming_language)">https://en.wikipedia.org/wiki/Python_(programming_language)</a>',
            res1,
        )

        # AC-FR-002-1
        text2 = "did you try https://example.com/docs?"
        res2 = md(text2)
        self.assertIn(
            '<a href="https://example.com/docs">https://example.com/docs</a>?',
            res2,
        )

        # AC-FR-002-2
        text3 = "check https://example.com/path! for info"
        res3 = md(text3)
        self.assertIn(
            '<a href="https://example.com/path">https://example.com/path</a>!',
            res3,
        )

        # AC-FR-003-1
        text4 = "visit https://example.com."
        res4 = md(text4)
        self.assertIn(
            '<a href="https://example.com">https://example.com</a>.',
            res4,
        )

        # AC-FR-003-2
        text5 = "see https://example.com, and more"
        res5 = md(text5)
        self.assertIn(
            '<a href="https://example.com">https://example.com</a>, and more',
            res5,
        )

    def test_url_plugin_combined_with_other_plugins_and_brackets(self):
        # AC-FR-004-1 and combined plugins (url, strikethrough, speedup)
        md = mistune.create_markdown(escape=False, plugins=["url", "strikethrough", "speedup"])

        text = "[link https://example.com] and ~~strikethrough text~~ with https://example.com/test?a=1"
        res = md(text)
        self.assertIn('<del>strikethrough text</del>', res)
        self.assertIn('<a href="https://example.com/test?a=1">https://example.com/test?a=1</a>', res)

    def test_url_plugin_performance_scaling_nfr(self):
        # AC-NFR-001-1: O(n) relative to text length
        md = mistune.create_markdown(escape=False, plugins=["url", "speedup"])

        base_str = "Check https://example.com/path/to/resource?query=1&b=2 for details. "
        text_small = base_str * 100
        text_large = base_str * 1000

        t0 = perf_counter()
        res_small = md(text_small)
        t1 = perf_counter()
        duration_small = t1 - t0

        t0 = perf_counter()
        res_large = md(text_large)
        t1 = perf_counter()
        duration_large = t1 - t0

        # Verify output integrity and reasonable linear/sub-quadratic scaling
        self.assertIn('<a href="https://example.com', res_small)
        self.assertIn('<a href="https://example.com', res_large)
        self.assertLess(duration_large, duration_small * 50 + 0.5)

    def test_regression_explicit_links_and_autolinks(self):
        # Regression test 1: explicit markdown links and angle-bracket autolinks work correctly whether url plugin is present or not
        md_default = mistune.create_markdown(escape=False)
        md_url = mistune.create_markdown(escape=False, plugins=["url"])

        text = "Visit [Mistune](https://github.com/lepture/mistune) or <https://python.org>."
        res_default = md_default(text)
        res_url = md_url(text)

        self.assertIn('<a href="https://github.com/lepture/mistune">Mistune</a>', res_default)
        self.assertIn('<a href="https://python.org">https://python.org</a>', res_default)
        self.assertIn('<a href="https://github.com/lepture/mistune">Mistune</a>', res_url)
        self.assertIn('<a href="https://python.org">https://python.org</a>', res_url)

    def test_regression_urls_in_block_elements_and_plugin_toggle(self):
        # Regression test 2: URLs in block elements (lists, blockquotes) and behavior when url plugin is omitted vs included
        text = "- Check https://python.org/\n> Info at https://example.com."

        md_no_plugin = mistune.create_markdown(escape=False)
        res_no_plugin = md_no_plugin(text)
        self.assertNotIn('<a href="https://python.org/">', res_no_plugin)
        self.assertNotIn('<a href="https://example.com">', res_no_plugin)

        md_with_plugin = mistune.create_markdown(escape=False, plugins=["url"])
        res_with_plugin = md_with_plugin(text)
        self.assertIn('<li>Check <a href="https://python.org/">https://python.org/</a></li>', res_with_plugin)
        self.assertIn('<blockquote>\n<p>Info at <a href="https://example.com">https://example.com</a>.</p>\n</blockquote>', res_with_plugin)
