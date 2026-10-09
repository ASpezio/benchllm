#!/usr/bin/env python3
"""LLM проверяет привязку уроков к элементам содержания (то, что раньше делал эксперт).

  python3 llm_lessons.py history   — вход промежуточное/align_auto.json   → решения/overrides.json
  python3 llm_lessons.py physics   — вход физика_поурочное/_авто/*.csv     → решения/overrides_physics.json

В файл решений попадают только уроки, где решение модели отличается от алгоритма, — в том же формате,
что старые ручные правки, поэтому скрипты разметки применяют их без изменений.
"""
import os
import sys
from collections import defaultdict

import paths as P
from common import csv_rows, jload, mode, records, setting, short, write_overrides, copy_replay
from llm import LLM, chunks, prompt, run_stage

SUBJ = sys.argv[1] if len(sys.argv) > 1 else "history"
STAGE = f"уроки_{'история' if SUBJ == 'history' else 'физика'}"
OUT_NAME = "overrides.json" if SUBJ == "history" else "overrides_physics.json"
BATCH = int(setting("llm", "уроков_за_запрос", 15))


def class_elements(recs, part, grade, extra_grades=()):
    """Листья и разделы кодификатора класса. extra_grades — элементы других классов с кодом «класс:код»."""
    by_id = {r["id"]: r for r in recs}
    leaves, groups = [], []
    for g in (grade, *extra_grades):
        for r in recs:
            if (r["subject"] == SUBJ and r["part"] == part and r["type"] == "element"
                    and r["block"] == "class_codifier" and r["grade"] == g):
                code = r["code"] if g == grade else f"{g}:{r['code']}"
                if r.get("is_group"):
                    groups.append({"code": code, "text": short(r["text"], 200), "_id": r["id"]})
                else:
                    par = by_id.get(r.get("parent_id"))
                    leaves.append({"code": code, "text": short(r["text"]), "раздел": f'{par["code"]} {short(par["text"], 120)}' if par else "",
                                   "_id": r["id"]})
    return leaves, groups


def auto_rows():
    """Результат алгоритма: [(ключ класса, part, grade, [уроки с предложением])]."""
    out = []
    if SUBJ == "history":
        A = jload(P.tmp("align_auto.json"))
        for key, rows in A.items():
            part, g = key.split(".g")
            ls = []
            for r in sorted(rows, key=lambda r: r["n"]):
                if r["kind"] == "review":
                    ids = r.get("sections") or ([r["section"]] if r.get("section") else [])
                else:
                    ids = r.get("elements") or ([r["element"]] if r.get("element") else [])
                ls.append(dict(id=r["lesson"], n=r["n"], title=r["title"], kind=r["kind"], auto=ids))
            out.append((key, part, int(g), ls))
    else:
        rows = csv_rows(os.path.join(P.PH, "_авто", "lesson_element_physics.csv"))
        by = defaultdict(list)
        for r in rows:
            by[(r["part"], int(r["grade"]))].append(dict(id=r["lesson_id"], n=int(r["n"]), title=r["title"], kind=r["kind"],
                                                       auto=[x for x in r["element_ids"].split(";") if x]))
        for (part, g), ls in sorted(by.items()):
            out.append((f"{part}.g{g}", part, g, sorted(ls, key=lambda x: x["n"])))
    return out


def main():
    recs = records()
    classes = auto_rows()
    tasks, ctx = [], {}
    for key, part, g, lessons in classes:
        # физика: уроки повторения в начале года и модуль 9 кл. ссылаются на разделы прошлых классов уровня
        first = 7 if part == "OOO" else 10
        extra = tuple(range(first, g)) if SUBJ == "physics" else ()
        leaves, groups = class_elements(recs, part, g, extra)
        id2code = {x["_id"]: x["code"] for x in leaves + groups}
        code2id_new = {x["code"]: x["_id"] for x in leaves}
        code2id_rev = {x["code"]: x["_id"] for x in groups}
        for i, batch in enumerate(chunks(lessons, BATCH)):
            tid = f"{key}.{i + 1:02d}"
            ns = {l["n"] for l in batch}
            lo, hi = min(ns), max(ns)
            neigh = [{"n": l["n"], "title": l["title"]} for l in lessons if lo - 3 <= l["n"] < lo or hi < l["n"] <= hi + 3]
            user = {"предмет": SUBJ, "класс": g,
                    "элементы": [{k: v for k, v in x.items() if not k.startswith("_")} for x in leaves],
                    "разделы": [{k: v for k, v in x.items() if not k.startswith("_")} for x in groups],
                    "уроки": [{"id": l["id"], "n": l["n"], "title": l["title"], "kind": "review" if l["kind"] == "review" else "new",
                               "предложено": [id2code.get(x, x) for x in l["auto"]]} for l in batch],
                    "соседние_уроки": neigh}
            tasks.append((tid, prompt("уроки"), user))
            ctx[tid] = dict(batch=batch, code2id_new=code2id_new, code2id_rev=code2id_rev)

    if mode() == "replay":
        print(f"{STAGE}: задач для модели {len(tasks)} (уроков {sum(len(c['batch']) for c in ctx.values())}); replay — берём прошлые решения")
        copy_replay(OUT_NAME, OUT_NAME)
        return

    def validate_for(tid):
        c = ctx[tid]

        def v(obj):
            errs = []
            res = obj.get("результат") if isinstance(obj, dict) else None
            if not isinstance(res, list):
                return ["нужен объект {\"результат\": [...]}"]
            want = [l["id"] for l in c["batch"]]
            got = [x.get("id") for x in res if isinstance(x, dict)]
            if got != want:
                errs.append(f"нужно ровно по одному объекту на урок в порядке: {want}; получено: {got}")
            kinds = {l["id"]: l["kind"] for l in c["batch"]}
            for x in res:
                if not isinstance(x, dict) or x.get("id") not in kinds:
                    continue
                allowed = c["code2id_rev"] if kinds[x["id"]] == "review" else c["code2id_new"]
                codes = x.get("коды")
                if not isinstance(codes, list):
                    errs.append(f'{x["id"]}: «коды» должны быть списком')
                    continue
                for code in codes:
                    if str(code) not in allowed:
                        what = "разделов" if kinds[x["id"]] == "review" else "элементов"
                        errs.append(f'{x["id"]}: кода {code!r} нет в списке {what}')
            return errs
        return v

    llm = LLM(STAGE)
    answers = llm.ask_many(tasks, validate_for)
    llm.report()
    overrides, meta = {}, {}
    for tid, obj in answers.items():
        c = ctx[tid]
        for x in obj["результат"]:
            l = next(l for l in c["batch"] if l["id"] == x["id"])
            m = c["code2id_rev"] if l["kind"] == "review" else c["code2id_new"]
            ids = [m[str(code)] for code in x["коды"]]
            if set(ids) != set(l["auto"]):
                if SUBJ == "history":
                    overrides[l["id"]] = ids[0] if len(ids) == 1 else (ids or None)
                else:
                    overrides[l["id"]] = [str(code) for code in x["коды"]]
                meta[l["id"]] = dict(урок=l["title"], алгоритм=l["auto"], модель=ids)
    write_overrides(OUT_NAME, overrides, meta)


if __name__ == "__main__":
    run_stage(main)
