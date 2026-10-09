#!/usr/bin/env python3
"""Сопоставляет таблицы из Markdown MinerU (физика ООО/СОО) с записями records.jsonl по коду.
Выход: mineru_text.json {id записи: текст с формулами LaTeX ($...$) и ссылками на картинки}."""
import paths as _P  # пути прогона (автоматизация/этапы/paths.py)
import json, re, sys, difflib, os
B = _P.M
from collections import Counter
MD = {k: v for k, v in (("OOO", _P.env("OZ_MINERU_OOO")), ("SOO", _P.env("OZ_MINERU_SOO"))) if v}
recs = [json.loads(l) for l in open(os.path.join(B, "records.jsonl"), encoding="utf-8")]
byid = {r["id"]: r for r in recs}

def cells(line):
    s = line.strip()
    assert s.startswith("|") and s.endswith("|"), line
    s = s[1:-1]
    out, cur, m, i = [], "", False, 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s) and s[i + 1] == "|" and not m:
            cur += "|"; i += 2; continue
        if ch == "$":
            m = not m
        if ch == "|" and not m:
            out.append(cur.strip()); cur = ""
        else:
            cur += ch
        i += 1
    out.append(cur.strip())
    return out

def section_prefix(head, part):
    h = head.lower()
    exam = "oge" if part == "OOO" else "ege"
    g = re.search(r"(\d+)\s*\(?\s*класс", h) or re.search(r"\((\d+) класс\)", h)
    if "перечень элементов содержания, проверяем" in h:
        return f"{part}.physics.{exam}.el"
    if "проверяемые на огэ" in h or "проверяемые на егэ" in h:
        return f"{part}.physics.{exam}.req"
    if g and "элементы содержания" in h:
        return f"{part}.physics.cls.g{g.group(1)}.el"
    if g and ("результаты" in h or "требования" in h):
        return f"{part}.physics.cls.g{g.group(1)}.req"
    return None

def join(a, b):
    if not a: return b
    if not b: return a
    return a + ("" if a.endswith("-") else " ") + b

out, problems = {}, []
for part, path in MD.items():
    prefix, last = None, None
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line.startswith("|"):
            if line.strip() and not line.startswith("Таблица"):
                p = section_prefix(line, part)
                if p: prefix, last = p, None
            continue
        if re.fullmatch(r"\|(\s*-+\s*\|)+", line.strip()) or prefix is None:
            continue
        c = cells(line)
        if c[0].startswith("Код"):
            continue
        if len(c) == 3:
            a, b, t = c
            if a and not b and t:         # раздел (ЕГЭ): | 1 |  | МЕХАНИКА |
                code, text = a, t
            elif a and b and not t:       # раздел (классы): | 1 | ФИЗИКА ... |  |
                code, text = a, b
            elif b and t:                 # элемент: |  | 1.1 | текст |  или | 1 | 1.1 | текст |
                code, text = b, t
            elif not a and not b:         # продолжение
                code, text = None, t
            else:
                code, text = (a or b), t
        else:
            code, text = (c[0] or None), " ".join(c[1:]).strip()
        if code is None:
            if last: out[last] = join(out[last], text)
            continue
        code = code.rstrip(".")
        rid = f"{prefix}.{code}"
        if rid not in byid:
            alt = [k for k in byid if k.split("~")[0] == rid]
            if alt: rid = alt[0]
            else:
                problems.append(("нет записи", rid, text[:60])); last = None; continue
        if rid in out:
            problems.append(("повтор кода", rid, text[:60]))
            rid2 = next((k for k in byid if k.split("~")[0] == rid.split("~")[0] and k not in out), None)
            if rid2: rid = rid2
        out[rid] = text; last = rid

def plain(s):
    s = re.sub(r"!\[\]\([^)]*\)", " ", s)
    s = re.sub(r"\$[^$]*\$", " ", s)
    return re.sub(r"[^а-яё]", "", s.lower().replace("ё", "е"))
scope = [r for r in recs if r["subject"] == "physics" and r["type"] in ("requirement", "element", "exam_requirement", "exam_element")]
missing = [r["id"] for r in scope if r["id"] not in out]
sims = []
for rid, t in out.items():
    a, b = plain(byid[rid]["text"]), plain(t)
    sims.append((difflib.SequenceMatcher(None, a, b).ratio() if a or b else 1.0, rid))
low = sorted(s for s in sims if s[0] < 0.8)
print("сопоставлено", len(out), "из", len(scope), "| нет в MinerU:", len(missing), missing[:15])
print("проблемы:", len(problems)); [print("  ", p) for p in problems[:20]]
print("сходство текста без формул < 0.8:", len(low))
for s, rid in low[:25]:
    print(f"  {s:.2f} {rid}\n      PRIK: {byid[rid]['text'][:110]}\n      MINE: {out[rid][:110]}")
withmath = sum(1 for t in out.values() if "$" in t); withimg = sum(1 for t in out.values() if "![](" in t)
print("с формулами:", withmath, "с картинками:", withimg)
json.dump(out, open(os.path.join(B, "формулы_mineru.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
