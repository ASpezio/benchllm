#!/usr/bin/env python3
"""Встраивает поурочное и тематическое планирование по физике (Конструктор edsoo) в данные навигатора.

data.json (дерево навигатора) + выход build_physics.py -> data_new.json
"""
import csv
import json
import sys
from collections import defaultdict

PH = sys.argv[1] if len(sys.argv) > 1 else "../phys"
D = json.load(open("data.json", encoding="utf-8"))

lessons = [json.loads(l) for l in open(f"{PH}/records_physics_lessons.jsonl", encoding="utf-8")]
links = {r["lesson_id"]: r for r in csv.DictReader(open(f"{PH}/lesson_element_physics.csv", encoding="utf-8-sig"))}
weights = {r["element_id"]: r for r in csv.DictReader(open(f"{PH}/element_weights_physics.csv", encoding="utf-8-sig"))}
themes = list(csv.DictReader(open(f"{PH}/themes_physics.csv", encoding="utf-8-sig")))
tpages = json.load(open(f"{PH}/theme_pages.json", encoding="utf-8"))

SRC = {"OOO": "c79", "SOO": "c1011"}
GRADES = {"OOO": [7, 8, 9], "SOO": [10, 11]}

nodes = {}


def walk(n):
    nodes[n["i"]] = n
    for c in n.get("c", []) or []:
        walk(c)
    for r in n.get("r", []) or []:
        nodes[r["i"]] = r


for p in D["tree"]:
    walk(p)


def num(x):
    x = float(x)
    return int(x) if x == int(x) else x


# ------------------------------------------------------------------ уроки
for part in ("OOO", "SOO"):
    subj = nodes[f"{part}.physics"]
    tables = []
    for g in GRADES[part]:
        L = sorted([l for l in lessons if l["part"] == part and l["grade"] == g], key=lambda l: l["lesson_n"])
        recs = []
        for l in L:
            k = links[l["id"]]
            le = [x for x in k["element_ids"].split(";") if x]
            r = {"i": l["id"], "c": l["code"], "x": l["text"], "pg": l["page"], "ty": "lesson",
                 "lk": l["lesson_kind"], "h": num(l["hours"]), "le": le, "m": k["method"], "lt": l["lesson_type"]}
            if k["share"] and len(le) > 1:
                sh = [float(s) for s in k["share"].split(";")]
                if max(sh) - min(sh) > 0.01:
                    r["sh"] = sh
            if l["control_works"]:
                r["kr"] = num(l["control_works"])
            if l["practical_works"]:
                r["pr"] = num(l["practical_works"])
            if "vpr" in l["flags"]:
                r["f"] = ["vpr"]
            recs.append(r)
        tables.append({"i": f"{part}.physics.les.g{g}", "t": "table", "l": f"{g} класс · уроки", "s": "",
                       "pg": recs[0]["pg"], "pe": recs[-1]["pg"], "sn": [f"{g} КЛАСС"], "n": len(recs),
                       "rev": sum(r["lk"] == "review" for r in recs), "r": recs})
    les_block = {"i": f"{part}.physics.les@constructor", "t": "block", "l": "Поурочное планирование",
                 "s": "Конструктор edsoo", "src": SRC[part], "pg": tables[0]["pg"], "pe": tables[-1]["pe"],
                 "sn": ["ПОУРОЧНОЕ ПЛАНИРОВАНИЕ"], "c": tables}

    # ------------------------------------------------------------- тематическое планирование ФРП
    ttables = []
    for g in GRADES[part]:
        T = [t for t in themes if t["part"] == part and int(t["grade"]) == g]
        recs, last_pg = [], None
        sec_rec = None
        for t in T:
            if t["theme"] == "Резервное время":
                pg = tpages.get(f"{part}.{g}.reserve", last_pg)
                recs.append({"i": f"{part}.physics.thm.g{g}.reserve", "c": "—", "x": "Резервное время", "pg": pg,
                             "ty": "theme", "h": num(t["hours"])})
                continue
            sec = t["section_no"]
            if not sec_rec or sec_rec["c"] != sec:
                sec_rec = {"i": f"{part}.physics.thm.g{g}.{sec}", "c": sec, "x": t["section"],
                           "pg": tpages.get(f"{part}.{g}.{sec}"), "ty": "theme", "ig": 1, "h": 0}
                recs.append(sec_rec)
            pg = tpages.get(f"{part}.{g}.{t['theme_code']}", sec_rec["pg"])
            last_pg = pg
            r = {"i": f"{part}.physics.thm.g{g}.{t['theme_code']}", "c": t["theme_code"], "x": t["theme"], "pg": pg,
                 "ty": "theme", "h": num(t["hours"]), "p": sec_rec["i"]}
            if float(t["control"] or 0):
                r["kr"] = num(t["control"])
            if float(t["practical"] or 0):
                r["pr"] = num(t["practical"])
            sec_rec["h"] = num(sec_rec["h"] + float(t["hours"]))
            recs.append(r)
        ttables.append({"i": f"{part}.physics.thm.g{g}", "t": "table", "l": f"{g} класс · темы", "s": "",
                        "pg": recs[0]["pg"], "pe": recs[-1]["pg"], "sn": [f"{g} КЛАСС"],
                        "n": sum(1 for r in recs if not r.get("ig")), "r": recs})
    thm_block = {"i": f"{part}.physics.thm@frp", "t": "block", "l": "Тематическое планирование ФРП",
                 "s": "часы по темам", "src": SRC[part], "pg": ttables[0]["pg"], "pe": ttables[-1]["pe"],
                 "sn": ["ТЕМАТИЧЕСКОЕ ПЛАНИРОВАНИЕ"], "c": ttables}

    subj["c"] = [b for b in subj["c"] if b["i"] not in (les_block["i"], thm_block["i"])]
    subj["c"] = [les_block, thm_block] + subj["c"]

# ------------------------------------------------------------------ веса элементов
for eid, w in weights.items():
    e = nodes.get(eid)
    if not e:
        raise SystemExit(f"нет элемента {eid}")
    e["wh"] = num(round(float(w["lesson_hours"]), 2))
    e["ws"] = num(round(float(w["share_of_class_pct"]), 2))
    e["wl"] = [x for x in w["lessons"].split(";") if x] if not e.get("ig") else []
    e["wr"] = [x for x in w["review_lessons"].split(";") if x]

# часы за пунктами ОГЭ/ЕГЭ: как у истории — вес элемента класса делится между его пунктами экзамена
for x in nodes.values():
    if x.get("ty") != "exam_element" or ".physics." not in x["i"] or x.get("ig"):
        continue
    s = 0.0
    for c in x.get("xc", []):
        C = nodes.get(c)
        if C and not C.get("ig") and x["i"] in C.get("xe", []) and C.get("wh") is not None:
            s += C["wh"] / len(C["xe"])
    x["xh"] = num(round(s, 2))
kids = defaultdict(list)
for x in nodes.values():
    if x.get("ty") == "exam_element" and ".physics." in x["i"] and x.get("p"):
        kids[x["p"]].append(x)
for x in nodes.values():
    if x.get("ty") == "exam_element" and ".physics." in x["i"] and x.get("ig"):
        x["xh"] = num(round(sum(k.get("xh", 0) for k in kids[x["i"]]), 2))

D["meta"]["records"] = D["meta"].get("records", 0) + len(lessons)
D["meta"]["sources"] = {
    "c79": "Конструктор рабочих программ edsoo.ru, «Физика. Базовый уровень» 7–9 кл., ID 12372761",
    "c1011": "Конструктор рабочих программ edsoo.ru, «Физика. Базовый уровень» 10–11 кл., ID 12372794",
}
json.dump(D, open("data_new.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("ok", len(lessons), "уроков;", sum(1 for t in themes), "строк тематического")
