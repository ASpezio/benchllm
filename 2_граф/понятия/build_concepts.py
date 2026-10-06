#!/usr/bin/env python3
"""SyllaBench · Граф · слой понятий.

Склеивает результаты извлечения (out_*.json в подпапках) в узлы-понятия и связи «упоминает»:
  элемент / пункт экзамена --mentions--> понятие   (с цитатой-основанием и ролью)
Одинаковые имена (без учёта регистра, ё/е и вида тире) и синонимы из синонимы.json — один узел.

Выход: concepts.jsonl, mentions.jsonl, concepts.csv (для просмотра), stats.json.
Запуск: python3 build_concepts.py [папка с out_*.json ...]   (по умолчанию — все подпапки)
"""
import csv, glob, json, os, re, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SKEL = os.path.join(HERE, "..", "каркас", "nodes.jsonl")
nodes = {json.loads(l)["id"]: json.loads(l) for l in open(SKEL, encoding="utf-8")}
SYN = json.load(open(os.path.join(HERE, "синонимы.json"), encoding="utf-8"))

TR = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
              ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t", "u", "f",
               "h", "ts", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"]))


def norm(s):
    s = s.lower().replace("ё", "е").replace("­", "")
    s = re.sub(r"[‐-‒–—−]", "-", s)
    s = re.sub(r"\s*-\s*", "-", s)
    return re.sub(r"\s+", " ", s).strip(" .")


def slug(s):
    s = "".join(TR.get(ch, ch) for ch in norm(s))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:80]


syn = {subj: {norm(k): v for k, v in m.items()} for subj, m in SYN.items() if not subj.startswith("_")}
dirs = sys.argv[1:] or [d for d in glob.glob(os.path.join(HERE, "*")) if os.path.isdir(d)]
files = sorted(f for d in dirs for f in glob.glob(os.path.join(d, "out_*.json")))

concepts, mentions = {}, []
for f in files:
    for o in json.load(open(f, encoding="utf-8")):
        src = o["source_id"]
        sn = nodes[src]
        subj = sn["subject"]
        for c in o["concepts"]:
            name = syn.get(subj, {}).get(norm(c["name"]), c["name"])
            key = (subj, norm(name))
            cid = f"C.{subj}.{slug(name)}"
            k = concepts.get(key)
            if not k:
                k = concepts[key] = {"id": cid, "type": "concept", "label": name, "subject": subj, "ctype": c["type"],
                                     "aliases": [], "formulas": [], "dates": [], "types_seen": Counter()}
            k["types_seen"][c["type"]] += 1
            for a in (c.get("aliases") or []) + ([c["name"]] if c["name"] != name else []):
                if norm(a) != norm(name) and a not in k["aliases"]:
                    k["aliases"].append(a)
            if c.get("formula") and c["formula"] not in k["formulas"]:
                k["formulas"].append(c["formula"])
            if c.get("date") and c["date"] not in k["dates"]:
                k["dates"].append(c["date"])
            mentions.append({"source": src, "target": k["id"], "type": "mentions", "role": c.get("role", "part"),
                             "evidence": c["evidence"]})

# уникальность id
ids = Counter(k["id"] for k in concepts.values())
assert all(v == 1 for v in ids.values()), [i for i, v in ids.items() if v > 1][:10]

# где встречается: классы, первое появление (класс → код элемента), пункты экзамена
pos = defaultdict(list)
for m in mentions:
    s = nodes[m["source"]]
    pos[m["target"]].append(s)
def order_key(s):
    g = s.get("grade") or 99
    code = [int(x) if x.isdigit() else 0 for x in str(s.get("code", "0")).split(".")]
    return (0 if s["type"] == "element" else 1, g, code)
for k in concepts.values():
    ps = sorted(pos[k["id"]], key=order_key)
    k["ctype"] = k["types_seen"].most_common(1)[0][0]
    k["types_seen"] = dict(k["types_seen"])
    cls = [p for p in ps if p["type"] == "element"]
    k["grades"] = sorted({p["grade"] for p in cls})
    if cls:
        k["first_element"] = cls[0]["id"]
        k["first_grade"] = cls[0]["grade"]
    k["exam_items"] = sorted({p["id"] for p in ps if p["type"] == "exam_element"})
    k["n_mentions"] = len(ps)
    for f in ("aliases", "formulas", "dates", "exam_items"):
        if not k[f]:
            del k[f]

with open(os.path.join(HERE, "concepts.jsonl"), "w", encoding="utf-8") as f:
    for k in sorted(concepts.values(), key=lambda k: (k["subject"], k.get("first_grade", 99), k["label"])):
        f.write(json.dumps(k, ensure_ascii=False) + "\n")
with open(os.path.join(HERE, "mentions.jsonl"), "w", encoding="utf-8") as f:
    for m in mentions:
        f.write(json.dumps(m, ensure_ascii=False) + "\n")
with open(os.path.join(HERE, "concepts.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["id", "subject", "name", "type", "grades", "first_element", "mentions", "exam_items", "aliases", "formulas", "dates"])
    for k in sorted(concepts.values(), key=lambda k: (k["subject"], k.get("first_grade", 99), k["label"])):
        w.writerow([k["id"], k["subject"], k["label"], k["ctype"], ";".join(map(str, k["grades"])), k.get("first_element", ""),
                    k["n_mentions"], ";".join(k.get("exam_items", [])), ";".join(k.get("aliases", [])),
                    " ; ".join(k.get("formulas", [])), ";".join(k.get("dates", []))])
st = {"files": [os.path.relpath(f, HERE) for f in files], "concepts": len(concepts), "mentions": len(mentions),
      "by_subject": dict(Counter(k["subject"] for k in concepts.values())),
      "by_type": {s: dict(Counter(k["ctype"] for k in concepts.values() if k["subject"] == s).most_common()) for s in ("history", "physics")},
      "with_formula": sum(1 for k in concepts.values() if k.get("formulas")),
      "in_several_grades": sum(1 for k in concepts.values() if len(k["grades"]) > 1),
      "only_in_exam": sum(1 for k in concepts.values() if not k["grades"])}
json.dump(st, open(os.path.join(HERE, "stats.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(st, ensure_ascii=False, indent=1))
