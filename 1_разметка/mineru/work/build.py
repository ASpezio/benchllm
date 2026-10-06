"""Собирает физику из вывода MinerU (tier advanced): вырезка, правка формул, md + html."""
import html
import re
import shutil
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "out_adv"
OUT = ROOT / "result"

# (старое, новое, ожидаемое число вхождений; None — «хотя бы одно», печатаем факт)
FIX_OGE = [
    (r"\nu = \frac{S}{t}", r"\upsilon = \frac{S}{t}", 1),
    (r"\nu_x t", r"\upsilon_x t", 1),
    (r"\nu_{0x}", r"\upsilon_{0x}", 3),
    (r"\nu_x(t)", r"\upsilon_x(t)", 1),
    (r"\nu_{2x}^2 - \nu_{1x}^2", r"\upsilon_{2x}^2 - \upsilon_{1x}^2", 1),
    (r"\nu = \frac{2\pi R}{T}", r"\upsilon = \frac{2\pi R}{T}", 1),
    (r"\frac{\nu^{2}}{R}", r"\frac{\upsilon^{2}}{R}", 1),
    (r"m\vec{v}", r"m\vec{\upsilon}", 1),
    (r"\vec{v}_{1}", r"\vec{\upsilon}_{1}", 1),
    (r"\vec{v}_{2}", r"\vec{\upsilon}_{2}", 1),
    (r"\frac{mv^{2}}{2}", r"\frac{m\upsilon^{2}}{2}", 1),
    (r"\lambda = \nu \cdot T", r"\lambda = \upsilon \cdot T", 1),
]

FIX_EGE = [
    # скорость — υ
    (r"\vec{v}", r"\vec{\upsilon}", None),
    (r"F \cdot v \cdot \cos", r"F \cdot \upsilon \cdot \cos", 1),
    (r"\frac{mv^2}{2} = \frac{p^2}{2m}", r"\frac{m\upsilon^2}{2} = \frac{p^2}{2m}", 1),
    (r"\frac{mv^{2}}{2} + \frac{kx^{2}}{2} = \frac{mv_{max}^{2}}{2}",
     r"\frac{m\upsilon^{2}}{2} + \frac{kx^{2}}{2} = \frac{m\upsilon_{\max}^{2}}{2}", 1),
    (r"\frac{mv_{\text{max}}^2}{2}", r"\frac{m\upsilon_{\text{max}}^2}{2}", 1),
    (r"n \overline{v^{2}}", r"n \overline{\upsilon^{2}}", 1),
    (r"\left( \frac{m_{0} v^{2}}{2} \right)", r"\overline{\left( \frac{m_{0} \upsilon^{2}}{2} \right)}", 2),
    (r"\frac{c}{\nu}", r"\frac{c}{\upsilon}", 1),
    (r"\frac{\nu_1}{\nu_2}", r"\frac{\upsilon_1}{\upsilon_2}", 1),
    # частота / количество вещества — ν
    (r"\frac{2\pi}{\omega} = \frac{1}{v}", r"\frac{2\pi}{\omega} = \frac{1}{\nu}", 1),
    (r"\frac{\upsilon}{v}", r"\frac{\upsilon}{\nu}", 1),
    (r"= vRT = NkT", r"= \nu RT = NkT", 1),
    (r"\frac{3}{2} vRT", r"\frac{3}{2} \nu RT", 1),
    (r"= vc_{v} T", r"= \nu c_{\upsilon} T", 1),
    (r"v_{1} = v_{2}", r"\nu_{1} = \nu_{2}", 1),
    (r"Формула Планка: E = hv", r"Формула Планка: $E = h\nu$", 1),
    (r"hv_{mn}", r"h\nu_{mn}", 1),
    # опечатки распознавания
    (r"потенци}", r"потенц}", 6),
    (r"$|M| = F1$ , где 1 – плечо", r"$|M| = Fl$ , где l – плечо", 1),
    (r"длиной 1,", r"длиной l,", 1),
    # ЭДС — ℰ
    (r"E = \frac{A_{\text{сторонних сил}}}{q}", r"\mathcal{E} = \frac{A_{\text{сторонних сил}}}{q}", 1),
    (r"E = IR + Ir", r"\mathcal{E} = IR + Ir", 1),
    (r"I = \frac{E}{R + r}", r"I = \frac{\mathcal{E}}{R + r}", 1),
    (r"P_E = ", r"P_{\mathcal{E}} = ", 1),
    (r"= EI$", r"= \mathcal{E}I$", 1),
    (r"E_{t} = -\frac{\Delta \Phi}", r"\mathcal{E}_{i} = -\frac{\Delta \Phi}", 1),
    (r"|E_{i}| = Blv \cos", r"|\mathcal{E}_{i}| = Bl\upsilon \cos", 1),
    (r"|E_{i}| = Blv$", r"|\mathcal{E}_{i}| = Bl\upsilon$", 1),
    (r"E_{si} = -L", r"\mathcal{E}_{si} = -L", 1),
    # ядерные реакции: VLM записал индексы нуклида дробями
    (r"\frac{A}{Z}X \to \frac{A-4}{Z-2}Y + \frac{4}{2}He",
     r"{}^{A}_{Z}\mathrm{X} \to {}^{A-4}_{Z-2}\mathrm{Y} + {}^{4}_{2}\mathrm{He}", 1),
    (r"\frac{A}{Z}X \to \frac{A}{Z+1}Y + \frac{0}{-1}e + \widetilde{v}_e",
     r"{}^{A}_{Z}\mathrm{X} \to {}^{A}_{Z+1}\mathrm{Y} + {}^{0}_{-1}e + \tilde{\nu}_e", 1),
    (r"\frac{A}{Z}X \to \frac{A}{Z-1}Y + \frac{0}{+1}\widetilde{e} + v_e",
     r"{}^{A}_{Z}\mathrm{X} \to {}^{A}_{Z-1}\mathrm{Y} + {}^{0}_{+1}\tilde{e} + \nu_e", 1),
]

# Текстовые дефекты VLM вокруг формул (после нормализации): перестановки слов, подписи с рисунков
POST_EGE = [
    (r"где $m_{0}$ — масса одной $n = \frac{N}{V}$ — концентрация молекул молекулы,",
     r"где $m_{0}$ — масса одной молекулы, $n = \frac{N}{V}$ — концентрация молекул", 1),
    ("количеством вещества v)", "количеством вещества ν)", 1),
    ("количества вещества v", "количества вещества ν", 1),
    ("(замкнутой) E, электрической цепи", "(замкнутой) электрической цепи", 1),
    ("смещение из равновесия.положения<br>Динамическое", "смещение из положения равновесия.<br>Динамическое", 1),
]
POST_EGE_RE = [
    (r"рассеивающей (\$[^$]+\$) линзы:", r"рассеивающей линзы: \1", 1),
]

DOCS = [
    # имя, папка MinerU, начало вырезки, конец вырезки, правки формул, пост-правки текста, заголовок
    ("Физика_ОГЭ_стр571-599", "oge", "пункт 153 дополнить подпунктами 153.7", "Пункт 155 дополнить",
     FIX_OGE, [], [], "Физика, основное общее образование (п. 153.7–153.8, ОГЭ) — PDF стр. 572–598"),
    ("Физика_ЕГЭ_стр1007-1038", "ege", "пункт 115 дополнить подпунктом 115.9", "пункт 117 дополнить",
     FIX_EGE, POST_EGE, POST_EGE_RE, "Физика, среднее общее образование (п. 115.9, 116.9 — ЕГЭ) — PDF стр. 1008–1037"),
]


GLUE_EXCLUDE = {"используемыми"}


def fix_spacing(text, vocab):
    """Слипшиеся на переносах слова и пропущенные пробелы после знаков — только вне формул."""
    from glued import find

    glue = {k: v for k, v in find(text, vocab).items() if k not in GLUE_EXCLUDE}
    for k, v in glue.items():
        a, b = v.split(" ")
        print(f"  склейка: {k} -> {a} | {b}")
    parts = split_math(text)
    for i in range(0, len(parts), 2):
        s = parts[i]
        for k, v in glue.items():
            a, b = v.split(" ")
            sep = "<br>" if b[:1].isupper() and a[-1:].islower() else " "
            s = re.sub(rf"(?<![А-Яа-яЁё]){k}(?![А-Яа-яЁё])", a + sep + b, s)
        s = re.sub(r"([а-яё»)])\.([А-ЯЁ])", r"\1. \2", s)
        s = re.sub(r"^\.([А-ЯЁ])", r". \1", s) if i > 0 else s
        s = re.sub(r"([,;:])([А-Яа-яЁё])", r"\1 \2", s)
        s = re.sub(r"^([,;:])(?=\S)", r"\1 ", s) if i > 0 else s
        s = re.sub(r"Таблица(\d)", r"Таблица \1", s)
        parts[i] = s
    return "$".join(parts)


def apply_fixes(text, fixes, label):
    for old, new, expected in fixes:
        n = text.count(old)
        if n == 0 or (expected is not None and n != expected):
            raise SystemExit(f"[{label}] правка не сошлась: {old!r} найдено {n}, ожидалось {expected}")
        text = text.replace(old, new)
        if expected is None:
            print(f"[{label}] {old!r}: заменено {n}")
    return text


CYR_RUN = re.compile(r"[А-Яа-яЁё]+(?:[ .,]*[А-Яа-яЁё]+)*\.?")


def clean_math(m):
    """Кириллица в формулах — в \\text{}, '|' — в \\vert (иначе ломает pipe-таблицы)."""
    parts = re.split(r"(\\text\{[^{}]*\})", m.strip())
    for i in range(0, len(parts), 2):
        parts[i] = CYR_RUN.sub(lambda x: r"\text{" + x.group(0) + "}", parts[i])
    m = "".join(parts)
    m = m.replace(r"\|", r"\Vert ").replace("|", r"\vert ")
    return re.sub(r"\\vert (?=[_^}])", r"\\vert", m)


def split_math(text):
    parts = text.split("$")
    if len(parts) % 2 == 0:
        raise SystemExit("непарный $ в тексте")
    return parts  # чётные — текст, нечётные — формулы


def normalize_math(text):
    parts = split_math(text)
    out = []
    for i, p in enumerate(parts):
        out.append(p if i % 2 == 0 else " $" + clean_math(p) + "$ ")
    s = "".join(out)
    s = re.sub(r"[ \t]{2,}", " ", s)
    s = re.sub(r" ([.,;:])", r"\1", s)
    s = re.sub(r"(<td[^>]*>) ", r"\1", s)
    return re.sub(r" (</td>)", r"\1", s)


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows, self.cell, self.attrs = [], None, {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "tr":
            self.rows.append([])
        elif tag in ("td", "th"):
            self.cell, self.attrs = [], a
        elif tag == "img" and self.cell is not None:
            self.cell.append(f"![]({a.get('src', '')})")
        elif tag == "br" and self.cell is not None:
            self.cell.append("<br>")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.rows[-1].append(("".join(self.cell).strip(), int(self.attrs.get("rowspan", 1)),
                                  int(self.attrs.get("colspan", 1))))
            self.cell = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)


def html_table_to_pipe(table_html):
    p = TableParser()
    p.feed(table_html)
    grid, pending = [], {}  # pending[col] = оставшиеся строки rowspan
    for row in p.rows:
        out, col, it = [], 0, iter(row)
        cells = list(row)
        while cells or pending.get(col, 0) > 0:
            if pending.get(col, 0) > 0:
                out.append("")
                pending[col] -= 1
                col += 1
                continue
            text, rs, cs = cells.pop(0)
            for k in range(cs):
                out.append(text if k == 0 else "")
                if rs > 1:
                    pending[col] = rs - 1
                col += 1
        grid.append(out)
    width = max(len(r) for r in grid)
    grid = [r + [""] * (width - len(r)) for r in grid if any(c.strip() for c in r)]

    def esc(c):
        parts = split_math(c.replace("\n", " "))
        return "".join(p.replace("|", r"\|") if i % 2 == 0 else "$" + p + "$" for i, p in enumerate(parts))

    lines = ["| " + " | ".join(esc(c) for c in grid[0]) + " |", "|" + " --- |" * width]
    lines += ["| " + " | ".join(esc(c) for c in r) + " |" for r in grid[1:]]
    return "\n".join(lines)


def to_pipe_markdown(text):
    return re.sub(r"<table>.*?</table>", lambda m: "\n" + html_table_to_pipe(m.group(0)) + "\n", text, flags=re.S)


def esc_math_html(s, escape_text=False):
    """Экранирует формулы (а при escape_text — и обычный текст) ровно один раз."""
    parts = split_math(s)
    out = "".join((html.escape(p, quote=False) if escape_text else p) if i % 2 == 0
                  else "$" + html.escape(p, quote=False) + "$" for i, p in enumerate(parts))
    return out.replace("&lt;br&gt;", "<br>")


def md_to_html(text):
    """Мини-конвертер: абзацы, pipe-таблицы, HTML-таблицы как есть."""
    blocks, out = re.split(r"\n\s*\n", text.strip()), []
    for b in blocks:
        b = b.strip()
        if b.startswith("<table"):
            b = re.sub(r"<img src=\"([^\"]+)\"\s*/?>", r'<img src="\1" alt="">', b)
            out.append('<div class="tw">' + esc_math_html(b) + "</div>")
        elif b.startswith("|"):
            rows = [r for r in b.splitlines() if not re.fullmatch(r"\|(\s*-+\s*\|)+", r.strip())]
            trs = []
            for k, r in enumerate(rows):
                cells = re.split(r"(?<!\\)\|", r.strip()[1:-1])
                tag = "th" if k == 0 else "td"
                trs.append("<tr>" + "".join(f"<{tag}>{esc_math_html(c.strip().replace(chr(92) + '|', '|'), True)}</{tag}>"
                                            for c in cells) + "</tr>")
            out.append('<div class="tw"><table>' + "".join(trs) + "</table></div>")
        elif b.startswith("#"):
            lvl = len(b) - len(b.lstrip("#"))
            out.append(f"<h{lvl}>{html.escape(b.lstrip('#').strip())}</h{lvl}>")
        else:
            out.append("<p>" + esc_math_html(b, True).replace("\n", "<br>") + "</p>")
    return "\n".join(out)


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "images").mkdir(parents=True)
    html_sections = []
    sys.path.insert(0, str(ROOT / "work"))
    import os
    os.chdir(ROOT)
    from glued import vocab
    voc = vocab()
    for name, folder, start, end, fixes, post, post_re, title in DOCS:
        md = (SRC / folder / "markdown.md").read_text(encoding="utf-8")
        i = md.index(start)
        j = md.index(end, i)
        part = apply_fixes(md[i:j].rstrip(), fixes, name)
        part = normalize_math(part)
        part = fix_spacing(part, voc)
        part = apply_fixes(part, post, name + " (текст)")
        for pat, repl, expected in post_re:
            part, n = re.subn(pat, repl, part)
            if n != expected:
                raise SystemExit(f"[{name}] regex-правка не сошлась: {pat!r} {n} != {expected}")
        assert "\\frac{A}{Z}" not in part
        imgs = sorted(set(re.findall(r"images/([^\"')\s]+)", part)))
        for im in imgs:
            shutil.copy(SRC / folder / "images" / im, OUT / "images" / f"{folder}_{im}")
        part = re.sub(r"images/([^\"')\s]+)", rf"images/{folder}_\1", part)
        header = f"# {title}\n\n"
        (OUT / f"{name}.md").write_text(header + to_pipe_markdown(part) + "\n", encoding="utf-8")
        html_sections.append(f"<section><h1>{html.escape(title)}</h1>\n{md_to_html(part)}</section>")
        n_math = len(split_math(part)) // 2
        print(f"{name}: {len(part)} символов, формул {n_math}, картинок {len(imgs)}")
    page = (ROOT / "work" / "template.html").read_text(encoding="utf-8").replace("{{BODY}}", "\n".join(html_sections))
    (OUT / "Физика_формулы.html").write_text(page, encoding="utf-8")


if __name__ == "__main__":
    main()
