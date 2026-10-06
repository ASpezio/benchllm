#!/usr/bin/env python3
"""Сборка локального навигатора (с физикой из Конструктора):
build_data.py → data.json → integrate_phys.py → data_new.json → template_v2.html → local/аа/navigator/index.html"""
s = open("/home/claude/nav/template_v2.html", encoding="utf-8").read()
data = open("/home/claude/nav/data_new.json", encoding="utf-8").read().replace("</", "<\\/")
assert s.count("/*__DATA__*/") == 1
s = s.replace("/*__DATA__*/", data)
open("/home/claude/nav/local/аа/navigator/index.html", "w", encoding="utf-8").write(s)
print("bytes", len(s.encode()))
