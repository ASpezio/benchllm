#!/usr/bin/env python3
"""SyllaBench · Граф · примеры запросов к графу кодом (только стандартная библиотека Python).

Запуск:  python3 примеры.py                 — все примеры
         python3 примеры.py "закон архимеда"  — карточка одного понятия

Граф лежит в граф/nodes.jsonl (узлы) и граф/edges.jsonl (связи): по одному JSON-объекту на строку.
У узла: id, type (subject / grade / section / element / requirement / lesson / exam_element / concept …), label, …
У связи: source, target, type (is_part_of / appears_in / tested_by / mentions / prerequisites_for / is_a / …), …
"""
import json, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
G = os.path.join(HERE, "граф")

# ---------- загрузка и индексы
nodes = {}
for line in open(os.path.join(G, "nodes.jsonl"), encoding="utf-8"):
    n = json.loads(line)
    nodes[n["id"]] = n
edges = [json.loads(line) for line in open(os.path.join(G, "edges.jsonl"), encoding="utf-8")]
out_e, in_e = defaultdict(list), defaultdict(list)          # исходящие / входящие связи по узлу
for e in edges:
    out_e[e["source"]].append(e)
    in_e[e["target"]].append(e)


def find(name, ntype="concept"):
    """Узел по имени (без учёта регистра и ё); сначала точное совпадение, потом подстрока."""
    q = name.lower().replace("ё", "е")
    cands = [n for n in nodes.values() if n["type"] == ntype and q in n["label"].lower().replace("ё", "е")]
    exact = [n for n in cands if n["label"].lower().replace("ё", "е") == q]
    return (exact or cands or [None])[0]


def prerequisites(cid):
    """Все предпосылки понятия (транзитивно): что нужно знать до него. Возвращает {id: глубина}."""
    seen, frontier, depth = {}, [cid], 0
    while frontier:
        depth += 1
        nxt = []
        for u in frontier:
            for e in in_e[u]:
                if e["type"] == "prerequisites_for" and e["source"] not in seen:
                    seen[e["source"]] = depth
                    nxt.append(e["source"])
        frontier = nxt
    return seen


def elements_of(cid):
    """Элементы кодификатора, где названо понятие (с цитатой)."""
    return [(nodes[e["source"]], e["evidence"]) for e in in_e[cid] if e["type"] == "mentions" and nodes[e["source"]]["type"] == "element"]


def exam_items_of(cid):
    """Пункты ОГЭ/ЕГЭ: где понятие названо прямо + куда ведут его элементы (tested_by)."""
    direct = {e["source"] for e in in_e[cid] if e["type"] == "mentions" and nodes[e["source"]]["type"] == "exam_element"}
    via = {t["target"] for el, _ in elements_of(cid) for t in out_e[el["id"]] if t["type"] == "tested_by"}
    return direct, via - direct


def concept_card(name):
    c = find(name)
    if not c:
        print(f"Понятие «{name}» не найдено"); return
    print(f"\n=== {c['label']} [{c['ctype']}], классы {c.get('grades')}")
    for f in c.get("formulas", []):
        print("  формула:", f)
    for el, ev in elements_of(c["id"]):
        print(f"  в программе: {el['grade']} кл. {el['code']} — «{ev}»  (часов у элемента: {el.get('hours')})")
    d, v = exam_items_of(c["id"])
    print("  на экзамене:", ", ".join(nodes[x]["label"][:50] for x in sorted(d | v)) or "—")
    for e in out_e[c["id"]] + in_e[c["id"]]:
        if e["type"] in ("prerequisites_for", "is_a", "part_of", "participant_of", "verifies"):
            a, b = nodes[e["source"]]["label"], nodes[e["target"]]["label"]
            print(f"  {a} —{e['type']}→ {b}  | {e.get('why', '')}{'  [порядок!]' if e.get('order_issue') else ''}")


if len(sys.argv) > 1:
    concept_card(" ".join(sys.argv[1:]))
    sys.exit()

# ---------- 1. Сколько чего в графе
from collections import Counter
print("Узлы:", dict(Counter(n["type"] for n in nodes.values()).most_common()))
print("Связи:", dict(Counter(e["type"] for e in edges).most_common()))

# ---------- 2. Карточка понятия
concept_card("Закон Архимеда")
concept_card("Персидская держава")

# ---------- 3. Что нужно знать до понятия — цепочка предпосылок по уровням
c = find("Закон Архимеда")
pre = prerequisites(c["id"])
print(f"\nЧтобы понять «{c['label']}», нужно знать ({len(pre)}):")
for cid, depth in sorted(pre.items(), key=lambda x: x[1]):
    print(f"  {'  ' * (depth - 1)}{depth}: {nodes[cid]['label']}")

# ---------- 4. Понятия одного элемента
el = next(n for n in nodes.values() if n["type"] == "element" and n["id"] == "OOO.history.cls.g5.el.2.4")
print(f"\nЭлемент {el['grade']} кл. {el['code']}: {el['text']}")
for e in out_e[el["id"]]:
    if e["type"] == "mentions":
        print(f"  {nodes[e['target']]['label']} [{nodes[e['target']]['ctype']}] ← «{e['evidence']}»")

# ---------- 5. Темы, где предпосылка в программе идёт позже (order_issue)
print("\nПредпосылка идёт позже, чем нужна:")
for e in edges:
    if e.get("order_issue"):
        print(f"  {nodes[e['source']]['label']} → {nodes[e['target']]['label']}  | {e.get('why', '')}")

# ---------- 6. С networkx (если установлен: pip install networkx) — то же в одну строку
try:
    import networkx as nx
    D = nx.DiGraph()
    D.add_edges_from((e["source"], e["target"]) for e in edges if e["type"] == "prerequisites_for")
    longest = nx.dag_longest_path(D)
    print("\nnetworkx: самая длинная цепочка «нужно знать до»:", " → ".join(nodes[x]["label"] for x in longest))
except ImportError:
    pass
