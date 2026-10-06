import pymupdf, sys
d = pymupdf.open("work/render.pdf")
for n in map(int, sys.argv[1:]):
    d[n - 1].get_pixmap(dpi=100).save(f"work/img/render_{n}.png")
