#!/usr/bin/env python3
"""Сборка навигатора: template.html + data_new.json → ../index.html.
Цепочка: build_data.py → integrate_phys.py → integrate_mineru.py → build_local_v2.py"""
import os as _os
K = _os.path.dirname(_os.path.abspath(__file__))
ROOT = _os.path.normpath(_os.path.join(K, "..", ".."))
s = open(_os.path.join(K, "template.html"), encoding="utf-8").read()
data = open(_os.path.join(K, "data_new.json"), encoding="utf-8").read().replace("</", "<\\/")
assert s.count("/*__DATA__*/") == 1
s = s.replace("/*__DATA__*/", data)
open(_os.path.join(ROOT, "navigator", "index.html"), "w", encoding="utf-8").write(s)
print("bytes", len(s.encode()))
