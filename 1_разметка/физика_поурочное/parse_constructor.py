"""Разбор поурочного и тематического планирования по физике из выгрузки Конструктора edsoo."""
import json
import re
import sys

import pdfplumber


def clean(s):
    if s is None:
        return ""
    s = s.replace("­", "")
    # перенос с дефисом в конце строки: «Урок-\nисследование» -> «Урок-исследование»
    s = re.sub(r"-\n", "-", s)
    s = re.sub(r"\s*\n\s*", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def num(s):
    s = clean(s).replace(",", ".")
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return None


def collect_rows(pdf, start_marker, stop_markers):
    """Собирает строки таблиц со страницы, где встречается start_marker,
    до страницы, где встречается один из stop_markers (вне таблиц)."""
    rows, on = [], False
    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        if not on and start_marker in text:
            on = True
        if not on:
            continue
        for t in page.extract_tables():
            for r in t:
                rows.append((i + 1, r))
        if any(m in text for m in stop_markers) and start_marker not in text:
            # страница со следующим разделом: таблицы этой страницы уже взяты,
            # фильтруем позже по ширине строк
            break
    return rows


def parse_lessons(pdf, grades):
    rows = collect_rows(pdf, "ПОУРОЧНОЕ ПЛАНИРОВАНИЕ", ["ПЕРЕЧЕНЬ", "УЧЕБНО-МЕТОДИЧЕСКОЕ", "ПРОВЕРЯЕМЫЕ"])
    out, gi, cur, totals = [], -1, None, []
    for page, r in rows:
        if len(r) != 7:
            continue
        n, topic, h, kr, pr, date, cok = r
        n_c, topic_c = clean(n), clean(topic)
        if n_c.startswith("№") or topic_c == "" and clean(h) in ("Всего", ""):
            if not topic_c:
                continue
        if n_c.startswith("№"):
            continue
        if n_c.upper().startswith("ОБЩЕЕ") or topic_c.upper().startswith("ОБЩЕЕ"):
            totals.append({"grade": grades[gi], "raw": [clean(x) for x in r]})
            cur = None
            continue
        if re.fullmatch(r"\d+", n_c):
            k = int(n_c)
            if k == 1:
                gi += 1
            cur = {
                "grade": grades[gi],
                "n": k,
                "topic": topic_c,
                "hours": num(h),
                "kr": num(kr),
                "pr": num(pr),
                "cok": clean(cok),
                "page": page,
            }
            out.append(cur)
        elif n_c == "" and cur is not None:
            # продолжение ячейки на следующей странице
            if topic_c:
                sep = "" if cur["topic"].endswith("-") else " "
                cur["topic"] = (cur["topic"] + sep + topic_c).strip()
            if clean(cok) and not cur["cok"]:
                cur["cok"] = clean(cok)
    return out, totals


def parse_themes(pdf, grades):
    rows = collect_rows(pdf, "ТЕМАТИЧЕСКОЕ ПЛАНИРОВАНИЕ", ["ПОУРОЧНОЕ ПЛАНИРОВАНИЕ"])
    out, gi, section = [], -1, None
    for page, r in rows:
        if len(r) != 6:
            continue
        c = [clean(x) for x in r]
        n, name, h, kr, pr, cok = c
        joined = " ".join(c)
        if n.startswith("№") or name.startswith("Наименование") or h == "Всего":
            continue
        m = re.match(r"Раздел (\d+)\.\s*(.*)", n or name)
        if m:
            if m.group(1) == "1":
                gi += 1
            section = {"grade": grades[gi], "sec": int(m.group(1)), "name": m.group(2).strip(), "themes": []}
            out.append(section)
            continue
        if re.fullmatch(r"\d+\.\d+", n):
            section["themes"].append({"code": n, "name": name, "hours": num(h), "kr": num(kr), "pr": num(pr), "cok": cok})
            continue
        if n.startswith("Резервное") or name.startswith("Резервное"):
            hv = num(h) if num(h) else num(name.split()[-1]) if name else None
            out.append({"grade": grades[gi], "sec": None, "name": "Резервное время", "reserve_hours": num(h) or num(kr), "raw": c})
            continue
    return out


def main():
    res = {}
    for fn, grades, key in [("источники/Конструктор_Физика_7-9_база_ID12372761.pdf", [7, 8, 9], "OOO"), ("источники/Конструктор_Физика_10-11_база_ID12372794.pdf", [10, 11], "SOO")]:
        with pdfplumber.open(fn) as pdf:
            lessons, totals = parse_lessons(pdf, grades)
            themes = parse_themes(pdf, grades)
        res[key] = {"lessons": lessons, "totals": totals, "themes": themes}
    json.dump(res, open("parsed.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
