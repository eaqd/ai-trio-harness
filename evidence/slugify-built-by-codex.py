"""Convert titles into ASCII slugs."""

import re
import unicodedata


def slugify(text: str) -> str:
    """Fold case, remove Unicode marks, and hyphenate non-ASCII runs."""
    normalized = unicodedata.normalize("NFKD", text.casefold())
    unmarked = "".join(
        char for char in normalized
        if not unicodedata.category(char).startswith("M")
    )
    return re.sub(r"[^A-Za-z0-9]+", "-", unmarked).strip("-")
