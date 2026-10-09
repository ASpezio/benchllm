#!/usr/bin/env python3
"""Веса элементов содержания истории по учебному времени.

вес элемента = сумма часов содержательных уроков, отнесённых к элементу
               (урок на несколько элементов делится поровну);
доля         = вес / все содержательные часы класса.
Уроки повторения/контроля в вес не входят — считаются отдельно по разделам.
"""
import paths as _P  # пути прогона (автоматизация/этапы/paths.py)
import csv, json
from collections import defaultdict

REC = _P.REC
A = json.load(open(_P.tmp("align_out.json"), encoding="utf-8"))
recs = {json.loads(l)["id"]: json.loads(l) for l in open(REC, encoding="utf-8")}
OUT = _P.M
import os; os.makedirs(OUT, exist_ok=True)

lesson_rows, w, wl, rev = [], defaultdict(float), defaultdict(list), defaultdict(list)
class_hours = defaultdict(float)
for key, rows in A.items():
    for r in rows:
        les = recs[r["lesson"]]
        h = les.get("hours") or 1
        if r["kind"] == "review":
            secs = r.get("sections") or ([r["section"]] if r.get("section") else [])
            for s in secs:
                rev[s].append(r["lesson"])
            lesson_rows.append(dict(lesson_id=r["lesson"], part=les["part"], grade=les["grade"], n=les["lesson_n"],
                                    title=les["text"], kind="review", element_ids=";".join(secs),
                                    codes=r.get("section_code") or "", share="", method=r["method"], score=""))
            continue
        els = r.get("elements") or ([r["element"]] if r.get("element") else [])
        class_hours[key] += h
        for e in els:
            w[e] += h / len(els)
            wl[e].append(r["lesson"])
        lesson_rows.append(dict(lesson_id=r["lesson"], part=les["part"], grade=les["grade"], n=les["lesson_n"],
                                title=les["text"], kind=r["kind"], element_ids=";".join(els),
                                codes=r.get("code") or "", share=round(1 / len(els), 3) if els else "",
                                method=r["method"], score=r.get("score") if r["method"] == "auto" else ""))

with open(f"{OUT}/lesson_element.csv", "w", newline="", encoding="utf-8-sig") as f:
    wr = csv.DictWriter(f, fieldnames=list(lesson_rows[0].keys()))
    wr.writeheader(); wr.writerows(lesson_rows)

# веса по всем элементам классных кодификаторов истории (в т.ч. с нулём уроков) + элемент ОГЭ 6
el_rows, weights = [], {}
for e in recs.values():
    if e["subject"] != "history" or e["type"] not in ("element", "exam_element"):
        continue
    if e["block"] == "class_codifier":
        key = f'{e["part"]}.g{e["grade"]}'
    elif e["id"] in w:
        key = "OOO.g9"
    else:
        continue
    tot = class_hours[key]
    if e.get("is_group"):
        hours = sum(v for k, v in w.items() if k.startswith(e["id"] + "."))
    else:
        hours = w.get(e["id"], 0.0)
    share = hours / tot if tot else 0
    weights[e["id"]] = dict(h=round(hours, 2), s=round(share * 100, 2), l=wl.get(e["id"], []), r=rev.get(e["id"], []))
    el_rows.append(dict(element_id=e["id"], part=e["part"], grade=e["grade"] or 9, code=e["code"],
                        is_section=bool(e.get("is_group")), text=e["text"][:160], lesson_hours=round(hours, 2),
                        share_of_class_pct=round(share * 100, 2), class_content_hours=tot,
                        lessons=";".join(wl.get(e["id"], [])), review_lessons=";".join(rev.get(e["id"], []))))
with open(f"{OUT}/element_weights.csv", "w", newline="", encoding="utf-8-sig") as f:
    wr = csv.DictWriter(f, fieldnames=list(el_rows[0].keys()))
    wr.writeheader(); wr.writerows(el_rows)
json.dump({"weights": weights, "lessons": {r["lesson_id"]: dict(e=r["element_ids"].split(";") if r["element_ids"] else [],
                                                                  m=r["method"], k=r["kind"]) for r in lesson_rows}},
          open(_P.tmp("weights.json"), "w", encoding="utf-8"), ensure_ascii=False)

# сводка
leaves = [r for r in el_rows if not r["is_section"] and r["element_id"].count(".cls.")]
zero = [r for r in leaves if r["lesson_hours"] == 0]
print("содержательных часов по классам:", dict(class_hours))
print("листьев:", len(leaves), "без уроков:", len(zero))
for r in zero:
    print("   0 ч:", r["element_id"], r["text"][:70])
top = sorted(leaves, key=lambda r: -r["share_of_class_pct"])[:12]
for r in top:
    print(f'  {r["share_of_class_pct"]:5.1f}%  {r["lesson_hours"]:4.1f} ч  {r["part"]} {r["grade"]} кл. {r["code"]:6} {r["text"][:60]}')
