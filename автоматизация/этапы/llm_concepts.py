#!/usr/bin/env python3
"""LLM извлекает понятия из элементов содержания и пунктов ОГЭ/ЕГЭ (раньше — Claude по ИНСТРУКЦИЯ_извлечение.md).

Наборы задаёт конфиг (понятия.наборы): набор классов предмета или «экзамен» — пункты ОГЭ/ЕГЭ, связанные
с элементами указанных наборов. Для каждого набора пишутся 2_граф/понятия/наборы/in_<имя>.json (вход) и
out_<имя>.json (выход) — в тех же форматах, что пилот, поэтому build_concepts.py собирает их без изменений.
"""
import os
from collections import OrderedDict

import paths as P
from common import cfg, csv_rows, jdump, jload, mode, norm, records, replay_path, setting
from llm import LLM, chunks, prompt, run_stage

TYPES = {
    "history": {"событие", "процесс", "личность", "государство_народ", "место", "документ", "термин",
                "памятник_культуры", "религия_верование", "период"},
    "physics": {"явление", "величина", "закон", "модель", "понятие", "опыт", "прибор", "природное_явление"},
}
DIR = os.path.join(P.G, "понятия", "наборы")
BATCH = int(setting("llm", "элементов_за_запрос_понятия", 6))


def build_sets():
    recs = records()
    by_id = {r["id"]: r for r in recs}
    pos = {r["id"]: i for i, r in enumerate(recs)}
    latex = jload(os.path.join(P.M, "формулы_mineru.json")) if os.path.exists(os.path.join(P.M, "формулы_mineru.json")) else {}
    cat = {}
    wp = os.path.join(P.PH, "element_weights_physics.csv")
    if os.path.exists(wp):
        cat = {r["element_id"]: r["category"] for r in csv_rows(wp) if r.get("category")}
    links = jload(P.tmp("exam_links.json"))["cls"]            # элемент класса -> {"e": пункты экзамена, "d": через другой уровень}

    def item(r):
        par = by_id.get(r.get("parent_id"))
        d = OrderedDict(source_id=r["id"], code=r["code"], text=r["text"])
        if "$" in (latex.get(r["id"]) or ""):
            d["text_latex"] = latex[r["id"]]
        if par:
            d["section"] = f'{par["code"]} {par["text"]}'
        if r["id"] in cat:
            d["category"] = cat[r["id"]]
        return dict(d)

    sets, members = [], {}
    for s in cfg()["понятия"]["наборы"]:
        if s.get("экзамен_для"):
            ids = set()
            for ref in s["экзамен_для"]:
                for eid in members[ref]:
                    row = links.get(eid) or {}
                    ids.update(x for x in row.get("e", []) + row.get("d", []) if not x.endswith(".1-6"))
            items = [item(by_id[i]) for i in sorted(ids) if i in by_id]
        else:
            els = [r for r in recs if r["subject"] == s["предмет"] and r["part"] == s.get("уровень", "OOO")
                   and r["type"] == "element" and r["block"] == "class_codifier" and r["grade"] in s["классы"]
                   and not r.get("is_group")]
            els.sort(key=lambda r: pos[r["id"]])
            members[s["имя"]] = [r["id"] for r in els]
            items = [item(r) for r in els]
        sets.append((s, items))
    return sets


def validator(subj, batch):
    texts = {it["source_id"]: norm(it["text"]) + " || " + norm(it.get("text_latex", "")) for it in batch}

    def v(obj):
        res = obj.get("результат") if isinstance(obj, dict) else None
        if not isinstance(res, list):
            return ["нужен объект {\"результат\": [...]}"]
        want = [it["source_id"] for it in batch]
        got = [x.get("source_id") for x in res if isinstance(x, dict)]
        errs = [] if got == want else [f"нужно ровно по одному объекту на элемент в порядке {want}; получено {got}"]
        for x in res:
            if not isinstance(x, dict) or x.get("source_id") not in texts:
                continue
            sid, cs = x["source_id"], x.get("concepts")
            if not cs or not isinstance(cs, list):
                errs.append(f"{sid}: нет понятий")
                continue
            for c in cs:
                if not isinstance(c, dict) or not c.get("name"):
                    errs.append(f"{sid}: понятие без имени")
                    continue
                if c.get("type") not in TYPES[subj]:
                    errs.append(f"{sid}: тип {c.get('type')!r} у «{c['name']}» — допустимы: {', '.join(sorted(TYPES[subj]))}")
                if c.get("role") not in ("main", "part"):
                    errs.append(f"{sid}: role у «{c['name']}» должен быть main или part")
                ev = c.get("evidence") or ""
                if not ev or norm(ev) not in texts[sid]:
                    errs.append(f"{sid}: evidence {ev!r} у «{c['name']}» не найден в тексте дословно")
        return errs
    return v


def main():
    sets = build_sets()
    old = {}
    rp = replay_path("понятия")
    if mode() == "replay" and rp:
        for f in sorted(os.listdir(rp)):
            if f.startswith("out_") and f.endswith(".json"):
                for o in jload(os.path.join(rp, f)):
                    old[o["source_id"]] = o
    llm = LLM("понятия", replay=lambda tid: {"результат": [old[sid] for sid in ctx[tid]]})
    ctx, tasks, plan = {}, [], []
    for s, items in sets:
        subj = s["предмет"]
        jdump({"set": s["имя"], "items": items}, os.path.join(DIR, f'in_{s["имя"]}.json'))
        tids = []
        for i, batch in enumerate(chunks(items, BATCH)):
            tid = f'{s["имя"]}.{i + 1:03d}'
            ctx[tid] = [it["source_id"] for it in batch]
            tasks.append((tid, prompt("понятия"), {"предмет": subj, "элементы": batch}))
            tids.append((tid, subj, batch))
        plan.append((s, items, tids))
    vals = {tid: validator(subj, batch) for _, _, tids in plan for tid, subj, batch in tids}
    answers = llm.ask_many(tasks, lambda tid: vals[tid])
    llm.report()
    for s, items, tids in plan:
        out = [x for tid, _, _ in tids for x in answers[tid]["результат"]]
        jdump(out, os.path.join(DIR, f'out_{s["имя"]}.json'))
        print(f'{s["имя"]}: элементов {len(items)}, понятий {sum(len(x["concepts"]) for x in out)}')


if __name__ == "__main__":
    run_stage(main)
