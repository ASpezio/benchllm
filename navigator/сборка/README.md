# Сборка навигатора

Навигатор (`../index.html`) собирается из разметки, данные встраиваются в страницу:

```
python3 build_data.py        # дерево приказа + веса + связи → data.json
python3 integrate_phys.py    # + уроки и темы физики из Конструктора, веса «база + углублённый» → data_new.json
python3 integrate_mineru.py  # + формулы MinerU (1_разметка/формулы_mineru.json)
python3 build_local_v2.py    # template.html + data_new.json → ../index.html
```

Входы:
- `../../1_разметка/index.json`, `records.jsonl`, `формулы_mineru.json`;
- `../../1_разметка/физика_поурочное/*` — уроки, веса и темы физики;
- `weights.json`, `exam_links.json`, `req_links.json` — промежуточные связи. Это выход скриптов `1_разметка/weights.py`, `exam_links.py`, `req_links.py`; в тех скриптах пути ещё от рабочей среды Claude.

`template.html` — страница навигатора без данных (место для них — `/*__DATA__*/`). Библиотеки лежат рядом с `../index.html`: `pdf.min.js`, `pdf.worker.min.js`, `katex/`.
