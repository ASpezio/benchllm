p="index.html"; s=open(p,encoding="utf-8").read()
def rep(old,new):
    global s
    assert s.count(old)==1,(s.count(old),old[:70]); s=s.replace(old,new)
rep('''      if (first) { document.getElementById("loadtitle").textContent = `Открываю ${DOCS[key].name}…`; }''',
    '''      const ltEl = document.getElementById("loadtitle");
      if (first) { if (ltEl) ltEl.textContent = `Открываю ${DOCS[key].name}…`; }''')
rep('''        if (!p.total || !first) return;
        document.getElementById("barfill").style.width = Math.round((p.loaded / p.total) * 100) + "%";
        document.getElementById("loadtxt").textContent = `${(p.loaded / 1048576).toFixed(1)} из ${(p.total / 1048576).toFixed(1)} МБ`;''',
    '''        const bf = document.getElementById("barfill"), lt = document.getElementById("loadtxt");
        if (!p.total || !first || !bf || !lt) return;
        bf.style.width = Math.round((p.loaded / p.total) * 100) + "%";
        lt.textContent = `${(p.loaded / 1048576).toFixed(1)} из ${(p.total / 1048576).toFixed(1)} МБ`;''')
rep('''    if (pdfDoc && key === curDoc) { renderPage(page, lastSnips, n); return; }''',
    '''    if (pdfDoc && key === curDoc) { document.getElementById("loading").hidden = true; sheet.hidden = false; renderPage(page, lastSnips, n); return; }''')
open(p,"w",encoding="utf-8").write(s); print("ok")
s=open(p,encoding="utf-8").read()
def rep(old,new):
    global s
    assert s.count(old)==1,(s.count(old),old[:70]); s=s.replace(old,new)
rep('''  async function renderPage(num, snips) {''', '''  // запасной поиск для ячеек таблиц: слова фрагмента по порядку, между ними допускается «шум»
  // (номер урока, часы, ссылка ЦОК из соседних колонок, перенос строки)
  function fuzzyRanges(idx, snippet) {
    const words = (snippet || "").toLowerCase().replace(/ё/g, "е").split(/[^\\p{L}\\p{N}]+/u).filter(w => w.length >= 2);
    if (words.length < 2) return null;
    let best = null, from = 0;
    for (let tries = 0; tries < 30; tries++) {
      const p0 = idx.s.indexOf(words[0], from); if (p0 < 0) break;
      const out = [[p0, p0 + words[0].length]]; let pos = p0 + words[0].length, miss = 0;
      for (let k = 1; k < words.length && miss <= 1; k++) {
        const p = idx.s.indexOf(words[k], pos);
        if (p < 0 || p - pos > 70) { miss++; continue; }
        out.push([p, p + words[k].length]); pos = p + words[k].length;
      }
      if (!best || out.length > best.length) best = out;
      if (out.length === words.length) break;
      from = p0 + 1;
    }
    return best && best.length >= 2 ? best : null;
  }

  async function renderPage(num, snips) {''')
rep('''    snips.forEach(sn => {
      const r = findRange(idx, sn); if (!r) return;
      foundAny = true;
      const per = new Map();
      for (let q = r[0]; q < r[1]; q++) { const [ii, k] = idx.map[q]; const cur = per.get(ii); if (!cur) per.set(ii, [k, k]); else cur[1] = k; }''',
'''    snips.forEach(sn => {
      const r0 = findRange(idx, sn);
      const rs = r0 ? [r0] : (fuzzyRanges(idx, sn) || []);
      if (!rs.length) return;
      foundAny = true;
      const per = new Map();
      rs.forEach(r => { for (let q = r[0]; q < r[1]; q++) { const [ii, k] = idx.map[q]; const cur = per.get(ii); if (!cur) per.set(ii, [k, k]); else { cur[0] = Math.min(cur[0], k); cur[1] = Math.max(cur[1], k); } } });''')
open(p,"w",encoding="utf-8").write(s); print("ok2")
