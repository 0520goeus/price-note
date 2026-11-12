# -*- coding: utf-8 -*-
"""한국소비자원 '생필품 가격 정보' 오픈API(공공데이터포털, 공공누리 제1유형)로 금요일 조사 가격을 받아 data/ 에 쌓는다.
표준 라이브러리만 사용. 환경변수 DATA_KEY = 공공데이터포털에서 받은 인증키(Decoding 값 권장)."""
import json, os, re, sys, time
import urllib.request, urllib.parse, urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta, date

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
KST = timezone(timedelta(hours=9))
BASE = "https://apis.data.go.kr/B551919/ProductPriceInfoService"
KEEP_WEEKS = 80        # 상품당 보관하는 주간 기록 수
BACKFILL_WEEKS = 26    # 처음에 거슬러 올라가 채우는 주 수
CALL_BUDGET = 4000     # 한 번 실행에 쓰는 최대 호출 수 (하루 한도에 걸리면 거기서 멈추고 다음 날 이어서 한다)


class QuotaError(Exception): pass


def api(op, **params):
    """기준정보 조회는 주소 끝에 .do가 붙고 가격 조회는 붙지 않는다(2026-11 확인). 한쪽이 안 되면 다른 쪽을 써 보고 기억해 둔다."""
    key = os.environ["DATA_KEY"]
    key = urllib.parse.unquote(key) if "%" in key else key
    memo = api.__dict__.setdefault("memo", {})
    cands = [memo[op]] if op in memo else ([op, op + ".do"] if op == "getProductPriceInfoSvc" else [op + ".do", op])
    last = None
    for path in cands:
        url = f"{BASE}/{path}?" + urllib.parse.urlencode({"serviceKey": key, **params})
        for attempt in range(3):                      # 연결이 가끔 끊겨서 다시 시도한다
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "pricenote/1.0"}), timeout=60) as r:
                    text = r.read().decode("utf-8", "replace")
                if "LIMITED_NUMBER_OF_SERVICE_REQUESTS" in text or "<returnReasonCode>22<" in text: raise QuotaError("하루 호출 한도를 다 썼습니다")
                rows, code, msg = parse(text)
                if code not in ("", "00", "0", "INFO-000") and not rows: raise RuntimeError(f"{op}: {code} {msg}")
                memo[op] = path
                return rows
            except QuotaError: raise
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")
                if "LIMITED_NUMBER" in body or "<returnReasonCode>22<" in body or e.code == 429: raise QuotaError("하루 호출 한도를 다 썼습니다")
                last = RuntimeError(f"{op}: HTTP {e.code} {re.sub(r'<[^>]+>|\\s+', ' ', body)[:120]}"); break     # 주소가 틀린 경우 → 다음 후보
            except Exception as e:
                last = e; time.sleep(1.5 * (attempt + 1))
    raise last


def parse(text):
    """<result> 아래에서 '자식이 값만 가진' 묶음을 모두 행으로 읽는다 (묶음 태그 이름에 의존하지 않음)"""
    text = text.strip()
    if text.startswith("{"):
        j = json.loads(text); rows = []
        def walk(o):
            if isinstance(o, list):
                for x in o: walk(x)
            elif isinstance(o, dict):
                if any(k in o for k in ("goodId", "entpId", "code")) and all(not isinstance(v, (dict, list)) for v in o.values()): rows.append({k: str(v) for k, v in o.items()})
                else:
                    for v in o.values(): walk(v)
        walk(j)
        return rows, str(j.get("resultCode", "")), str(j.get("resultMsg", ""))
    root = ET.fromstring(text)
    rows = []
    for el in root.iter():
        kids = list(el)
        if kids and all(len(k) == 0 for k in kids) and any(k.tag in ("goodId", "entpId", "code") for k in kids):
            rows.append({k.tag: (k.text or "").strip() for k in kids})
    return rows, (root.findtext(".//resultCode") or "").strip(), (root.findtext(".//resultMsg") or root.findtext(".//returnAuthMsg") or "").strip()


def fridays(n, today=None):
    d = today or datetime.now(KST).date()
    d -= timedelta(days=(d.weekday() - 4) % 7)
    return [(d - timedelta(weeks=i)) for i in range(n)]


def load(name, default):
    p = os.path.join(DATA, name)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f: return json.load(f)
    return default


def save(name, obj):
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def codes(api_fn, cls):
    try: return {r.get("code", ""): r for r in api_fn("getStandardInfoSvc", classCode=cls) if r.get("code")}
    except Exception as e:
        print(f"[참고] 기준정보 {cls} 못 받음: {e}", file=sys.stderr); return {}


def refresh_reference(api_fn):
    goods = {r["goodId"]: r for r in api_fn("getProductInfoSvc") if r.get("goodId")}
    stores = {r["entpId"]: r for r in api_fn("getStoreInfoSvc") if r.get("entpId")}
    al, bu, ar = codes(api_fn, "AL"), codes(api_fn, "BU"), codes(api_fn, "AR")
    def top(code):          # 소분류 → 대분류 이름
        seen, c = set(), al.get(code)
        while c and c.get("highCode") and c["highCode"] in al and c["highCode"] not in seen and c["highCode"] != c.get("code"):
            seen.add(c["code"]); c = al[c["highCode"]]
        return (c or {}).get("codeName", "") , (c or {}).get("code", "")
    ref = {"goods": {}, "stores": {}}
    for gid, g in goods.items():
        tname, tcode = top(g.get("goodSmlclsCode", ""))
        ref["goods"][gid] = {"name": g.get("goodName", gid), "cls": (al.get(g.get("goodSmlclsCode", ""), {}).get("codeName") or ""),
                             "top": tname or "생필품", "top_code": tcode or "etc",
                             "size": " ".join(x for x in (g.get("goodTotalCnt", ""), g.get("goodTotalDivCode", "")) if x and x != "null").strip()}
    for sid, s in stores.items():
        ref["stores"][sid] = {"name": s.get("entpName", sid), "type": bu.get(s.get("entpTypeCode", ""), {}).get("codeName") or s.get("entpTypeCode", ""),
                              "area": ar.get(s.get("entpAreaCode", ""), {}).get("codeName") or ""}
    save("ref.json", ref)
    return ref


def summarize(rows, stores):
    """한 상품의 한 주치 매장별 가격 → 평균·최저·최고, 업태별 평균, 가장 싼 매장 5곳"""
    pts = []
    for r in rows:
        try: p = int(float(r.get("goodPrice") or 0))
        except ValueError: continue
        if p <= 0: continue
        s = stores.get(r.get("entpId", ""), {})
        pts.append((p, s.get("name", ""), s.get("type", ""), s.get("area", ""), r.get("goodDcYn") == "Y", r.get("plusoneYn") == "Y"))
    if len(pts) < 3: return None
    prices = sorted(p for p, *_ in pts)
    med = prices[len(prices) // 2]
    pts = [x for x in pts if med * 0.3 <= x[0] <= med * 3]          # 입력 실수로 보이는 값 제외
    prices = [p for p, *_ in pts]
    by = {}
    for p, _, t, *_ in pts:
        if t: by.setdefault(t, []).append(p)
    cheap = sorted(pts, key=lambda x: x[0])[:5]
    return {"avg": round(sum(prices) / len(prices)), "min": min(prices), "max": max(prices), "n": len(prices),
            "sale": sum(1 for x in pts if x[4]), "plus": sum(1 for x in pts if x[5]),
            "types": {t: round(sum(v) / len(v)) for t, v in by.items() if len(v) >= 2},
            "cheap": [{"p": c[0], "name": c[1], "type": c[2], "area": c[3]} for c in cheap]}


def run(api_fn=api, today=None, budget=CALL_BUDGET):
    meta = load("meta.json", {"done": []})
    ref_age = meta.get("ref_day", "")
    now = today or datetime.now(KST).date()
    if not os.path.exists(os.path.join(DATA, "ref.json")) or ref_age < (now - timedelta(days=6)).isoformat():
        ref = refresh_reference(api_fn); meta["ref_day"] = now.isoformat(); budget -= 5
    else:
        ref = load("ref.json", {})
    goods = load("goods.json", {})
    todo = [d for d in fridays(BACKFILL_WEEKS, now) if d.strftime("%Y-%m-%d") not in meta["done"]]
    gids = list(ref["goods"])
    sample = gids[::max(1, len(gids) // 4)][:4]
    part = meta.setdefault("partial", {})
    calls = fails = filled = 0
    stop = ""
    for d in todo:                                   # 최신 조사일부터, 호출이 남으면 과거를 채운다
        if stop or budget - calls < 10: break
        day, ymd = d.strftime("%Y-%m-%d"), d.strftime("%Y%m%d")
        start = int(part.get(day, 0))
        try:
            if not start:                            # 조사가 없는 주(격주 조사, 아직 안 올라온 주)는 몇 개만 물어보고 넘어간다
                calls += len(sample)
                if not any(api_fn("getProductPriceInfoSvc", goodInspectDay=ymd, goodId=g) for g in sample):
                    if (now - d).days >= 28: meta["done"].append(day)      # 한 달이 지나도 없으면 조사가 없던 주
                    print(f"{day}: 조사 자료 없음"); continue
            got = 0
            for i in range(start, len(gids)):
                if budget - calls <= 0: stop = "이번 실행의 호출 수를 다 씀"; break
                gid = gids[i]; calls += 1
                try: rows = api_fn("getProductPriceInfoSvc", goodInspectDay=ymd, goodId=gid)
                except QuotaError: raise
                except Exception as e:
                    fails += 1
                    if fails > 40: raise RuntimeError(f"가격 조회가 계속 실패합니다: {e}")
                    part[day] = i + 1; continue
                part[day] = i + 1
                s = summarize(rows, ref["stores"])
                if not s: continue
                got += 1
                g = goods.setdefault(gid, {"history": []})
                h = [x for x in g["history"] if x[0] != day] + [[day, s["avg"], s["min"], s["max"], s["n"]]]
                h.sort(); g["history"] = h[-KEEP_WEEKS:]
                if h[-1][0] == day: g["latest"] = {k: s[k] for k in ("sale", "plus", "types", "cheap")}
            if not stop:
                meta["done"].append(day); part.pop(day, None); filled += 1
            print(f"{day}: 상품 {got}개 기록" + (f" (중간까지, {stop})" if stop else ""))
        except QuotaError as e:
            stop = str(e); print(f"{day}: {stop}. 내일 이어서 합니다.")
    meta["done"] = sorted(set(meta["done"]))[-(BACKFILL_WEEKS + 60):]
    days = sorted({h[0] for g in goods.values() for h in g["history"]})
    meta.update(last_run=datetime.now(KST).isoformat(timespec="minutes"), day=days[-1] if days else "", weeks=len(days),
                goods=len(goods), calls=calls, fails=fails)
    save("goods.json", goods); save("meta.json", meta)
    print(f"호출 {calls}회(실패 {fails}), 이번 실행에서 채운 주 {filled}개, 기록된 주 {len(days)}개, 상품 {len(goods)}개")
    return bool(days)


if __name__ == "__main__":
    if not os.environ.get("DATA_KEY"):
        sys.exit("DATA_KEY 환경변수가 없습니다 (공공데이터포털 인증키).")
    sys.exit(0 if run() else 1)
