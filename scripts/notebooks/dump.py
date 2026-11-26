import nbformat, sys
nb=nbformat.read(sys.argv[1],4)
for i,c in enumerate(nb.cells):
    if c.cell_type!="code": continue
    print(f"=== cell {i}")
    for o in c.outputs:
        if o.output_type=="stream": print(o.text[:3000])
        elif "data" in o and "text/plain" in o["data"] and "image/png" not in o["data"]: print(o["data"]["text/plain"][:3000])
        elif "image/png" in o.get("data",{}): print("[image]")
