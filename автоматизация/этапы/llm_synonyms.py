#!/usr/bin/env python3
"""LLM находит разные имена одного понятия (раньше — ручной словарь 2_граф/понятия/синонимы.json).

Имена берутся из out_*.json этапа «понятия» и группируются по предмету и типу; модель получает список
имён одного типа и возвращает группы синонимов. Результат — решения/синонимы.json в старом формате.
"""
import os
import re
from collections import defaultdict

import paths as P
from common import copy_replay, jdump, jload, mode, norm, setting
from llm import LLM, chunks, prompt, run_stage

DIR = os.path.join(P.G, "понятия", "наборы")
LIMIT = int(setting("llm", "имён_за_запрос", 150))


def main():
    names = defaultdict(dict)                # (предмет, тип) -> {norm: имя}
    subj_of = {}
    for f in sorted(os.listdir(DIR)):
        if f.startswith("in_"):
            for it in jload(os.path.join(DIR, f))["items"]:
                subj_of[it["source_id"]] = "history" if ".history." in it["source_id"] else "physics"
    for f in sorted(os.listdir(DIR)):
        if f.startswith("out_"):
            for o in jload(os.path.join(DIR, f)):
                subj = subj_of.get(o["source_id"], "history" if ".history." in o["source_id"] else "physics")
                for c in o["concepts"]:
                    names[(subj, c["type"])].setdefault(norm(c["name"]), c["name"])
    tasks, ctx = [], {}
    for (subj, typ), d in sorted(names.items()):
        if len(d) < 2:
            continue
        # сортировка по «основе» (без первых букв-приставок не мудрим): похожие имена окажутся в одном запросе
        lst = sorted(d.values(), key=lambda s: re.sub(r"[^а-яa-z0-9 ]", "", norm(s)))
        for i, part in enumerate(chunks(lst, LIMIT)):
            tid = f"{subj}.{typ}.{i + 1:02d}"
            tasks.append((tid, prompt("синонимы"), {"предмет": subj, "тип": typ, "имена": part}))
            ctx[tid] = (subj, part)

    if mode() == "replay":
        print(f"синонимы: задач для модели {len(tasks)}; replay — берём прошлый словарь")
        copy_replay("синонимы.json", "синонимы.json")
        return

    def validate_for(tid):
        allowed = {norm(x): x for x in ctx[tid][1]}

        def v(obj):
            gs = obj.get("группы") if isinstance(obj, dict) else None
            if not isinstance(gs, list):
                return ["нужен объект {\"группы\": [...]}"]
            errs, seen = [], set()
            for g in gs:
                if not isinstance(g, dict):
                    errs.append("группа должна быть объектом"); continue
                can, var = g.get("каноническое"), g.get("варианты") or []
                if norm(can or "") not in allowed:
                    errs.append(f"каноническое имя {can!r} должно быть из списка")
                for x in [can] + list(var):
                    if norm(x or "") not in allowed:
                        errs.append(f"имени {x!r} нет в списке")
                    elif norm(x) in seen:
                        errs.append(f"имя {x!r} попало в несколько групп")
                    seen.add(norm(x or ""))
            return errs
        return v

    llm = LLM("синонимы")
    answers = llm.ask_many(tasks, validate_for)
    llm.report()
    out = {"_": "Варианты имён одного понятия → каноническое имя (внутри предмета). Составлено этапом «синонимы» (LLM).",
           "physics": {}, "history": {}}
    for tid, obj in answers.items():
        subj = ctx[tid][0]
        for g in obj["группы"]:
            for x in g.get("варианты") or []:
                if norm(x) != norm(g["каноническое"]):
                    out[subj][x] = g["каноническое"]
    jdump(out, P.dec("синонимы.json"))
    print("синонимов:", {k: len(v) for k, v in out.items() if k != "_"})


if __name__ == "__main__":
    run_stage(main)
