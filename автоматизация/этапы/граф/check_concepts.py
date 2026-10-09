#!/usr/bin/env python3
"""Проверка выхода извлечения понятий: покрытие source_id, типы, evidence как подстрока текста."""
import json, sys, re

TYPES = {"событие", "процесс", "личность", "государство_народ", "место", "документ", "термин", "памятник_культуры",
         "религия_верование", "период", "явление", "величина", "закон", "модель", "понятие", "опыт", "прибор", "природное_явление"}


def norm(s):
    s = s.replace("ё", "е").replace("Ё", "Е").replace("­", "")
    s = re.sub(r"[‐-‒–—−]", "-", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def main(inp, outp):
    items = {i["source_id"]: i for i in json.load(open(inp, encoding="utf-8"))["items"]}
    out = json.load(open(outp, encoding="utf-8"))
    errs, seen = [], set()
    for o in out:
        sid = o.get("source_id")
        if sid not in items:
            errs.append(f"лишний source_id {sid}"); continue
        if sid in seen:
            errs.append(f"повтор source_id {sid}")
        seen.add(sid)
        it = items[sid]
        hay = norm(it["text"]) + " || " + norm(it.get("text_latex", ""))
        if not o.get("concepts"):
            errs.append(f"{sid}: нет понятий")
        for c in o.get("concepts", []):
            if not c.get("name"):
                errs.append(f"{sid}: понятие без имени")
            if c.get("type") not in TYPES:
                errs.append(f"{sid}: тип {c.get('type')!r} у «{c.get('name')}»")
            ev = c.get("evidence", "")
            if not ev or norm(ev) not in hay:
                errs.append(f"{sid}: evidence не найден в тексте: {ev!r} («{c.get('name')}»)")
    for sid in items:
        if sid not in seen:
            errs.append(f"нет source_id {sid}")
    if errs:
        print(f"ОШИБОК: {len(errs)}")
        for e in errs[:60]:
            print(" ", e)
        sys.exit(1)
    n = sum(len(o["concepts"]) for o in out)
    print(f"OK: элементов {len(out)}, понятий {n}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
