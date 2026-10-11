#!/usr/bin/env python3
"""Этап «задания_llm»: модель по каждому разделу составляет то, что не выводится из графа (в пилоте — Claude в чате):
типичные ошибки, ситуации «какое явление», вопросы «почему» с ключевыми пунктами, неверные формулировки законов,
прочие задания с выбором ответа (графики, формулы словами, применение, техника безопасности).

Проверка ответа программой: названия — из среза; в ситуации ответ не входит в неверные и не связан с ними в графе
(те же правила, что у неверных вариантов в заданиях из графа); роли умений есть у этого класса; у законов ровно три
неверные формулировки; номера верных вариантов существуют.
Выход: решения/задания_llm.json — {код раздела: {...}}. replay: конфиг replay.задания.
"""
from bench_common import C, ROLES, dec, jdump, jl, jload, kn, load_slice_full, mode, replay_path, resolve_role
from llm import LLM, prompt, run_stage

KEYS = ("неверные", "ситуации", "объяснения", "законы", "прочие")


def validator(sl, sec):
    labels = set(sl.L)
    in_sec = {c["label"] for c in sl.s["concepts"] if c["section"] == sec}
    reqs = sl.s["requirements"]

    def role_ok(r):
        return resolve_role(reqs, r) is not None

    def v(obj):
        if not isinstance(obj, dict):
            return ["нужен объект с ключами " + ", ".join(KEYS)]
        errs = [f"нет ключа «{k}» (если нечего писать — пустой список)" for k in KEYS if not isinstance(obj.get(k), list)]
        if errs:
            return errs
        for i, x in enumerate(obj["неверные"]):
            if x.get("понятие") not in in_sec:
                errs.append(f"неверные[{i}]: понятие {x.get('понятие')!r} не из этого раздела")
            if not x.get("утверждение") or not x.get("почему"):
                errs.append(f"неверные[{i}]: нужны утверждение и почему")
        for i, x in enumerate(obj["ситуации"]):
            ans, wr = x.get("ответ"), x.get("неверные") or []
            bad = [w for w in [ans] + wr if w not in labels]
            if bad:
                errs.append(f"ситуации[{i}]: названия не из списка: {bad}"); continue
            if len(wr) != 3 or len(set(wr)) != 3 or ans in wr:
                errs.append(f"ситуации[{i}]: нужно три разных неверных варианта, не совпадающих с ответом")
            rel = sl.also_correct(sl.L[ans]["id"])
            near = [w for w in wr if sl.L[w]["id"] in rel]
            if near:
                errs.append(f"ситуации[{i}]: неверные варианты {near} — род, вид или часть ответа «{ans}», тоже могут считаться верными — замените")
            if not role_ok(x.get("умение")):
                errs.append(f"ситуации[{i}]: умение {x.get('умение')!r} — нужна роль из списка «умения»")
            if not x.get("ситуация"):
                errs.append(f"ситуации[{i}]: пустой текст")
        for i, x in enumerate(obj["объяснения"]):
            if not x.get("вопрос") or not x.get("эталон"):
                errs.append(f"объяснения[{i}]: нужны вопрос и эталон")
            p = x.get("пункты") or []
            if not 1 <= len(p) <= 4:
                errs.append(f"объяснения[{i}]: пунктов 1–4")
            bad = [c for c in x.get("понятия") or [] if c not in labels]
            if not x.get("понятия") or bad:
                errs.append(f"объяснения[{i}]: понятия не из списка: {bad or 'пусто'}")
            if x.get("шагов") not in (1, 2, 3):
                errs.append(f"объяснения[{i}]: шагов — 1, 2 или 3")
        for i, x in enumerate(obj["законы"]):
            w = x.get("неверные") or []
            if x.get("понятие") not in in_sec:
                errs.append(f"законы[{i}]: понятие {x.get('понятие')!r} не из этого раздела")
            if not x.get("верная") or len(w) != 3 or len(set(w)) != 3 or x.get("верная") in w:
                errs.append(f"законы[{i}]: нужна верная формулировка и три разные неверные")
        for i, x in enumerate(obj["прочие"]):
            ops, right = x.get("варианты") or [], x.get("верные") or []
            if not 3 <= len(ops) <= 5 or len(set(ops)) != len(ops):
                errs.append(f"прочие[{i}]: 3–5 разных вариантов")
            if not right or any(not isinstance(r, int) or not 0 <= r < len(ops) for r in right):
                errs.append(f"прочие[{i}]: верные — номера вариантов с 0")
            bad = [c for c in x.get("понятия") or [] if c not in labels]
            if not x.get("понятия") or bad:
                errs.append(f"прочие[{i}]: понятия не из списка: {bad or 'пусто'}")
            if not role_ok(x.get("умение")):
                errs.append(f"прочие[{i}]: умение {x.get('умение')!r} — нужна роль из списка «умения»")
        return errs
    return v


def main():
    sl = load_slice_full()
    know = {}
    for k in jl(kn("знания.jsonl")):
        if k["status"] != "ошибка источника":
            know.setdefault(k["concept_id"], []).append(f"[{k['kind']}] {k['text']}")
    roles = {r: next(q["text"] for q in sl.s["requirements"] if q["code"] == resolve_role(sl.s["requirements"], r))
             for r in ROLES if resolve_role(sl.s["requirements"], r)}
    old = jload(replay_path("задания")) if mode() == "replay" and replay_path("задания") else {}
    sec_of = {}
    llm = LLM("задания", replay=lambda tid: old.get(sec_of[tid], {k: [] for k in KEYS}))
    tasks, vals = [], {}
    for s in sl.s["sections"]:
        cs = [c for c in sl.s["concepts"] if c["section"] == s["code"]]
        if not cs:
            continue
        tid = f"{C['срез']['имя']}.раздел_{s['code']}"
        sec_of[tid] = s["code"]
        user = {"классы": sl.s["классы"], "раздел": {"код": s["code"], "текст": s["text"]},
                "понятия": [{"название": c["label"], "тип": c["ctype"], "элемент": c["element"], "знания": know.get(c["id"], [])} for c in cs],
                "все_названия": sorted(sl.L), "умения": roles}
        tasks.append((tid, prompt("задания"), user))
        vals[tid] = validator(sl, s["code"])
    answers = llm.ask_many(tasks, lambda tid: vals[tid])
    llm.report()
    out = {sec_of[tid]: answers[tid] for tid, _, _ in tasks}
    jdump(out, dec("задания_llm.json"))
    tot = {k: sum(len(o.get(k, [])) for o in out.values()) for k in KEYS}
    print("разделов", len(out), "·", ", ".join(f"{k} {v}" for k, v in tot.items()))


if __name__ == "__main__":
    run_stage(main)
