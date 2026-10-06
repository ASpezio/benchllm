#!/usr/bin/env python3
"""Обратные связи «требование экзамена ← требования классов», CSV и сводка пробелов."""
import csv, json
from collections import defaultdict, Counter

REC = "/mnt/user-data/uploads/аа/разметка/records.jsonl"
recs = {json.loads(l)["id"]: json.loads(l) for l in open(REC, encoding="utf-8")}
X = json.load(open("/home/claude/nav/req_out.json", encoding="utf-8"))

rev = defaultdict(list)
for cid, v in X.items():
    for e in v["e"]:
        rev[e].append(cid)
exam_reqs = [r for r in recs.values() if r["type"] == "exam_requirement" and r["subject"] in ("history", "physics")]
json.dump(dict(cls={k: dict(e=v["e"], m=v["m"], why=v["why"]) for k, v in X.items()},
               exam={r["id"]: rev.get(r["id"], []) for r in exam_reqs}),
          open("/home/claude/nav/req_links.json", "w", encoding="utf-8"), ensure_ascii=False)

OUT = "/home/claude/nav/out"
with open(f"{OUT}/requirement_exam.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["requirement_id", "subject", "part", "grade", "code", "text", "exam", "exam_req_ids", "exam_req_codes", "why", "method"])
    for cid, v in X.items():
        r = recs[cid]
        w.writerow([cid, r["subject"], r["part"], r["grade"], r["code"], r["text"][:200], "ОГЭ" if r["part"] == "OOO" else "ЕГЭ",
                    ";".join(v["e"]), ";".join(recs[i]["code"] for i in v["e"]), v["why"], v["m"]])
with open(f"{OUT}/exam_requirement_coverage.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["exam_req_id", "subject", "exam", "code", "text", "class_req_count", "by_grade", "class_req_ids"])
    for r in exam_reqs:
        cs = rev.get(r["id"], [])
        bg = Counter(recs[c]["grade"] for c in cs)
        w.writerow([r["id"], r["subject"], r["exam"], r["code"], r["text"][:200], len(cs),
                    "; ".join(f"{g} кл.: {n}" for g, n in sorted(bg.items())), ";".join(cs)])

# сводка
for subj in ("history", "physics"):
    for ex in ("oge", "ege"):
        ers = [r for r in exam_reqs if f".{subj}.{ex}." in r["id"]]
        print(f"\n{subj} {ex}: требований экзамена {len(ers)}")
        for r in ers:
            cs = rev.get(r["id"], [])
            bg = Counter(recs[c]["grade"] for c in cs)
            print(f"  {r['code']:>3} [{len(cs):>3}] {dict(sorted(bg.items()))}  {r['text'][:70]}")
none = Counter(v["why"] for v in X.values() if not v["e"])
print("\nтребования классов без аналога в экзамене:", sum(none.values()), dict(none))
print("ручных правок:", sum(1 for v in X.values() if v["m"] == "manual"))
