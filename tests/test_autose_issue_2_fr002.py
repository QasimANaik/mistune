from unittest import TestCase

from mistune import create_markdown
from tests.perf_utils import assert_near_linear


class TestAutoseIssue2Fr002(TestCase):
    def test_url_plugin_trailing_question_mark(self):
        """AC-FR-002-1: Given Markdown input "did you try https://example.com/docs?", when markdown is created with plugins=["url"], then output HTML contains <a href="https://example.com/docs">https://example.com/docs</a>?."""
        md = create_markdown(plugins=["url"])
        result = md("did you try https://example.com/docs?")
        self.assertIn('<a href="https://example.com/docs">https://example.com/docs</a>?', result)

    def test_url_plugin_trailing_exclamation_mark(self):
        """AC-FR-002-2: Given Markdown input "check https://example.com/path! for info", when markdown is created with plugins=["url"], then output HTML contains <a href="https://example.com/path">https://example.com/path</a>!."""
        md = create_markdown(plugins=["url"])
        result = md("check https://example.com/path! for info")
        self.assertIn('<a href="https://example.com/path">https://example.com/path</a>!', result)

    def test_url_plugin_performance_linear(self):
        """AC-NFR-001-1: Execution time is O(n) relative to text length for URL parsing."""
        md = create_markdown(plugins=["url"])

        def render(size):
            text = " ".join(f"https://example.com/path/{i}?" for i in range(size))
            return md(text)

        assert_near_linear(self, render, 1000, 2000)
