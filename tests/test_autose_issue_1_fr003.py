import mistune


def test_ac_fr_003_1():
    """AC-FR-003-1: Table rendering with matching header and row columns."""
    text = "| Name | Role |\n|---|---|\n| Ana | Dev |"
    md = mistune.create_markdown(plugins=["table"])
    expected = (
        "<table>\n"
        "<thead>\n"
        "<tr>\n"
        "  <th>Name</th>\n"
        "  <th>Role</th>\n"
        "</tr>\n"
        "</thead>\n"
        "<tbody>\n"
        "<tr>\n"
        "  <td>Ana</td>\n"
        "  <td>Dev</td>\n"
        "</tr>\n"
        "</tbody>\n"
        "</table>\n"
    )
    assert md(text) == expected


def test_ac_fr_004_1():
    """AC-FR-004-1: Invalid table fallback to paragraph when delimiter column count doesn't match header."""
    text = "| Name | Role |\n|---|"
    md = mistune.create_markdown(plugins=["table"])
    expected = "<p>| Name | Role |\n|---|</p>\n"
    assert md(text) == expected


def test_table_row_padding_and_truncation():
    """AC-FR-003-1: Table row cell count mismatch handling (padding fewer cells and truncating excess cells)."""
    md = mistune.create_markdown(plugins=["table"])

    # Fewer cells in row than header -> padded with empty string
    text_fewer = "| A | B | C |\n|---|---|---|\n| 1 |"
    expected_fewer = (
        "<table>\n"
        "<thead>\n"
        "<tr>\n"
        "  <th>A</th>\n"
        "  <th>B</th>\n"
        "  <th>C</th>\n"
        "</tr>\n"
        "</thead>\n"
        "<tbody>\n"
        "<tr>\n"
        "  <td>1</td>\n"
        "  <td></td>\n"
        "  <td></td>\n"
        "</tr>\n"
        "</tbody>\n"
        "</table>\n"
    )
    assert md(text_fewer) == expected_fewer

    # More cells in row than header -> truncated to header length
    text_more = "| A | B |\n|---|---|\n| 1 | 2 | 3 |"
    expected_more = (
        "<table>\n"
        "<thead>\n"
        "<tr>\n"
        "  <th>A</th>\n"
        "  <th>B</th>\n"
        "</tr>\n"
        "</thead>\n"
        "<tbody>\n"
        "<tr>\n"
        "  <td>1</td>\n"
        "  <td>2</td>\n"
        "</tr>\n"
        "</tbody>\n"
        "</table>\n"
    )
    assert md(text_more) == expected_more
