from unittest import TestCase

import mistune


class TestAutoseIssue3E2EAndRegression(TestCase):
    def test_link_rel_renderer_options(self):
        # AC-FR-001-1: link_rel="nofollow ugc" with markdown link
        renderer = mistune.HTMLRenderer(link_rel="nofollow ugc")
        md = mistune.create_markdown(renderer=renderer)
        self.assertEqual(
            md("[site](https://example.com)"),
            '<p><a href="https://example.com" rel="nofollow ugc">site</a></p>\n',
        )

        # AC-FR-001-2: default HTMLRenderer() with markdown link
        renderer_default = mistune.HTMLRenderer()
        md_default = mistune.create_markdown(renderer=renderer_default)
        self.assertEqual(
            md_default("[site](https://example.com)"),
            '<p><a href="https://example.com">site</a></p>\n',
        )

        # AC-FR-004-1: link_rel=None explicitly with markdown link
        renderer_none = mistune.HTMLRenderer(link_rel=None)
        md_none = mistune.create_markdown(renderer=renderer_none)
        self.assertEqual(
            md_none("[link](https://example.com)"),
            '<p><a href="https://example.com">link</a></p>\n',
        )

    def test_link_rel_autolinks(self):
        # AC-FR-002-1: angle bracket autolink with link_rel="nofollow ugc"
        renderer = mistune.HTMLRenderer(link_rel="nofollow ugc")
        md = mistune.create_markdown(renderer=renderer)
        self.assertEqual(
            md("<https://example.com>"),
            '<p><a href="https://example.com" rel="nofollow ugc">https://example.com</a></p>\n',
        )

        # AC-FR-002-2: url plugin autolink with link_rel="nofollow ugc"
        md_url = mistune.create_markdown(renderer=renderer, plugins=["url"])
        self.assertEqual(
            md_url("https://example.com"),
            '<p><a href="https://example.com" rel="nofollow ugc">https://example.com</a></p>\n',
        )

    def test_link_rel_image_isolation(self):
        # AC-FR-003-1: images should not receive rel attribute from link_rel
        renderer = mistune.HTMLRenderer(link_rel="nofollow ugc")
        md = mistune.create_markdown(renderer=renderer)
        self.assertEqual(
            md("![alt text](https://example.com/img.png)"),
            '<p><img src="https://example.com/img.png" alt="alt text" /></p>\n',
        )

    def test_regression_link_with_title_and_escaping(self):
        # Regression: links with titles should include both title and rel attributes correctly
        renderer = mistune.HTMLRenderer(link_rel="nofollow ugc")
        md = mistune.create_markdown(renderer=renderer)
        self.assertEqual(
            md('[site](https://example.com "Example Title")'),
            '<p><a href="https://example.com" title="Example Title" rel="nofollow ugc">site</a></p>\n',
        )

        # Regression: default renderer with titles
        md_default = mistune.create_markdown()
        self.assertEqual(
            md_default('[site](https://example.com "Title")'),
            '<p><a href="https://example.com" title="Title">site</a></p>\n',
        )

    def test_regression_nearby_inline_elements(self):
        # Regression: emphasis, code, and standard formatting remain unaffected
        md = mistune.create_markdown()
        self.assertEqual(
            md("*emphasis* and `code`"),
            '<p><em>emphasis</em> and <code>code</code></p>\n',
        )
