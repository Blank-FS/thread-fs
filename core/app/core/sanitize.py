# app/core/sanitize.py

from bs4 import BeautifulSoup
import bleach

ALLOWED_TAGS = [
    "p",
    "br",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "s",
    "blockquote",
    "code",
    "pre",
    "ul",
    "ol",
    "li",
    "a",
]

ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "target", "rel"],
}

ALLOWED_PROTOCOLS = ["http", "https", "mailto"]


def remove_trailing_empty_blocks(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")

    def is_empty_block(tag) -> bool:
        if tag.name not in {"p", "div"}:
            return False

        text = tag.get_text().replace("\xa0", " ").strip()
        if text:
            return False

        for child in tag.contents:
            if getattr(child, "name", None) == "br":
                continue

            if isinstance(child, str) and child.replace("\xa0", " ").strip() == "":
                continue

            return False

        return True

    while soup.contents:
        last = soup.contents[-1]

        if isinstance(last, str):
            if last.strip() == "":
                last.extract()
                continue
            break

        if is_empty_block(last):
            last.extract()
            continue

        break

    return str(soup)


def sanitize_comment_html(html: str) -> str:
    html = remove_trailing_empty_blocks(html)

    cleaned = bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )

    cleaned = bleach.linkify(cleaned)

    return remove_trailing_empty_blocks(cleaned)
