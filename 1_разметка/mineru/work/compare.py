import re, sys, collections
def words(p):
    t = open(p, encoding='utf-8').read()
    t = re.sub(r'\$\$.*?\$\$|\$[^$]*\$', ' ', t, flags=re.S)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = t.replace('ё','е').replace('Ё','Е')
    return collections.Counter(w.lower() for w in re.findall(r'[А-Яа-яЁё]{4,}', t))
a, b = words(sys.argv[1]), words(sys.argv[2])
miss = {w: a[w]-b[w] for w in a if a[w] > b[w]}
print('std words', sum(a.values()), 'adv words', sum(b.values()), 'missing occurrences', sum(miss.values()))
print(sorted(miss.items(), key=lambda x: -x[1])[:80])
