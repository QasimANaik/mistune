import unittest

import mistune


class TestIssue18FR001(unittest.TestCase):
    def test_ac_fr_001_1(self):
        """AC-FR-001-1: Given Markdown input `"visit www.example.com/docs"` with url plugin enabled."""
        markdown = "visit www.example.com/docs"
        expected = '<p>visit <a href="https://www.example.com/docs">www.example.com/docs</a></p>\n'
        result = mistune.markdown(markdown, plugins=['url'])
        self.assertEqual(result, expected)

        md = mistune.create_markdown(plugins=['url'])
        self.assertEqual(md(markdown), expected)

    def test_ac_fr_002_1(self):
        """AC-FR-002-1: Given Markdown input `"visit https://example.com/old"` with url plugin enabled."""
        markdown = "visit https://example.com/old"
        expected = '<p>visit <a href="https://example.com/old">https://example.com/old</a></p>\n'
        result = mistune.markdown(markdown, plugins=['url'])
        self.assertEqual(result, expected)

        md = mistune.create_markdown(plugins=['url'])
        self.assertEqual(md(markdown), expected)

    def test_ac_fr_003_1(self):
        """AC-FR-003-1: Given Markdown input `"www.example.com"` with url plugin enabled."""
        markdown = "www.example.com"
        expected = '<p><a href="https://www.example.com">www.example.com</a></p>\n'
        result = mistune.markdown(markdown, plugins=['url'])
        self.assertEqual(result, expected)

        md = mistune.create_markdown(plugins=['url'])
        self.assertEqual(md(markdown), expected)

    def test_ac_fr_004_1(self):
        """AC-FR-004-1: Given Markdown input `"not a link: my_www.example"` with url plugin enabled."""
        markdown = "not a link: my_www.example"
        expected = '<p>not a link: my_www.example</p>\n'
        result = mistune.markdown(markdown, plugins=['url'])
        self.assertEqual(result, expected)

        md = mistune.create_markdown(plugins=['url'])
        self.assertEqual(md(markdown), expected)
