import json, re, sys
name, start = sys.argv[1], int(sys.argv[2])
m = json.load(open(f'out_adv/{name}/middle_json.json', encoding='utf-8'))
for pdfp in map(int, sys.argv[3:]):
    p = m['pages'][pdfp - start]
    s = json.dumps(p, ensure_ascii=False)
    s = json.loads(s)
    txt = ''
    def walk(o):
        global txt
        if isinstance(o, dict):
            c = o.get('content')
            if isinstance(c, str): txt += c + '\n'
            for k, v in o.items():
                if k != 'content' or not isinstance(v, str): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(p)
    print(f'##### PDF {pdfp}')
    for row in re.findall(r'<tr>(.*?)</tr>', txt, flags=re.S):
        if '<eq>' in row or '$' in row:
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, flags=re.S)
            code = next((c for c in cells if re.fullmatch(r'[\d.]+', c.strip())), '?')
            eqs = re.findall(r'<eq>(.*?)</eq>|\$([^$]+)\$', row)
            print(code, ' || '.join((a or b).strip() for a, b in eqs))
    for e in re.findall(r'<eq>(.*?)</eq>', re.sub(r'<table>.*?</table>', '', txt, flags=re.S)):
        print('OUTSIDE-TABLE', e)
