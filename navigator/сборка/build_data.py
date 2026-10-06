#!/usr/bin/env python3
"""Собирает компактное дерево для навигатора из index.json + records.jsonl."""
import json, sys, re
import os as _os
K = _os.path.dirname(_os.path.abspath(__file__))           # navigator/сборка
ROOT = _os.path.normpath(_os.path.join(K, "..", ".."))   # корень проекта «SyllaBench»
M = _os.path.join(ROOT, "1_разметка")
from collections import defaultdict

IDX = _os.path.join(M, "index.json")
REC = _os.path.join(M, "records.jsonl")

index = json.load(open(IDX, encoding="utf-8"))
records = [json.loads(l) for l in open(REC, encoding="utf-8")]

PART_WORD = {"NOO": "начального", "OOO": "основного", "SOO": "среднего"}
PART_SHORT = {"NOO": "НОО", "OOO": "ООО", "SOO": "СОО"}
BLOCK_LABEL = {"lessons": "Поурочное планирование",
               "class_codifier": "Кодификатор по классам",
               "meta_codifier": "Метапредметный кодификатор"}
BLOCK_HEAD = {"lessons": "Поурочное", "class_codifier": "В федеральных",
              "meta_codifier": "В федеральных", "exam_codifier": "Для проведения"}
KIND_LABEL = {"requirements": "Требования", "elements": "Элементы содержания",
              "meta": "Метапредметные требования", "unknown": "Таблица"}


def rec_key(r):
    if r["type"] == "lesson":
        return f'{r["part"]}.{r["subject"]}.les.g{r["grade"]}'
    base = r["id"].split("~")[0]
    return base[: -(len(r["code"]) + 1)]


by_table = defaultdict(list)
for r in records:
    by_table[rec_key(r)].append(r)


W = json.load(open(_os.path.join(K, "weights.json"), encoding="utf-8"))
XL = json.load(open(_os.path.join(K, "exam_links.json"), encoding="utf-8"))
RL = json.load(open(_os.path.join(K, "req_links.json"), encoding="utf-8"))


def compact(r):
    d = {"i": r["id"], "c": r["code"], "x": r["text"], "pg": r["page"], "ty": r["type"]}
    if r.get("verb"):
        words = re.findall(r"[А-Яа-яЁё-]+", r["text"].lower())
        verbs = [w for w in words[:12] if re.search(r"(ть|ться|ти)$", w)]
        r = dict(r, verb=verbs[0] if verbs else r["verb"])
    for src, dst in (("lesson_kind", "lk"), ("hours", "h"), ("verb", "v"), ("parent_id", "p"), ("group", "g")):
        if r.get(src) not in (None, ""):
            d[dst] = r[src]
    if r.get("is_group"):
        d["ig"] = 1
    if r.get("flags"):
        d["f"] = r["flags"]
    if r["id"] in W["lessons"]:
        d["le"] = W["lessons"][r["id"]]["e"]
        d["m"] = W["lessons"][r["id"]]["m"]
    if r["id"] in XL["cls"]:
        x = XL["cls"][r["id"]]
        d["xe"], d["xm"] = x["e"], x["m"]
        if x["d"]:
            d["xd"] = x["d"]
    if r["id"] in XL["exam"]:
        x = XL["exam"][r["id"]]
        d["xc"] = x["c"]
        if x["h"] is not None:
            d["xh"] = x["h"]
    if r["id"] in RL["cls"]:
        x = RL["cls"][r["id"]]
        d["re"], d["rm"] = x["e"], x["m"]
        if not x["e"]:
            d["rn"] = x["why"]
    if r["id"] in RL["exam"]:
        d["rc"] = RL["exam"][r["id"]]
    if r["id"] in W["weights"]:
        x = W["weights"][r["id"]]
        d["wh"], d["ws"], d["wl"], d["wr"] = x["h"], x["s"], x["l"], x["r"]
    return d


tree, used = [], set()
for p in index["parts"]:
    pn = {"i": p["id"], "t": "part", "l": f'ФОП {PART_SHORT[p["id"]]}', "s": p["title"].split("(")[-1].rstrip(")"),
          "note": p["amends"], "pg": p["pages"][0], "pe": p["pages"][1],
          "sn": [f'программе {PART_WORD[p["id"]]} общего образования'], "c": []}
    for s in p["subjects"]:
        sn = {"i": s["id"], "t": "subj", "l": s["name"], "pg": s["pages"][0], "pe": s["pages"][1],
              "parsed": 1 if s["parsed"] else 0, "c": []}
        for b in s["blocks"]:
            bid = f'{b["id"]}@{b["punkt"]}'
            lab = (f'Кодификатор {b["exam"]}' if b["type"] == "exam_codifier" else BLOCK_LABEL[b["type"]])
            bn = {"i": bid, "t": "block", "l": lab, "s": f'п. {b["punkt"]}', "pg": b["pages"][0], "pe": b["pages"][1],
                  "sn": [f'{b["punkt"]} {BLOCK_HEAD[b["type"]]}'], "c": []}
            for t in b["tables"]:
                g = t.get("grade")
                if t["kind"] == "lessons":
                    key = f'{b["id"]}.g{g}'
                    lab_t = f'{g} класс · уроки'
                    sn_t = [f'{g} класс']
                else:
                    k = {"requirements": "req", "elements": "el"}.get(t["kind"], "x")
                    key = f'{b["id"]}{".g" + str(g) if g else ""}.{k}'
                    lab_t = KIND_LABEL.get(t["kind"], "Таблица") + (f' · {g} класс' if g else "")
                    sn_t = [f'Таблица {t["table_no"]}'] if t.get("table_no") else []
                tid = key if key not in used else f'{key}@{t["pages"][0]}'
                used.add(tid)
                tn = {"i": tid, "t": "table", "l": lab_t, "s": (f'табл. {t["table_no"]}' if t.get("table_no") else ""),
                      "pg": t["pages"][0], "pe": t["pages"][1], "sn": sn_t}
                recs = by_table.get(key) if s["parsed"] else None
                if recs:
                    tn["r"] = [compact(r) for r in recs]
                    tn["n"] = len(recs)
                    if t["kind"] == "lessons":
                        tn["rev"] = sum(r["lesson_kind"] == "review" for r in recs)
                bn["c"].append(tn)
            sn["c"].append(bn)
        pn["c"].append(sn)
    tree.append(pn)

meta = {"title": index["document_title"], "in_force": index["in_force"], "pages": index["pages"],
        "status": index["status"], "records": len(records)}
out = json.dumps({"meta": meta, "tree": tree}, ensure_ascii=False, separators=(",", ":"))
open(_os.path.join(K, "data.json"), "w", encoding="utf-8").write(out)
lost = set(by_table) - {k for k in by_table if any(k in json.dumps(1) for _ in [0])}
print("bytes", len(out.encode()), "records", len(records))
# проверка: все ли записи попали в дерево
placed = sum(len(tn.get("r", [])) for pn in tree for sn in pn["c"] for bn in sn["c"] for tn in bn["c"])
print("placed", placed)
