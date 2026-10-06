#!/usr/bin/env python3
"""Сопоставление уроков истории с элементами содержания того же класса.

1) сходство «название урока ↔ текст элемента»: TF-IDF по символьным n-граммам основ слов;
2) монотонное выравнивание (динамика): уроки идут в порядке элементов, элемент может
   занимать несколько уроков подряд, элементы без уроков допускаются;
3) уроки повторения/контроля в выравнивание не входят — привязываются к разделу (вес 0).
Ручные правки — в overrides.json: {"<lesson_id>": "<element_id>" | null}.
"""
import json, re, sys, os
from collections import defaultdict
import numpy as np
import Stemmer
from sklearn.feature_extraction.text import TfidfVectorizer

REC = sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/uploads/аа/разметка/records.jsonl"
OVR = sys.argv[2] if len(sys.argv) > 2 else "/home/claude/nav/overrides.json"
OUT = sys.argv[3] if len(sys.argv) > 3 else "/home/claude/nav/align_out.json"

st = Stemmer.Stemmer("russian")
STOP = set("и в во на с со к по о об от до из за для при как его ее её их а но или не что это же бы ли то".split())


def prep(t):
    words = re.findall(r"[А-Яа-яЁёA-Za-z]+|\d{3,4}", (t or "").lower().replace("ё", "е"))
    return " ".join(st.stemWord(w) for w in words if w not in STOP and len(w) > 1)


recs = [json.loads(l) for l in open(REC, encoding="utf-8")]
lessons = defaultdict(list)
elements = defaultdict(list)
for r in recs:
    if r["subject"] != "history":
        continue
    if r["type"] == "lesson":
        lessons[(r["part"], r["grade"])].append(r)
    elif r["type"] == "element" and r["block"] == "class_codifier":
        elements[(r["part"], r["grade"])].append(r)

overrides = json.load(open(OVR, encoding="utf-8")) if os.path.exists(OVR) else {}

result = {}
for key in sorted(lessons):
    L = sorted(lessons[key], key=lambda r: r["lesson_n"])
    E_all = elements[key]
    leaves = [e for e in E_all if not e.get("is_group")]
    groups = [e for e in E_all if e.get("is_group")]
    # текст листа = свой текст + название раздела (контекст)
    by_code = {e["code"]: e for e in E_all}
    def ctx(e):
        par = by_code.get(e["code"].rsplit(".", 1)[0]) if "." in e["code"] else None
        return (par["text"] + " " if par else "") + e["text"]
    corpus = [prep(ctx(e)) for e in leaves] + [prep(g["text"]) for g in groups] + [prep(l["text"]) for l in L]
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=1)
    X = vec.fit_transform(corpus)
    XE = X[: len(leaves)]
    XG = X[len(leaves): len(leaves) + len(groups)]
    XL = X[len(leaves) + len(groups):]
    S = (XL @ XE.T).toarray()          # уроки × листья
    SG = (XL @ XG.T).toarray() if groups else None

    main_idx = [i for i, l in enumerate(L) if l["lesson_kind"] != "review"]
    n, m = len(main_idx), len(leaves)
    # DP: dp[i][j] — лучшая сумма, если i-й основной урок отнесён к j-му листу (j не убывает)
    NEG = -1e9
    dp = np.full((n, m), NEG)
    bp = np.zeros((n, m), dtype=int)
    JUMP = 0.004  # лёгкий штраф за пропуск листьев, чтобы не перескакивать без причины
    for j in range(m):
        dp[0][j] = S[main_idx[0]][j] - JUMP * j
    for i in range(1, n):
        best, arg = NEG, 0
        for j in range(m):
            # переход из любого j' <= j
            cand = dp[i - 1][j]
            if j > 0 and best - JUMP <= dp[i - 1][j]:
                pass
            if dp[i - 1][j] > best:
                best, arg = dp[i - 1][j], j
            dp[i][j] = S[main_idx[i]][j] + best - JUMP * (j - arg)
            bp[i][j] = arg
    j = int(np.argmax(dp[n - 1]))
    assign = [0] * n
    for i in range(n - 1, -1, -1):
        assign[i] = j
        j = bp[i][j]

    rows = []
    for k, i in enumerate(main_idx):
        l = L[i]
        e = leaves[assign[k]]
        top = int(np.argmax(S[i]))
        rows.append(dict(lesson=l["id"], n=l["lesson_n"], kind=l["lesson_kind"], title=l["text"],
                         element=e["id"], elements=[e["id"]], code=e["code"], etext=e["text"],
                         score=round(float(S[i][assign[k]]), 3),
                         best_code=leaves[top]["code"], best_score=round(float(S[i][top]), 3), method="auto"))
    for i, l in enumerate(L):
        if l["lesson_kind"] != "review":
            continue
        g = None
        if groups:
            q = re.search(r"«(.+)", l["text"])
            gi = int(np.argmax(SG[i]))
            g = groups[gi]
        rows.append(dict(lesson=l["id"], n=l["lesson_n"], kind="review", title=l["text"],
                         element=None, section=(g["id"] if g else None), section_code=(g["code"] if g else None),
                         section_text=(g["text"] if g else None), score=None, method="review"))
    rows.sort(key=lambda r: r["n"])
    # ручные правки
    eid = {x["id"]: x for x in recs if x["subject"] == "history" and x["type"] != "lesson"}
    for r in rows:
        if r["lesson"] in overrides:
            v = overrides[r["lesson"]]
            if r["kind"] == "review":
                vs = v if isinstance(v, list) else ([v] if v else [])
                r["sections"] = vs
                r["section"] = vs[0] if vs else None
                r["section_code"] = "+".join(eid[x]["code"] for x in vs) if vs else None
                r["section_text"] = " | ".join(eid[x]["text"][:60] for x in vs) if vs else None
            else:
                vs = v if isinstance(v, list) else ([v] if v else [])
                r["elements"] = vs
                r["element"] = vs[0] if vs else None
                r["code"] = "+".join(eid[x]["code"] for x in vs) if vs else None
                r["etext"] = " | ".join(eid[x]["text"][:60] for x in vs) if vs else None
            r["method"] = "manual"
    result[f"{key[0]}.g{key[1]}"] = rows

json.dump(result, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for k, rows in result.items():
    a = [r for r in rows if r["kind"] != "review"]
    low = sum(1 for r in a if r["score"] is not None and r["score"] < 0.15)
    dis = sum(1 for r in a if r.get("best_code") and r["best_code"] != r["code"])
    print(k, "lessons", len(rows), "aligned", len(a), "low<0.15:", low, "dp≠argmax:", dis)
