#!/usr/bin/env python3
"""Добавляет в data_new.json поле xl (текст с формулами LaTeX от MinerU) записям с формулами или картинками."""
import json
D = json.load(open("/home/claude/nav/data_new.json", encoding="utf-8"))
T = json.load(open("/home/claude/nav/mineru/mineru_text.json", encoding="utf-8"))
n = 0
def walk(x):
    global n
    for r in x.get("r", []) or []:
        t = T.get(r["i"])
        if t and ("$" in t or "![](" in t):
            r["xl"] = t; n += 1
    for c in x.get("c", []) or []:
        walk(c)
for p in D["tree"]:
    walk(p)
json.dump(D, open("/home/claude/nav/data_new.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("xl:", n)
