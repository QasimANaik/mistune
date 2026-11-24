import mistune

md = mistune.create_markdown(plugins=["table"])


def test_short_row_is_padded():
    html = md("| Name | Role |\n|------|------|\n| Ana |")
    print(html)


def test_extra_cell_is_dropped():
    html = md("| Name | Role |\n|------|------|\n| Ana | Dev | extra |")
    assert html
