# 네트워크 없이 가짜 응답(XML)으로 수집과 사이트 생성을 시험한다
import random, collect, shutil
from datetime import date
random.seed(3)
shutil.rmtree(collect.DATA, ignore_errors=True)
G = [("101", "신라면(5개입)", "30101"), ("102", "진라면 순한맛(5개입)", "30101"), ("201", "서울우유 흰우유(1L)", "30201"), ("301", "퍼실 파워젤(2.7L)", "40101"), ("302", "다우니 섬유유연제(2L)", "40102")]
S = [(str(i), f"{c} {a}점", t, ar) for i, (c, t, ar, a) in enumerate([("이마트", "LM", "0201", "성수"), ("홈플러스", "LM", "0201", "합정"), ("롯데마트", "LM", "0202", "동래"),
     ("GS25", "CS", "0201", "역삼"), ("CU", "CS", "0202", "서면"), ("현대백화점", "DP", "0201", "무역"), ("망원시장", "TR", "0201", "망원"), ("GS더프레시", "SM", "0201", "방배")], 1)]
base = {g[0]: random.randint(30, 150) * 100 for g in G}
def x(tag, rows): return "<response><result>" + "".join(f"<{tag}>" + "".join(f"<{k}>{v}</{k}>" for k, v in r.items()) + f"</{tag}>" for r in rows) + "</result><resultCode>00</resultCode></response>"
def fake(op, **p):
    if op == "getProductInfoSvc": t = x("item", [{"goodId": a, "goodName": b, "goodSmlclsCode": c, "goodTotalCnt": "1", "goodTotalDivCode": "개"} for a, b, c in G])
    elif op == "getStoreInfoSvc": t = x("item", [{"entpId": a, "entpName": b, "entpTypeCode": c, "entpAreaCode": d} for a, b, c, d in S])
    elif op == "getStandardInfoSvc":
        m = {"AL": [("30101", "라면", "301"), ("301", "가공식품", "3"), ("3", "가공식품", ""), ("30201", "우유", "302"), ("302", "유제품", "3"), ("40101", "세탁세제", "401"), ("40102", "섬유유연제", "401"), ("401", "세제", "4"), ("4", "일상용품", "")],
             "BU": [("LM", "대형마트", ""), ("CS", "편의점", ""), ("DP", "백화점", ""), ("TR", "전통시장", ""), ("SM", "기업형 슈퍼", "")], "AR": [("0201", "서울", ""), ("0202", "부산", "")]}[p["classCode"]]
        t = x("iros.openapi.service.vo.stdInfoVO", [{"code": a, "codeName": b, "highCode": c} for a, b, c in m])
    else:
        r = random.Random(p["goodInspectDay"] + p["goodId"]); wk = int(p["goodInspectDay"]) % 7
        mult = {"LM": 1.0, "CS": 1.25, "DP": 1.3, "TR": 0.97, "SM": 1.08}
        t = x("iros.openapi.service.vo.goodPriceVO", [{"goodInspectDay": p["goodInspectDay"], "entpId": s[0], "goodId": p["goodId"],
              "goodPrice": int(base[p["goodId"]] * mult[s[2]] * (1 + r.uniform(-0.06, 0.06)) / 10) * 10, "plusoneYn": "N", "goodDcYn": "Y" if r.random() < .2 else "N"} for s in S])
    return collect.parse(t)[0]
collect.time.sleep = lambda s: None
print(collect.run(fake, date(2026, 11, 12)))
