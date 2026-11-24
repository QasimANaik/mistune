from unittest import TestCase

import mistune


class TestAutoseIssue3Fr002(TestCase):
    def test_ac_fr_002_1(self):
        """AC-FR-002-1: Given renderer equals mistune.HTMLRenderer(link_rel="nofollow ugc") and md equals mistune.create_markdown(renderer=renderer), when calling md("<https://example.com>"), then the return value equals "<p><a href=\"https://example.com\" rel=\"nofollow ugc\">https://example.com</a></p>\n"."""
        renderer = mistune.HTMLRenderer(link_rel="nofollow ugc")
        md = mistune.create_markdown(renderer=renderer)
        result = md("<https://example.com>")
        expected = '<p><a href="https://example.com" rel="nofollow ugc">https://example.com</a></p>\n'
        self.assertEqual(result, expected)

    def test_ac_fr_002_2(self):
        """AC-FR-002-2: Given renderer equals mistune.HTMLRenderer(link_rel="nofollow ugc") and md equals mistune.create_markdown(renderer=renderer, plugins=["url"]), when calling md("https://example.com"), then the return value equals "<p><a href=\"https://example.com\" rel=\"nofollow ugc\">https://example.com</a></p>\n"."""
        renderer = mistune.HTMLRenderer(link_rel="nofollow ugc")
        md = mistune.create_markdown(renderer=renderer, plugins=["url"])
        result = md("https://example.com")
        expected = '<p><a href="https://example.com" rel="nofollow ugc">https://example.com</a></p>\n'
        self.assertEqual(result, expected)

    def test_ac_fr_003_1(self):
        """AC-FR-003-1: Given renderer equals mistune.HTMLRenderer(link_rel="nofollow ugc") and md equals mistune.create_markdown(renderer=renderer), when calling md("![alt text](https://example.com/img.png)"), then the return value equals "<p><img src=\"https://example.com/img.png\" alt=\"alt text\" /></p>\n"."""
        renderer = mistune.HTMLRenderer(link_rel="nofollow ugc")
        md = mistune.create_markdown(renderer=renderer)
        result = md("![alt text](https://example.com/img.png)")
        expected = '<p><img src="https://example.com/img.png" alt="alt text" /></p>\n'
        self.assertEqual(result, expected)

    def test_ac_fr_004_1(self):
        """AC-FR-004-1: Given renderer equals mistune.HTMLRenderer(link_rel=None) and md equals mistune.create_markdown(renderer=renderer), when calling md("[link](https://example.com)"), then the return value equals "<p><a href=\"https://example.com\">link</a></p>\n"."""
        renderer = mistune.HTMLRenderer(link_rel=None)
        md = mistune.create_markdown(renderer=renderer)
        result = md("[link](https://example.com)")
        expected = '<p><a href="https://example.com">link</a></p>\n'
        self.assertEqual(result, expected)
