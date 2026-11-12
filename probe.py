# 실제 API 응답 형식을 확인하는 임시 점검 파일
import os, urllib.request, urllib.parse, urllib.error
from datetime import date, timedelta
K = os.environ["DATA_KEY"]; K = urllib.parse.unquote(K) if "%" in K else K
B = "https://apis.data.go.kr/B551919/ProductPriceInfoService"
def get(path, **p):
    for kn in ("serviceKey", "ServiceKey"):
        url = f"{B}/{path}?" + urllib.parse.urlencode({kn: K, **p})
        try:
            with urllib.request.urlopen(url, timeout=40) as r: body, code = r.read().decode("utf-8", "replace"), r.status
        except urllib.error.HTTPError as e: body, code = e.read().decode("utf-8", "replace"), e.code
        except Exception as e: body, code = str(e), 0
        print(f"--- {path} {kn} {p} -> {code} len={len(body)}\n{body[:700].replace(K, '***')}\n")
        if code == 200 and len(body) > 200: return body
    return ""
d = date.today(); d -= timedelta(days=(d.weekday() - 4) % 7)
for op in ("getProductInfoSvc.do", "getProductInfoSvc"):
    b = get(op, goodId="1000")
    if b: break
for op in ("getStoreInfoSvc.do", "getStoreInfoSvc"):
    if get(op, entpId="115"): break
for op in ("getStandardInfoSvc.do", "getStandardInfoSvc"):
    if get(op, classCode="AL"): break
for wk in (1, 2, 4):
    day = (d - timedelta(weeks=wk)).strftime("%Y%m%d")
    for op in ("getProductPriceInfoSvc.do", "getProductPriceInfoSvc"):
        for extra in ({"goodId": "1000"}, {"entpId": "115"}, {"goodId": "1000", "pageNo": "1", "numOfRows": "10"}):
            get(op, goodInspectDay=day, **extra)
