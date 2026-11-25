# Cross-check

~~~
In Python 3.12: is sorted() guaranteed to be stable, and what does my_list.sort(key=str.lower) return? Answer in 2 short sentences.
~~~

Disagreements are leads to verify, not truth.

## Answer key

### A — codex

~~~
Yes, Python 3.12’s `sorted()` is guaranteed to be stable: items with equal keys retain their original relative order. `my_list.sort(key=str.lower)` sorts the list in place using lowercase comparison keys and returns `None`.
~~~

### B — claude

~~~
Yes — `sorted()` is guaranteed stable in Python (3.12 included), meaning elements that compare equal keep their original relative order. `my_list.sort(key=str.lower)` returns `None`; it sorts the list in place rather than returning a new list.
~~~

### C — gemini

~~~
Yes, `sorted()` is guaranteed to be stable in Python 3.12. 

`my_list.sort(key=str.lower)` sorts the list in place and returns `None`.
~~~

## Verdict from claude

All three answers are correct and substantively equivalent: sorted() (like list.sort()) is guaranteed stable in Python 3.12, and my_list.sort(key=str.lower) mutates in place and returns None. The only difference is depth of explanation — A and B define what stability means and note the lowercase comparison keys, while C is more terse but still accurate.

Confidence: high

### Agreement

A, B, and C all state that sorted() is guaranteed to be stable in Python 3.12.

A, B, and C all state that my_list.sort(key=str.lower) sorts the list in place and returns None.

A and B additionally explain correctly that stability means equal-keyed items retain their original relative order (C asserts stability without defining it).

### Disagreement

None reported.
