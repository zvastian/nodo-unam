import requests, time

urls = [
    "https://tesiunam.dgb.unam.mx/cgi-bin/koha/opac-main.pl",
    "https://tesiunam.dgb.unam.mx/cgi-bin/koha/opac-detail.pl?biblionumber=222123",
    "https://etesiunam.dgb.unam.mx/F?func=find-b-0&local_base=TESBIDI",
]

for url in urls:
    print("\nURL:", url)
    t0 = time.time()
    try:
        r = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
        print("status:", r.status_code, "len:", len(r.text), "secs:", round(time.time() - t0, 2))
        print(r.text[:80].replace("\n", " "))
    except Exception as e:
        print("ERROR:", repr(e), "secs:", round(time.time() - t0, 2))
