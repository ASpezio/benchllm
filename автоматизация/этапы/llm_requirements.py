#!/usr/bin/env python3
"""LLM проверяет связь «умение класса → требование ОГЭ/ЕГЭ».

Вход: промежуточное/req_auto.json (req_map.py без правок: правила по ключевым словам).
Выход: решения/req_overrides.json — только умения, где решение модели отличается от правил.
"""
from collections import defaultdict

import paths as P
from common import copy_replay, jload, mode, records, setting, short, write_overrides
from llm import LLM, chunks, prompt, run_stage

BATCH = int(setting("llm", "умений_за_запрос", 20))


def main():
    recs = records()
    by_id = {r["id"]: r for r in recs}
    auto = jload(P.tmp("req_auto.json"))
    groups = defaultdict(list)
    for rid, v in auto.items():
        r = by_id[rid]
        groups[(r["subject"], r["part"])].append((rid, v))
    tasks, ctx = [], {}
    for (subj, part), items in sorted(groups.items()):
        exam = "ОГЭ" if part == "OOO" else "ЕГЭ"
        ex = [r for r in recs if r["subject"] == subj and r["part"] == part and r["type"] == "exam_requirement"
              and not r.get("is_group")]
        codes = {r["code"]: r["id"] for r in ex}
        id2code = {v: k for k, v in codes.items()}
        catalog = [{"code": r["code"], "text": short(r["text"], 400)} for r in ex]
        items.sort(key=lambda x: (by_id[x[0]]["grade"], x[0]))
        for i, batch in enumerate(chunks(items, BATCH)):
            tid = f"{subj}.{part}.{i + 1:03d}"
            reqs = []
            for rid, v in batch:
                r = by_id[rid]
                par = by_id.get(r.get("parent_id"))
                reqs.append({"id": rid, "класс": r["grade"], "code": r["code"], "text": short(r["text"]),
                             "группа": f'{par["code"]} {short(par["text"], 150)}' if par else (r.get("group") or ""),
                             "предложено": [id2code.get(x, x) for x in v["e"]], "почему": v.get("why", "")})
            tasks.append((tid, prompt("умения"), {"предмет": subj, "экзамен": exam, "требования_экзамена": catalog, "умения": reqs}))
            ctx[tid] = dict(batch=batch, codes=codes, id2code=id2code)

    if mode() == "replay":
        print(f"умения: задач для модели {len(tasks)}; replay — берём прошлые решения")
        copy_replay("req_overrides.json", "req_overrides.json")
        return

    def validate_for(tid):
        c = ctx[tid]

        def v(obj):
            res = obj.get("результат") if isinstance(obj, dict) else None
            if not isinstance(res, list):
                return ["нужен объект {\"результат\": [...]}"]
            want = [rid for rid, _ in c["batch"]]
            got = [x.get("id") for x in res if isinstance(x, dict)]
            errs = [] if got == want else [f"нужно по одному объекту на умение в порядке {want}; получено {got}"]
            for x in res:
                if isinstance(x, dict):
                    ks = x.get("коды")
                    if not isinstance(ks, list):
                        errs.append(f'{x.get("id")}: «коды» должны быть списком')
                    else:
                        errs += [f'{x.get("id")}: требования {k!r} нет в списке' for k in ks if str(k) not in c["codes"]]
            return errs
        return v

    llm = LLM("умения")
    answers = llm.ask_many(tasks, validate_for)
    llm.report()
    overrides, meta = {}, {}
    for tid, obj in answers.items():
        c = ctx[tid]
        auto_by = dict(c["batch"])
        for x in obj["результат"]:
            ks = [str(k) for k in x["коды"]]
            before = [c["id2code"].get(e, e) for e in auto_by[x["id"]]["e"]]
            if set(ks) != set(before) or auto_by[x["id"]]["m"] == "none":
                overrides[x["id"]] = ks
                meta[x["id"]] = dict(правила=before, модель=ks)
    write_overrides("req_overrides.json", overrides, meta)


if __name__ == "__main__":
    run_stage(main)
