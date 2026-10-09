#!/usr/bin/env python3
"""Добавляет в data_new.json поле xl (текст с формулами LaTeX от MinerU) записям с формулами или картинками."""
import json
import os as _os
K = _os.path.dirname(_os.path.abspath(__file__))           # navigator/сборка
ROOT = _os.path.normpath(_os.path.join(K, "..", ".."))   # корень проекта «ИС ОЗЯМ-ФОП»
M = _os.path.join(ROOT, "1_разметка")
D = json.load(open(_os.path.join(K, "data_new.json"), encoding="utf-8"))
T = json.load(open(_os.path.join(M, "формулы_mineru.json"), encoding="utf-8"))
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
json.dump(D, open(_os.path.join(K, "data_new.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("xl:", n)
