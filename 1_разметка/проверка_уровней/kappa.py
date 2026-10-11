#!/usr/bin/env python3
"""Согласие двух разметчиков по уровням_действий.csv: доля совпадений, kappa Коэна и Brennan–Prediger (как у Bean и др.).

  python3 kappa.py [уровни_действий.csv]      учитываются строки, где заполнены оба столбца уровень_1 и уровень_2
Ориентир: kappa ≥ 0,6 — приемлемо; у Bean и др. на 30 категориальных вопросах средняя Brennan–Prediger = 0,524.
"""
import csv
import os
import sys
from collections import Counter

p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "уровни_действий.csv")
rows = [r for r in csv.DictReader(open(p, encoding="utf-8-sig"), delimiter=";") if r["уровень_1"].strip() and r["уровень_2"].strip()]
if not rows:
    sys.exit("Нет строк с обоими уровнями.")


def stats(rs):
    a = [r["уровень_1"].strip() for r in rs]; b = [r["уровень_2"].strip() for r in rs]
    n = len(a); po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b); cats = set(a) | set(b)
    pe = sum(ca[c] / n * cb[c] / n for c in cats)
    k = 7  # число категорий в листе
    kappa = (po - pe) / (1 - pe) if pe < 1 else 1.0
    bp = (po - 1 / k) / (1 - 1 / k)
    return n, po, kappa, bp


for name, rs in [("всё", rows)] + [(s, [r for r in rows if r["предмет"] == s]) for s in ("history", "physics")] + \
        [("неоднозначные глаголы", [r for r in rows if r["неоднозначный"]])]:
    if rs:
        n, po, ka, bp = stats(rs)
        print(f"{name:24} n={n:4}  совпадение {po:.0%}  kappa Коэна {ka:.2f}  Brennan–Prediger {bp:.2f}")
auto = [r for r in rows if r["уровень_авто"] != "?"]
if auto:
    print(f"словарь vs разметчик 1: совпадение {sum(r['уровень_авто'] == r['уровень_1'].strip() for r in auto) / len(auto):.0%} (n={len(auto)})")
