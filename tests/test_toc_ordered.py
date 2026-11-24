from mistune.toc import render_toc_ul


def test_ordered_toc_uses_ol():
    html = render_toc_ul([(1, "a", "A"), (1, "b", "B")], ordered=True)
    assert html.startswith("<ol>")
    assert html.endswith("</ol>\n")


def test_default_toc_unchanged():
    assert render_toc_ul([(1, "a", "A")]).startswith("<ul>")
