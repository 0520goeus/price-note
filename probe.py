# 실제 API에서 어느 조사일·상품·매장에 가격이 있는지 확인하는 임시 점검 파일
import os, re, urllib.request, urllib.parse, urllib.error
from datetime import date, timedelta
K = os.environ["DATA_KEY"]; K = urllib.parse.unquote(K) if "%" in K else K
B = "https://apis.data.go.kr/B551919/ProductPriceInfoService"
def get(path, **p):
    url = f"{B}/{path}?" + urllib.parse.urlencode({"serviceKey": K, **p})
    try:
        with urllib.request.urlopen(url, timeout=60) as r: return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e: return f"HTTP{e.code} " + e.read().decode("utf-8", "replace")[:200]
    except Exception as e: return "ERR " + str(e)
goods = re.findall(r"<goodId>(\d+)</goodId>\s*<goodName>([^<]*)", get("getProductInfoSvc.do"))
stores = re.findall(r"<entpId>(\d+)</entpId>\s*<entpName>([^<]*)</entpName>\s*<entpTypeCode>([^<]*)", get("getStoreInfoSvc.do"))
print("상품 수", len(goods), goods[:5], goods[-5:]); print("매장 수", len(stores), stores[:3], stores[-3:])
for c in ("BU", "AR", "UT"):
    print(c, re.findall(r"<code>([^<]*)</code>\s*<codeName>([^<]*)", get("getStandardInfoSvc.do", classCode=c))[:12])
gs = [goods[0][0], goods[len(goods)//2][0], goods[-1][0]]; ss = [stores[10][0], stores[len(stores)//2][0], stores[-1][0]]
d = date.today()
for back in list(range(0, 21)) + [28, 35, 42, 56, 84, 180, 365, 730]:
    day = (d - timedelta(days=back)).strftime("%Y%m%d"); out = []
    for kind, ids in (("goodId", gs), ("entpId", ss)):
        for i in ids:
            b = get("getProductPriceInfoSvc", goodInspectDay=day, **{kind: i})
            out.append(f"{kind[0]}{i}:{b.count('<goodPrice>') if not b.startswith(('HTTP','ERR')) else b[:40]}")
    print(day, (d - timedelta(days=back)).strftime("%a"), " ".join(out))
b = ""
for back in range(0, 60):
    day = (d - timedelta(days=back)).strftime("%Y%m%d")
    b = get("getProductPriceInfoSvc", goodInspectDay=day, entpId=ss[1])
    if "<goodPrice>" in b: print("예시", day, b[:900]); break
