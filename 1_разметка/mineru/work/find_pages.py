import pymupdf, sys
d = pymupdf.open("work/render.pdf")
print("pages", d.page_count)
for key in sys.argv[1:]:
    for i, p in enumerate(d):
        if key in p.get_text():
            print(key, "->", i + 1); break
