"""Пути одного прогона. Их задаёт run.py через переменные окружения; скрипты этапов импортируют этот модуль.

Папка прогона повторяет устройство проекта, чтобы результаты было легко сравнить со старыми:
  <прогон>/1_разметка/                 records.jsonl, index.json, CSV со связями и весами
  <прогон>/1_разметка/промежуточное/   align_out.json, exam_out.json, req_out.json, weights.json …
  <прогон>/1_разметка/физика_поурочное/ уроки физики из Конструктора
  <прогон>/2_граф/                     каркас/, понятия/, связи/, граф/, просмотр/
  <прогон>/решения/                    решения LLM (или эксперта): привязки, синонимы — в формате старых *overrides.json
  <прогон>/llm/                        журнал запросов, запросы и ответы ручного режима
"""
import os

RUN = os.environ["OZ_RUN"]
M = os.path.join(RUN, "1_разметка")
TMP = os.path.join(M, "промежуточное")
PH = os.path.join(M, "физика_поурочное")
G = os.path.join(RUN, "2_граф")
DEC = os.path.join(RUN, "решения")
REC = os.path.join(M, "records.jsonl")
MANUAL = os.environ.get("OZ_MANUAL", "")

for _d in (M, TMP, PH, G, DEC):
    os.makedirs(_d, exist_ok=True)


def env(key, default=None):
    v = os.environ.get(key, default)
    return v or default


def tmp(name):
    return os.path.join(TMP, name)


def ph(name):
    return os.path.join(PH, name)


def dec(name):
    return os.path.join(DEC, name)


def manual(name):
    return os.path.join(MANUAL, name)


def has_manual(name):
    return bool(MANUAL) and os.path.exists(manual(name))
