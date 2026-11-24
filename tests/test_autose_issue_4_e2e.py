from time import perf_counter
from unittest import TestCase

from mistune import create_markdown
from mistune.toc import add_toc_hook, render_toc_ul


class TestAutoseIssue4E2E(TestCase):
    def test_render_toc_ul_ordered_and_unordered(self):
        # AC-FR-001-1: ordered single item
        toc_items_1 = [(1, 'toc_1', 'Introduction')]
        self.assertEqual(
            render_toc_ul(toc_items_1, ordered=True),
            '<ol>\n<li><a href="#toc_1">Introduction</a></li>\n</ol>\n'
        )

        # AC-FR-001-2: ordered nested items
        toc_items_2 = [(1, 'toc_1', 'One'), (2, 'toc_2', 'Sub')]
        self.assertEqual(
            render_toc_ul(toc_items_2, ordered=True),
            '<ol>\n<li><a href="#toc_1">One</a>\n<ol>\n<li><a href="#toc_2">Sub</a></li>\n</ol>\n</li>\n</ol>\n'
        )

        # AC-FR-002-1: unordered default
        self.assertEqual(
            render_toc_ul(toc_items_1),
            '<ul>\n<li><a href="#toc_1">Introduction</a></li>\n</ul>\n'
        )

        # AC-FR-002-2: unordered explicit
        self.assertEqual(
            render_toc_ul(toc_items_1, ordered=False),
            '<ul>\n<li><a href="#toc_1">Introduction</a></li>\n</ul>\n'
        )

    def test_toc_performance(self):
        # AC-NFR-001-1: < 5ms for 1000 TOC items
        toc_items = [(i % 3 + 1, f"toc_{i}", f"Heading {i}") for i in range(1000)]
        start = perf_counter()
        result = render_toc_ul(toc_items, ordered=True)
        duration = perf_counter() - start
        self.assertTrue(result)
        self.assertLess(duration, 0.005)  # less than 5ms

    def test_regression_empty_and_complex_unordered_toc(self):
        # Regression test 1: empty and filtered TOC
        self.assertEqual(render_toc_ul([]), "")
        self.assertEqual(render_toc_ul(filter(lambda _: False, [])), "")

        # Regression test 2: complex multi-level unordered TOC rendering
        toc_items = [
            (1, 'h1', 'Heading 1'),
            (2, 'h2', 'Heading 2'),
            (3, 'h3', 'Heading 3'),
            (1, 'h1-2', 'Heading 1.2'),
        ]
        expected = (
            '<ul>\n'
            '<li><a href="#h1">Heading 1</a>\n'
            '<ul>\n'
            '<li><a href="#h2">Heading 2</a>\n'
            '<ul>\n'
            '<li><a href="#h3">Heading 3</a></li>\n'
            '</ul>\n'
            '</li>\n'
            '</ul>\n'
            '</li>\n'
            '<li><a href="#h1-2">Heading 1.2</a></li>\n'
            '</ul>\n'
        )
        self.assertEqual(render_toc_ul(toc_items, ordered=False), expected)

    def test_regression_markdown_toc_hook_integration(self):
        # Regression test 3: Markdown parser integration with toc hook
        md = create_markdown(escape=False)
        add_toc_hook(md)
        html, state = md.parse("# Introduction\n\n## Sub")
        toc_html = render_toc_ul(state.env["toc_items"], ordered=True)
        self.assertIn('<ol>', toc_html)
        self.assertIn('<a href="#toc_1">Introduction</a>', toc_html)
        self.assertIn('<a href="#toc_2">Sub</a>', toc_html)
