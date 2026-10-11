#!/usr/bin/env python3
"""Автоматическая проверка набора заданий (вызывается этапом «итог»; можно запустить отдельно: bench_check.py <задания.jsonl>).

- у задания есть вопрос, ответ и способ проверки; у тестовых — 3–5 различных вариантов, ключ указывает на существующие варианты;
- в задании с одним ответом ровно один ключ; в «порядке» ключ — перестановка;
- текст верного варианта не повторяется в вопросе (подсказка);
- числовые ответы конечны, у них есть единица и допуск;
- задания с одинаковым текстом вопроса и вариантов не повторяются;
- веса заданий каждой дорожки в сумме дают 1.
"""
import json
import math
import sys
from collections import Counter


def check(path):
    T = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    err, warn, seen = [], [], Counter()
    for t in T:
        tid = t["id"]
        if not t.get("question") or t.get("answer") in (None, "") or not t.get("check"):
            err.append(f"{tid}: нет вопроса, ответа или проверки")
            continue
        if not t.get("requirement"):
            warn.append(f"{tid}: умение ФОП не определено")
        if "options" in t:
            opts, keys, ans = [o["text"] for o in t["options"]], [o["key"] for o in t["options"]], str(t["answer"])
            if not 3 <= len(opts) <= 5:
                err.append(f"{tid}: вариантов {len(opts)}")
            if len(set(opts)) != len(opts):
                err.append(f"{tid}: повторяющиеся варианты")
            if t["format"] == "порядок":
                if sorted(ans) != sorted(keys):
                    err.append(f"{tid}: ключ порядка не перестановка")
            else:
                if any(a not in keys for a in ans):
                    err.append(f"{tid}: ключ вне вариантов")
                if t["format"] == "один_ответ" and len(ans) != 1:
                    err.append(f"{tid}: один ответ, но ключ {ans}")
                if t["format"] == "несколько_ответов" and len(ans) < 2:
                    err.append(f"{tid}: несколько ответов, но ключ {ans}")
                for a in ans:
                    txt = t["options"][int(a) - 1]["text"]
                    if len(txt) > 6 and txt.lower() in t["question"].lower():
                        warn.append(f"{tid}: текст верного варианта есть в вопросе: «{txt[:50]}»")
            seen[(t["question"], tuple(sorted(opts)))] += 1
        else:
            seen[(t["question"], None)] += 1
        c = t["check"]
        if c["type"] == "number":
            v = c["value"]
            if not isinstance(v, (int, float)) or not math.isfinite(v):
                err.append(f"{tid}: нечисловой ответ {v}")
            if not c.get("unit"):
                warn.append(f"{tid}: нет единицы")
            if not c.get("rel_tol"):
                err.append(f"{tid}: нет допуска")
        if c["type"] == "rubric" and not c.get("reference"):
            err.append(f"{tid}: рубрика без эталона")
    for k, n in seen.items():
        if n > 1:
            err.append(f"повтор задания ×{n}: {k[0][:70]}")
    for track in sorted({t["track"] for t in T}):
        s = sum(t.get("weight", 0) for t in T if t["track"] == track)
        if abs(s - 1) > 1e-4:
            err.append(f"сумма весов дорожки «{track}» = {s:.6f}")
    print(f"проверка набора: заданий {len(T)}, ошибок {len(err)}, предупреждений {len(warn)}")
    for e in err[:40]:
        print("  ОШИБКА", e)
    for w in warn[:20]:
        print("  внимание", w)
    return 1 if err else 0


if __name__ == "__main__":
    sys.exit(check(sys.argv[1]))
