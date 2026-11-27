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

for html in root.rglob("*.html"):
    text=html.read_text(encoding="utf-8")
    p=IDs(); p.feed(text)
    dup={x for x in p.ids if p.ids.count(x)>1}
    if dup: errors.append(f"{html}: IDs duplicados {sorted(dup)}")
    for attr in ["src","href"]:
        for val in re.findall(fr'{attr}=["\']([^"\']+)["\']', text):
            if val.startswith(("http://","https://","#","mailto:","tel:","data:")) or val.startswith("/") or "?" in val or val == "":
                continue
            # "pagina.html#secao": confere o arquivo e também a âncora de destino.
            caminho, _, ancora = val.partition("#")
            target=(html.parent/caminho).resolve()
            if not target.exists(): errors.append(f"{html}: referência ausente {val}")
            elif ancora and target.suffix == ".html" and not re.search(fr'id=["\']{re.escape(ancora)}["\']', target.read_text(encoding="utf-8")):
                errors.append(f"{html}: âncora ausente {val}")
# Service worker: cada arquivo pré-carregado precisa existir (cache.addAll é
# tudo ou nada) e cada página segura precisa estar publicada.
sw=(root/"sw.js").read_text(encoding="utf-8")
for bloco in ("STATIC_ASSETS", "SAFE_PAGES"):
    achado=re.search(bloco+r"\s*=\s*(?:new Set\()?\[(.*?)\]", sw, re.S)
    if not achado:
        errors.append(f"sw.js: lista {bloco} não encontrada"); continue
    for caminho in re.findall(r'"(/[^"]*)"', achado.group(1)):
        alvo=root/(caminho.lstrip("/") or "index.html")
        if not alvo.is_file(): errors.append(f"sw.js: {bloco} aponta para arquivo ausente {caminho}")
if errors:
    print("\n".join(errors)); sys.exit(1)
print(f"OK: {len(list(root.rglob('*.html')))} HTML verificados")
