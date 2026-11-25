import pytest
from slugify import slugify


@pytest.mark.parametrize(("text", "expected"), [
    ("  Crème brûlée, Straße! ", "creme-brulee-strasse"),
    ("Cafe\u0301", "cafe"),
    ("R&D / Q4___2026", "r-d-q4-2026"),
    ("...already-a-slug...", "already-a-slug"),
    ("a東京b", "a-b"),
    ("１２３", "123"),
    ("💡 / !", ""),
    ("", ""),
])
def test_slugify(text, expected):
    assert slugify(text) == expected
