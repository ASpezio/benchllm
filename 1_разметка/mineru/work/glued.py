"""Находит слипшиеся на переносах слова в выводе MinerU по словарю текстового слоя PDF."""
import glob
import re
import sys
from collections import Counter

import pymupdf

sys.stdout.reconfigure(encoding="utf-8")
WORD = re.compile(r"[А-Яа-яЁё]+")


def vocab():
    d = pymupdf.open(glob.glob("*.pdf")[0])
    v = Counter()
    for a, b in [(571, 599), (1007, 1038)]:
        for p in range(a - 1, b):
            for w in d[p].get_text("words"):
                for tok in WORD.findall(w[4]):
                    v[tok.lower()] += 1
    return v


def find(text, v):
    plain = re.sub(r"\$[^$]*\$", " ", text)
    fixes = {}
    for tok in set(WORD.findall(plain)):
        low = tok.lower()
        if low in v or len(tok) < 4:
            continue
        best = None
        for i in range(1, len(tok)):
            a, b = low[:i], low[i:]
            if a in v and b in v:
                score = min(v[a], v[b])
                if best is None or score > best[0]:
                    best = (score, i)
        if best:
            i = best[1]
            fixes[tok] = tok[:i] + " " + tok[i:]
    return fixes


if __name__ == "__main__":
    v = vocab()
    for path in sys.argv[1:]:
        t = open(path, encoding="utf-8").read()
        f = find(t, v)
        print(path, len(f))
        for k, val in sorted(f.items()):
            print("  ", k, "->", val)
