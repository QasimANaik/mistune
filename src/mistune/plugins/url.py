from typing import TYPE_CHECKING, Match

from ..util import escape_url

if TYPE_CHECKING:
    from ..core import InlineState
    from ..inline_parser import InlineParser
    from ..markdown import Markdown

__all__ = ["url"]

URL_LINK_PATTERN = r"""https?:\/\/[^\s<]+"""


def clean_url_text(text: str) -> str:
    while text:
        last = text[-1]
        if last in '.,;:?!\'"':
            text = text[:-1]
        elif last == ')':
            if text.count('(') < text.count(')'):
                text = text[:-1]
            else:
                break
        else:
            break
    return text


def parse_url_link(inline: "InlineParser", m: Match[str], state: "InlineState") -> int:
    text = m.group(0)
    pos = m.end()
    if state.brackets:
        close = text.find("]")
        if close >= 0:
            text = text[:close]
            pos = m.start() + close

    text = clean_url_text(text)
    pos = m.start() + len(text)

    if state.in_link or state.depth >= inline.max_nested_level:
        inline.process_text(text, state)
        return pos
    state.append_token(
        {
            "type": "link",
            "children": [{"type": "text", "raw": text}],
            "attrs": {"url": escape_url(text)},
            "_autolink": text,
        }
    )
    return pos


def url(md: "Markdown") -> None:
    md.inline.register("url_link", URL_LINK_PATTERN, parse_url_link)
