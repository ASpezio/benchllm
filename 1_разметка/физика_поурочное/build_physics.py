#!/usr/bin/env python3
"""Поурочное планирование по физике (Конструктор рабочих программ edsoo) -> разметка.

Вход:  parsed.json (parse.py), records.jsonl (основная разметка приказа).
Выход: records_physics_lessons.jsonl, lesson_element_physics.csv,
       element_weights_physics.csv, themes_physics.csv, check.txt

Привязка урок -> элемент кодификатора класса (п. 153.7 ООО / 115.9 СОО приказа):
  1) название урока делится на фрагменты по точкам («Электромагнитная индукция.
     Поток вектора магнитной индукции. ЭДС индукции…» -> 3 фрагмента);
  2) сходство фрагмент ↔ элемент: TF-IDF по символьным n-граммам основ (как align.py);
  3) раздел кодификатора: монотонное выравнивание фрагментов по разделам
     (разделы в уроках идут в том же порядке, что в кодификаторе);
  4) элемент внутри раздела: лучший по сходству — порядок тем внутри раздела
     в Конструкторе и в кодификаторе не совпадает;
  5) лабораторная часть урока -> элемент «Практические работы» раздела
     (урок целиком лабораторный — 1.0, «теория + лабораторная» — 0.5);
  6) контрольные, повторение, подготовка к КР и резервные уроки в веса не входят —
     привязываются к разделу(ам) по сходству.
Час урока делится между элементами пропорционально числу фрагментов.
Ручные правки — overrides_physics.json: {"<lesson_id>": ["<element_id>", ...]}.
"""
import csv
import sys
import json
import os
import re
import unicodedata
from collections import Counter, defaultdict

import numpy as np
import Stemmer
from sklearn.feature_extraction.text import TfidfVectorizer

PARSED = "parsed.json"
REC = sys.argv[1] if len(sys.argv) > 1 else "../records.jsonl"
OVR = "overrides_physics.json"
SRC = {"OOO": "12372761", "SOO": "12372794"}

st = Stemmer.Stemmer("russian")
STOP = set("и в во на с со к по о об от до из за для при как его ее её их а но или не что это же бы ли то "
           "тема теме темам урок".split())
LAB_PREFIX = re.compile(r"^(лабораторная работа|урок-(исследование|практикум|эксперимент)|экспериментальная)", re.I)
PREFIX = re.compile(r'^(урок-(исследование|конференция|практикум|эксперимент)( по теме)?|лабораторная работа( по теме)?|'
                    r'экспериментальная( \(лабораторная\))? работа( № ?\d+)?|решение задач( на [а-яё ]+?)?'
                    r'( по темам?| на тему)?|резервный урок)[\s.:]*', re.I)


def norm(t):
    t = unicodedata.normalize("NFC", t or "").replace("̆", "")
    return re.sub(r"\s+", " ", t).strip()


def prep(t):
    words = re.findall(r"[А-Яа-яЁёA-Za-z]+", (t or "").lower().replace("ё", "е"))
    return " ".join(st.stemWord(w) for w in words if w not in STOP and len(w) > 1)


def lesson_type(t, pr):
    tl = t.lower()
    if "контрольная работа" in tl:
        return "control"
    if re.match(r"рез\w*ный урок", tl):
        return "reserve"
    if re.search(r"(повторение, обобщение|обобщающий урок|подготовка к контрольной|^итоговый урок|^обобщение)", tl):
        return "review"
    if tl.startswith("урок-конференция"):
        return "conference"
    if LAB_PREFIX.match(tl):
        return "lab"
    if "лабораторная работа" in tl or pr > 0:
        return "mixed"
    if tl.startswith("решение задач"):
        return "problems"
    return "theory"


def leaf_cat(text):
    t = text.lower()
    if t.startswith("практические работы"):
        return "practice"
    if t.startswith("физические явления в природе"):
        return "nature"
    if t.startswith("технические устройства"):
        return "devices"
    return "content"


def parent(code):
    return code.rsplit(".", 1)[0] if "." in code else None


def fragments(text):
    """[(фрагмент, это_лабораторная)] — деление по точкам вне кавычек, не после инициалов."""
    t = norm(text)
    out, buf, depth = [], "", 0
    for k, ch in enumerate(t):
        if ch in "«“":
            depth += 1
        elif ch in "»”":
            depth = max(0, depth - 1)
        elif ch == '"':
            depth = 0 if depth else 1
        buf += ch
        if ch == "." and depth == 0 and k + 2 < len(t) and t[k + 1] == " " and t[k + 2].isupper():
            last = re.findall(r"(\S+)\.$", buf)
            if last and len(last[0]) <= 2:  # инициалы «А. Г. Столетова»
                continue
            out.append(buf.strip(" ."))
            buf = ""
    if buf.strip(" ."):
        out.append(buf.strip(" ."))
    res = []
    for f in out:
        is_lab = bool(LAB_PREFIX.match(f))
        g = PREFIX.sub("", f).strip(' «»"“”.')
        res.append((g or f, is_lab))
    return res


parsed = json.load(open(PARSED, encoding="utf-8"))
recs = [json.loads(l) for l in open(REC, encoding="utf-8")]
els, by_id = defaultdict(list), {}
for r in recs:
    if r["subject"] == "physics" and r["type"] == "element" and r["block"] == "class_codifier":
        els[(r["part"], r["grade"])].append(r)
        by_id[r["id"]] = r
overrides = json.load(open(OVR, encoding="utf-8")) if os.path.exists(OVR) else {}


def resolve(part, grade, v):
    """Код из overrides ("3.7", "8:7") -> {element_id: доля}."""
    if isinstance(v, dict):
        items = list(v.items())
    else:
        items = [(c, 1 / len(v)) for c in v] if v else []
    out = {}
    for c, sh in items:
        g, code = (int(c.split(":")[0]), c.split(":")[1]) if ":" in c else (grade, c)
        eid = f"{part}.physics.cls.g{g}.el.{code}"
        assert eid in by_id, eid
        out[eid] = sh
    return out

# ------------------------------------------------------------------ записи уроков
lesson_recs = []
for part in ("OOO", "SOO"):
    for l in parsed[part]["lessons"]:
        text = norm(l["topic"])
        pr, kr = float(l["pr"] or 0), float(l["kr"] or 0)
        lt = lesson_type(text, pr)
        lesson_recs.append({
            "id": f'{part}.physics.les.g{l["grade"]}.{l["n"]}',
            "type": "lesson", "part": part, "subject": "physics", "block": "lessons",
            "exam": None, "punkt": None, "grade": l["grade"], "table_no": None,
            "code": str(l["n"]), "text": text, "group": None, "page": l["page"],
            "flags": ["source:constructor"] + (["vpr"] if "всероссийская проверочная" in text.lower() else []),
            "lesson_n": l["n"], "hours": l["hours"],
            "lesson_kind": "review" if lt in ("control", "reserve", "review") else "new",
            "lesson_type": lt, "control_works": kr, "practical_works": pr, "cok": l["cok"],
            "source": f"Конструктор рабочих программ edsoo.ru, ID {SRC[part]}",
        })

by_class = defaultdict(list)
for r in lesson_recs:
    by_class[(r["part"], r["grade"])].append(r)

# ------------------------------------------------------------------ выравнивание
rows_out = []
SEC_JUMP = 0.01
GLUE = 0.10

for key in sorted(by_class):
    L = sorted(by_class[key], key=lambda r: r["lesson_n"])
    E = els[key]
    by_code = {e["code"]: e for e in E}
    leaves = [e for e in E if not e.get("is_group")]
    cats = [leaf_cat(e["text"]) for e in leaves]
    secs = list(dict.fromkeys(parent(e["code"]) for e in leaves))   # разделы в порядке кодификатора
    sec_idx = [secs.index(parent(e["code"])) for e in leaves]

    def ctx(e):
        p = by_code.get(parent(e["code"]))
        return (p["text"] + " " if p else "") + e["text"]

    cand_groups = [g for (p, gr), lst in els.items() if p == key[0] and gr <= key[1] for g in lst if g.get("is_group")]
    main = [i for i, l in enumerate(L) if l["lesson_kind"] == "new"]
    frags = [(i, f, lab) for i in main for f, lab in fragments(L[i]["text"])]

    corpus = ([prep(ctx(e)) for e in leaves] + [prep(g["text"]) for g in cand_groups]
              + [prep(l["text"]) for l in L] + [prep(f) for _, f, _ in frags])
    X = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True).fit_transform(corpus)
    a, b, c = len(leaves), len(leaves) + len(cand_groups), len(leaves) + len(cand_groups) + len(L)
    XE, XG, XL, XF = X[:a], X[a:b], X[b:c], X[c:]
    S, SG, SF = (XL @ XE.T).toarray(), (XL @ XG.T).toarray(), (XF @ XE.T).toarray()

    # сходство фрагмент ↔ раздел = максимум по элементам раздела
    SS = np.zeros((len(frags), len(secs)))
    for x, s in enumerate(sec_idx):
        SS[:, s] = np.maximum(SS[:, s], SF[:, x])

    dp_frag = [k for k in range(len(frags)) if SS[k].max() >= GLUE]
    with_dp = {frags[k][0] for k in dp_frag}
    dp_frag += [k for k in range(len(frags)) if frags[k][0] not in with_dp]
    dp_frag.sort()

    n, m = len(dp_frag), len(secs)
    Sc = SS[dp_frag]
    dp, bp = np.full((n, m), -1e9), np.zeros((n, m), dtype=int)
    dp[0] = Sc[0] - SEC_JUMP * np.arange(m)
    for i in range(1, n):
        best, arg = -1e9, 0
        for j in range(m):
            if dp[i - 1][j] > best:
                best, arg = dp[i - 1][j], j
            dp[i][j] = Sc[i][j] + best - SEC_JUMP * (j - arg)
            bp[i][j] = arg
    j = int(np.argmax(dp[n - 1]))
    sec_of_frag = {}
    for i in range(n - 1, -1, -1):
        sec_of_frag[dp_frag[i]] = j
        j = bp[i][j]

    for i in main:
        l = L[i]
        ks = [k for k in range(len(frags)) if frags[k][0] == i]
        lsecs = [sec_of_frag[k] for k in ks if k in sec_of_frag]
        lsec = Counter(lsecs).most_common(1)[0][0]
        lt = l["lesson_type"]
        prac = [x for x in range(len(leaves)) if cats[x] == "practice" and sec_idx[x] == lsec]
        theory_parts, notes, scores = defaultdict(float), [], []
        lab_frags = 0
        for k in ks:
            s = sec_of_frag.get(k, lsec)
            _, f, is_lab = frags[k]
            if lt == "lab" or (lt == "mixed" and is_lab):
                lab_frags += 1
                continue
            if SS[k].max() < GLUE and len(ks) > 1:
                continue                                     # «клей» без содержания
            pool = [x for x in range(len(leaves)) if sec_idx[x] == s and cats[x] != "practice"]
            cont = [x for x in pool if cats[x] == "content"] or pool
            x = max(cont, key=lambda x: SF[k][x])
            alt = [y for y in pool if cats[y] in ("nature", "devices")]
            if alt:
                y = max(alt, key=lambda y: SF[k][y])
                if SF[k][y] > SF[k][x] + 0.05:
                    x = y
                    notes.append("явления/устройства")
            theory_parts[x] += 1
            scores.append(float(SF[k][x]))
        # доли
        parts = []
        if lt == "lab":
            p_share, t_share = 1.0, 0.0
        elif lt == "mixed":
            p_share, t_share = 0.5, 0.5
        else:
            p_share, t_share = 0.0, 1.0
        if theory_parts and t_share:
            tot = sum(theory_parts.values())
            parts += [(leaves[x], t_share * v / tot) for x, v in theory_parts.items()]
        elif t_share and not theory_parts:
            p_share = 1.0
        if p_share:
            if prac:
                parts.append((leaves[prac[0]], p_share))
            else:
                notes.append("в разделе нет элемента «Практические работы»")
                kx = [k for k in ks]
                x = max([x for x in range(len(leaves)) if sec_idx[x] == lsec],
                        key=lambda x: max(SF[k][x] for k in kx))
                parts.append((leaves[x], p_share))
        merged = defaultdict(float)
        for e, sh in parts:
            merged[e["id"]] += sh
        uniq = list(merged)
        method = "auto"
        if l["id"] in overrides:
            merged = resolve(key[0], key[1], overrides[l["id"]])
            uniq = list(merged)
            method = "manual"
        top = int(np.argmax(S[i]))
        rows_out.append(dict(
            lesson_id=l["id"], part=key[0], grade=key[1], n=l["lesson_n"], title=l["text"],
            kind=l["lesson_kind"], lesson_type=lt, element_ids=";".join(uniq),
            codes="+".join(by_id[u]["code"] for u in uniq),
            share=";".join(str(round(merged[u], 3)) for u in uniq), method=method,
            score=round(min(scores), 3) if scores else "", best_code=leaves[top]["code"],
            note="; ".join(dict.fromkeys(notes))))

    for i, l in enumerate(L):
        if l["lesson_kind"] != "review":
            continue
        sc = SG[i] * np.array([1.25 if g["grade"] == key[1] else 1.0 for g in cand_groups])
        order = np.argsort(-sc)
        chosen = []
        if sc[order[0]] > 0.12:
            for gi in order[:4]:
                g = cand_groups[gi]
                if sc[gi] < 0.7 * sc[order[0]] or sc[gi] <= 0.12:
                    continue
                if any(cg["id"].startswith(g["id"] + ".") or g["id"].startswith(cg["id"] + ".") for cg in chosen):
                    continue
                chosen.append(g)
        ids = [g["id"] for g in chosen]
        method = "review"
        if l["id"] in overrides:
            ids = list(resolve(key[0], key[1], overrides[l["id"]]))
            method = "manual"
        rows_out.append(dict(
            lesson_id=l["id"], part=key[0], grade=key[1], n=l["lesson_n"], title=l["text"],
            kind="review", lesson_type=l["lesson_type"], element_ids=";".join(ids),
            codes="+".join(f'{by_id[g]["grade"]}кл:{by_id[g]["code"]}' for g in ids),
            share="", method=method, score=round(float(sc[order[0]]), 3), best_code="", note=""))

rows_out.sort(key=lambda r: (r["part"], r["grade"], r["n"]))

# ------------------------------------------------------------------ веса элементов
w, wl, rev = defaultdict(float), defaultdict(list), defaultdict(list)
class_hours = defaultdict(float)
for r in rows_out:
    key = (r["part"], r["grade"])
    if r["kind"] == "review":
        for g in filter(None, r["element_ids"].split(";")):
            rev[g].append(r["lesson_id"])
        continue
    class_hours[key] += 1.0
    for eid, sh in zip(r["element_ids"].split(";"), r["share"].split(";")):
        w[eid] += float(sh)
        wl[eid].append(r["lesson_id"])

el_rows = []
for key in sorted(els):
    tot = class_hours[key]
    for e in els[key]:
        h = sum(v for k, v in w.items() if k.startswith(e["id"] + ".")) if e.get("is_group") else w.get(e["id"], 0.0)
        el_rows.append(dict(element_id=e["id"], part=e["part"], grade=e["grade"], code=e["code"],
                            is_section=bool(e.get("is_group")),
                            category="" if e.get("is_group") else leaf_cat(e["text"]),
                            text=e["text"][:160], lesson_hours=round(h, 2),
                            share_of_class_pct=round(100 * h / tot, 2) if tot else 0, class_content_hours=tot,
                            lessons=";".join(wl.get(e["id"], [])), review_lessons=";".join(rev.get(e["id"], []))))

# ------------------------------------------------------------------ тематическое планирование (ФРП)
theme_rows = []
for part in ("OOO", "SOO"):
    for s in parsed[part]["themes"]:
        if s.get("themes") is None:
            theme_rows.append(dict(part=part, grade=s["grade"], section_no="", section="Резервное время",
                                   theme_code="", theme="Резервное время", hours=s.get("reserve_hours"),
                                   control=0, practical=0))
            continue
        for t in s["themes"]:
            theme_rows.append(dict(part=part, grade=s["grade"], section_no=s["sec"], section=norm(s["name"]),
                                   theme_code=t["code"], theme=norm(t["name"]), hours=t["hours"],
                                   control=t["kr"], practical=t["pr"]))
if not any(r["part"] == "SOO" and r["grade"] == 10 and r["theme"] == "Резервное время" for r in theme_rows):
    idx = max(i for i, r in enumerate(theme_rows) if r["part"] == "SOO" and r["grade"] == 10)
    theme_rows.insert(idx + 1, dict(part="SOO", grade=10, section_no="", section="Резервное время", theme_code="",
                                    theme="Резервное время", hours=2.0, control=0, practical=0))

# ------------------------------------------------------------------ запись
with open("records_physics_lessons.jsonl", "w", encoding="utf-8") as f:
    for r in lesson_recs:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
for name, rows in (("lesson_element_physics.csv", rows_out), ("element_weights_physics.csv", el_rows),
                   ("themes_physics.csv", theme_rows)):
    with open(name, "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)

# ------------------------------------------------------------------ сводка
out = []
for key in sorted(by_class):
    L = by_class[key]
    th = [t for t in theme_rows if t["part"] == key[0] and t["grade"] == key[1]]
    out.append(f'{key[0]} {key[1]} кл: уроков {len(L)}, часов {sum(l["hours"] for l in L):g}; '
               f'КР {sum(l["control_works"] for l in L):g} (тематич. {sum(t["control"] or 0 for t in th):g}), '
               f'ПР {sum(l["practical_works"] for l in L):g} (тематич. {sum(t["practical"] or 0 for t in th):g}); '
               f'ВПР {sum("vpr" in l["flags"] for l in L)}; типы {dict(Counter(l["lesson_type"] for l in L))}; '
               f'содержательных часов {class_hours[key]:g}')
leaves_all = [r for r in el_rows if not r["is_section"]]
zero = [r for r in leaves_all if r["lesson_hours"] == 0]
out.append(f"листьев кодификатора: {len(leaves_all)}, без уроков: {len(zero)} {dict(Counter(r['category'] for r in zero))}")
for r in zero:
    out.append(f'   0 ч: {r["part"]} {r["grade"]} {r["code"]} [{r["category"]}] {r["text"][:90]}')
multi = sum(1 for r in rows_out if r["kind"] == "new" and ";" in r["element_ids"])
out.append(f"содержательных уроков на несколько элементов: {multi}")
open("check.txt", "w", encoding="utf-8").write("\n".join(out) + "\n")
print("\n".join(out))
