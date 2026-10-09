#!/usr/bin/env python3
"""LLM ставит связи между понятиями (раньше — Claude по ИНСТРУКЦИЯ_связи.md, весь набор за раз).

Здесь набор режется на «опорные» понятия: для каждого опорного X модель ставит его предпосылки (A → X)
и связи X → B (вид, часть, участник, подтверждает). Так каждая связь решается один раз, а запрос остаётся
небольшим. Если набор больше config «каталог_целиком_до», в каталог идут не все понятия, а кандидаты:
похожие по словам, из тех же элементов и самые ранние (базовые).

После модели программа: убирает дубли и пары «предпосылка + вид/часть», разрывает циклы и сама ставит
order_issue (предпосылка появляется в программе позже и не в том же элементе).
Выход: 2_граф/связи/наборы/in_<имя>.json и out_<имя>.json в форматах пилота.
"""
import os
import re
from collections import Counter, defaultdict

import paths as P
from common import cfg, jdump, jl, jload, mode, norm, replay_path, setting
from llm import LLM, chunks, prompt, run_stage

DIR = os.path.join(P.G, "связи", "наборы")
TYPES = {"history": {"prerequisites_for", "is_a", "part_of", "participant_of"},
         "physics": {"prerequisites_for", "is_a", "part_of", "verifies"}}
BATCH = int(setting("llm", "опорных_за_запрос", 8))
FULL = int(setting("llm", "каталог_целиком_до", 400))
TOPK = int(setting("llm", "кандидатов_на_понятие", 60))


def build_sets():
    recs = jl(P.REC)
    pos = {r["id"]: i for i, r in enumerate(recs)}
    by_id = {r["id"]: r for r in recs}
    C = {c["id"]: c for c in jl(os.path.join(P.G, "понятия", "concepts.jsonl"))}
    M = jl(os.path.join(P.G, "понятия", "mentions.jsonl"))
    inv = defaultdict(set)                                   # пункт экзамена -> элементы классов
    for cid, v in jload(P.tmp("exam_links.json"))["cls"].items():
        for x in v.get("e", []) + v.get("d", []):
            inv[x].add(cid)
    els_of, ex_of = defaultdict(list), defaultdict(list)
    for m in M:
        src = by_id.get(m["source"])
        if not src:
            continue
        (els_of if src["type"] == "element" else ex_of)[m["target"]].append(m["source"])
    sets = []
    for s in cfg()["связи"]["наборы"]:
        subj, grades = s["предмет"], set(s["классы"])
        cls = [c for c in C.values() if c["subject"] == subj and set(c.get("grades") or []) & grades]
        ids = {c["id"] for c in cls}
        if s.get("с_экзаменом", True):
            set_els = {e for c in cls for e in els_of[c["id"]]}
            for c in C.values():
                if c["subject"] == subj and not c.get("grades") and c["id"] not in ids:
                    linked = {e for x in ex_of[c["id"]] for e in inv[x]}
                    if linked & set_els:
                        cls.append(c); ids.add(c["id"])

        def key(c):
            if c.get("first_element"):
                return (pos[c["first_element"]], c["label"])
            linked = [pos[e] for x in ex_of[c["id"]] for e in inv[x] if e in pos]
            return (min(linked) if linked else 10 ** 9, c["label"])
        cls.sort(key=key)
        items = []
        for i, c in enumerate(cls, 1):
            fe = by_id.get(c.get("first_element") or "")
            if fe:
                first = f'{fe["grade"]} кл., {fe["code"]}: {fe["text"][:150]}'
            else:
                ex = by_id[ex_of[c["id"]][0]]
                first = f'{ex["exam"]} {ex["code"]}: {ex["text"][:150]}'
            els = []
            for e in sorted(set(els_of[c["id"]]), key=lambda e: pos[e]):
                els.append(f'{by_id[e]["code"]} ({by_id[e]["grade"]} кл.)')
            for x in sorted(set(ex_of[c["id"]]), key=lambda e: pos[e]):
                if not c.get("grades"):
                    els.append(f'{by_id[x]["exam"]} {by_id[x]["code"]}')
            d = {"id": c["id"], "name": c["label"], "type": c["ctype"], "order": i, "first": first, "elements": els}
            if c.get("formulas"):
                d["formulas"] = c["formulas"]
            if c.get("aliases"):
                d["aliases"] = c["aliases"]
            items.append(d)
        sets.append((s, items))
    return sets


def tfidf_neighbors(items):
    """Похожие по словам понятия: TF-IDF по n-граммам символов (имя + текст элемента первого появления)."""
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    docs = [norm(it["name"] + " " + it["name"] + " " + it["first"].split(":", 1)[-1]) for it in items]
    X = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True).fit_transform(docs)
    S = (X @ X.T).toarray()
    np.fill_diagonal(S, -1)

    def top(i, k):
        return [int(j) for j in np.argsort(-S[i])[:k]]
    return top


def catalog_for(items, batch_idx, top):
    if len(items) <= FULL:
        return items
    pick = set(batch_idx) | set(range(min(40, len(items))))       # опорные + самые ранние (базовые) понятия
    for i in batch_idx:
        pick.update(top(i, TOPK))
        els = set(items[i]["elements"])
        pick.update(j for j, it in enumerate(items) if els & set(it["elements"]))
    return [items[j] for j in sorted(pick)]


def compact(it):
    return {"id": it["id"], "name": it["name"], "type": it["type"], "order": it["order"],
            "first": it["first"].split(":", 1)[0]}


def anchored(r, x):
    return (r["target"] == x) if r["type"] == "prerequisites_for" else (r["source"] == x)


def validator(subj, anchors, cat_ids, types):
    def v(obj):
        res = obj.get("результат") if isinstance(obj, dict) else None
        if not isinstance(res, list):
            return ["нужен объект {\"результат\": [...]}"]
        want = [a["id"] for a in anchors]
        got = [x.get("id") for x in res if isinstance(x, dict)]
        errs = [] if got == want else [f"нужно по одному объекту на опорное понятие в порядке {want}; получено {got}"]
        for x in res:
            if not isinstance(x, dict):
                continue
            for r in x.get("связи") or []:
                a, b, t = r.get("source"), r.get("target"), r.get("type")
                tag = f"{a} → {b} ({t})"
                if a not in cat_ids or b not in cat_ids:
                    errs.append(f"{tag}: id нет в каталоге"); continue
                if t not in TYPES[subj]:
                    errs.append(f"{tag}: тип {t!r} не подходит, допустимы {sorted(TYPES[subj])}")
                if a == b:
                    errs.append(f"{tag}: связь понятия с самим собой")
                if not anchored(r, x.get("id")):
                    errs.append(f"{tag}: для опорного {x.get('id')} предпосылка должна идти в него (target = опорное), "
                                f"остальные связи — из него (source = опорное)")
                if t == "participant_of" and types.get(a) != "личность":
                    errs.append(f"{tag}: participant_of ставится только от личности")
                if t == "verifies" and types.get(a) != "опыт":
                    errs.append(f"{tag}: verifies ставится только от опыта")
                if not (r.get("why") or "").strip():
                    errs.append(f"{tag}: нет why")
        return errs
    return v


def clean(rels, items):
    """Дубли, пары «предпосылка + вид/часть», циклы; order_issue по порядку в программе."""
    C = {it["id"]: it for it in items}
    out, seen = [], set()
    for r in rels:
        k = (r["source"], r["target"], r["type"])
        if k not in seen:
            seen.add(k); out.append(r)
    pair = defaultdict(set)
    for r in out:
        pair[frozenset((r["source"], r["target"]))].add(r["type"])
    out = [r for r in out if not (r["type"] == "prerequisites_for" and pair[frozenset((r["source"], r["target"]))] & {"is_a", "part_of"})]
    log = []
    for t in ("prerequisites_for", "is_a", "part_of"):
        while True:
            g = defaultdict(list)
            for r in out:
                if r["type"] == t:
                    g[r["source"]].append(r)
            cyc = find_cycle(g)
            if not cyc:
                break
            worst = max(cyc, key=lambda r: C[r["source"]]["order"] - C[r["target"]]["order"])
            out.remove(worst)
            log.append(f'цикл {t}: убрана {C[worst["source"]]["name"]} → {C[worst["target"]]["name"]}')
    for r in out:
        r.pop("order_issue", None)
        if r["type"] == "prerequisites_for":
            a, b = C[r["source"]], C[r["target"]]
            if a["order"] > b["order"] and not set(a["elements"]) & set(b["elements"]):
                r["order_issue"] = True
    return out, log


def find_cycle(g):
    """Цикл в графе {вершина: [рёбра]} как список рёбер или None."""
    color, stack = {}, []

    def dfs(u):
        color[u] = 1
        for r in g.get(u, []):
            v = r["target"]
            if color.get(v) == 1:
                i = next((k for k, e in enumerate(stack) if e["source"] == v), len(stack))
                return stack[i:] + [r]
            if not color.get(v):
                stack.append(r)
                c = dfs(v)
                if c:
                    return c
                stack.pop()
        color[u] = 2
        return None
    for u in list(g):
        if not color.get(u):
            c = dfs(u)
            if c:
                return c
    return None


def main():
    sets = build_sets()
    old = []
    rp = replay_path("связи")
    if mode() == "replay" and rp:
        for f in sorted(os.listdir(rp)):
            if f.startswith("out_") and f.endswith(".json"):
                old += jload(os.path.join(rp, f))
    ctx, tasks, plan = {}, [], []

    def replay(tid):
        return {"результат": [{"id": x, "связи": [r for r in old if anchored(r, x)]} for x in ctx[tid]]}

    llm = LLM("связи", replay=replay)
    vals = {}
    for s, items in sets:
        subj = s["предмет"]
        jdump({"set": s["имя"], "concepts": items}, os.path.join(DIR, f'in_{s["имя"]}.json'))
        top = tfidf_neighbors(items) if len(items) > FULL else None
        types = {it["id"]: it["type"] for it in items}
        tids = []
        for i, idx in enumerate(chunks(range(len(items)), BATCH)):
            tid = f'{s["имя"]}.{i + 1:03d}'
            anchors = [items[j] for j in idx]
            cat = catalog_for(items, idx, top)
            ctx[tid] = [a["id"] for a in anchors]
            vals[tid] = validator(subj, anchors, {c["id"] for c in cat}, types)
            tasks.append((tid, prompt("связи"), {"предмет": subj, "опорные": anchors, "каталог": [compact(c) for c in cat]}))
            tids.append(tid)
        plan.append((s, items, tids))
    answers = llm.ask_many(tasks, lambda tid: vals[tid])
    llm.report()
    for s, items, tids in plan:
        rels = []
        for tid in tids:
            for x in answers[tid]["результат"]:
                for r in x.get("связи") or []:
                    d = {"source": r["source"], "target": r["target"], "type": r["type"], "why": r.get("why", "")}
                    rels.append(d)
        rels, log = clean(rels, items)
        jdump(rels, os.path.join(DIR, f'out_{s["имя"]}.json'))
        deg = Counter(x for r in rels for x in (r["source"], r["target"]))
        print(f'{s["имя"]}: понятий {len(items)}, связей {len(rels)} {dict(Counter(r["type"] for r in rels))}, '
              f'order_issue {sum(1 for r in rels if r.get("order_issue"))}, без связей {sum(1 for it in items if not deg[it["id"]])}')
        for line in log:
            print("  ", line)


if __name__ == "__main__":
    run_stage(main)
