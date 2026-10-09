#!/usr/bin/env python3
"""Прямые и обратные связи «элемент класса ↔ элемент ОГЭ/ЕГЭ» + часы уроков за пунктом экзамена.

История ООО: элементы истории России, связанные с ОГЭ 1–4, дополнительно связаны с ЕГЭ «1–6»
(в ЕГЭ эти разделы даны одной строкой со ссылкой на кодификатор ОГЭ).
Часы пункта экзамена = сумма часов связанных элементов классов (элемент на k пунктов делится на k)
+ уроки, напрямую привязанные к пункту экзамена (модуль новейшей истории в 9 классе → ОГЭ 6).
Физика: часы элементов — базовый план Конструктора edsoo + недостающее из углублённого (phys/element_weights_physics_combined.csv);
связь «через другой уровень» (7–9 кл. → ЕГЭ) получает ту же долю часа, что и один прямой пункт.
"""
import paths as _P  # пути прогона (автоматизация/этапы/paths.py)
import csv, json
from collections import defaultdict

REC = _P.REC
recs = {json.loads(l)["id"]: json.loads(l) for l in open(REC, encoding="utf-8")}
X = json.load(open(_P.tmp("exam_out.json"), encoding="utf-8"))
W = json.load(open(_P.tmp("weights.json"), encoding="utf-8"))
EGE16 = "SOO.history.ege.el.1-6"

EXTRA = (json.load(open(_P.manual("exam_extra.json"), encoding="utf-8")) if _P.has_manual("exam_extra.json") else {})
PW = {r["element_id"]: float(r["hours"]) for r in csv.DictReader(open(_P.ph("element_weights_physics_combined.csv"), encoding="utf-8-sig"))
      if r["is_section"] == "False"}
cls_links, rev, rev_h = {}, defaultdict(list), defaultdict(float)
for cid, v in X.items():
    ids = list(v["ids"])
    derived = []
    if cid.startswith("OOO.history.") and any(i.split(".el.")[1].split(".")[0] in ("1", "2", "3", "4") for i in ids):
        derived = [EGE16]
    derived = derived + EXTRA.get(cid, [])
    cls_links[cid] = dict(e=ids, d=derived, m=v["method"], s=v.get("score"))
    phys = cid.startswith(("OOO.physics.", "SOO.physics."))
    h = PW.get(cid, 0.0) if phys else W["weights"].get(cid, {}).get("h", 0.0)
    for i in ids:
        rev[i].append(cid)
        rev_h[i] += h / len(ids)
    for i in derived:
        rev[i].append(cid)
        if phys:
            rev_h[i] += h / max(len(ids), 1)
        else:
            rev_h[i] += h / len(ids) * len([x for x in ids if x.split(".el.")[1].split(".")[0] in ("1", "2", "3", "4")])
# уроки, привязанные к пункту экзамена напрямую
for lid, L in W["lessons"].items():
    if L["k"] == "review":
        continue
    for e in L["e"]:
        if ".oge." in e or ".ege." in e:
            rev_h[e] += 1 / len(L["e"])

exam_links = {}
for r in recs.values():
    if r["type"] != "exam_element" or r["subject"] not in ("history", "physics"):
        continue
    exam_links[r["id"]] = dict(c=rev.get(r["id"], []), h=round(rev_h.get(r["id"], 0.0), 2))
# разделы экзамена: сумма по детям
for eid, d in exam_links.items():
    r = recs[eid]
    if r.get("is_group"):
        kids = [k for k in exam_links if k.startswith(eid + ".")]
        d["c"] = sorted({c for k in kids for c in exam_links[k]["c"]}, key=lambda x: list(X).index(x) if x in X else 0)
        d["h"] = round(sum(exam_links[k]["h"] or 0 for k in kids if not recs[k].get("is_group")), 2)

json.dump(dict(cls=cls_links, exam=exam_links), open(_P.tmp("exam_links.json"), "w", encoding="utf-8"), ensure_ascii=False)

OUT = _P.M
with open(f"{OUT}/element_exam.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["element_id", "subject", "part", "grade", "code", "text", "exam", "exam_ids", "exam_codes", "also_ege_via_ooo", "method", "score"])
    for cid, v in cls_links.items():
        c = recs[cid]
        w.writerow([cid, c["subject"], c["part"], c["grade"], c["code"], c["text"][:160], X[cid]["exam"],
                    ";".join(v["e"]), ";".join(recs[i]["code"] for i in v["e"]), ";".join(recs[i]["exam"] + " " + recs[i]["code"] for i in v["d"]),
                    v["m"], v["s"] if v["s"] is not None else ""])
with open(f"{OUT}/exam_coverage.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["exam_element_id", "subject", "exam", "code", "is_section", "text", "class_elements", "class_element_count", "lesson_hours"])
    for eid, d in exam_links.items():
        r = recs[eid]
        w.writerow([eid, r["subject"], r["exam"], r["code"], bool(r.get("is_group")), r["text"][:160], ";".join(d["c"]), len(d["c"]),
                    d["h"] if d["h"] is not None else ""])

# сводка
for subj in ("history", "physics"):
    for ex in ("oge", "ege"):
        leaves = [k for k in exam_links if f".{subj}.{ex}." in k and not recs[k].get("is_group")]
        empty = [recs[k]["code"] for k in leaves if not exam_links[k]["c"]]
        print(subj, ex, "пунктов", len(leaves), "без элементов классов:", len(empty), empty[:25])
top = sorted([(d["h"], k) for k, d in exam_links.items() if d["h"] and not recs[k].get("is_group")], reverse=True)[:8]
for h, k in top:
    print(f"  {h:5.1f} ч  {recs[k]['exam']} {recs[k]['code']:5} {recs[k]['text'][:60]}")
