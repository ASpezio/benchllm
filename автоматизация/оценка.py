#!/usr/bin/env python3
"""Насколько решения модели совпадают с эталоном — например, локальная Qwen против пилота, сделанного Claude.

  python3 оценка.py прогоны/qwen прогоны/проект_2024

Эталон — прогон в режиме replay (текущие данные проекта). Сравниваются итоговые результаты, а не ответы:
  уроки → элементы (история и физика), элемент → пункт экзамена, умение → требование экзамена — доля совпадений;
  понятия по каждому элементу и связи между понятиями — точность, полнота, F1.
"""
import csv
import json
import os
import re
import sys
from collections import defaultdict


def rows(path, key, val):
    out = {}
    for r in csv.DictReader(open(path, encoding="utf-8-sig")):
        out[r[key]] = frozenset(x for x in r[val].split(";") if x)
    return out


def agree(name, a, b):
    keys = sorted(set(a) & set(b))
    same = sum(1 for k in keys if a[k] == b[k])
    print(f"  {name:34s} совпало {same} из {len(keys)} ({100 * same / max(1, len(keys)):.1f}%)")
    return [k for k in keys if a[k] != b[k]]


def norm(s):
    s = (s or "").lower().replace("ё", "е")
    s = re.sub(r"[‐-‒–—−]", "-", s)
    return re.sub(r"\s+", " ", s).strip(" .")


def prf(name, got, gold):
    tp = len(got & gold)
    p, r = tp / max(1, len(got)), tp / max(1, len(gold))
    f = 2 * p * r / max(1e-9, p + r)
    print(f"  {name:34s} точность {p:.2f}  полнота {r:.2f}  F1 {f:.2f}  (модель {len(got)}, эталон {len(gold)})")


def concepts(run):
    d = os.path.join(run, "2_граф", "понятия", "наборы")
    out = set()
    for f in os.listdir(d) if os.path.isdir(d) else []:
        if f.startswith("out_"):
            for o in json.load(open(os.path.join(d, f), encoding="utf-8")):
                out |= {(o["source_id"], norm(c["name"])) for c in o["concepts"]}
    return out


def relations(run):
    d = os.path.join(run, "2_граф", "связи", "наборы")
    out = set()
    for f in os.listdir(d) if os.path.isdir(d) else []:
        if f.startswith("out_"):
            out |= {(r["source"], r["target"], r["type"]) for r in json.load(open(os.path.join(d, f), encoding="utf-8"))}
    return out


def main(a, b):
    print(f"модель: {a}\nэталон: {b}\n\nпривязки:")
    M = lambda run, *p: os.path.join(run, "1_разметка", *p)
    diffs = {}
    diffs["уроки истории"] = agree("уроки истории → элементы", rows(M(a, "lesson_element.csv"), "lesson_id", "element_ids"),
                                   rows(M(b, "lesson_element.csv"), "lesson_id", "element_ids"))
    diffs["уроки физики"] = agree("уроки физики → элементы", rows(M(a, "физика_поурочное", "lesson_element_physics.csv"), "lesson_id", "element_ids"),
                                  rows(M(b, "физика_поурочное", "lesson_element_physics.csv"), "lesson_id", "element_ids"))
    diffs["экзамен"] = agree("элементы → пункты ОГЭ/ЕГЭ", rows(M(a, "element_exam.csv"), "element_id", "exam_ids"),
                             rows(M(b, "element_exam.csv"), "element_id", "exam_ids"))
    diffs["умения"] = agree("умения → требования экзамена", rows(M(a, "requirement_exam.csv"), "requirement_id", "exam_req_ids"),
                            rows(M(b, "requirement_exam.csv"), "requirement_id", "exam_req_ids"))
    print("\nграф:")
    prf("понятия (элемент, имя)", concepts(a), concepts(b))
    ra, rb = relations(a), relations(b)
    prf("связи (откуда, куда, тип)", ra, rb)
    prf("связи без учёта типа", {(x, y) for x, y, _ in ra}, {(x, y) for x, y, _ in rb})
    out = os.path.join(a, "оценка_расхождения.json")
    json.dump(diffs, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nрасхождения по привязкам: {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
