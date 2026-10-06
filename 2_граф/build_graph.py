#!/usr/bin/env python3
"""SyllaBench · Граф · сборка всех слоёв в один граф.

каркас/ (build_skeleton.py) + понятия/ (build_concepts.py) + связи/*/out_*.json → граф/
  nodes.jsonl, edges.jsonl, stats.json,
  graph.graphml (весь граф) и понятия.graphml (только понятия и связи между ними) — для Gephi / yEd
Связи между понятиями: prerequisites_for, is_a, part_of, participant_of (история), verifies (физика).
Запуск: python3 build_skeleton.py && python3 понятия/build_concepts.py && python3 build_graph.py
"""
import glob, json, os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "граф")
os.makedirs(OUT, exist_ok=True)


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")]


nodes = {n["id"]: n for n in jl(os.path.join(HERE, "каркас", "nodes.jsonl"))}
edges = jl(os.path.join(HERE, "каркас", "edges.jsonl"))
for c in jl(os.path.join(HERE, "понятия", "concepts.jsonl")):
    nodes[c["id"]] = c
edges += jl(os.path.join(HERE, "понятия", "mentions.jsonl"))

rel_files = sorted(glob.glob(os.path.join(HERE, "связи", "*", "out_*.json")))
seen = set()
for f in rel_files:
    for r in json.load(open(f, encoding="utf-8")):
        k = (r["source"], r["target"], r["type"])
        if k in seen:
            continue
        seen.add(k)
        e = {"source": r["source"], "target": r["target"], "type": r["type"], "why": r.get("why")}
        if r.get("order_issue"):
            e["order_issue"] = True
        edges.append(e)

bad = [e for e in edges if e["source"] not in nodes or e["target"] not in nodes]
assert not bad, bad[:5]
with open(os.path.join(OUT, "nodes.jsonl"), "w", encoding="utf-8") as f:
    for n in nodes.values():
        f.write(json.dumps(n, ensure_ascii=False) + "\n")
with open(os.path.join(OUT, "edges.jsonl"), "w", encoding="utf-8") as f:
    for e in edges:
        f.write(json.dumps({k: v for k, v in e.items() if v is not None}, ensure_ascii=False) + "\n")

stats = {"nodes": len(nodes), "edges": len(edges),
         "node_types": dict(Counter(n["type"] for n in nodes.values()).most_common()),
         "edge_types": dict(Counter(e["type"] for e in edges).most_common()),
         "relation_files": [os.path.relpath(f, HERE) for f in rel_files],
         "order_issues": sum(1 for e in edges if e.get("order_issue"))}
json.dump(stats, open(os.path.join(OUT, "stats.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---------- GraphML для Gephi / yEd (без сторонних библиотек)
# Атрибут «type» переименован: у узлов → kind, у связей → relation (в Gephi «Type» — служебная колонка).
from xml.sax.saxutils import escape, quoteattr


def write_graphml(path, ns, es):
    def val(v):
        return json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else str(v)
    nkeys = sorted({k for n in ns for k in n if k != "id"})
    ekeys = sorted({k for e in es for k in e if k not in ("source", "target")})
    ren_n = {"type": "kind"}
    ren_e = {"type": "relation"}
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<graphml xmlns="http://graphml.graphdrawing.org/xmlns">\n')
        for k in nkeys:
            f.write(f'  <key id="n_{k}" for="node" attr.name={quoteattr(ren_n.get(k, k))} attr.type="string"/>\n')
        for k in ekeys:
            f.write(f'  <key id="e_{k}" for="edge" attr.name={quoteattr(ren_e.get(k, k))} attr.type="string"/>\n')
        f.write('  <graph id="G" edgedefault="directed">\n')
        for n in ns:
            f.write(f'    <node id={quoteattr(n["id"])}>')
            for k in nkeys:
                if n.get(k) not in (None, "", []):
                    f.write(f'<data key="n_{k}">{escape(val(n[k]))}</data>')
            f.write("</node>\n")
        for i, e in enumerate(es):
            f.write(f'    <edge id="e{i}" source={quoteattr(e["source"])} target={quoteattr(e["target"])}>')
            for k in ekeys:
                if e.get(k) not in (None, "", []):
                    f.write(f'<data key="e_{k}">{escape(val(e[k]))}</data>')
            f.write("</edge>\n")
        f.write("  </graph>\n</graphml>\n")


SHORT = ("id", "type", "label", "subject", "level", "grade", "code", "ctype", "hours", "share_pct", "first_grade", "n_mentions", "category")
write_graphml(os.path.join(OUT, "graph.graphml"), [{k: n.get(k) for k in SHORT if k in n} for n in nodes.values()], edges)
RELS = {"prerequisites_for", "is_a", "part_of", "participant_of", "verifies"}
cn = [n for n in nodes.values() if n["type"] == "concept"]
ce = [e for e in edges if e["type"] in RELS]
write_graphml(os.path.join(OUT, "понятия.graphml"),
              [{k: n.get(k) for k in ("id", "label", "subject", "ctype", "first_grade", "n_mentions") if k in n} for n in cn], ce)
print(json.dumps(stats, ensure_ascii=False, indent=1))
