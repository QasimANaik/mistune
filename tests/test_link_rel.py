import mistune


def _md(**kw):
    return mistune.create_markdown(renderer=mistune.HTMLRenderer(**kw), plugins=["url"])


def test_rel_added_to_links():
    html = _md(link_rel="nofollow ugc")("[site](https://example.com)")
    assert html == '<p><a href="https://example.com" rel="nofollow ugc">site</a></p>\n'


def test_rel_on_plain_urls():
    assert 'rel="nofollow"' in _md(link_rel="nofollow")("see https://example.com")


def test_link_title_kept():
    html = _md(link_rel="nofollow")('[site](https://example.com "Home")')
    assert 'title="Home"' in html


def test_default_unchanged():
    assert _md()("[site](https://example.com)") == '<p><a href="https://example.com">site</a></p>\n'
