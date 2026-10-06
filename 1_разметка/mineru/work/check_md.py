import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
for path in sys.argv[1:]:
    lines = open(path, encoding="utf-8").read().split("\n")
    bad, tables, width = 0, 0, None
    for n, l in enumerate(lines, 1):
        if l.startswith("|"):
            masked = re.sub(r"\$[^$]*\$", "M", l)
            cols = len(re.split(r"(?<!\\)\|", masked)) - 2
            if width is None:
                width, tables = cols, tables + 1
            elif cols != width:
                bad += 1
                print(f"  {path}:{n}: {cols} столбцов вместо {width}")
        else:
            width = None
    dollars = sum(l.count("$") for l in lines)
    print(f"{path}: таблиц {tables}, битых строк {bad}, '$' чётно: {dollars % 2 == 0}, "
          f"html-таблиц осталось: {sum('<table' in l for l in lines)}")
