"""Unit tests for transcript styling (2026-10-28): punctuation strip -> leet -> aLtCaPs. Offline, no GUI."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "widget"))
import eagle_core as core

CASES = [
    (core.strip_punct("Hello, world! Don't stop; it's fine."), "Hello world Don't stop it's fine"),
    (core.strip_punct("'quoted' well-known 3.5 GB (yes)?"), "quoted well known 3.5 GB yes"),
    (core.strip_punct("rock \u2019n\u2019 roll, it\u2019s"), "rock n roll it\u2019s"),
    (core.leet("Eagle Ear test"), "34gl3 34r 7357"),
    (core.alt_caps("hello world!"), "hElLo WoRlD!"),
    (core.alt_caps("a, b c"), "a, B c"),
    (core.style_text("Hi, it's set.", True, True, True), "h1 17'5 537"),
    (core.style_text("Hi, there.", False, False, False), "Hi, there."),
    (core.style_text("Don't stop.", True, False, True), "dOn'T sToP"),
]
bad = [(i, got, exp) for i, (got, exp) in enumerate(CASES) if got != exp]
for b in bad:
    print("FAIL", b)
print(f"style tests: {len(CASES) - len(bad)}/{len(CASES)} passed")
sys.exit(1 if bad else 0)
