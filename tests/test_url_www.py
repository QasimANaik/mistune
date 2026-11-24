import mistune

md = mistune.create_markdown(plugins=["url"])


def test_www_address_is_linked():
    assert md("docs at www.example.com/docs now") == (
        '<p>docs at <a href="http://www.example.com/docs">www.example.com/docs</a> now</p>\n')


def test_www_trailing_comma_excluded():
    assert '</a>, or' in md("see www.example.com, or later")


def test_https_links_unchanged():
    assert md("old https://example.com/old") == (
        '<p>old <a href="https://example.com/old">https://example.com/old</a></p>\n')


def test_code_span_not_linked():
    assert md("`www.example.com`") == "<p><code>www.example.com</code></p>\n"
