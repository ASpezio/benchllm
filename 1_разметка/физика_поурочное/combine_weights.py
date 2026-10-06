#!/usr/bin/env python3
"""Веса элементов физики: базовый план Конструктора + недостающее из углублённого (не больше).
element_weights_physics.csv + deep_fill.json + deep_lessons.json → element_weights_physics_combined.csv"""
import csv, json, os
from collections import defaultdict
H = os.path.dirname(os.path.abspath(__file__))
W = list(csv.DictReader(open(f"{H}/element_weights_physics.csv", encoding="utf-8-sig")))
F = json.load(open(f"{H}/deep_fill.json", encoding="utf-8"))
D = {(l["g"], l["n"]): l["t"] for l in json.load(open(f"{H}/deep_lessons.json", encoding="utf-8"))}
k = {int(g): a / b for g, (a, b) in F["scale"].items()}
add, src = defaultdict(float), defaultdict(list)
for eid, ls in F["fill"].items():
    for g, n, sh in ls:
        add[eid] += sh * k[g]
        src[eid].append(f"{g} кл. урок {n} (доля {sh:g}): {D[(g, n)]}")
leaf = [w for w in W if w["is_section"] == "False"]
base = {w["element_id"]: float(w["lesson_hours"]) for w in leaf}
tot = defaultdict(float)
for w in leaf:
    tot[(w["part"], w["grade"])] += base[w["element_id"]] + add[w["element_id"]]
hours = {e: base[e] + add[e] for e in base}
# разделы: сумма потомков-листьев
for w in W:
    if w["is_section"] == "True":
        pre = w["element_id"] + "."
        hours[w["element_id"]] = sum(hours[x] for x in base if x.startswith(pre))
        add[w["element_id"]] = sum(add[x] for x in base if x.startswith(pre))
out = f"{H}/element_weights_physics_combined.csv"
with open(out, "w", newline="", encoding="utf-8-sig") as f:
    wr = csv.writer(f)
    wr.writerow(["element_id", "part", "grade", "code", "is_section", "category", "text", "hours_base", "hours_from_deep", "hours",
                 "share_of_class_pct", "class_content_hours", "source", "lessons", "deep_lessons", "note"])
    for w in W:
        e = w["element_id"]; T = tot[(w["part"], w["grade"])]
        hb = float(w["lesson_hours"]); hd = round(add[e], 3); h = round(hours[e], 3)
        s = "база+углублённый" if hb and hd else ("углублённый" if hd else ("база" if hb else "нет"))
        wr.writerow([e, w["part"], w["grade"], w["code"], w["is_section"], w["category"], w["text"], hb, hd, h,
                     round(h / T * 100, 2), round(T, 2), s, w["lessons"], " | ".join(src.get(e, [])), F["left_empty"].get(e, "")])
print("добавлено часов:", {g: round(sum(add[e] for e in base if f".g{g}." in e), 2) for g in (10, 11)})
print("итого содержательных:", {f"{p} {g}": round(v, 2) for (p, g), v in tot.items()})
print("элементов без часов:", sum(1 for e in base if hours[e] == 0))
