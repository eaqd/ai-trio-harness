# Review

Reviewers: claude, gemini

## Diff stat

~~~
 /dev/null => ./slugify.py | 14 ++++++++++++++
 1 file changed, 14 insertions(+)
~~~

## Findings

### claude — minor

claude: Docstring inaccuracy in slugify(): it says the function will "hyphenate non-ASCII runs", but the regex substitution r"[^A-Za-z0-9]+" collapses ALL non-alphanumeric runs — spaces, ASCII punctuation, and non-ASCII characters alike — into a single hyphen. Reword the docstring to describe the actual behavior (replace every run of non-ASCII-alphanumeric characters with '-').

### claude — minor

claude: slugify() silently drops characters that have no NFKD ASCII decomposition. NFKD only strips combining marks, so letters like 'ø', 'ł', 'đ', 'þ', 'ß' (ß is handled by casefold, but stroke/bar letters are not) and entire non-Latin scripts (e.g. CJK) survive normalization unchanged, then get replaced by '-' and stripped. As a result 'Søren' -> 's-ren' (the 'ø' is lost, not transliterated) and a purely non-Latin title collapses to an empty string. An empty slug can be problematic for URLs (collisions/invalid paths); consider transliteration or a fallback for empty results if those inputs are expected.
