#!/usr/bin/env python3
"""Этап «дистракторы_llm»: модель-проверяющий ищет тестовые задания, где неверный вариант может оказаться верным
(граф неполон, близкие по смыслу понятия) или неверен сам ключ. Такие задания этап «итог» помечает
«варианты под вопросом» — они идут на вычитку, а при оценке моделей их можно исключить.

Проверяются тестовые задания дорожки «содержание» пачками по llm.заданий_за_запрос_дистракторы (по умолчанию 15).
Выход: решения/дистракторы.json — {id задания: {спорные, ключ_неверен, комментарий}}.
replay: конфиг replay.дистракторы; если прошлых решений нет — этап записывает пустой файл (проверка не проводилась).
"""
from bench_common import C, bn, dec, jdump, jl, jload, mode, replay_path, setting
from llm import LLM, chunks, prompt, run_stage


def main():
    tasks_all = [t for t in jl(bn("задания.jsonl")) if t["track"] == "содержание" and t.get("options") and t["format"] != "порядок"]
    if mode() == "replay" and not replay_path("дистракторы"):
        jdump({}, dec("дистракторы.json"))
        print("replay: прошлых решений проверки вариантов нет — проверка не проводилась, файл пустой")
        return
    old = jload(replay_path("дистракторы")) if mode() == "replay" else {}
    ctx = {}
    llm = LLM("дистракторы", replay=lambda tid: {"результат": [{"id": i, **old.get(i, {"спорные": [], "ключ_неверен": False, "комментарий": ""})} for i in ctx[tid]]})
    reqs, vals = [], {}
    for n, batch in enumerate(chunks(tasks_all, int(setting("заданий_за_запрос_дистракторы", 15)))):
        tid = f"{C['срез']['имя']}.{n + 1:03d}"
        ctx[tid] = [t["id"] for t in batch]
        reqs.append((tid, prompt("дистракторы"), {"классы": C["срез"]["классы"], "задания": [
            {"id": t["id"], "вопрос": t["question"], "варианты": [{"ключ": o["key"], "текст": o["text"]} for o in t["options"]],
             "верный_ключ": t["answer"]} for t in batch]}))

        def v(obj, batch=batch):
            res = obj.get("результат") if isinstance(obj, dict) else None
            if not isinstance(res, list):
                return ['нужен объект {"результат": [...]}']
            want, got = [t["id"] for t in batch], [x.get("id") for x in res if isinstance(x, dict)]
            errs = [] if got == want else [f"нужно по одному объекту на задание в порядке {want}; получено {got}"]
            by = {t["id"]: t for t in batch}
            for x in res:
                t = by.get(x.get("id"))
                if not t:
                    continue
                keys = {o["key"] for o in t["options"]}
                sp = x.get("спорные")
                if not isinstance(sp, list) or any(k not in keys or k in str(t["answer"]) for k in sp):
                    errs.append(f"{t['id']}: «спорные» — список ключей неверных вариантов из {sorted(keys - set(str(t['answer'])))}")
                if not isinstance(x.get("ключ_неверен"), bool):
                    errs.append(f"{t['id']}: «ключ_неверен» — true или false")
            return errs
        vals[tid] = v
    answers = llm.ask_many(reqs, lambda tid: vals[tid])
    llm.report()
    out = {}
    for tid, _, _ in reqs:
        for x in answers[tid]["результат"]:
            out[x["id"]] = {"спорные": x.get("спорные", []), "ключ_неверен": x.get("ключ_неверен", False), "комментарий": x.get("комментарий", "")}
    jdump(out, dec("дистракторы.json"))
    flagged = sum(1 for x in out.values() if x["спорные"] or x["ключ_неверен"])
    print(f"проверено заданий {len(out)}, помечено {flagged}")


if __name__ == "__main__":
    run_stage(main)
