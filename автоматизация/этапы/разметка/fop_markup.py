#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Разметка проекта приказа Минпросвещения
«О внесении изменений в некоторые приказы ... касающиеся ФОП НОО, ООО и СОО».

Слой 1 — навигация по всему документу (index.json, оглавление.md):
    уровень (НОО/ООО/СОО) -> предмет -> блок (поурочное / кодификатор по классам / ОГЭ-ЕГЭ) -> таблица, со страницами.
Слой 2 — построчная разметка выбранных предметов (records.jsonl):
    уроки, требования, элементы содержания, требования и элементы экзаменов — со стабильными ID.

Запуск:  python3 fop_markup.py "Проект приказа 2.pdf" разметка
Нужно:   pdftotext (poppler-utils), pdfplumber
"""
import os, re, sys, json, bisect, subprocess
from collections import defaultdict

SRC = sys.argv[1] if len(sys.argv) > 1 else "Проект приказа 2.pdf"
OUT = sys.argv[2] if len(sys.argv) > 2 else "разметка"
SELECTED = {"history", "physics"}      # какие предметы размечать построчно
SELECTED_PARTS = {"OOO", "SOO"}

PARTS = {"начального": ("NOO", "ФОП НОО (1–4 классы)"),
         "основного":  ("OOO", "ФОП ООО (5–9 классы)"),
         "среднего":   ("SOO", "ФОП СОО (10–11 классы)")}

SUBJ_KEYS = [  # (подстрока в названии, slug, название) — порядок важен
    ("метапредмет", "meta", "Метапредметные результаты"),
    ("литературн", "lit_reading", "Литературное чтение"),
    ("литератур", "literature", "Литература"),
    ("русск", "russian", "Русский язык"),
    ("английск", "english", "Иностранный язык (английский)"),
    ("немецк", "german", "Иностранный язык (немецкий)"),
    ("французск", "french", "Иностранный язык (французский)"),
    ("испанск", "spanish", "Иностранный язык (испанский)"),
    ("китайск", "chinese", "Иностранный язык (китайский)"),
    ("иностранн", "foreign", "Иностранный язык"),
    ("математ", "math", "Математика"),
    ("информат", "informatics", "Информатика"),
    ("истори", "history", "История"),
    ("обществозн", "social", "Обществознание"),
    ("географ", "geography", "География"),
    ("физик", "physics", "Физика"),
    ("хими", "chemistry", "Химия"),
    ("биолог", "biology", "Биология"),
    ("окружающ", "env", "Окружающий мир"),
]
NAMES = {slug: name for _, slug, name in SUBJ_KEYS}
NAMES.update({"technology": "Технология (труд)", "obzr": "ОБЗР"})
# блоки поурочного планирования, у которых нет кодификатора с тем же номером пункта
LESSON_ONLY = {("OOO", "162"): "technology", ("OOO", "1621"): "obzr",
               ("SOO", "1271"): "obzr", ("NOO", "167"): "technology"}
BTYPE_RU = {"lessons": "Поурочное планирование",
            "class_codifier": "Кодификатор по классам (ВПР и региональные процедуры)",
            "exam_codifier": "Кодификатор экзамена",
            "meta_codifier": "Кодификатор метапредметных результатов"}

HEAD = re.compile(r"«?\s*(\d{1,4}(?:\s?\.\s?\d+){1,2})\s?\.?\s+(Поурочное\s+планирование|В\s+федеральных\s+и\s+региональных\s+процедурах|Для\s+проведения\s+(?:основного|единого)\s+государственного\s+экзамена)")
FOOTER = re.compile(r"^(Изменения\s*[–-]\s*\d+|О внесении изменений\s*[–-]\s*\d+|\d{1,4}|»;?)$")
CODE = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,3})\.?$|^(\d{1,2}\s*[–-]\s*\d{1,2})$")
LESSON = re.compile(r"^Урок\s*(\d+)\.?$")
SUSPECT = re.compile(r"[-]|[=∆Δ→√∑∫²³]|(?<![А-Яа-яЁё])[a-zA-Z]\s*\(\s*[a-zA-Z]\s*\)")


def squash(s):
    return re.sub(r"\s+", " ", s or "").strip()


def norm_subject(s):
    if not s:
        return None
    low = s.lower()
    for key, slug, _ in SUBJ_KEYS:
        if key in low:
            return slug
    return None


def grade_from(title):
    m = re.search(r"(\d{1,2})\s*\(?\s*класс", title or "")
    return int(m.group(1)) if m else None


def table_kind(title, btype):
    t = (title or "").lower()
    if btype == "meta_codifier":
        return "meta"
    if "элемент" in t:
        return "elements"
    if "требован" in t or "результат" in t:
        return "requirements"
    return "unknown"


# ---------------------------------------------------------------- слой 1: оглавление
def build_index():
    raw = subprocess.run(["pdftotext", "-layout", SRC, "-"], capture_output=True, text=True, check=True).stdout
    pages = raw.split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    offs, pos = [], 0
    for p in pages:
        offs.append(pos)
        pos += len(p) + 1
    full = "\n".join(pages)
    page_of = lambda o: bisect.bisect_right(offs, o)  # 1-based

    p1 = squash(pages[0])
    doc_title = re.search(r"(О внесении изменений.+?среднего общего образования)", p1)
    in_force = re.search(r"вступает в силу\s+(с\s+\d{1,2}\s+\S+\s+\d{4}\s*г?\.?)", p1)

    parts = []
    for m in re.finditer(r"(?m)^\s*(\d)\.\s+В\s+федеральной\s+образовательной\s+программе\s+(начального|основного|среднего)\s+общего\s+образования", full):
        pid, ptitle = PARTS[m.group(2)]
        ctx = squash(full[m.start(): m.start() + 900])
        mo = re.search(r"утвержденной\s+приказом\s+Министерства\s+просвещения\s+Российской\s+Федерации\s+от\s+(\d{1,2}\s+\S+\s+\d{4})\s*г\.\s*№\s*(\d+)", ctx)
        parts.append(dict(id=pid, item=int(m.group(1)), title=ptitle,
                          amends=(f"ФОП, утв. приказом Минпросвещения от {mo.group(1)} г. № {mo.group(2)}" if mo else None),
                          offset=m.start(), start_page=page_of(m.start())))

    def part_at(o):
        cur = None
        for pm in parts:
            if pm["offset"] <= o:
                cur = pm
        return cur

    blocks = []
    for m in HEAD.finditer(full):
        num = re.sub(r"\s", "", m.group(1))
        word = m.group(2)
        ctx = squash(full[m.start(): m.start() + 700])
        pm = part_at(m.start())
        b = dict(part=pm["id"] if pm else None, num=num, top=num.split(".")[0],
                 offset=m.start(), start_page=page_of(m.start()), exam=None, subject_raw=None)
        if word.startswith("Поурочное"):
            b["type"] = "lessons"
        elif word.startswith("Для"):
            b["type"] = "exam_codifier"
            b["exam"] = "ОГЭ" if "основного" in word else "ЕГЭ"
            mo = re.search(r"экзамена\s+(?:по\s+)?(.+?)\s*\(далее", ctx) or re.search(r"экзамена\s+(?:по\s+)?(\S+\s+\S+)", ctx)
            b["subject_raw"] = mo.group(1) if mo else None
        elif "метапредмет" in ctx[:300]:
            b["type"] = "meta_codifier"
            b["subject_raw"] = "метапредметные"
        else:
            b["type"] = "class_codifier"
            mo = re.search(r"элементов\s+содержания\s+по\s+(?:учебному\s+предмету\s+)?«?(.+?)(?:»|\.\s)", ctx)
            b["subject_raw"] = mo.group(1) if mo else None
        blocks.append(b)

    for b in blocks:
        if b["type"] != "lessons":
            b["subject"] = norm_subject(b["subject_raw"])
    bytop = {}
    for b in blocks:
        if b["type"] in ("class_codifier", "exam_codifier") and b.get("subject"):
            bytop.setdefault((b["part"], b["top"]), b["subject"])
    for b in blocks:
        if b["type"] == "lessons":
            b["subject"] = bytop.get((b["part"], b["top"])) or LESSON_ONLY.get((b["part"], b["top"]))

    bounds = sorted([b["offset"] for b in blocks] + [p["offset"] for p in parts])
    for b in blocks:
        nxt = [o for o in bounds if o > b["offset"]]
        b["end_offset"] = nxt[0] if nxt else len(full)
        b["end_page"] = page_of(nxt[0]) if nxt else len(pages)

    # таблицы внутри блоков (по тексту; для выбранных предметов уточняются в слое 2)
    for b in blocks:
        seg = full[b["offset"]: b["end_offset"]]
        tabs = []
        if b["type"] == "lessons":
            for m in re.finditer(r"(?m)^\s*(Вариант\s+\d+\s*)?$|^\s*(\d{1,2})\s+класс\s*$", seg):
                if m.group(2):
                    tabs.append(dict(table_no=None, kind="lessons", grade=int(m.group(2)),
                                     title=f"{m.group(2)} класс", start_page=page_of(b["offset"] + m.start())))
        else:
            for m in re.finditer(r"Таблица\s*(\d+(?:\.\d+)*)\.?", seg):
                parts_t = []
                for x in seg[m.end(): m.end() + 500].split("\n"):
                    x = squash(x)
                    if not x or FOOTER.match(x):
                        continue
                    if x.startswith("Код") or x.startswith("№"):
                        break
                    parts_t.append(x)
                    if len(parts_t) >= 3:
                        break
                title = " ".join(parts_t)
                tabs.append(dict(table_no=m.group(1), kind=table_kind(title, b["type"]), grade=grade_from(title),
                                 title=title, start_page=page_of(b["offset"] + m.start())))
        for i, t in enumerate(tabs):
            t["end_page"] = tabs[i + 1]["start_page"] if i + 1 < len(tabs) else b["end_page"]
        b["tables"] = tabs
    return dict(pages=len(pages), title=doc_title.group(1) if doc_title else None,
                in_force=in_force.group(1) if in_force else None, parts=parts, blocks=blocks)


# ---------------------------------------------------------------- слой 2: построчная разметка
def block_short(b):
    return {"lessons": "les", "class_codifier": "cls", "meta_codifier": "meta",
            "exam_codifier": "oge" if b.get("exam") == "ОГЭ" else "ege"}[b["type"]]


def lesson_kind(t):
    tl = t.lower()
    if re.search(r"(урок повторени|повторительно|^обобщение|обобщающий урок|^итогов)", tl):
        return "review"
    if "наш край" in tl:
        return "region"
    return "new"


def parse_rows(idx):
    import pdfplumber
    blocks = idx["blocks"]
    headmap = {(b["start_page"], b["num"]): b for b in blocks}
    groups = defaultdict(list)
    for b in blocks:
        if b["part"] in SELECTED_PARTS and b.get("subject") in SELECTED:
            groups[(b["part"], b["subject"])].append(b)

    pdf = pdfplumber.open(SRC)
    records, ids, tables_out = [], set(), []

    def open_table(blk, kind, grade, no, title, page):
        t = dict(block=blk, kind=kind, grade=grade, table_no=no, title=title, start_page=page,
                 end_page=page, recs=[], last=None, group=None, declared_total=None, flags=[])
        tables_out.append(t)
        return t

    def add(tab, code, text, page, img, **extra):
        blk = tab["block"]
        if tab["kind"] == "lessons":
            rid = f'{blk["part"]}.{blk["subject"]}.les.g{tab["grade"]}.{extra["lesson_n"]}'
            rtype = "lesson"
        else:
            k = {"requirements": "req", "elements": "el"}.get(tab["kind"], "x")
            g = f'.g{tab["grade"]}' if tab["grade"] else ""
            rid = f'{blk["part"]}.{blk["subject"]}.{block_short(blk)}{g}.{k}.{code}'
            rtype = ("exam_" if blk["type"] == "exam_codifier" else "") + {"req": "requirement", "el": "element"}.get(k, "unknown")
        flags = []
        base, i = rid, 2
        while rid in ids:
            rid = f"{base}~{i}"
            i += 1
        if rid != base:
            flags.append("duplicate_id")
        ids.add(rid)
        if img:
            flags.append("page_has_images")
        rec = dict(id=rid, type=rtype, part=blk["part"], subject=blk["subject"], block=blk["type"],
                   exam=blk.get("exam"), punkt=blk["num"], grade=tab["grade"], table_no=tab["table_no"],
                   code=code, text=text, group=tab["group"], page=page, flags=flags)
        rec.update(extra)
        records.append(rec)
        tab["recs"].append(rec)
        tab["last"] = rec
        tab["end_page"] = page
        return rec

    def append_text(tab, txt, page, img):
        if tab["last"] is None:
            tab["flags"].append(f"orphan_text_p{page}")
            return
        r = tab["last"]
        r["text"] = squash(r["text"] + " " + txt)
        if page != r["page"] and "spans_pages" not in r["flags"]:
            r["flags"].append("spans_pages")
        if img and "page_has_images" not in r["flags"]:
            r["flags"].append("page_has_images")
        tab["end_page"] = page

    def handle_row(tab, row, page, img):
        cells = [squash(c) for c in row]
        nonempty = [c for c in cells if c]
        if not nonempty:
            return
        first = nonempty[0]
        if first.startswith("Код") or first.startswith("№"):
            return
        if tab["kind"] == "lessons":
            if first.upper().startswith("ОБЩЕЕ КОЛИЧЕСТВО"):
                m = re.search(r"(\d+)", " ".join(nonempty))
                tab["declared_total"] = int(m.group(1)) if m else None
                return
            li = next((i for i, c in enumerate(cells) if LESSON.match(c)), None)
            if li is None:
                append_text(tab, " ".join(c for c in nonempty if not re.fullmatch(r"\d+", c)), page, img)
                return
            n = int(LESSON.match(cells[li]).group(1))
            texts, hours = [], None
            for c in [c for i, c in enumerate(cells) if i != li and c]:
                if re.fullmatch(r"\d+", c) and texts and hours is None:
                    hours = int(c)
                else:
                    texts.append(c)
            title = squash(" ".join(texts))
            add(tab, str(n), title, page, img, lesson_n=n, hours=hours if hours is not None else 1,
                lesson_kind=lesson_kind(title))
            return
        ci = next((i for i, c in enumerate(cells) if c and CODE.match(c)), None)
        if ci is None:
            m = re.match(r"^(\d{1,2}(?:\.\d{1,2}){0,3})\.?\s+(\S.*)$", cells[0]) if cells[0] else None
            if m:
                add(tab, m.group(1), squash(m.group(2) + " " + " ".join(cells[1:])), page, img)
                return
            txt = " ".join(nonempty)
            letters = [ch for ch in txt if ch.isalpha()]
            if letters and sum(ch.isupper() for ch in letters) / len(letters) > 0.85 and len(txt) < 80:
                tab["group"] = txt
                return
            append_text(tab, txt, page, img)
            return
        code = re.sub(r"\s", "", cells[ci]).replace("–", "-").rstrip(".")
        text = squash(" ".join(c for i, c in enumerate(cells) if i > ci and c))
        add(tab, code, text, page, img)

    def flush_loose(tab, lines, page, img):
        """Строки над первой таблицей страницы = строка таблицы, перенесённая без верхней рамки."""
        if not lines or tab is None:
            return
        rows, pre = [], []
        for s in lines:
            if tab["kind"] == "lessons":
                m = re.match(r"^Урок\s*(\d+)\.?\s*(.*)$", s)
            else:
                m = re.match(r"^(\d{1,2}(?:\.\d{1,2}){0,3})\.?(?:\s+(.*))?$", s)
            if m:
                rows.append([m.group(1), list(pre) + ([m.group(2)] if m.group(2) else []), bool(m.group(2))])
                pre = []
            elif rows and not rows[-1][2]:
                rows[-1][1].append(s)
            elif rows:
                rows[-1][1].append(s)
            else:
                pre.append(s)
        if pre:  # текст без метки — продолжение предыдущей записи
            append_text(tab, " ".join(pre), page, img)
        for key, texts, _ in rows:
            txt = squash(" ".join(texts))
            if tab["kind"] == "lessons":
                handle_row(tab, ["Урок " + key, txt], page, img)
            else:
                handle_row(tab, [key, txt], page, img)
        tab["loose_rows"] = tab.get("loose_rows", 0) + len(rows)

    for (part, subj), bl in groups.items():
        p0 = min(b["start_page"] for b in bl)
        p1 = max(b["end_page"] for b in bl)
        cur_block = cur_tab = pending = None
        grade_ctx = None
        for pn in range(p0, p1 + 1):
            page = pdf.pages[pn - 1]
            tables = page.find_tables()
            boxes = [t.bbox for t in tables]
            img = bool(page.images)
            events = []
            for ln in page.extract_text_lines(strip=True):
                yc = (ln["top"] + ln["bottom"]) / 2
                if any(bx[1] - 1 <= yc <= bx[3] + 1 and ln["x0"] < bx[2] and ln["x1"] > bx[0] for bx in boxes):
                    continue
                events.append((ln["top"], 0, squash(ln["text"])))
            for t in tables:
                events.append((t.bbox[1], 1, t))
            events.sort(key=lambda e: (e[0], e[1]))
            loose, seen_table = [], False
            for _, kind, obj in events:
                if kind == 0:
                    s = obj
                    if FOOTER.match(s):
                        continue
                    mh = HEAD.search(s)
                    if mh:
                        num = re.sub(r"\s", "", mh.group(1))
                        b = headmap.get((pn, num))
                        cur_block = b if (b is not None and any(b is x for x in bl)) else None
                        cur_tab = pending = None
                        grade_ctx = None
                        loose = []
                        continue
                    if cur_block is None:
                        continue
                    mg = re.fullmatch(r"(\d{1,2})\s+класс", s)
                    if mg and cur_block["type"] == "lessons":
                        cur_tab = open_table(cur_block, "lessons", int(mg.group(1)), None, s, pn)
                        loose = []
                        continue
                    mt = re.match(r"Таблица\s*(\d+(?:\.\d+)*)\.?\s*(.*)$", s)
                    if mt:
                        pending = dict(no=mt.group(1), title=[mt.group(2)] if mt.group(2) else [], page=pn)
                        loose = []
                        continue
                    if pending is not None:
                        pending["title"].append(s)
                    elif cur_tab is not None and not seen_table:
                        loose.append(s)
                else:
                    seen_table = True
                    if cur_block is None:
                        continue
                    if pending is not None:
                        title = squash(" ".join(pending["title"]))
                        g = grade_from(title)
                        if g is None and cur_block["type"] == "class_codifier":
                            g = grade_ctx
                        if g is not None:
                            grade_ctx = g
                        cur_tab = open_table(cur_block, table_kind(title, cur_block["type"]), g, pending["no"], title, pending["page"])
                        if len(pending["title"]) > 5:
                            cur_tab["flags"].append("long_title_check_missed_table")
                        pending = None
                    if cur_tab is None:
                        cur_tab = open_table(cur_block, "unknown", None, None, "(таблица без подписи)", pn)
                        cur_tab["flags"].append("no_caption")
                    if loose:
                        flush_loose(cur_tab, loose, pn, img)
                        loose = []
                    for row in obj.extract():
                        handle_row(cur_tab, row, pn, img)

    # иерархия, глаголы, проверки
    for t in tables_out:
        codes = {r["code"]: r for r in t["recs"] if t["kind"] != "lessons"}
        children = defaultdict(int)
        for r in t["recs"]:
            if t["kind"] == "lessons":
                continue
            pc = r["code"].rsplit(".", 1)[0] if "." in r["code"] else None
            r["parent_id"] = codes[pc]["id"] if pc in codes else None
            if pc in codes:
                children[pc] += 1
        for r in t["recs"]:
            if t["kind"] == "lessons":
                continue
            r["is_group"] = children[r["code"]] > 0
            if r["type"].endswith("requirement") and not r["is_group"]:
                w = re.match(r"[«(]?([А-Яа-яЁё-]+)", r["text"] or "")
                r["verb"] = w.group(1).lower() if w else None
            if SUSPECT.search(r["text"] or "") and "formula_suspect" not in r["flags"]:
                r["flags"].append("formula_suspect")
            if not r["text"]:
                r["flags"].append("empty_text")
        if t["kind"] == "lessons":
            ns = [r["lesson_n"] for r in t["recs"]]
            if ns != list(range(1, len(ns) + 1)):
                t["flags"].append("lesson_numbering_gap")
            if t["declared_total"] is not None and t["declared_total"] != len(ns):
                t["flags"].append(f"total_mismatch_declared_{t['declared_total']}")
    return records, tables_out


# ---------------------------------------------------------------- вывод
def main():
    os.makedirs(OUT, exist_ok=True)
    idx = build_index()
    records, tabs = parse_rows(idx)

    parsed = defaultdict(list)
    for t in tabs:
        parsed[id(t["block"])].append(t)

    def table_json(t, from_rows):
        d = dict(table_no=t["table_no"], kind=t["kind"], grade=t["grade"], title=t["title"],
                 pages=[t["start_page"], t["end_page"]])
        if from_rows:
            recs = t["recs"]
            d["records"] = len(recs)
            d["id_prefix"] = recs[0]["id"].rsplit(".", 1)[0] if recs and t["kind"] == "lessons" else (
                re.sub(r"\.[^.]*$", "", recs[0]["id"].split("~")[0][:-len(recs[0]["code"])] + "x") if recs else None)
            if t["kind"] == "lessons":
                d["review_lessons"] = sum(r["lesson_kind"] == "review" for r in recs)
                d["region_lessons"] = sum(r["lesson_kind"] == "region" for r in recs)
                d["declared_total"] = t["declared_total"]
            if t["flags"]:
                d["flags"] = t["flags"]
        return d

    out_parts = []
    for p in idx["parts"]:
        pb = [b for b in idx["blocks"] if b["part"] == p["id"]]
        subj_order, subj = [], defaultdict(list)
        for b in pb:
            k = b.get("subject") or "unknown"
            if k not in subj:
                subj_order.append(k)
            subj[k].append(b)
        nxt = [q["start_page"] for q in idx["parts"] if q["offset"] > p["offset"]]
        part_json = dict(id=p["id"], title=p["title"], amends=p["amends"],
                         pages=[p["start_page"], nxt[0] if nxt else idx["pages"]], subjects=[])
        for k in subj_order:
            sj = dict(id=f'{p["id"]}.{k}', slug=k, name=NAMES.get(k, k),
                      pages=[min(b["start_page"] for b in subj[k]), max(b["end_page"] for b in subj[k])],
                      parsed=bool(parsed.get(id(subj[k][0]))) or any(parsed.get(id(b)) for b in subj[k]), blocks=[])
            for b in subj[k]:
                bj = dict(id=f'{p["id"]}.{k}.{block_short(b)}', type=b["type"], type_ru=BTYPE_RU[b["type"]],
                          exam=b["exam"], punkt=b["num"], pages=[b["start_page"], b["end_page"]])
                if b.get("subject") is None:
                    bj["subject_raw"] = b["subject_raw"]
                pt = parsed.get(id(b))
                bj["tables"] = [table_json(t, True) for t in pt] if pt else [table_json(t, False) for t in b["tables"]]
                sj["blocks"].append(bj)
            part_json["subjects"].append(sj)
        out_parts.append(part_json)

    index = dict(source=os.path.basename(SRC), document_title=idx["title"], in_force=idx["in_force"],
                 status="проект (дата и номер не заполнены)", pages=idx["pages"],
                 parsed_subjects=sorted(SELECTED), parsed_parts=sorted(SELECTED_PARTS),
                 id_format={"lesson": "<уровень>.<предмет>.les.g<класс>.<№ урока>",
                            "class_codifier": "<уровень>.<предмет>.cls.g<класс>.<req|el>.<код>",
                            "exam": "<уровень>.<предмет>.<oge|ege>.<req|el>.<код>"},
                 parts=out_parts)
    with open(os.path.join(OUT, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT, "records.jsonl"), "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # человекочитаемое оглавление
    L = [f"# Оглавление: {index['source']}", "",
         f"**{index['document_title']}** — {index['status']}. Вступает в силу {index['in_force']}. Страниц: {index['pages']}.", "",
         "Построчно размечены: " + ", ".join(NAMES[s] for s in sorted(SELECTED)) + " (ООО и СОО) → `records.jsonl`.",
         "Формат ID: `" + index["id_format"]["lesson"] + "`, `" + index["id_format"]["class_codifier"] + "`, `" + index["id_format"]["exam"] + "`.", ""]
    for p in out_parts:
        L += [f"## {p['title']} — стр. {p['pages'][0]}–{p['pages'][1]}", f"_Изменения в {p['amends']}_", ""]
        for s in p["subjects"]:
            mark = " ✅ размечено построчно" if s["parsed"] else ""
            L.append(f"### {s['name']} — стр. {s['pages'][0]}–{s['pages'][1]}{mark}")
            for b in s["blocks"]:
                ex = f" ({b['exam']})" if b["exam"] else ""
                L.append(f"- **{b['type_ru']}{ex}**, п. {b['punkt']} — стр. {b['pages'][0]}–{b['pages'][1]} · `{b['id']}`")
                for t in b["tables"]:
                    what = {"lessons": "Уроки", "requirements": "Требования", "elements": "Элементы содержания",
                            "meta": "Метапредметные требования"}.get(t["kind"], t["kind"])
                    g = f", {t['grade']} класс" if t["grade"] else ""
                    no = f"Табл. {t['table_no']} · " if t["table_no"] else ""
                    extra = ""
                    if "records" in t:
                        extra = f" — {t['records']} зап."
                        if t["kind"] == "lessons":
                            extra += f" (повторение/контроль: {t['review_lessons']}, «наш край»: {t['region_lessons']})"
                        if t.get("flags"):
                            extra += " ⚠️ " + ", ".join(t["flags"])
                    L.append(f"  - {no}{what}{g} — стр. {t['pages'][0]}–{t['pages'][1]}{extra}")
            L.append("")
    with open(os.path.join(OUT, "оглавление.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"blocks={len(idx['blocks'])} records={len(records)} tables_parsed={len(tabs)}")


if __name__ == "__main__":
    main()
