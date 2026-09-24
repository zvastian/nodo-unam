import requests
from bs4 import BeautifulSoup

b = "881312"
url = f"https://tesiunam.dgb.unam.mx/cgi-bin/koha/opac-MARCdetail.pl?biblionumber={b}"

r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
html = r.text
soup = BeautifulSoup(html, "html.parser")

print("status:", r.status_code, "len:", len(html))

# Buscar filas de tabla que parezcan MARC
print("\n=== TABLE ROWS SAMPLE ===")
rows = soup.find_all("tr")
for i, tr in enumerate(rows[:80], start=1):
    txt = " ".join(tr.get_text(" ", strip=True).split())
    if txt:
        print(f"\nROW {i}:")
        print(txt[:1000])

print("\n=== ELEMENTS WITH class/id containing marc ===")
for tag in soup.find_all(True):
    attrs = " ".join([
        str(tag.get("class", "")),
        str(tag.get("id", "")),
    ]).lower()
    if "marc" in attrs:
        txt = " ".join(tag.get_text(" ", strip=True).split())
        print(tag.name, tag.get("class"), tag.get("id"), txt[:1000])
