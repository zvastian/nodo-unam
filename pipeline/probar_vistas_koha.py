import requests
from bs4 import BeautifulSoup

ids = ["881312", "881852", "885610", "222123"]

candidates = [
    "https://tesiunam.dgb.unam.mx/cgi-bin/koha/opac-MARCdetail.pl?biblionumber={b}",
    "https://tesiunam.dgb.unam.mx/cgi-bin/koha/opac-ISBDdetail.pl?biblionumber={b}",
    "https://tesiunam.dgb.unam.mx/cgi-bin/koha/opac-detail.pl?biblionumber={b}",
]

headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "es-MX,es;q=0.9"}

for b in ids:
    print("\n" + "="*100)
    print("BIBLIONUMBER", b)

    for template in candidates:
        url = template.format(b=b)
        try:
            r = requests.get(url, headers=headers, timeout=20)
            text = r.text or ""
            soup = BeautifulSoup(text, "html.parser")
            plain = " ".join(soup.get_text(" ").split())

            print("\nURL:", url)
            print("status:", r.status_code, "len:", len(text))
            print("has MARC?", "MARC" in plain[:2000] or "LDR" in plain or "100" in plain)
            print("has doc_number?", "doc_number=" in text)
            print("has WEB-FULL?", "WEB-FULL" in text)
            print("has Texto completo?", "Texto completo" in plain or "texto completo" in plain.lower())
            print("sample:", plain[:600])
        except Exception as e:
            print("ERROR", url, repr(e))
