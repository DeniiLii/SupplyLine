import sys, openpyxl, pathlib
src = sys.argv[1]; out = pathlib.Path(sys.argv[2])
wf = openpyxl.load_workbook(src)
wv = openpyxl.load_workbook(src, data_only=True)
for i, ws in enumerate(wf):
    vs = wv[ws.title]
    lines = []
    for row in ws.iter_rows():
        for c in row:
            if c.value is None: continue
            v = vs[c.coordinate].value
            if isinstance(c.value, str) and c.value.startswith('='):
                lines.append(f"{c.coordinate}\t{c.value}\t=> {v!r}")
            else:
                lines.append(f"{c.coordinate}\t{c.value!r}")
    (out / f"{i:02d}_{ws.title}.txt").write_text("\n".join(lines), encoding="utf-8")
    print(i, ws.title.encode('unicode_escape').decode(), len(lines))
print([d.name for d in wf.defined_names.values()] if hasattr(wf.defined_names,'values') else list(wf.defined_names))
