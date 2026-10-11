#!/usr/bin/env python3
"""Сравнение двух результатов: прогона с проектом (проверка воспроизводимости) или двух прогонов
на разных редакциях документа (что изменилось в программе).

  python3 сравнить.py прогоны/проект_2024 ..             файлы прогона против текущих файлов проекта
  python3 сравнить.py прогоны/физика_7 ..                 то же для бенчмарка (знания и задания среза)
  python3 сравнить.py прогоны/старая прогоны/новая --записи   какие элементы, умения, уроки добавлены, убраны, изменены
"""
import csv
import json
import os
import sys
from collections import Counter

FILES = [
    "1_разметка/records.jsonl", "1_разметка/index.json", "1_разметка/формулы_mineru.json",
    "1_разметка/lesson_element.csv", "1_разметка/element_weights.csv",
    "1_разметка/element_exam.csv", "1_разметка/exam_coverage.csv",
    "1_разметка/requirement_exam.csv", "1_разметка/exam_requirement_coverage.csv",
    "1_разметка/физика_поурочное/records_physics_lessons.jsonl", "1_разметка/физика_поурочное/lesson_element_physics.csv",
    "1_разметка/физика_поурочное/element_weights_physics.csv", "1_разметка/физика_поурочное/element_weights_physics_combined.csv",
    "1_разметка/физика_поурочное/themes_physics.csv",
    "2_граф/каркас/nodes.jsonl", "2_граф/каркас/edges.jsonl",
    "2_граф/понятия/concepts.jsonl", "2_граф/понятия/mentions.jsonl",
    "2_граф/граф/nodes.jsonl", "2_граф/граф/edges.jsonl",
]


def bench_files(run):
    """Если прогон — бенчмарк (конфиг с «вид»: «бенчмарк»), сравниваются файлы частей 3–4 его среза."""
    p = os.path.join(run, "конфиг.json")
    cfg = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    if cfg.get("вид") != "бенчмарк":
        return None
    s = cfg["срез"]["имя"]
    return [f"3_знания/{s}/срез.json", f"3_знания/{s}/источники/цок_корпус.jsonl", f"3_знания/{s}/знания.jsonl",
            f"3_знания/{s}/формулы.json", f"4_бенчмарк/{s}/задания.jsonl", f"4_бенчмарк/{s}/сводка.json"]


def canon(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True)


def load(path):
    if path.endswith(".jsonl"):
        return Counter(canon(json.loads(l)) for l in open(path, encoding="utf-8") if l.strip())
    if path.endswith(".csv"):
        return Counter(canon(r) for r in csv.DictReader(open(path, encoding="utf-8-sig")))
    return json.load(open(path, encoding="utf-8"))


def files(a, b):
    same = 0
    lst = bench_files(a) or bench_files(b) or FILES
    for f in lst:
        pa, pb = os.path.join(a, f), os.path.join(b, f)
        if not (os.path.exists(pa) and os.path.exists(pb)):
            print(f"  ?  {f}: нет в {'первом' if not os.path.exists(pa) else 'втором'}")
            continue
        x, y = load(pa), load(pb)
        if x == y:
            same += 1
            print(f"  =  {f}")
            continue
        if isinstance(x, Counter):
            only_a, only_b = x - y, y - x
            print(f"  ≠  {f}: только в первом {sum(only_a.values())}, только во втором {sum(only_b.values())}")
            for s in list(only_a)[:2]:
                print("       1:", s[:220])
            for s in list(only_b)[:2]:
                print("       2:", s[:220])
        else:
            ka, kb = set(x) if isinstance(x, dict) else set(), set(y) if isinstance(y, dict) else set()
            diff = [k for k in ka & kb if x[k] != y[k]]
            print(f"  ≠  {f}: ключей {len(ka)} / {len(kb)}, различаются {len(diff)}", diff[:5])
    print(f"совпало файлов: {same} из {len(lst)}")


def records_diff(a, b):
    def recs(d):
        return {r["id"]: r for r in (json.loads(l) for l in open(os.path.join(d, "1_разметка/records.jsonl"), encoding="utf-8"))}
    x, y = recs(a), recs(b)
    added, removed = sorted(set(y) - set(x)), sorted(set(x) - set(y))
    changed = sorted(k for k in set(x) & set(y) if x[k]["text"] != y[k]["text"])

    def grp(ids, src):
        return Counter(f'{src[i]["part"]} {src[i]["subject"]} {src[i]["type"]}' + (f' {src[i]["grade"]} кл.' if src[i].get("grade") else "") for i in ids)
    for title, ids, src in (("добавлено", added, y), ("убрано", removed, x), ("изменён текст", changed, y)):
        print(f"{title}: {len(ids)}")
        for k, n in sorted(grp(ids, src).items()):
            print(f"   {n:4d}  {k}")
    for k in changed[:15]:
        print(f"  ~ {k}\n      было: {x[k]['text'][:160]}\n      стало: {y[k]['text'][:160]}")


if __name__ == "__main__":
    a, b = sys.argv[1], sys.argv[2]
    if "--записи" in sys.argv:
        records_diff(a, b)
    else:
        files(a, b)
