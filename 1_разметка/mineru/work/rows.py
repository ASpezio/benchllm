import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
for l in open(sys.argv[1], encoding="utf-8").read().split("\n"):
    if "$" in l:
        masked = re.sub(r"\$[^$]*\$", "§", l)
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", masked) if c.strip()]
        print(" | ".join(cells)[:420])
