#!/usr/bin/env python3
"""ИС ОЗЯМ-ФОП · Граф · страница просмотра: граф/ → просмотр/index.html (данные встраиваются в шаблон).
Наборы — по файлам связей (связи/*/in_*.json): каждый набор показывает свои понятия, элементы и связи."""
import glob, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
G = os.path.join(HERE, "..", "граф")
nodes = {json.loads(l)["id"]: json.loads(l) for l in open(os.path.join(G, "nodes.jsonl"), encoding="utf-8")}
edges = [json.loads(l) for l in open(os.path.join(G, "edges.jsonl"), encoding="utf-8")]
REL = {"prerequisites_for", "is_a", "part_of", "participant_of", "verifies"}
parent = {e["source"]: e["target"] for e in edges if e["type"] == "is_part_of"}
mentions = [e for e in edges if e["type"] == "mentions"]

NAMES = {"физика_7-8": ("phys78", "Физика · 7–8 класс"), "история_5": ("hist5", "История · 5 класс"),
         "история_6": ("hist6", "История · 5–6 класс"), "история_7": ("hist7", "История · 5–7 класс")}
HIDDEN = {"история_5", "история_6"}
sets = []
for f in sorted(glob.glob(os.path.join(HERE, "..", "связи", "*", "in_*.json"))):
    name = re.sub(r"^in_|\.json$", "", os.path.basename(f))
    if name in HIDDEN:  # старые вкладки: их понятия целиком входят в более поздний набор
        continue
    key, title = NAMES.get(name, (re.sub(r"\W+", "", name), name))
    cids = [c["id"] for c in json.load(open(f, encoding="utf-8"))["concepts"]]
    cs = set(cids)
    concepts, els_used = {}, {}
    for cid in cids:
        c = nodes[cid]
        d = {"n": c["label"], "t": c["ctype"], "g": c.get("grades", []), "els": [], "ex": []}
        for k_src, k_dst in (("aliases", "a"), ("formulas", "f"), ("dates", "d")):
            if c.get(k_src):
                d[k_dst] = c[k_src]
        concepts[cid] = d
    for m in mentions:
        if m["target"] not in cs:
            continue
        s = nodes[m["source"]]
        if s["type"] == "element":
            concepts[m["target"]]["els"].append([s["id"], m.get("role", "part"), m["evidence"]])
            els_used.setdefault(s["id"], []).append(m["target"])
        else:
            concepts[m["target"]]["ex"].append([s["id"], m["evidence"]])
    def okey(eid):
        n = nodes[eid]
        return (n["grade"], [int(x) for x in n["code"].split(".") if x.isdigit()])
    elements = []
    for eid in sorted(els_used, key=okey):
        n = nodes[eid]
        p = nodes.get(parent.get(eid))
        sec = f'{n["grade"]} кл. · {p["code"]} {p["text"]}' if p and p["type"] == "section" else f'{n["grade"]} класс'
        seen, order = set(), []
        for cid in els_used[eid]:
            if cid not in seen:
                seen.add(cid); order.append(cid)
        elements.append({"id": eid, "code": n["code"], "g": n["grade"], "x": n["text"], "sec": sec, "c": order})
    rels = [[e["source"], e["target"], e["type"], e.get("why", ""), 1 if e.get("order_issue") else 0]
            for e in edges if e["type"] in REL and e["source"] in cs and e["target"] in cs]
    start = max(cids, key=lambda c: sum(1 for r in rels if c in r[:2]))
    sets.append({"key": key, "name": title, "concepts": concepts, "elements": elements, "rels": rels, "start": start})

order = {"phys78": 0, "hist5": 1, "hist6": 2}
sets.sort(key=lambda s: order.get(s["key"], 9))
data = json.dumps({"sets": sets}, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
t = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
assert t.count("/*__DATA__*/") == 1
open(os.path.join(HERE, "index.html"), "w", encoding="utf-8").write(t.replace("/*__DATA__*/", data))
print("наборы:", [(s["name"], len(s["concepts"]), len(s["elements"]), len(s["rels"])) for s in sets], "байт:", len(data.encode()))
