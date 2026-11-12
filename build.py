# -*- coding: utf-8 -*-
"""data/ 의 가격 기록으로 정적 사이트(site/)를 만든다. AI를 쓰지 않고 숫자만으로 문장을 만든다."""
import json, os, re, shutil, html
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA, OUT = os.path.join(ROOT, "data"), os.path.join(ROOT, "site")
esc = lambda s: html.escape(str(s or ""), quote=True)
won = lambda n: f"{int(n):,}원"


def load_json(path, default=None):
    if not os.path.exists(path): return default
    with open(path, encoding="utf-8") as f: return json.load(f)


CFG = load_json(os.path.join(ROOT, "config.json"), {})
META = load_json(os.path.join(DATA, "meta.json"), {})
repo = os.environ.get("GITHUB_REPOSITORY", "")
BASE = (CFG.get("base_url") or (f"https://{repo.split('/')[0].lower()}.github.io/{repo.split('/')[1]}" if "/" in repo else "")).rstrip("/")
DAY = META.get("day") or ""
SITE = CFG.get("site_name", "가격노트")


def kday(d):
    if not d: return "아직 기록 전"
    y, m, dd = d.split("-"); return f"{int(m)}월 {int(dd)}일"


def stats(g):
    h = g["history"]
    cur = h[-1][1]; prev = h[-2][1] if len(h) > 1 else None
    win = h[-26:]; avgs = [x[1] for x in win]
    lo, hi = min(avgs), max(avgs)
    d = (cur - prev) if prev else 0
    return {"cur": cur, "prev": prev, "d": d, "pct": (d / prev * 100) if prev else 0.0, "lo": lo, "hi": hi,
            "lo_day": next(x[0] for x in reversed(win) if x[1] == lo), "hi_day": next(x[0] for x in reversed(win) if x[1] == hi),
            "min": h[-1][2], "max": h[-1][3], "n": h[-1][4], "weeks": len(h),
            "is_low": len(h) >= 6 and cur == lo and hi > lo, "fresh": h[-1][0] == DAY}


# ---------------------------------------------------------------- 그림
def spark(h, w=96, hgt=28):
    pts = [x[1] for x in h[-26:]]
    if len(pts) < 2: return '<span class="nodata">기록 쌓는 중</span>'
    lo, hi = min(pts), max(pts); rng = (hi - lo) or 1
    xy = " ".join(f"{i * (w - 4) / (len(pts) - 1) + 2:.1f},{hgt - 3 - (v - lo) * (hgt - 6) / rng:.1f}" for i, v in enumerate(pts))
    cls = "down" if pts[-1] < pts[0] else "up" if pts[-1] > pts[0] else "flat"
    return f'<svg class="spark {cls}" viewBox="0 0 {w} {hgt}" width="{w}" height="{hgt}" role="img" aria-label="최근 가격 흐름"><polyline points="{xy}"/></svg>'


def chart(h):
    win = [(x[0], x[1]) for x in h[-52:]]
    if len(win) < 2:
        return '<p class="note">아직 한 주치 기록만 있어요. 다음 주부터 가격 흐름이 그려져요.</p>'
    W, H, L, R_, T, B = 720, 260, 64, 16, 16, 30
    vals = [v for _, v in win]; lo, hi = min(vals), max(vals); rng = (hi - lo) or max(1, hi * 0.02)
    lo_a, hi_a = lo - rng * 0.12, hi + rng * 0.12
    X = lambda i: L + i * (W - L - R_) / (len(win) - 1)
    Y = lambda v: T + (hi_a - v) * (H - T - B) / (hi_a - lo_a)
    line = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, (_, v) in enumerate(win))
    i_lo = max(i for i, (_, v) in enumerate(win) if v == lo)
    grid = "".join(f'<line class="grid" x1="{L}" x2="{W - R_}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/>'
                   f'<text class="ax" x="{L - 8}" y="{Y(v) + 4:.1f}" text-anchor="end">{int(v):,}</text>' for v in ((lo, hi) if hi > lo else (lo,)))
    return (f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="최근 {len(win)}주 평균 판매가 흐름">{grid}'
            f'<polyline class="line" points="{line}"/>'
            f'<circle class="dot-lo" cx="{X(i_lo):.1f}" cy="{Y(lo):.1f}" r="4.5"/>'
            f'<circle class="dot-now" cx="{X(len(win) - 1):.1f}" cy="{Y(vals[-1]):.1f}" r="4.5"/>'
            f'<text class="ax" x="{L}" y="{H - 8}">{kday(win[0][0])}</text>'
            f'<text class="ax" x="{W - R_}" y="{H - 8}" text-anchor="end">{kday(win[-1][0])}</text></svg>')


def delta(s):
    if not s["prev"]: return '<span class="chg flat">첫 기록</span>'
    if s["d"] == 0: return '<span class="chg flat">변동 없음</span>'
    cls, mark = ("down", "▼") if s["d"] < 0 else ("up", "▲")
    return f'<span class="chg {cls}">{mark} {abs(s["d"]):,}원 <small>{abs(s["pct"]):.1f}%</small></span>'



# ---------------------------------------------------------------- 자료 읽기
REF = load_json(os.path.join(DATA, "ref.json"), {"goods": {}, "stores": {}})
GOODS = []
for gid, g in (load_json(os.path.join(DATA, "goods.json"), {}) or {}).items():
    if not g.get("history"): continue
    r = REF["goods"].get(gid, {})
    g = {**g, "id": re.sub(r"[^0-9A-Za-z_-]", "", gid), "name": r.get("name", gid), "cls": r.get("cls", ""), "top": r.get("top", "생필품"),
         "slug": "c" + re.sub(r"[^0-9A-Za-z]", "", str(r.get("top_code", "etc"))), "size": r.get("size", "")}
    g["s"] = stats(g); GOODS.append(g)
CATS = []
for g in GOODS:
    c = next((c for c in CATS if c["slug"] == g["slug"]), None)
    if c: c["n"] += 1
    else: CATS.append({"slug": g["slug"], "name": g["top"], "n": 1})
CATS.sort(key=lambda c: -c["n"])

# ---------------------------------------------------------------- 틀
def partner():
    w = (CFG.get("coupang_widget_html") or "").strip()
    if not w: return ""
    return ('<aside class="partner"><p class="disc">이 영역은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.</p>' + w + "</aside>")


def page(path, title, desc, body, depth=0, jsonld=""):
    R = "../" * depth
    head_extra = ""
    if CFG.get("google_verification"): head_extra += f'<meta name="google-site-verification" content="{esc(CFG["google_verification"])}">'
    if CFG.get("naver_verification"): head_extra += f'<meta name="naver-site-verification" content="{esc(CFG["naver_verification"])}">'
    if CFG.get("adsense_client"):
        head_extra += f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={esc(CFG["adsense_client"])}" crossorigin="anonymous"></script>'
    canon = f'<link rel="canonical" href="{BASE}/{path}">' if BASE else ""
    nav = "".join(f'<a href="{R}c/{c["slug"]}.html">{esc(c["name"])}</a>' for c in CATS[:8])
    doc = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title><meta name="description" content="{esc(desc)}">{canon}
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}"><meta property="og:type" content="website">
<link rel="alternate" type="application/rss+xml" title="{esc(SITE)}" href="{R}rss.xml">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">
<link rel="stylesheet" href="{R}assets/style.css">{head_extra}{jsonld}</head>
<body><header class="top"><div class="wrap bar"><a class="logo" href="{R}index.html">{esc(SITE)}</a><nav>{nav}</nav></div></header>
<main class="wrap">{body}</main>
<footer class="wrap foot"><p>가격 출처: 한국소비자원 참가격 「생필품 가격 정보」(공공데이터포털, 공공누리 제1유형). 매주 금요일 전국 조사 매장의 판매가이며, 매장과 시점에 따라 실제 가격은 다를 수 있습니다.</p>
<p><a href="{R}about.html">이 사이트는</a> · <a href="{R}privacy.html">개인정보 처리방침</a> · <a href="{R}rss.xml">RSS</a></p></footer></body></html>"""
    full = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f: f.write(doc)


def row(g, depth=0, show_cat=True):
    R = "../" * depth; s = g["s"]
    badge = '<span class="low">반년 최저</span>' if s["is_low"] else ""
    sub = " · ".join(x for x in ((g["top"] if show_cat else g["cls"]), g["size"]) if x)
    return (f'<li class="item noimg-row"><div class="name"><span class="cat">{esc(sub)}</span><a href="{R}p/{g["id"]}.html">{esc(g["name"])}</a></div>'
            f'<div class="trend">{spark(g["history"])}</div>'
            f'<div class="price"><b>{won(s["cur"])}</b>{badge}{delta(s)}</div></li>')


def iga(w):
    c = ord(w[-1]) if w else 0
    return w + ("이" if 0xAC00 <= c <= 0xD7A3 and (c - 0xAC00) % 28 else "가")


def sentence(g):
    s, L = g["s"], g.get("latest", {}); out = []
    head = f"{kday(g['history'][-1][0])} 조사에서 전국 {s['n']}개 매장 평균 판매가는 {won(s['cur'])}"
    if not s["prev"]: out.append(head + "입니다.")
    elif s["d"] == 0: out.append(head + "으로 지난 조사와 같습니다.")
    else: out.append(head + f"으로 지난 조사보다 {abs(s['d']):,}원({abs(s['pct']):.1f}%) {'내렸습니다' if s['d'] < 0 else '올랐습니다'}.")
    if s["max"] > s["min"]: out.append(f"같은 주에 가장 싼 매장은 {won(s['min'])}, 가장 비싼 매장은 {won(s['max'])}이었습니다.")
    t = sorted((L.get("types") or {}).items(), key=lambda x: x[1])
    if len(t) >= 2 and t[-1][1] > t[0][1]: out.append(f"업태별 평균은 {iga(t[0][0])} {won(t[0][1])}으로 가장 낮고 {iga(t[-1][0])} {won(t[-1][1])}으로 가장 높습니다.")
    if s["weeks"] >= 4 and s["hi"] > s["lo"]:
        out.append(f"기록한 최근 {min(s['weeks'], 26)}주 동안 평균가가 가장 낮았던 때는 {kday(s['lo_day'])}의 {won(s['lo'])}, 가장 높았던 때는 {kday(s['hi_day'])}의 {won(s['hi'])}입니다.")
    if L.get("sale"): out.append(f"이번 조사에서 {L['sale']}개 매장이 할인 중이었습니다.")
    return " ".join(out)


def main():
    if os.path.isdir(OUT): shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "assets"))
    shutil.copy(os.path.join(ROOT, "assets", "style.css"), os.path.join(OUT, "assets", "style.css"))
    allg = sorted(GOODS, key=lambda g: g["name"])
    fresh = [g for g in allg if g["s"]["fresh"]]
    drops = sorted([g for g in fresh if g["s"]["pct"] <= -1.0], key=lambda g: g["s"]["pct"])
    rises = sorted([g for g in fresh if g["s"]["pct"] >= 1.0], key=lambda g: -g["s"]["pct"])
    lows = [g for g in fresh if g["s"]["is_low"] and g not in drops[:20]]
    has_hist = any(g["s"]["prev"] for g in allg)

    b = [f'<section class="lede"><p class="date">{kday(DAY)} 조사 기준</p><h1>{esc(CFG.get("tagline", ""))}</h1>'
         f'<p class="sub">생필품 {len(allg):,}개의 전국 매장 판매가를 매주 적습니다. 지난 조사보다 내린 품목 {len(drops)}개, 오른 품목 {len(rises)}개.</p></section>']
    if not allg:
        b.append('<section><h2>첫 기록을 기다리는 중</h2><p class="note">첫 가격 수집이 끝나면 이 자리에 목록이 나옵니다.</p></section>')
    if drops: b.append(f'<section><h2>지난 조사보다 내린 품목</h2><ul class="list">{"".join(row(g) for g in drops[:20])}</ul></section>')
    elif has_hist: b.append('<section><h2>지난 조사보다 내린 품목</h2><p class="note">이번 주는 1% 넘게 내린 품목이 없어요.</p></section>')
    if lows: b.append(f'<section><h2>지금이 최근 반년 중 가장 싼 품목</h2><ul class="list">{"".join(row(g) for g in lows[:12])}</ul></section>')
    b.append(partner())
    if rises: b.append(f'<section><h2>지난 조사보다 오른 품목</h2><ul class="list">{"".join(row(g) for g in rises[:12])}</ul></section>')
    if CATS: b.append('<section><h2>종류별로 보기</h2><div class="cats">' + "".join(
        f'<a href="c/{c["slug"]}.html"><b>{esc(c["name"])}</b><span>{c["n"]}개 품목</span></a>' for c in CATS) + "</div></section>")
    page("index.html", f"{SITE} | 생필품 가격, 지난주보다 올랐을까", f"{kday(DAY)} 조사 기준 생필품 {len(allg)}개의 전국 평균 판매가와 지난 조사 대비 변화.", "".join(b))

    for c in CATS:
        gs = [g for g in allg if g["slug"] == c["slug"]]
        groups = {}
        for g in gs: groups.setdefault(g["cls"] or c["name"], []).append(g)
        body = [f'<section class="lede"><p class="date">{kday(DAY)} 조사 기준</p><h1>{esc(c["name"])} 가격</h1><p class="sub">{len(gs)}개 품목의 전국 평균 판매가와 반년 흐름.</p></section>']
        for k in sorted(groups): body.append(f'<section><h2>{esc(k)}</h2><ul class="list">{"".join(row(g, 1, False) for g in groups[k])}</ul></section>')
        body.append(partner())
        page(f"c/{c['slug']}.html", f"{c['name']} 가격 흐름 | {SITE}", f"{c['name']} {len(gs)}개 품목의 이번 주 평균 판매가와 지난 조사 대비 변화.", "".join(body), 1)

    for g in allg:
        s, L = g["s"], g.get("latest", {})
        types = sorted((L.get("types") or {}).items(), key=lambda x: x[1])
        tmax = max([v for _, v in types], default=1)
        tbl = "".join(f'<div class="bar-row"><span>{esc(t)}</span><i style="width:{v / tmax * 100:.0f}%"></i><b>{won(v)}</b></div>' for t, v in types)
        cheap = "".join(f'<li><b>{won(c["p"])}</b><span>{esc(c["name"])}</span><small>{esc(" · ".join(x for x in (c["type"], c["area"]) if x))}</small></li>' for c in L.get("cheap", []))
        facts = [("전국 평균", won(s["cur"])), ("지난 조사 대비", delta(s)), ("이번 주 최저 매장", won(s["min"])), ("이번 주 최고 매장", won(s["max"])),
                 ("조사 매장 수", f'{s["n"]}곳'), ("기록한 기간", f'{s["weeks"]}주')]
        if g["size"]: facts.insert(0, ("용량", esc(g["size"])))
        sib = [x for x in allg if x["cls"] == g["cls"] and x["id"] != g["id"] and g["cls"]][:6]
        body = (f'<p class="crumb"><a href="../c/{g["slug"]}.html">{esc(g["top"])}</a>{" › " + esc(g["cls"]) if g["cls"] else ""}</p>'
                f'<article class="prod solo"><div><h1>{esc(g["name"])}</h1>'
                f'<p class="big">{won(s["cur"])} <small class="unit">전국 평균</small> {"<span class=low>반년 최저</span>" if s["is_low"] else ""}</p>'
                f'<p class="say">{esc(sentence(g))}</p></div></article>'
                f'<section><h2>평균 판매가 흐름</h2>{chart(g["history"])}<p class="legend"><span class="k-now"></span>이번 조사 <span class="k-lo"></span>기간 중 최저</p></section>'
                + (f'<section><h2>어디가 쌀까, 업태별 평균</h2><div class="bars">{tbl}</div></section>' if tbl else "")
                + (f'<section><h2>이번 조사에서 가장 쌌던 매장</h2><ol class="cheap">{cheap}</ol><p class="note">조사 대상 매장 가운데 순서이며, 지금 가격은 다를 수 있습니다.</p></section>' if cheap else "")
                + f'<section><h2>숫자로 보기</h2><dl class="facts">{"".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in facts)}</dl></section>'
                + partner()
                + (f'<section><h2>같은 종류의 다른 품목</h2><ul class="list">{"".join(row(x, 1, False) for x in sib)}</ul></section>' if sib else ""))
        page(f"p/{g['id']}.html", f"{g['name']} 가격 {won(s['cur'])}, 어디가 쌀까 | {SITE}", sentence(g)[:150], body, 1)

    contact = f'<p>문의: {esc(CFG["contact"])}</p>' if CFG.get("contact") else ""
    page("about.html", f"이 사이트는 | {SITE}", "가격을 어떻게 모으고 무엇을 보여 주는지 설명합니다.",
         f'<section class="lede"><h1>이 사이트는</h1></section><section class="doc"><p>{esc(SITE)}는 라면, 우유, 세제 같은 생필품이 지난주보다 올랐는지 내렸는지, 어떤 업태에서 더 싼지 한눈에 보도록 정리한 개인 운영 사이트입니다.</p>'
         '<h2>가격 출처</h2><p>한국소비자원이 참가격(price.go.kr)을 통해 공개하는 「생필품 가격 정보」를 공공데이터포털 오픈API로 받아 사용합니다. 이 자료는 공공누리 제1유형(출처표시)으로 개방된 공공저작물이며, 매주 금요일 전국 조사 매장의 판매가입니다.</p>'
         '<h2>이 사이트가 더한 것</h2><p>매장별 가격을 품목마다 전국 평균, 최저, 최고, 업태별 평균으로 다시 계산하고, 주마다 쌓아 흐름을 그렸습니다. 평균에서 크게 벗어난 입력 오류로 보이는 값은 계산에서 뺐습니다. 모든 문장은 숫자에서 자동으로 만들어지며, 한국소비자원의 공식 통계나 의견이 아닙니다.</p>'
         '<h2>광고와 수수료</h2><p>이 사이트에는 광고가 표시될 수 있고, 쿠팡 파트너스 영역을 통해 구매가 일어나면 운영자가 일정액의 수수료를 받을 수 있습니다. 해당 영역에는 그 사실을 따로 적어 둡니다. 가격 기록과 정렬 순서는 광고나 수수료와 무관합니다.</p>'
         f'{contact}</section>')
    page("privacy.html", f"개인정보 처리방침 | {SITE}", "개인정보 처리방침",
         '<section class="lede"><h1>개인정보 처리방침</h1></section><section class="doc"><p>이 사이트는 회원 가입이 없고, 방문자의 이름·연락처 같은 개인정보를 직접 수집하거나 보관하지 않습니다.</p>'
         '<h2>쿠키와 광고</h2><p>Google을 포함한 제3자 광고 사업자는 쿠키를 사용해 방문자의 이전 방문 기록을 바탕으로 광고를 게재할 수 있습니다. 방문자는 Google 광고 설정(adssettings.google.com)에서 맞춤 광고를 끌 수 있습니다. 쿠팡 파트너스 영역은 쿠팡이 제공하는 스크립트로 표시되며, 쿠팡의 정책에 따라 쿠키가 사용될 수 있습니다.</p>'
         '<h2>접속 기록</h2><p>사이트는 GitHub Pages에서 제공되며, 호스팅 사업자가 보안과 운영을 위해 접속 IP 등 기술 정보를 기록할 수 있습니다.</p>'
         f'<p>시행일: {DAY or datetime.now().strftime("%Y-%m-%d")}</p></section>')

    with open(os.path.join(OUT, "robots.txt"), "w") as f:
        f.write("User-agent: *\nAllow: /\n" + (f"Sitemap: {BASE}/sitemap.xml\n" if BASE else ""))
    if BASE:
        urls = ["index.html", "about.html", "privacy.html"] + [f"c/{c['slug']}.html" for c in CATS] + [f"p/{g['id']}.html" for g in allg]
        with open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' +
                    "".join(f"<url><loc>{BASE}/{u}</loc><lastmod>{DAY}</lastmod></url>" for u in urls) + "</urlset>")
    items = "".join(f"<item><title>{esc(g['name'])} {won(g['s']['cur'])} ({g['s']['pct']:+.1f}%)</title><link>{BASE}/p/{g['id']}.html</link>"
                    f"<guid isPermaLink=\"false\">{g['id']}-{DAY}</guid><description>{esc(sentence(g))}</description></item>" for g in (drops[:20] + rises[:10]))
    with open(os.path.join(OUT, "rss.xml"), "w", encoding="utf-8") as f:
        f.write(f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{esc(SITE)}</title><link>{BASE}/</link>'
                f'<description>{esc(CFG.get("tagline", ""))}</description>{items}</channel></rss>')
    if CFG.get("adsense_client"):
        with open(os.path.join(OUT, "ads.txt"), "w") as f:
            f.write(f"google.com, {CFG['adsense_client'].replace('ca-', '')}, DIRECT, f08c47fec0942fa0\n")
    open(os.path.join(OUT, ".nojekyll"), "w").close()
    page("404.html", f"없는 페이지 | {SITE}", "없는 페이지", '<section class="lede"><h1>찾는 페이지가 없어요</h1><p class="sub"><a href="' + ((BASE + '/') if BASE else 'index.html') + '">첫 화면</a>에서 다시 찾아보세요.</p></section>')
    print(f"사이트 생성: 품목 {len(allg)}개, 내림 {len(drops)}개, 오름 {len(rises)}개, 반년 최저 {len(lows)}개")


if __name__ == "__main__":
    main()
