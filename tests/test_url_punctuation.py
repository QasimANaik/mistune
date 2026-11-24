import mistune

md = mistune.create_markdown(plugins=["url"])


def test_trailing_question_mark_not_in_link():
    assert md("did you try https://example.com/docs?") == (
        '<p>did you try <a href="https://example.com/docs">https://example.com/docs</a>?</p>\n')


def test_trailing_exclamation_not_in_link():
    assert '</a>!' in md("look at https://example.com/new!")
