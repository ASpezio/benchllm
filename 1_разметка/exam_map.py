#!/usr/bin/env python3
"""Связь элементов содержания по классам с кодификаторами ОГЭ/ЕГЭ (история и физика).

Сходство: доля «веса» основ слов элемента класса, которые встречаются в элементе экзамена
(IDF-взвешенное покрытие) + сходство заголовков разделов. Кандидаты ограничены «областью»:
всеобщая история ↔ всеобщая история, история России ↔ история России, «Наш край» — без связи.
Ручные правки — exam_overrides.json: {"<id элемента класса>": ["<id экзамена>", ...] | []}.
"""
import json, re, math, sys, os
from collections import defaultdict, Counter
import Stemmer

REC = "/mnt/user-data/uploads/аа/разметка/records.jsonl"
OVR = "/home/claude/nav/exam_overrides.json"
OUT = "/home/claude/nav/exam_out.json"
st = Stemmer.Stemmer("russian")
STOP = set("и в во на с со к по о об от до из за для при как его ее её их а но или не что это же бы ли то век вв гг г".split())


def toks(t):
    ws = re.findall(r"[А-Яа-яЁёA-Za-z]+|\d{3,4}", (t or "").lower().replace("ё", "е"))
    return [st.stemWord(w) for w in ws if w not in STOP and len(w) > 2]


recs = [json.loads(l) for l in open(REC, encoding="utf-8")]
byid = {r["id"]: r for r in recs}
ovr = json.load(open(OVR, encoding="utf-8")) if os.path.exists(OVR) else {}


def section_of(r):
    p = r.get("parent_id")
    return byid[p] if p else r


def domain_class(r):
    """world | russia | region | None"""
    sec = section_of(r)
    t = (sec["text"] + " " + r["text"]).lower()
    if "наш край" in r["text"].lower() or "наш край" in sec["text"].lower() and sec is r:
        return "region"
    if r["subject"] == "physics":
        return "phys"
    if r["part"] == "SOO":
        return "world" if (r.get("group") or "").startswith("ВСЕОБЩ") else "russia"
    if r["grade"] == 5 or sec["text"].lower().startswith("всеобщая история"):
        return "world"
    return "russia"


def pkind(r):
    t = r["text"].lstrip().lower()
    if t.startswith("практическ"):
        return "practical"
    if t.startswith("физические явления в природе"):
        return "nature"
    if t.startswith("технические устройства"):
        return "devices"
    return "content"


def domain_exam(r):
    if r["subject"] == "physics":
        return "phys"
    top = r["code"].split(".")[0]
    if r["exam"] == "ОГЭ":
        return "world" if top == "5" else "russia"
    if r["code"] == "1-6":
        return "pre1914"
    return "world" if top in ("11", "12") else "russia"


result = {}
for subj in ("history", "physics"):
    for part, exam in (("OOO", "ОГЭ"), ("SOO", "ЕГЭ")):
        cls = [r for r in recs if r["subject"] == subj and r["part"] == part and r["type"] == "element"
               and r["block"] == "class_codifier" and not r.get("is_group")]
        ex_all = [r for r in recs if r["subject"] == subj and r["part"] == part and r["type"] == "exam_element"]
        ex = [r for r in ex_all if not r.get("is_group") and r["code"] != "1-6"]
        exsec = {r["code"]: r for r in ex_all if r.get("is_group")}
        # IDF по всем текстам этой пары
        docs = [set(toks(r["text"])) for r in cls + ex_all]
        df = Counter(w for d in docs for w in d)
        N = len(docs)
        idf = lambda w: math.log((N + 1) / (df.get(w, 0) + 1)) + 1
        ex_t = {e["id"]: set(toks(e["text"] + " " + (exsec.get(e["code"].split(".")[0], {}).get("text", "") if "." in e["code"] else ""))) for e in ex}
        for c in cls:
            dom = domain_class(c)
            sec = section_of(c)
            if dom == "region":
                result[c["id"]] = dict(exam=exam, ids=[], score=None, method="region", alt=[])
                continue
            ct = set(toks(c["text"]))
            st_ = set(toks(sec["text"])) if sec is not c else set()
            denom = sum(idf(w) for w in ct) or 1
            denom_s = sum(idf(w) for w in st_) or 1
            cands = []
            for e in ex:
                if dom != "phys" and domain_exam(e) != dom:
                    continue
                if dom == "phys" and pkind(e) != pkind(c):
                    continue
                et = ex_t[e["id"]]
                cov = sum(idf(w) for w in ct & et) / denom
                scov = sum(idf(w) for w in st_ & et) / denom_s if st_ else 0
                score = 0.7 * cov + 0.3 * scov if part == "OOO" or subj == "physics" else 0.35 * cov + 0.65 * scov
                cands.append((round(score, 3), e["id"]))
            cands.sort(reverse=True)
            best = cands[0] if cands else (0, None)
            result[c["id"]] = dict(exam=exam, ids=[best[1]] if best[1] else [], score=best[0], method="auto",
                                   alt=[x[1] for x in cands[1:3]])
for k, v in ovr.items():
    if k in result:
        result[k]["ids"] = v
        result[k]["method"] = "manual"
json.dump(result, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("mapped", len(result), "manual", sum(1 for v in result.values() if v["method"] == "manual"))
