#!/usr/bin/env python3
"""Проверка связей между понятиями: id из списка, типы, без петель и дублей, без циклов
в prerequisites_for / is_a / part_of, отметки order_issue согласованы с порядком."""
import json, sys
from collections import Counter, defaultdict

TYPES = {"prerequisites_for", "is_a", "part_of", "participant_of", "verifies"}


def cycles(edges, ids):
    g = defaultdict(list)
    for a, b in edges:
        g[a].append(b)
    color, stack, found = {}, [], []

    def dfs(u):
        color[u] = 1; stack.append(u)
        for v in g[u]:
            if color.get(v) == 1:
                found.append(stack[stack.index(v):] + [v])
            elif not color.get(v):
                dfs(v)
        stack.pop(); color[u] = 2
    sys.setrecursionlimit(10000)
    for u in ids:
        if not color.get(u):
            dfs(u)
    return found


def main(inp, outp):
    C = {c["id"]: c for c in json.load(open(inp, encoding="utf-8"))["concepts"]}
    R = json.load(open(outp, encoding="utf-8"))
    errs, warn, seen = [], [], set()
    for r in R:
        a, b, t = r.get("source"), r.get("target"), r.get("type")
        if a not in C or b not in C:
            errs.append(f"нет id: {a} → {b}"); continue
        if t not in TYPES:
            errs.append(f"тип {t!r}: {a} → {b}")
        if a == b:
            errs.append(f"петля {a}")
        if (a, b, t) in seen:
            errs.append(f"дубль {a} → {b} {t}")
        seen.add((a, b, t))
        if not r.get("why"):
            errs.append(f"нет why: {a} → {b}")
        if t == "prerequisites_for":
            late = C[a]["order"] > C[b]["order"] and not (set(C[a]["elements"]) & set(C[b]["elements"]))
            if late and not r.get("order_issue"):
                warn.append(f"предпосылка позже, но без order_issue: {C[a]['name']} → {C[b]['name']}")
    for t in ("prerequisites_for", "is_a", "part_of"):
        cyc = cycles([(r["source"], r["target"]) for r in R if r.get("type") == t], C)
        for c in cyc[:10]:
            errs.append(f"цикл {t}: " + " → ".join(C[x]["name"] for x in c))
    pairs = defaultdict(set)
    for r in R:
        pairs[frozenset((r["source"], r["target"]))].add(r["type"])
    for p, ts in pairs.items():
        if "prerequisites_for" in ts and (ts & {"is_a", "part_of"}):
            warn.append("prerequisites_for вместе с is_a/part_of: " + " / ".join(C[x]["name"] for x in p))
    if errs:
        print(f"ОШИБОК: {len(errs)}")
        for e in errs[:60]:
            print(" ", e)
        sys.exit(1)
    deg = Counter()
    for r in R:
        deg[r["source"]] += 1; deg[r["target"]] += 1
    iso = [C[c]["name"] for c in C if not deg[c]]
    print(f"OK: связей {len(R)}", dict(Counter(r['type'] for r in R)), f"order_issue: {sum(1 for r in R if r.get('order_issue'))}")
    print(f"понятий без связей: {len(iso)} из {len(C)}", iso[:30])
    for w in warn[:30]:
        print("  внимание:", w)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
