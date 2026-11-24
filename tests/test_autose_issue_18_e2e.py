from unittest import TestCase

import mistune


class TestAutoseIssue18E2E(TestCase):
    def test_url_plugin_acceptance_criteria(self):
        md = mistune.create_markdown(escape=False, plugins=["url"])
        # AC-FR-001-1
        self.assertEqual(
            md("visit www.example.com/docs"),
            '<p>visit <a href="https://www.example.com/docs">www.example.com/docs</a></p>\n',
        )
        # AC-FR-002-1
        self.assertEqual(
            md("visit https://example.com/old"),
            '<p>visit <a href="https://example.com/old">https://example.com/old</a></p>\n',
        )
        # AC-FR-003-1
        self.assertEqual(
            md("www.example.com"),
            '<p><a href="https://www.example.com">www.example.com</a></p>\n',
        )
        # AC-FR-004-1
        self.assertEqual(
            md("not a link: my_www.example"),
            '<p>not a link: my_www.example</p>\n',
        )

    def test_url_plugin_combined_with_plugins_and_options(self):
        md = mistune.create_markdown(
            plugins=["url", "table", "task_lists"],
            hard_wrap=True,
            escape=False,
        )
        text = (
            "Check out www.example.com and https://example.org.\n"
            "Line two after hard wrap.\n\n"
            "- [x] Task with link www.task.org/item\n\n"
            "| Header | URL |\n"
            "| --- | --- |\n"
            "| Site | www.table.net |\n"
        )
        result = md(text)
        self.assertIn('<a href="https://www.example.com">www.example.com</a>', result)
        self.assertIn('<a href="https://example.org">https://example.org</a>', result)
        self.assertIn('<a href="https://www.task.org/item">www.task.org/item</a>', result)
        self.assertIn('<a href="https://www.table.net">www.table.net</a>', result)
        self.assertIn('<br />', result)
        self.assertIn('checked/>', result)
        self.assertIn('<table>', result)

    def test_regression_standard_markdown_links(self):
        # Regression test for standard markdown links [text](url) and reference links
        text = "Visit [Example](https://example.com) or [Ref][ref].\n\n[ref]: https://ref.example.com\n"
        md1 = mistune.create_markdown(escape=False, plugins=["url"])
        md2 = mistune.create_markdown(escape=False)
        result1 = md1(text)
        result2 = md2(text)
        expected = (
            '<p>Visit <a href="https://example.com">Example</a> or '
            '<a href="https://ref.example.com">Ref</a>.</p>\n'
        )
        self.assertEqual(result1, expected)
        self.assertEqual(result2, expected)

    def test_regression_autolinks_and_code_spans(self):
        # Regression test for angle-bracket autolinks and code spans containing www. or http://
        text = "Autolink <https://example.com> and code `www.example.com` and `http://example.com`."
        md = mistune.create_markdown(escape=False, plugins=["url"])
        result = md(text)
        self.assertIn('<a href="https://example.com">https://example.com</a>', result)
        self.assertIn('<code>www.example.com</code>', result)
        self.assertIn('<code>http://example.com</code>', result)

    def test_regression_strikethrough_and_formatting(self):
        # Regression test for strikethrough plugin combined with url plugin
        text = "Visit ~~www.strike.net~~ for details."
        md = mistune.create_markdown(escape=False, plugins=["url", "strikethrough"])
        result = md(text)
        self.assertIn('<del><a href="https://www.strike.net">www.strike.net</a></del>', result)
