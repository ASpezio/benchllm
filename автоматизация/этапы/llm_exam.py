#!/usr/bin/env python3
"""LLM проверяет связь «элемент содержания класса → пункт кодификатора ОГЭ/ЕГЭ».

Вход: промежуточное/exam_auto.json (exam_map.py без правок). Выход: решения/exam_overrides.json —
только элементы, где решение модели отличается от алгоритма (формат старых ручных правок).
"""
from collections import defaultdict

import paths as P
from common import copy_replay, jload, mode, records, setting, short, write_overrides
from llm import LLM, chunks, prompt, run_stage

BATCH = int(setting("llm", "элементов_за_запрос", 10))


def main():
    recs = records()
    by_id = {r["id"]: r for r in recs}
    auto = jload(P.tmp("exam_auto.json"))
    groups = defaultdict(list)
    for cid, v in auto.items():
        r = by_id[cid]
        if v.get("method") == "region":            # «Наш край»: на экзамен не выносится — модель не спрашиваем
            continue
        groups[(r["subject"], r["part"])].append((cid, v))
    tasks, ctx = [], {}
    for (subj, part), items in sorted(groups.items()):
        exam = "ОГЭ" if part == "OOO" else "ЕГЭ"
        ex = [r for r in recs if r["subject"] == subj and r["part"] == part and r["type"] == "exam_element"
              and not r.get("is_group") and r["code"] != "1-6"]
        code2id = {r["code"]: r["id"] for r in ex}
        id2code = {v: k for k, v in code2id.items()}
        catalog = []
        for r in ex:
            par = by_id.get(r.get("parent_id"))
            catalog.append({"code": r["code"], "text": short(r["text"], 300),
                            "раздел": f'{par["code"]} {short(par["text"], 100)}' if par else ""})
        items.sort(key=lambda x: (by_id[x[0]]["grade"], x[0]))
        for i, batch in enumerate(chunks(items, BATCH)):
            tid = f"{subj}.{part}.{i + 1:03d}"
            els = []
            for cid, v in batch:
                r = by_id[cid]
                par = by_id.get(r.get("parent_id"))
                els.append({"id": cid, "класс": r["grade"], "code": r["code"], "text": short(r["text"]),
                            "раздел": f'{par["code"]} {short(par["text"], 120)}' if par else "",
                            "предложено": [id2code.get(x, x) for x in v["ids"]],
                            "другие_кандидаты": [id2code.get(x, x) for x in v.get("alt", [])]})
            tasks.append((tid, prompt("экзамен"), {"предмет": subj, "экзамен": exam, "пункты_экзамена": catalog, "элементы": els}))
            ctx[tid] = dict(batch=batch, code2id=code2id)

    if mode() == "replay":
        print(f"экзамен: задач для модели {len(tasks)}; replay — берём прошлые решения")
        copy_replay("exam_overrides.json", "exam_overrides.json")
        return

    def validate_for(tid):
        c = ctx[tid]

        def v(obj):
            res = obj.get("результат") if isinstance(obj, dict) else None
            if not isinstance(res, list):
                return ["нужен объект {\"результат\": [...]}"]
            want = [cid for cid, _ in c["batch"]]
            got = [x.get("id") for x in res if isinstance(x, dict)]
            errs = [] if got == want else [f"нужно по одному объекту на элемент в порядке {want}; получено {got}"]
            for x in res:
                if not isinstance(x, dict):
                    continue
                codes = x.get("коды")
                if not isinstance(codes, list):
                    errs.append(f'{x.get("id")}: «коды» должны быть списком')
                    continue
                errs += [f'{x.get("id")}: пункта {k!r} нет в кодификаторе экзамена' for k in codes if str(k) not in c["code2id"]]
            return errs
        return v

    llm = LLM("экзамен")
    answers = llm.ask_many(tasks, validate_for)
    llm.report()
    overrides, meta = {}, {}
    for tid, obj in answers.items():
        c = ctx[tid]
        auto_by = dict(c["batch"])
        for x in obj["результат"]:
            ids = [c["code2id"][str(k)] for k in x["коды"]]
            if set(ids) != set(auto_by[x["id"]]["ids"]):
                overrides[x["id"]] = ids
                meta[x["id"]] = dict(алгоритм=auto_by[x["id"]]["ids"], модель=ids)
    write_overrides("exam_overrides.json", overrides, meta)


if __name__ == "__main__":
    run_stage(main)
