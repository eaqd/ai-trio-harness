# Slugify a title

Create `slugify.py` beside this file. Export `slugify(text: str) -> str` using the Python standard library.

Fold case with `str.casefold()`, apply Unicode NFKD normalization and drop combining marks. Keep ASCII letters and digits. Replace each run of other characters with one hyphen and trim leading and trailing hyphens. Return the empty string when no letters or digits survive.

For example, `"  Crème brûlée, Straße! "` becomes `"creme-brulee-strasse"`. Preserve the supplied acceptance tests. From this directory the check is `python -m pytest -q test_slugify.py`.
