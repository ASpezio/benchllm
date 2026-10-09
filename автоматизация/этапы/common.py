"""Общие функции этапов с LLM."""
import csv
import json
import os
import re
import shutil

import paths as P
from llm import load_config


def cfg():
    return load_config()


def jl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def jload(path):
    return json.load(open(path, encoding="utf-8"))


def jdump(obj, path, indent=1):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=indent)


def csv_rows(path):
    return list(csv.DictReader(open(path, encoding="utf-8-sig")))


def records():
    return jl(P.REC)


def norm(s):
    s = (s or "").replace("ё", "е").replace("Ё", "Е").replace("­", "")
    s = re.sub(r"[‐-‒–—−]", "-", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def short(t, n=400):
    t = re.sub(r"\s+", " ", t or "").strip()
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "…"


def replay_path(key):
    """Путь к прошлым данным для режима replay (config["replay"][key]) или None."""
    p = (cfg().get("replay") or {}).get(key)
    return p if p and os.path.exists(p) else None


def mode():
    return (cfg().get("llm") or {}).get("режим", "api")


def setting(section, key, default):
    return (cfg().get(section) or {}).get(key, default)


def copy_replay(key, dst_name):
    """replay для этапов-проверок: взять прошлый файл решений как есть."""
    src = replay_path(key)
    dst = P.dec(dst_name)
    if src:
        shutil.copy(src, dst)
        print(f"replay: {dst_name} ← {src}")
    else:
        jdump({}, dst)
        print(f"replay: прошлых решений «{key}» нет — {dst_name} пустой")


def write_overrides(name, overrides, meta):
    jdump(overrides, P.dec(name))
    jdump(meta, P.dec(name.replace(".json", ".подробно.json")))
    print(f"{name}: правок {len(overrides)}")
