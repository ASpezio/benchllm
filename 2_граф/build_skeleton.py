#!/usr/bin/env python3
"""ИС ОЗЯМ-ФОП · часть 2 «Граф» · каркас.

Собирает граф из готовой разметки (папка 1_разметка): узлы — предмет, класс, раздел, элемент
содержания, группа умений, умение, урок, экзамен, раздел/пункт экзамена, требование экзамена;
связи — часть-целое, урок → элемент (с часами), элемент → пункт экзамена, умение → требование
экзамена, порядок уроков.

Выход (папка каркас/): nodes.jsonl, edges.jsonl, graph.graphml (Gephi / yEd / Neo4j), stats.json.
Запуск: python3 build_skeleton.py
"""
import csv, json, os, re
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
M = os.path.join(HERE, "..", "1_разметка")
PH = os.path.join(M, "физика_поурочное")

SUBJ_RU = {"history": "История", "physics": "Физика"}
LEVEL_RU = {"OOO": "ООО", "SOO": "СОО"}
EXAM = {"OOO": ("oge", "ОГЭ"), "SOO": ("ege", "ЕГЭ")}

recs = [json.loads(l) for l in open(os.path.join(M, "records.jsonl"), encoding="utf-8")]
recs = [r for r in recs if r["subject"] in SUBJ_RU]
plessons = [json.loads(l) for l in open(os.path.join(PH, "records_physics_lessons.jsonl"), encoding="utf-8")]

nodes, edges = {}, []


def node(nid, ntype, label, **attrs):
    if nid in nodes:
        nodes[nid].update({k: v for k, v in attrs.items() if v not in (None, "", [])})
        return
    d = {"id": nid, "type": ntype, "label": label}
    d.update({k: v for k, v in attrs.items() if v not in (None, "", [])})
    nodes[nid] = d


def edge(src, dst, etype, **attrs):
    d = {"source": src, "target": dst, "type": etype}
    d.update({k: v for k, v in attrs.items() if v not in (None, "", [])})
    edges.append(d)


def base_id(rid):
    return rid.split("~")[0]


def parent_code(code):
    return code.rsplit(".", 1)[0] if "." in code else None


# ---------- верхние уровни
grades = sorted({(r["subject"], r["part"], r["grade"]) for r in recs if r.get("grade")})
for s in SUBJ_RU:
    node(s, "subject", SUBJ_RU[s])
for s, p, g in grades:
    gid = f"{p}.{s}.g{g}"
    node(gid, "grade", f"{SUBJ_RU[s]}, {g} класс", subject=s, level=p, grade=g)
    edge(gid, s, "is_part_of")
for s in SUBJ_RU:
    for p, (ek, en) in EXAM.items():
        node(f"{p}.{s}.{ek}", "exam", f"{en} · {SUBJ_RU[s]}", subject=s, level=p, exam=en)
        edge(f"{p}.{s}.{ek}", s, "is_part_of")

# ---------- записи приказа
TYPE = {"element": "element", "requirement": "requirement", "exam_element": "exam_element",
        "exam_requirement": "exam_requirement", "lesson": "lesson"}
byid = {}
for r in recs:
    t = r["type"]
    if t not in TYPE:
        continue
    rid = r["id"]
    byid[rid] = r
    group = bool(r.get("is_group"))
    nt = {"element": "section" if group else "element",
          "requirement": "requirement_group" if group else "requirement",
          "exam_element": "exam_section" if group else "exam_element",
          "exam_requirement": "exam_requirement",
          "lesson": "lesson"}[t]
    label = (f"Урок {r['code']}. " if t == "lesson" else f"{r['code']} ") + r["text"][:120]
    node(rid, nt, label, subject=r["subject"], level=r["part"], grade=r.get("grade"), code=r["code"],
         text=r["text"], page=r.get("page"), source="приказ", hours=r.get("hours") if t == "lesson" else None,
         lesson_kind=r.get("lesson_kind"), verb=r.get("verb"))

# часть-целое по кодам внутри таблицы
by_table = defaultdict(dict)
for rid, r in byid.items():
    key = base_id(rid)[: -(len(r["code"]) + 1)] if r["type"] != "lesson" else None
    if key:
        by_table[key][r["code"]] = rid
for rid, r in byid.items():
    s, p, g = r["subject"], r["part"], r.get("grade")
    if r["type"] == "lesson":
        edge(rid, f"{p}.{s}.g{g}", "is_part_of")
        continue
    key = base_id(rid)[: -(len(r["code"]) + 1)]
    pc = parent_code(r["code"])
    par = by_table[key].get(pc) if pc else None
    if r.get("parent_id") and r["parent_id"] in byid:
        par = r["parent_id"]
    if par:
        edge(rid, par, "is_part_of")
    elif r["type"] in ("exam_element", "exam_requirement"):
        edge(rid, f"{p}.{s}.{EXAM[p][0]}", "is_part_of")
    else:
        edge(rid, f"{p}.{s}.g{g}", "is_part_of")

# ---------- уроки физики (Конструктор edsoo, базовый уровень)
for l in plessons:
    node(l["id"], "lesson", f"Урок {l['code']}. {l['text'][:120]}", subject="physics", level=l["part"], grade=l["grade"],
         code=l["code"], text=l["text"], page=l.get("page"), source="Конструктор edsoo (базовый)", hours=l["hours"],
         lesson_kind=l["lesson_kind"], lesson_type=l.get("lesson_type"))
    edge(l["id"], f"{l['part']}.physics.g{l['grade']}", "is_part_of")

# порядок уроков
les_by_grade = defaultdict(list)
for n in nodes.values():
    if n["type"] == "lesson":
        les_by_grade[(n["subject"], n["level"], n["grade"])].append(n)
for k, ls in les_by_grade.items():
    ls.sort(key=lambda n: int(re.sub(r"\D", "", str(n["code"])) or 0))
    for a, b in zip(ls, ls[1:]):
        edge(a["id"], b["id"], "next")

# ---------- урок → элемент (appears_in: элемент появляется в уроке; доля часа)
def lesson_links(path):
    for r in csv.DictReader(open(path, encoding="utf-8-sig")):
        ids = [x for x in r["element_ids"].split(";") if x]
        if not ids:
            continue
        sh = [float(x) for x in r.get("share", "").split(";") if x] if r.get("share") else []
        if len(sh) != len(ids):
            sh = [1.0 / len(ids)] * len(ids)
        kind = r.get("kind", "new")
        for e, w in zip(ids, sh):
            if e not in nodes:
                continue
            if kind == "review":
                edge(e, r["lesson_id"], "reviewed_in")
            else:
                edge(e, r["lesson_id"], "appears_in", hours=round(w, 3), method=r.get("method"))
lesson_links(os.path.join(M, "lesson_element.csv"))
lesson_links(os.path.join(PH, "lesson_element_physics.csv"))

# ---------- веса элементов
for r in csv.DictReader(open(os.path.join(M, "element_weights.csv"), encoding="utf-8-sig")):
    if r["element_id"] in nodes:
        node(r["element_id"], nodes[r["element_id"]]["type"], nodes[r["element_id"]]["label"],
             hours=float(r["lesson_hours"]), share_pct=float(r["share_of_class_pct"]), hours_source="приказ")
for r in csv.DictReader(open(os.path.join(PH, "element_weights_physics_combined.csv"), encoding="utf-8-sig")):
    if r["element_id"] in nodes:
        node(r["element_id"], nodes[r["element_id"]]["type"], nodes[r["element_id"]]["label"],
             hours=float(r["hours"]), share_pct=float(r["share_of_class_pct"]), category=r.get("category"),
             hours_source={"база": "базовый план", "углублённый": "углублённый план", "нет": "нет уроков"}.get(r["source"], r["source"]))

# ---------- элемент → пункт экзамена
for r in csv.DictReader(open(os.path.join(M, "element_exam.csv"), encoding="utf-8-sig")):
    e = r["element_id"]
    for x in [x for x in r["exam_ids"].split(";") if x]:
        if x in nodes:
            edge(e, x, "tested_by", method=r["method"])
    for x in [x for x in r["also_ege_via_ooo"].split(";") if x]:
        # «ЕГЭ 1-6» и физика 7–9 → ЕГЭ: id восстанавливаем из exam_extra через код
        code = x.split(" ", 1)[1]
        ex = x.split(" ", 1)[0]
        xid = f"SOO.{r['subject']}.{'ege' if ex == 'ЕГЭ' else 'oge'}.el.{code}"
        if xid in nodes:
            edge(e, xid, "tested_by", via_level=True)

# ---------- умение → требование экзамена
for r in csv.DictReader(open(os.path.join(M, "requirement_exam.csv"), encoding="utf-8-sig")):
    for x in [x for x in r["exam_req_ids"].split(";") if x]:
        if x in nodes:
            edge(r["requirement_id"], x, "assessed_by", method=r["method"])
    if not r["exam_req_ids"]:
        node(r["requirement_id"], "requirement", nodes[r["requirement_id"]]["label"], not_in_exam=r["why"])

# ---------- формулы MinerU
F = json.load(open(os.path.join(M, "формулы_mineru.json"), encoding="utf-8"))
for k, t in F.items():
    if k in nodes and ("$" in t or "![](" in t):
        nodes[k]["text_latex"] = t

# ---------- запись
missing = [e for e in edges if e["source"] not in nodes or e["target"] not in nodes]
assert not missing, missing[:5]
with open(os.path.join(HERE, "каркас", "nodes.jsonl"), "w", encoding="utf-8") as f:
    for n in nodes.values():
        f.write(json.dumps(n, ensure_ascii=False) + "\n")
with open(os.path.join(HERE, "каркас", "edges.jsonl"), "w", encoding="utf-8") as f:
    for e in edges:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")

stats = {"nodes": len(nodes), "edges": len(edges),
         "node_types": dict(Counter(n["type"] for n in nodes.values()).most_common()),
         "edge_types": dict(Counter(e["type"] for e in edges).most_common())}
json.dump(stats, open(os.path.join(HERE, "каркас", "stats.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

try:
    import networkx as nx
    G = nx.MultiDiGraph()
    for n in nodes.values():
        G.add_node(n["id"], **{k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v)
                                for k, v in n.items() if k != "id" and v is not None})
    for e in edges:
        G.add_edge(e["source"], e["target"], key=None, **{k: v for k, v in e.items() if k not in ("source", "target")})
    nx.write_graphml(G, os.path.join(HERE, "каркас", "graph.graphml"))
except ImportError:
    print("networkx не установлен — graph.graphml пропущен")
print(json.dumps(stats, ensure_ascii=False, indent=1))
