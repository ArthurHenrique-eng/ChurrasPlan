from html.parser import HTMLParser
from pathlib import Path
import re, sys

root = Path("FrontEnd")
errors=[]
class IDs(HTMLParser):
    def __init__(self): super().__init__(); self.ids=[]
    def handle_starttag(self, tag, attrs):
        d=dict(attrs)
        if "id" in d: self.ids.append(d["id"])

for html in root.glob("*.html"):
    text=html.read_text(encoding="utf-8")
    p=IDs(); p.feed(text)
    dup={x for x in p.ids if p.ids.count(x)>1}
    if dup: errors.append(f"{html}: IDs duplicados {sorted(dup)}")
    for attr in ["src","href"]:
        for val in re.findall(fr'{attr}=["\']([^"\']+)["\']', text):
            if val.startswith(("http://","https://","#","mailto:","tel:","data:")) or val.startswith("/") or "?" in val or val == "":
                continue
            target=(html.parent/val).resolve()
            if not target.exists(): errors.append(f"{html}: referência ausente {val}")
if errors:
    print("\n".join(errors)); sys.exit(1)
print(f"OK: {len(list(root.glob('*.html')))} HTML verificados")
