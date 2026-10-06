#!/usr/bin/env python3
"""Патч навигатора: несколько PDF-источников, уроки и темы физики из Конструктора, веса физики."""
import json

src = open("orig.html", encoding="utf-8").read()
A = '<script type="application/json" id="data">'
a = src.index(A) + len(A)
b = src.index("</script>", a)
data = open("data_new.json", encoding="utf-8").read()
html = src[:a] + data.replace("</", "<\\/") + src[b:]


def rep(old, new, count=1):
    global html
    n = html.count(old)
    assert n == count, (n, old[:80])
    html = html.replace(old, new)


# ---------------------------------------------------------------- разметка страницы
rep('<div class="legend"><span class="chip ok">размечено</span> история и физика — построчно; остальные предметы — до таблиц. <span class="chip">7 ч</span> вес элемента истории по урокам</div>',
    '<div class="legend"><span><span class="chip ok">размечено</span> история и физика — построчно, остальные предметы — до таблиц</span><span><span class="chip">7 ч</span> вес элемента по урокам; уроки физики — из <span class="chip cons">Конструктора</span>, в приказе их нет</span></div>')
rep('<span class="status" id="status"></span>',
    '<span class="chip docname" id="docname"></span>\n      <span class="status" id="status"></span>')
rep('<strong>Открываю приказ…</strong>', '<strong id="loadtitle">Открываю приказ…</strong>')
rep('</style>\n<script>(function(){var t="light"',
    '.chip.cons { background: var(--reg-bg); color: var(--reg); border-color: transparent; }\n'
    '.chip.docname { font-size: 12px; white-space: nowrap; max-width: 320px; overflow: hidden; text-overflow: ellipsis; }\n'
    '.chip.lab { background: var(--accent-soft); color: var(--accent); border-color: transparent; }\n'
    '.note-src { margin: 6px 0 0; font-size: 13px; color: var(--muted); }\n'
    '</style>\n<script>(function(){var t="light"')

# ---------------------------------------------------------------- модель и источники PDF
rep('  const PDF_URL = "../" + encodeURIComponent("Проект приказа 2.pdf");\n',
    '''  const encPath = p => p.split("/").map(encodeURIComponent).join("/");
  const DOCS = {
    order: { url: "../" + encPath("Проект приказа 2.pdf"), name: "Проект приказа", file: "Проект приказа 2.pdf" },
    c79: { url: "../" + encPath("разметка/физика_поурочное/источники/Конструктор_Физика_7-9_база_ID12372761.pdf"), name: "Конструктор: Физика 7–9 (ID 12372761)", file: "Конструктор_Физика_7-9_база_ID12372761.pdf" },
    c1011: { url: "../" + encPath("разметка/физика_поурочное/источники/Конструктор_Физика_10-11_база_ID12372794.pdf"), name: "Конструктор: Физика 10–11 (ID 12372794)", file: "Конструктор_Физика_10-11_база_ID12372794.pdf" },
  };
''')
rep('  const ancestors = id => { const out = []; let p = parent.get(id); while (p) { out.unshift(p); p = parent.get(p); } return out; };\n',
    '''  const ancestors = id => { const out = []; let p = parent.get(id); while (p) { out.unshift(p); p = parent.get(p); } return out; };
  const srcOf = n => { if (!n) return "order"; if (n.src) return n.src; for (const a of ancestors(n.i).reverse()) { const A = nodes.get(a); if (A && A.src) return A.src; } return "order"; };
  const isCons = n => srcOf(n) !== "order";
''')
rep('    exam_requirement: "Требование экзамена", exam_element: "Элемент содержания экзамена", unknown: "Строка таблицы" };',
    '    exam_requirement: "Требование экзамена", exam_element: "Элемент содержания экзамена", theme: "Тема (тематическое планирование ФРП)", unknown: "Строка таблицы" };\n'
    '  const LT = { lab: ["лабораторная / исследование", "lab"], mixed: ["теория + лабораторная", "lab"], problems: ["решение задач", ""], conference: ["урок-конференция", ""], control: ["контрольная", "rev"], review: ["повторение", "rev"], reserve: ["резервный", "rev"] };')
rep('spans_pages: "текст переходит на следующую страницу", duplicate_id: "код повторяется в таблице" };',
    'spans_pages: "текст переходит на следующую страницу", duplicate_id: "код повторяется в таблице", vpr: "урок отдан под ВПР — стоит не на месте своей темы" };')

# ---------------------------------------------------------------- дерево
rep('''    if (n.t === "subj" && n.parsed) chips = '<span class="chip ok">размечено</span>';''',
    '''    if (n.t === "subj" && n.parsed) chips = '<span class="chip ok">размечено</span>';
    if (n.t === "block" && n.src) chips = '<span class="chip cons">Конструктор</span>';''')
rep('''      if (n.lk && n.lk !== "new") chips = `<span class="chip ${LK[n.lk][1]}">${LK[n.lk][0]}</span>`;''',
    '''      if (n.lk && n.lk !== "new") chips = `<span class="chip ${LK[n.lk][1]}">${n.lt && LT[n.lt] ? LT[n.lt][0] : LK[n.lk][0]}</span>`;
      else if (n.lt === "lab" || n.lt === "mixed") chips = '<span class="chip lab">лаб.</span>';
      if (n.f && n.f.includes("vpr")) chips += '<span class="chip warn">ВПР</span>';
      if (n.ty === "theme") chips += `<span class="chip">${fmtH(n.h)} ч</span>`;''')
rep('''    const pg = n.t === "rec" ? `с. ${n.pg}` : pages(n.pg, n.pe);
    return''', '''    const pg = (n.t === "rec" ? `с. ${n.pg}` : pages(n.pg, n.pe));
    return''')

# ---------------------------------------------------------------- карточка
rep('''      if (n.h != null && n.ty === "lesson") meta.push(`<span class="chip">${n.h} ч</span>`);''',
    '''      if (n.h != null && n.ty === "lesson") meta.push(`<span class="chip">${n.h} ч</span>`);
      if (n.lt && LT[n.lt]) meta.push(`<span class="chip ${LT[n.lt][1]}">${LT[n.lt][0]}</span>`);
      if (n.kr) meta.push(`<span class="chip">контрольных: ${fmtH(n.kr)}</span>`);
      if (n.pr) meta.push(`<span class="chip">практических: ${fmtH(n.pr)}</span>`);
      if (n.ty === "theme") meta.push(`<span class="chip">${fmtH(n.h)} ч</span>`);''')
rep('''      meta.push(`<span class="pg">стр. ${n.pg}${tbl ? " · " + esc(tbl.l) : ""}</span>`);''',
    '''      if (isCons(n)) meta.push('<span class="chip cons">Конструктор edsoo</span>');
      meta.push(`<span class="pg">${isCons(n) ? "Конструктор, " : ""}стр. ${n.pg}${tbl ? " · " + esc(tbl.l) : ""}</span>`);''')
rep('''        h = h.replace('<div class="meta">', `<div class="meta"><span class="chip ${n.wh > 0 ? "" : "warn"}">вес: ${fmtH(n.wh)} ч · ${fmtH(n.ws)}% учебного времени класса</span>`);''',
    '''        h = h.replace('<div class="meta">', `<div class="meta"><span class="chip ${n.wh > 0 ? "" : "warn"}">вес${n.i.includes(".physics.") ? " по Конструктору" : ""}: ${fmtH(n.wh)} ч · ${fmtH(n.ws)}% учебного времени класса</span>`);''')
rep('''(n.le && n.le.length > 1 ? `<span class="chip">час делится на ${n.le.length}</span>` : ""));''',
    '''(n.le && n.le.length > 1 && n.lk !== "review" ? `<span class="chip">${n.sh ? "доли часа: " + n.sh.map(fmtH).join(" / ") : "час делится на " + n.le.length}</span>` : ""));''')
rep('''      if (rel.length) h += `<div class="rel">${rel.join("")}</div>`;
    } else {''',
    '''      if (rel.length) h += `<div class="rel">${rel.join("")}</div>`;
      if (n.ty === "lesson" && isCons(n)) h += `<p class="note-src">Поурочный план по физике приказом не утверждён — это рекомендованный план Конструктора рабочих программ edsoo (${esc(DOCS[srcOf(n)].name)}). Слева — его страница.</p>`;
      if (n.ty === "theme") h += `<p class="note-src">Тематическое планирование — часть федеральной рабочей программы (ФРП 2025); страница — по выгрузке Конструктора.</p>`;
    } else {''')
rep('''      if (n.note) h += `<p class="body">Изменения в ${esc(n.note)}.</p>`;''',
    '''      if (n.note) h += `<p class="body">Изменения в ${esc(n.note)}.</p>`;
      if (n.t === "block" && n.src) h += `<p class="note-src">${n.i.includes(".les@") ? "Поурочного плана по физике в приказе нет. Здесь — рекомендованный план из Конструктора рабочих программ edsoo; уроки привязаны к элементам кодификатора приказа." : "Тематическое планирование федеральной рабочей программы: разделы и темы с часами (по выгрузке Конструктора, совпадает с ФРП 2025)."} Источник: ${esc(DOCS[n.src].name)}.</p>`;''')
rep('''      const m = [`<span class="pg">${pages(n.pg, n.pe)}</span>`];''',
    '''      const m = [`<span class="pg">${isCons(n) ? "Конструктор, " : ""}${pages(n.pg, n.pe)}</span>`];''')

# ---------------------------------------------------------------- выбор: страница предмета — в приказе
rep('''    if (n.t === "subj") { const b = (n.c || [])[0]; return b ? b.sn : []; }''',
    '''    if (n.t === "subj") { const b = (n.c || []).find(x => !x.src); return b ? b.sn : []; }''')
rep('''    const pg = n.t === "subj" ? ((n.c || [])[0] || n).pg : n.pg;''',
    '''    const pg = n.t === "subj" ? ((n.c || []).find(x => !x.src) || n).pg : n.pg;''')

# ---------------------------------------------------------------- PDF: несколько документов
rep('''  let pdfDoc = null, curPage = 1, zoom = 1, renderTask = null, token = 0, pendingGo = null, lastSnips = null;''',
    '''  let pdfDoc = null, curPage = 1, zoom = 1, renderTask = null, token = 0, pendingGo = null, lastSnips = null;
  let curDoc = null, wantDoc = "order", loadTok = 0, loadingKey = null;
  const docCache = new Map();''')
old_open = html[html.index("  async function openPdf(src) {"):html.index("  function goTo(page, snips, n) {")]
new_open = '''  async function openPdf(key, srcOverride) {
    const lib = window.pdfjsLib;
    if (!lib) throw new Error("не загрузилась библиотека pdf.js");
    lib.GlobalWorkerOptions.workerSrc = "pdf.worker.min.js";
    wantDoc = key; loadingKey = key;
    const my = ++loadTok;
    let doc = docCache.get(key);
    if (!doc) {
      const first = !pdfDoc;
      if (first) { document.getElementById("loadtitle").textContent = `Открываю ${DOCS[key].name}…`; }
      else setStatus(`<span class="toast">Открываю ${esc(DOCS[key].name)}…</span>`);
      const task = lib.getDocument(srcOverride || { url: DOCS[key].url, disableAutoFetch: true, rangeChunkSize: 262144 });
      task.onProgress = p => {
        if (!p.total || !first) return;
        document.getElementById("barfill").style.width = Math.round((p.loaded / p.total) * 100) + "%";
        document.getElementById("loadtxt").textContent = `${(p.loaded / 1048576).toFixed(1)} из ${(p.total / 1048576).toFixed(1)} МБ`;
      };
      try { doc = await task.promise; } finally { if (loadingKey === key) loadingKey = null; }
      docCache.set(key, doc);
    }
    if (loadingKey === key) loadingKey = null;
    if (my !== loadTok) return;
    pdfDoc = doc; curDoc = key;
    document.getElementById("loading").hidden = true;
    sheet.hidden = false;
    pgof.textContent = `из ${pdfDoc.numPages}`;
    document.getElementById("docname").textContent = DOCS[key].name;
    document.getElementById("docname").className = "chip docname" + (key === "order" ? "" : " cons");
    const g = pendingGo || [1, null]; pendingGo = null;
    renderPage(g[0], g[1]);
  }
  function showLoadError(err, key) {
    key = key || wantDoc;
    const box = document.getElementById("loading");
    box.hidden = false; sheet.hidden = true;
    box.innerHTML = `<strong>Не получилось открыть PDF</strong><span>${esc(err && err.message || err)}</span>
      <span>Можно открыть свой экземпляр «${esc(DOCS[key].file)}» с диска — навигация будет работать так же.</span>
      <input type="file" id="pick" accept="application/pdf">`;
    document.getElementById("pick").addEventListener("change", ev => {
      const f = ev.target.files[0]; if (!f) return;
      const rd = new FileReader();
      rd.onload = () => openPdf(key, { data: new Uint8Array(rd.result) }).catch(e => showLoadError(e, key));
      rd.readAsArrayBuffer(f);
    });
  }

'''
html = html.replace(old_open, new_open)
rep('''  function goTo(page, snips, n) {
    lastSnips = snips && snips.length ? snips : null;
    if (!pdfDoc) { pendingGo = [page, lastSnips]; return; }
    renderPage(page, lastSnips, n);
  }''', '''  function goTo(page, snips, n) {
    lastSnips = snips && snips.length ? snips : null;
    const key = srcOf(n);
    if (pdfDoc && key === curDoc) { renderPage(page, lastSnips, n); return; }
    pendingGo = [page, lastSnips];
    if (loadingKey !== key) openPdf(key).catch(e => showLoadError(e, key));
  }''')
rep('''  openPdf({ url: PDF_URL, disableAutoFetch: true, rangeChunkSize: 262144 }).catch(showLoadError);''',
    '''  // PDF открывается из select() → goTo(): нужный документ (приказ или выгрузка Конструктора) выбирается по пункту''')

# ---------------------------------------------------------------- «Связи»: физика с уроками
rep('''    physics: { name: "Физика", classes: [["OOO", 7], ["OOO", 8], ["OOO", 9], ["SOO", 10], ["SOO", 11]], views: [["elements", "по элементам"], ["exam", "по экзамену"]] },''',
    '''    physics: { name: "Физика", classes: [["OOO", 7], ["OOO", 8], ["OOO", 9], ["SOO", 10], ["SOO", 11]], views: [["lessons", "по урокам"], ["elements", "по элементам"], ["exam", "по экзамену"]] },''')
rep('''    const hist = subj === "history";''',
    '''    const hist = les.length > 0;  // есть поурочный план (история — приказ, физика — Конструктор)
    const cons = subj === "physics";''')
rep('''      lessons: [["all", "все"], ["manual", "исправлены вручную"], ["multi", "на несколько элементов"], ["review", "повторение"]],''',
    '''      lessons: [["all", "все"], ["manual", "исправлены вручную"], ["multi", "на несколько элементов"], ["review", "повторение"]].concat(cons ? [["lab", "лабораторные"], ["vpr", "ВПР"]] : []),''')
rep('''        ? `<b>${les.length}</b> уроков (с новым материалом <b>${les.filter(l => l.lk !== "review").length}</b>, исправлено вручную <b>${les.filter(l => l.lk !== "review" && l.m === "manual").length}</b>); `
        : `поурочного плана в приказе нет; `) +''',
    '''        ? `<b>${les.length}</b> уроков${cons ? ' <span class="chip cons">по Конструктору edsoo — в приказе поурочного плана нет</span>' : ""} (с новым материалом <b>${les.filter(l => l.lk !== "review").length}</b>, исправлено вручную <b>${les.filter(l => l.lk !== "review" && l.m === "manual").length}</b>); `
        : `поурочного плана в приказе нет; `) +''')
rep('''      const pass = l => lk.filter === "all" || (lk.filter === "manual" && l.m === "manual") || (lk.filter === "multi" && l.lk !== "review" && l.le && l.le.length > 1) || (lk.filter === "review" && l.lk === "review");''',
    '''      const pass = l => lk.filter === "all" || (lk.filter === "manual" && l.m === "manual") || (lk.filter === "multi" && l.lk !== "review" && l.le && l.le.length > 1) || (lk.filter === "review" && l.lk === "review") || (lk.filter === "lab" && (l.lt === "lab" || l.lt === "mixed")) || (lk.filter === "vpr" && l.f && l.f.includes("vpr"));''')
rep('''        const mchip = l.lk === "review" ? '<span class="chip rev">повторение, без веса</span>' : l.m === "manual" ? '<span class="chip ok">вручную</span>' : '<span class="chip">авто</span>';''',
    '''        const mchip = (l.lk === "review" ? `<span class="chip rev">${l.lt && LT[l.lt] ? LT[l.lt][0] : "повторение"}, без веса</span>` : l.m === "manual" ? '<span class="chip ok">вручную</span>' : '<span class="chip">авто</span>')
          + (l.lk !== "review" && (l.lt === "lab" || l.lt === "mixed") ? `<span class="chip lab">${l.lt === "lab" ? "лаб." : "теория + лаб."}</span>` : "") + (l.f && l.f.includes("vpr") ? '<span class="chip warn">ВПР</span>' : "");''')
rep('''(l.le && l.le.length > 1 && l.lk !== "review" ? ` <span class="chip">час ÷ ${l.le.length}</span>` : "");''',
    '''(l.le && l.le.length > 1 && l.lk !== "review" ? ` <span class="chip">${l.sh ? "час: " + l.sh.map(fmtH).join(" / ") : "час ÷ " + l.le.length}</span>` : "");''')
rep('''      h += `<div class="lsec"><span class="code">${esc(e.c)}</span>${esc(short(e.x, 120))}${e.wh != null ? ` <span class="chip">${fmtH(e.wh)} ч · ${fmtH(e.ws)}%</span>` : ""}${e.wr && e.wr.length ? ` <span class="chip rev">повторение: ${e.wr.map(x => nodes.get(x).c).join(", ")}</span>` : ""}</div>`;''',
    '''      h += `<div class="lsec"><span class="code">${esc(e.c)}</span>${esc(short(e.x, 120))}${e.wh != null ? ` <span class="chip">${fmtH(e.wh)} ч · ${fmtH(e.ws)}%</span>` : ""}${e.wr && e.wr.length ? ` <span class="chip rev">повторение: ${e.wr.map(x => (gradeOf(x) !== g ? gradeOf(x) + " кл. " : "") + nodes.get(x).c).join(", ")}</span>` : ""}</div>`;''')
rep('''      h += `<div class="lgrid"><div class="lrow x head"><span>Код</span><span>Пункт ${exName}</span><span>Элементы классов</span><span>${hist ? "Часы" : "Эл."}</span></div>`;''',
    '''      const withH = exEls.some(x => x.xh != null);
      h += `<div class="lgrid"><div class="lrow x head"><span>Код</span><span>Пункт ${exName}</span><span>Элементы классов</span><span>${withH ? "Часы" : "Эл."}</span></div>`;''')
rep('''элементы классов, на которые он опирается${hist ? ", и часы уроков за ними" : ""}.''',
    '''элементы классов, на которые он опирается${subj === "history" ? ", и часы уроков за ними" : ", и часы уроков за ними по Конструктору"}.''')
rep('''${part === "OOO" ? (hist ? "5–9" : "7–9") : "10–11"}''', '''${part === "OOO" ? (subj === "history" ? "5–9" : "7–9") : "10–11"}''')

open("index.html", "w", encoding="utf-8").write(html)
print("ok", len(html))
