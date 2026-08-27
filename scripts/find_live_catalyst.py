import sys
import requests
import json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

headers = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.kap.org.tr/tr/bildirim-sorgu",
}
payload = {
    "fromDate": "2026-08-26",
    "toDate": "2026-08-27",
    "disclosureClass": "ODA",
    "subjectList": [],
    "mkkMemberOidList": [],
    "inactiveMkkMemberOidList": [],
    "bdkMemberOidList": [],
    "fromSrc": False,
    "disclosureIndexList": [],
}

r = requests.post(
    "https://www.kap.org.tr/tr/api/disclosure/members/byCriteria",
    json=payload,
    headers=headers,
    timeout=20,
)

data = r.json() if r.status_code == 200 else []
print(f"Toplam 26-27 Ağustos ODA Bildirimi: {len(data)}")

for d in data:
    s = d.get("summary") or ""
    if any(k in s.lower() for k in ["sözleşme", "ihale", "alım", "satış", "üretim", "sipariş", "iş ilişkisi"]):
        print(f"[{d.get('stockCodes')}] {d.get('publishDate')} | Idx: {d.get('disclosureIndex')}")
        print(f"  Başlık: {d.get('kapTitle')}")
        print(f"  Özet: {s}\n")
