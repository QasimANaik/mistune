from unittest import TestCase

from mistune import create_markdown


class TestAutoseIssue2FR001(TestCase):
    def test_ac_fr_003_1(self):
        """AC-FR-003-1: Given Markdown input 'visit https://example.com.', when markdown is created with plugins=['url'], then output HTML contains '<a href=\"https://example.com\">https://example.com</a>.'."""
        md = create_markdown(plugins=["url"])
        result = md("visit https://example.com.")
        self.assertIn('<a href="https://example.com">https://example.com</a>.', result)

    def test_ac_fr_003_2(self):
        """AC-FR-003-2: Given Markdown input 'see https://example.com, and more', when markdown is created with plugins=['url'], then output HTML contains '<a href=\"https://example.com\">https://example.com</a>, and more'."""
        md = create_markdown(plugins=["url"])
        result = md("see https://example.com, and more")
        self.assertIn('<a href="https://example.com">https://example.com</a>, and more', result)

    def test_ac_fr_001_1(self):
        """AC-FR-001-1: Given Markdown input 'see https://en.wikipedia.org/wiki/Python_(programming_language) for details', when markdown is created with plugins=['url'], then output HTML contains link with parentheses."""
        md = create_markdown(plugins=["url"])
        result = md("see https://en.wikipedia.org/wiki/Python_(programming_language) for details")
        self.assertIn(
            '<a href="https://en.wikipedia.org/wiki/Python_(programming_language)">https://en.wikipedia.org/wiki/Python_(programming_language)</a>',
            result
        )

    def test_ac_fr_004_1(self):
        """AC-FR-004-1: Given Markdown input '[link https://example.com]', when markdown is created with plugins=['url'], then output HTML handles brackets according to existing mistune url plugin rules."""
        md = create_markdown(plugins=["url"])
        result = md("[link https://example.com]")
        self.assertIn('href="https://example.com"', result)
