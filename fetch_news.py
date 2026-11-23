"""Builds docs/index.html: world news translated to Bangla, with photos, videos and summaries.
Free: RSS feeds + Hacker News + free Google Translate endpoint. No API keys, no dependencies."""
import json, re, html, os, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

# ---- EDIT ME: add or remove feeds. (category, source name, url) ----
FEEDS = [
    ("World", "BBC", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("World", "Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("World", "The Guardian", "https://www.theguardian.com/world/rss"),
    ("World", "NPR", "https://feeds.npr.org/1001/rss.xml"),
    ("World", "DW", "https://rss.dw.com/rdf/rss-en-all"),
    ("South Asia", "BBC Asia", "https://feeds.bbci.co.uk/news/world/asia/rss.xml"),
    ("South Asia", "The Daily Star", "https://www.thedailystar.net/frontpage/rss.xml"),
    ("Business", "BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("Business", "CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("Tech", "BBC Tech", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
    ("Tech", "The Verge", "https://www.theverge.com/rss/index.xml"),
    ("Science", "BBC Science", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"),
    ("Social", "Reddit r/worldnews", "https://www.reddit.com/r/worldnews/top/.rss?t=day"),
    ("Social", "Reddit r/news", "https://www.reddit.com/r/news/top/.rss?t=day"),
    ("Social", "Reddit r/bangladesh", "https://www.reddit.com/r/bangladesh/top/.rss?t=day"),
    ("Social", "Reddit r/technology", "https://www.reddit.com/r/technology/top/.rss?t=day"),
    # Facebook/Instagram: see README. Paste a free fetchrss.com feed of a public page here, e.g.
    # ("Social", "Facebook: Page name", "https://rss.fetchrss.com/rss/XXXX.xml"),
    # News video channels (YouTube RSS, plays inside the page)
    ("Video", "Al Jazeera English", "https://www.youtube.com/feeds/videos.xml?channel_id=UCNye-wNBqNL5ZzHSJj3l8Bg"),
    ("Video", "DW News", "https://www.youtube.com/feeds/videos.xml?channel_id=UCknLrEdhRCp1aegoMqRaCZg"),
    ("Video", "BBC News", "https://www.youtube.com/feeds/videos.xml?channel_id=UC16niRr50-MSBwiO3YDb3RA"),
]
CATS = {"World": "বিশ্ব", "South Asia": "দক্ষিণ এশিয়া", "Business": "অর্থনীতি", "Tech": "প্রযুক্তি",
        "Science": "বিজ্ঞান", "Social": "সোশ্যাল মিডিয়া"}
PER_SECTION, N_TOP, N_MORE, N_VIDEOS = 8, 6, 8, 6
HN_URL = "https://hacker-news.firebaseio.com/v0/"
UA = {"User-Agent": "Mozilla/5.0 (personal-news-digest)"}
STOP = set("the a an and or of to in on for with at by from is are was be as it its this that after over into new says say will has have not but about than more".split())
DIG = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
DAYS = ["সোমবার", "মঙ্গলবার", "বুধবার", "বৃহস্পতিবার", "শুক্রবার", "শনিবার", "রবিবার"]
CACHE_FILE = "translations.json"
cache = json.load(open(CACHE_FILE, encoding="utf-8")) if os.path.exists(CACHE_FILE) else {}
used = {}

def get(url): return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20).read()
def tag(el): return el.tag.split("}")[-1]

def bn(text):
    """English -> Bangla (cached; falls back to English if translation fails)."""
    if not text: return ""
    if text in cache: used[text] = cache[text]; return cache[text]
    try:
        q = urllib.parse.urlencode({"client": "gtx", "sl": "auto", "tl": "bn", "dt": "t", "q": text})
        r = json.loads(get("https://translate.googleapis.com/translate_a/single?" + q))
        out = "".join(seg[0] for seg in r[0] if seg[0]); time.sleep(0.1)
    except Exception: return text
    cache[text] = used[text] = out
    return out

def shorten(s, n=320):
    if len(s) <= n: return s
    cut = s[:n]; end = cut.rfind(". ")
    return cut[:end + 1] if end > 120 else cut.rsplit(" ", 1)[0] + "…"

def fix(u): return ("https:" + u) if u and u.startswith("//") else u

def parse_feed(cat, source, url):
    out = []
    root = ET.fromstring(get(url))
    for rank, it in enumerate([e for e in root.iter() if tag(e) in ("item", "entry")][:25]):
        f = {"desc": "", "img": None, "video": None, "yt": None}
        for c in it:
            t = tag(c)
            if t == "link": f["link"] = f.get("link") or c.get("href") or (c.text or "").strip()
            elif t in ("title", "pubDate", "published", "updated", "date"): f.setdefault(t, (c.text or "").strip())
            elif t in ("description", "summary", "content"): f["desc"] = f["desc"] or (c.text or "")
            elif t == "videoId": f["yt"] = (c.text or "").strip()
        for c in it.iter():
            t, typ = tag(c), (c.get("type") or "") + (c.get("medium") or "")
            if t == "thumbnail" and not f["img"]: f["img"] = c.get("url")
            elif t in ("content", "enclosure") and c.get("url"):
                if "video" in typ and "youtube" not in c.get("url") and not f["video"]: f["video"] = c.get("url")
                elif "image" in typ and not f["img"]: f["img"] = c.get("url")
            elif t == "description" and c.text and not f["desc"]: f["desc"] = c.text
        raw = f["desc"]
        if not f["img"]:
            m = re.search(r'<img[^>]+src=["\']([^"\']+)', raw)
            f["img"] = m.group(1) if m else None
        s = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()
        if "submitted by" in s or cat == "Video" and False: s = ""
        ts = f.get("pubDate") or f.get("published") or f.get("updated") or f.get("date") or ""
        try: dt = parsedate_to_datetime(ts)
        except Exception:
            try: dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception: dt = datetime.now(timezone.utc)
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        if f.get("title") and f.get("link"):
            out.append(dict(cat=cat, src=source, title=html.unescape(f["title"]), url=f["link"], dt=dt, rank=rank, pts=0,
                            desc=s, img=fix(f["img"]), video=fix(f["video"]), yt=f["yt"]))
    return out

def hacker_news():
    out = []
    for r, i in enumerate(json.loads(get(HN_URL + "topstories.json"))[:15]):
        s = json.loads(get(f"{HN_URL}item/{i}.json"))
        if s and s.get("title"):
            out.append(dict(cat="Social", src="Hacker News", title=s["title"], dt=datetime.fromtimestamp(s["time"], timezone.utc),
                            url=s.get("url") or f"https://news.ycombinator.com/item?id={i}", rank=r, pts=s.get("score", 0),
                            desc="", img=None, video=None, yt=None))
    return out

def trends():
    """What people are searching for right now (Google Trends) - a good signal of what is spreading on social media."""
    out = []
    for geo in ("BD", "US"):
        root = ET.fromstring(get(f"https://trends.google.com/trending/rss?geo={geo}"))
        for it in [e for e in root.iter() if tag(e) == "item"][:8]:
            d = {"geo": geo, "term": "", "traffic": "", "nt": "", "nu": "", "ns": ""}
            for c in it.iter():
                t, x = tag(c), (c.text or "").strip()
                if t == "title" and not d["term"]: d["term"] = x
                elif t == "approx_traffic": d["traffic"] = x
                elif t == "news_item_title" and not d["nt"]: d["nt"] = html.unescape(x)
                elif t == "news_item_url" and not d["nu"]: d["nu"] = x
                elif t == "news_item_source" and not d["ns"]: d["ns"] = x
            if d["term"]: out.append(d)
    return out

def words(t): return {w for w in re.findall(r"[a-z0-9]+", t.lower()) if len(w) > 3 and w not in STOP}
E = html.escape

def media(it):
    if it.get("yt"):
        return f'<div class="vid"><iframe loading="lazy" allowfullscreen src="https://www.youtube-nocookie.com/embed/{E(it["yt"])}"></iframe></div>'
    if it.get("video"):
        poster = f' poster="{E(it["img"])}"' if it.get("img") else ""
        return f'<video controls preload="none"{poster} src="{E(it["video"])}"></video>'
    if it.get("img"):
        return f'<img loading="lazy" referrerpolicy="no-referrer" alt="" src="{E(it["img"])}">'
    return ""

def main():
    items, ok, bad = [], [], []
    for c, s, u in FEEDS:
        try: items += parse_feed(c, s, u); ok.append(s)
        except Exception: bad.append(s)
    try: items += hacker_news(); ok.append("Hacker News")
    except Exception: bad.append("Hacker News")
    try: trend_list = trends(); ok.append("Google Trends")
    except Exception: trend_list = []; bad.append("Google Trends")
    now = datetime.now(timezone.utc)
    items = [i for i in items if (now - i["dt"]).total_seconds() < 48 * 3600]
    videos_all = sorted([i for i in items if i["cat"] == "Video"], key=lambda i: i["dt"], reverse=True)
    news = [i for i in items if i["cat"] != "Video"]

    clusters = []
    for it in news:
        w = words(it["title"]); it["w"] = w
        for c in clusters:
            if len(w & c["w"]) / max(1, len(w | c["w"])) >= 0.4 and len(w & c["w"]) >= 2:
                c["items"].append(it); c["w"] |= w; break
        else: clusters.append({"w": set(w), "items": [it]})
    for c in clusters:
        srcs = {i["src"] for i in c["items"]}
        best = min(c["items"], key=lambda i: i["rank"])
        age_h = (now - best["dt"]).total_seconds() / 3600
        c["best"], c["srcs"] = best, sorted(srcs)
        c["desc"] = max((i["desc"] for i in c["items"]), key=len)
        c["media"] = next((i for i in sorted(c["items"], key=lambda i: i["rank"]) if i["yt"] or i["video"]), None) \
            or next((i for i in sorted(c["items"], key=lambda i: i["rank"]) if i["img"]), None)
        c["score"] = len(srcs) * 10 + 8 / (1 + best["rank"] * .4) + max(0, 12 - age_h) * .3 + min(best["pts"], 800) / 100
    clusters.sort(key=lambda c: -c["score"])

    def card(c, big=False):
        b, n = c["best"], len(c["srcs"])
        hrs = int((now - b["dt"]).total_seconds() // 3600)
        age = f"{hrs} ঘণ্টা আগে".translate(DIG) if hrs < 48 else "২ দিন আগে"
        outlets = f'<b class="multi">{n}টি সংবাদমাধ্যমে'.translate(DIG) + "</b>" if n > 1 else ""
        src = E(", ".join(c["srcs"][:3]))
        summ = f'<p class="sum">{E(bn(shorten(c["desc"])))}</p>' if c["desc"] else ""
        m = media(c["media"]) if c["media"] else ""
        en = f'<span class="en">{E(b["title"])}</span>' if big else ""
        return (f'<li class="{"big" if big else ""}"><div class="mm">{m}</div><div class="tx">'
                f'<a href="{E(b["url"])}" target="_blank" rel="noopener">{E(bn(b["title"]))}</a>{en}{summ}'
                f'<span class="m">{outlets}{src} · {age}</span></div></li>')

    top, more = clusters[:N_TOP], clusters[N_TOP:N_TOP + N_MORE]
    used_ids = {id(c) for c in top + more}
    sections = {k: [] for k in CATS}
    for c in clusters:
        k = c["best"]["cat"]
        if id(c) not in used_ids and len(sections[k]) < PER_SECTION: sections[k].append(c)

    glance = "".join(f"<li>{E(bn(c['best']['title']))}</li>" for c in top)
    top_html = "".join(card(c, True) for c in top)
    more_html = "".join(card(c) for c in more)
    sec_html = "".join(f'<section><h2>{CATS[k]}</h2><ol>{"".join(card(c) for c in v)}</ol></section>' for k, v in sections.items() if v)
    per, vids = {}, []
    for v in videos_all:
        if per.get(v["src"], 0) < 2 and len(vids) < N_VIDEOS: per[v["src"]] = per.get(v["src"], 0) + 1; vids.append(v)
    vid_html = "".join(f'<div class="vc">{media(v)}<a href="{E(v["url"])}" target="_blank" rel="noopener">{E(bn(v["title"]))}</a>'
                       f'<span class="m">{E(v["src"])}</span></div>' for v in vids)

    GEO = {"BD": "বাংলাদেশ", "US": "যুক্তরাষ্ট্র"}
    seen, tr_html = set(), ""
    for t in trend_list:
        if t["term"].lower() in seen: continue
        seen.add(t["term"].lower())
        link = (f'<a href="{E(t["nu"])}" target="_blank" rel="noopener">{E(bn(t["nt"]))}</a>'
                f'<span class="m">{E(t["ns"])}</span>') if t["nu"] else ""
        traf = f'{t["traffic"]} সার্চ · '.translate(DIG) if t["traffic"] else ""
        tr_html += f'<li><b>{E(bn(t["term"]))}</b><span class="m">{traf}{GEO[t["geo"]]}</span>{link}</li>'

    local = now + timedelta(hours=6)  # Bangladesh time
    stamp = f"{DAYS[local.weekday()]}, {local.strftime('%d/%m/%Y')} · সর্বশেষ আপডেট {local.strftime('%H:%M')}".translate(DIG)
    page = (TEMPLATE.replace("{{STAMP}}", stamp).replace("{{GLANCE}}", glance).replace("{{TRENDS}}", tr_html or "<li>আজ ট্রেন্ডিং তথ্য পাওয়া যায়নি।</li>").replace("{{TOP}}", top_html)
            .replace("{{MORE}}", more_html).replace("{{VIDEOS}}", vid_html or "<p>আজ কোনো ভিডিও পাওয়া যায়নি।</p>")
            .replace("{{SECTIONS}}", sec_html).replace("{{OK}}", str(len(ok)).translate(DIG))
            .replace("{{BAD}}", ", ".join(bad) or "নেই"))
    os.makedirs("docs", exist_ok=True)
    open("docs/index.html", "w", encoding="utf-8").write(page)
    json.dump(used, open(CACHE_FILE, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{len(news)} items, {len(clusters)} stories, {len(vids)} videos, ok={len(ok)} failed={bad}")

TEMPLATE = """<!doctype html><html lang="bn"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>আমার সকালের খবর</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Bengali:wght@400;600;700&family=Noto+Serif+Bengali:wght@700&display=swap" rel="stylesheet">
<style>
:root{--bg:#eef1f4;--ink:#16202b;--mute:#5d6b79;--line:#cdd5dd;--hi:#0a5fd1;--card:#fff;color-scheme:light}
@media(prefers-color-scheme:dark){:root{--bg:#10151b;--ink:#e6ebf0;--mute:#93a1b0;--line:#27313c;--hi:#6fb0ff;--card:#171e26;color-scheme:dark}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.6 "Noto Sans Bengali",system-ui,sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 18px 60px}
header{padding-bottom:14px;border-bottom:2px solid var(--ink);margin-bottom:22px}
h1{font:700 clamp(30px,6vw,50px)/1.25 "Noto Serif Bengali",Georgia,serif;margin:0}
.date{color:var(--mute);font-size:15px}
h2{font:700 22px/1.4 "Noto Serif Bengali",Georgia,serif;margin:0 0 10px;padding-bottom:6px;border-bottom:1px solid var(--line)}
.glance{background:var(--card);border-left:5px solid var(--hi);border-radius:6px;padding:12px 20px;margin-bottom:28px}
.glance ul{margin:6px 0 0;padding-left:20px}.glance li{padding:3px 0}
ol,.glance ul{margin-top:0}ol{list-style:none;margin:0;padding:0}
li{padding:12px 0;border-bottom:1px solid var(--line)}ol li:last-child{border:0}
ol li{display:flex;gap:14px;align-items:flex-start}
.mm{flex:0 0 140px}.mm:empty{display:none}.mm img,.mm video{width:100%;aspect-ratio:4/3;object-fit:cover;border-radius:6px;display:block;background:var(--line)}
.tx{flex:1;min-width:0}
a{color:var(--ink);text-decoration:none;font-weight:600}a:hover,a:focus-visible{color:var(--hi);text-decoration:underline}
.sum{margin:4px 0;color:var(--ink);font-size:15.5px;opacity:.92}
.en{display:block;font-size:13px;color:var(--mute);font-weight:400;font-family:system-ui,sans-serif}
.m{display:block;font-size:13px;color:var(--mute);margin-top:2px}.multi{color:var(--hi);margin-right:8px}
.top{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px 20px 8px;margin-bottom:30px}
.top ol{display:grid;grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:0 32px}
li.big{flex-direction:column}.big .mm{flex:none;width:100%}.big .mm img,.big .mm video{aspect-ratio:16/9}.big a{font-size:19px}
.tr{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:0 32px}.tr b{display:block;font-size:18px}.tr a{display:block;font-size:15px;margin-top:2px}
.vid{position:relative;aspect-ratio:16/9;border-radius:6px;overflow:hidden}.vid iframe{position:absolute;inset:0;width:100%;height:100%;border:0}
.vids{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px;margin-bottom:30px}.vc a{display:block;margin-top:6px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:28px 40px;margin-top:28px}
footer{margin-top:36px;color:var(--mute);font-size:13px}
@media(max-width:520px){.top ol{grid-template-columns:1fr}.mm{flex-basis:100px}}
</style></head><body><main>
<header><h1>আমার সকালের খবর</h1><div class="date">{{STAMP}}</div></header>
<div class="glance"><h2>আজকের এক নজরে</h2><ul>{{GLANCE}}</ul></div>
<section class="top"><h2>প্রধান খবর ও সারসংক্ষেপ</h2><ol>{{TOP}}</ol></section>
<section class="top"><h2>আরও গুরুত্বপূর্ণ খবর</h2><ol>{{MORE}}</ol></section>
<section class="top"><h2>সোশ্যাল মিডিয়ায় এখন যা ট্রেন্ডিং</h2><ul class="tr">{{TRENDS}}</ul></section>
<h2>আজকের ভিডিও</h2><div class="vids">{{VIDEOS}}</div>
<div class="grid">{{SECTIONS}}</div>
<footer>{{OK}}টি সূত্র থেকে খবর নেওয়া হয়েছে। আজ পাওয়া যায়নি: {{BAD}}। সব খবর স্বয়ংক্রিয়ভাবে বাংলায় অনুবাদ করা, তাই কিছু শব্দ নিখুঁত নাও হতে পারে; মূল খবর পড়তে শিরোনামে ক্লিক করুন।</footer>
</main></body></html>"""

if __name__ == "__main__": main()
