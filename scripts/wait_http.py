import sys, time, urllib.request
urls = sys.argv[1:]
for _ in range(90):
    ok = True
    for url in urls:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                ok = ok and 200 <= r.status < 500
        except Exception:
            ok = False
    if ok:
        raise SystemExit(0)
    time.sleep(1)
raise SystemExit("Serviços não ficaram disponíveis a tempo: " + ", ".join(urls))
