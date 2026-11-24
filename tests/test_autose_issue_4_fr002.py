from unittest import TestCase

from mistune.toc import render_toc_ul


class TestAutoseIssue4FR002(TestCase):
    def test_render_toc_ul_default(self):
        r"""AC-FR-002-1: Given TOC items [(1, 'toc_1', 'Introduction')], when render_toc_ul(toc_items), then <ul>\n<li><a href="#toc_1">Introduction</a></li>\n</ul>\n."""
        toc_items = [(1, 'toc_1', 'Introduction')]
        result = render_toc_ul(toc_items)
        expected = "<ul>\n<li><a href=\"#toc_1\">Introduction</a></li>\n</ul>\n"
        self.assertEqual(result, expected)

    def test_render_toc_ul_ordered_false(self):
        r"""AC-FR-002-2: Given TOC items [(1, 'toc_1', 'Introduction')], when render_toc_ul(toc_items, ordered=False), then <ul>\n<li><a href="#toc_1">Introduction</a></li>\n</ul>\n."""
        toc_items = [(1, 'toc_1', 'Introduction')]
        result = render_toc_ul(toc_items, ordered=False)
        expected = "<ul>\n<li><a href=\"#toc_1\">Introduction</a></li>\n</ul>\n"
        self.assertEqual(result, expected)

    def test_render_toc_ol_ordered_true(self):
        r"""AC-FR-002-2: Given TOC items [(1, 'toc_1', 'Introduction')], when render_toc_ul(toc_items, ordered=True), then <ol>\n<li><a href="#toc_1">Introduction</a></li>\n</ol>\n."""
        toc_items = [(1, 'toc_1', 'Introduction')]
        result = render_toc_ul(toc_items, ordered=True)
        expected = '<ol>\n<li><a href="#toc_1">Introduction</a></li>\n</ol>\n'
        self.assertEqual(result, expected)
