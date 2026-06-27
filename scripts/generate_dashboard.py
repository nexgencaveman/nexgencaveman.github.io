#!/usr/bin/env python3
"""
NexGen Caveman Content Engine
Runs daily via GitHub Actions — generates a content dashboard for Charlie
"""

import requests
import json
import random
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime

try:
    from pytrends.request import TrendReq
    PYTRENDS_AVAILABLE = True
except ImportError:
    PYTRENDS_AVAILABLE = False

# ─── CONFIGURATION ────────────────────────────────────────────────────────────

SUBREDDITS = [
    # AI / Tech
    'artificial', 'ChatGPT', 'MachineLearning', 'technology', 'Futurology',
    # Blue Collar / Trades
    'Construction', 'electricians', 'HVAC', 'Welding', 'Plumbing', 'carpentry', 'Truckers', 'BlueCollar',
    # Dad / Family / Money
    'daddit', 'Dads', 'personalfinance', 'povertyfinance', 'antiwork', 'jobs', 'financialindependence',
]

TREND_KEYWORDS = [
    'AI tools',
    'artificial intelligence jobs',
    'blue collar automation',
    'ChatGPT work',
    'AI replace workers',
]

YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY', '')

YOUTUBE_SEARCHES = [
    'AI tools for workers 2025',
    'blue collar AI automation',
    'ChatGPT for regular people',
    'AI replace jobs blue collar',
    'working dad financial tips',
]

HOOK_TEMPLATES = [
    "Nobody's telling blue collar guys about [TOPIC]. Here's what you need to know.",
    "Your employer already knows [TOPIC] is coming. Do you?",
    "I used AI to deal with [TOPIC] — here's what happened.",
    "The tech bros don't want guys like us knowing about [TOPIC].",
    "[TOPIC] is real. Here's how a regular guy with dirty hands handles it.",
    "I asked AI about [TOPIC] so you don't have to figure it out yourself.",
    "Blue collar dads need to hear this about [TOPIC] — nobody else is saying it.",
    "While everyone else is panicking about [TOPIC], here's what I'm actually doing.",
    "They told me [TOPIC] wasn't for guys like me. They were wrong.",
    "My boss knows about [TOPIC]. Your boss does too. Do you?",
]

# ─── REDDIT (RSS fallback — works from GitHub Actions) ────────────────────────

def fetch_reddit(subreddits, limit=5):
    posts = []
    for sub in subreddits:
        # Use RSS feed — no auth needed, not blocked by AWS IPs
        try:
            url = f'https://www.reddit.com/r/{sub}/top.rss?t=week&limit={limit}'
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; NexGenCavemanBot/1.0)',
                'Accept': 'application/rss+xml, application/xml, text/xml',
            }
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code == 200:
                root = ET.fromstring(r.content)
                ns = {'atom': 'http://www.w3.org/2005/Atom'}
                entries = root.findall('.//atom:entry', ns)
                for entry in entries[:limit]:
                    title_el = entry.find('atom:title', ns)
                    link_el = entry.find('atom:link', ns)
                    content_el = entry.find('atom:content', ns)
                    if title_el is None:
                        continue
                    title = title_el.text or ''
                    url_post = link_el.get('href', '') if link_el is not None else ''
                    # Parse upvotes from content if available
                    score = 100  # RSS doesn't give scores, use placeholder
                    posts.append({
                        'title': title,
                        'score': score,
                        'comments': 0,
                        'url': url_post,
                        'subreddit': sub,
                    })
            time.sleep(0.5)
        except Exception as e:
            print(f"  Reddit r/{sub} RSS: {e}")
            # Try JSON API as fallback
            try:
                url2 = f'https://www.reddit.com/r/{sub}/top.json?t=week&limit={limit}'
                headers2 = {'User-Agent': 'NexGenCavemanBot/1.0'}
                r2 = requests.get(url2, headers=headers2, timeout=10)
                if r2.status_code == 200:
                    for item in r2.json().get('data', {}).get('children', []):
                        p = item['data']
                        posts.append({
                            'title': p['title'],
                            'score': p.get('score', 100),
                            'comments': p.get('num_comments', 0),
                            'url': f"https://reddit.com{p['permalink']}",
                            'subreddit': sub,
                        })
            except Exception as e2:
                print(f"  Reddit r/{sub} JSON also failed: {e2}")
    # Deduplicate by title
    seen = set()
    unique = []
    for p in posts:
        if p['title'] not in seen and len(p['title']) > 10:
            seen.add(p['title'])
            unique.append(p)
    return unique[:30]

# ─── YOUTUBE ──────────────────────────────────────────────────────────────────

def fetch_youtube(searches):
    if not YOUTUBE_API_KEY:
        print("  YouTube API key not set — skipping")
        return []
    videos = []
    for query in searches[:3]:
        try:
            url = 'https://www.googleapis.com/youtube/v3/search'
            params = {
                'part': 'snippet',
                'q': query,
                'type': 'video',
                'order': 'viewCount',
                'publishedAfter': '2025-01-01T00:00:00Z',
                'maxResults': 3,
                'key': YOUTUBE_API_KEY,
            }
            r = requests.get(url, params=params, timeout=10)
            if r.status_code == 200:
                for item in r.json().get('items', []):
                    snippet = item['snippet']
                    vid_id = item['id']['videoId']
                    videos.append({
                        'title': snippet['title'],
                        'channel': snippet['channelTitle'],
                        'url': f"https://www.youtube.com/watch?v={vid_id}",
                        'query': query,
                    })
            time.sleep(0.3)
        except Exception as e:
            print(f"  YouTube search '{query}': {e}")
    return videos

# ─── GOOGLE TRENDS ────────────────────────────────────────────────────────────

def fetch_trends():
    if not PYTRENDS_AVAILABLE:
        return {'trends': [], 'rising': []}
    try:
        pt = TrendReq(hl='en-US', tz=300)
        pt.build_payload(TREND_KEYWORDS[:5], timeframe='now 7-d', geo='US')
        df = pt.interest_over_time()
        trends = []
        if not df.empty:
            for kw in TREND_KEYWORDS[:5]:
                if kw in df.columns:
                    trends.append({'keyword': kw, 'interest': round(float(df[kw].mean()), 1)})
        rising = []
        try:
            related = pt.related_queries()
            kw0 = TREND_KEYWORDS[0]
            if kw0 in related and related[kw0]['rising'] is not None:
                rising = related[kw0]['rising']['query'].head(6).tolist()
        except:
            pass
        return {'trends': sorted(trends, key=lambda x: x['interest'], reverse=True), 'rising': rising}
    except Exception as e:
        print(f"  Trends error: {e}")
        return {'trends': [], 'rising': []}

# ─── CARD GENERATION ──────────────────────────────────────────────────────────

def spin(topic):
    t = topic.lower()
    if any(w in t for w in ['job', 'work', 'employ', 'laid', 'fired', 'replac', 'automat']):
        return "Frame it as: guys who use AI stay employed longer. Your competition isn't AI — it's the guy next to you who's already using it."
    elif any(w in t for w in ['money', 'financ', 'cost', 'debt', 'pay', 'wage', 'salary', 'bill']):
        return "Frame it as: AI reads the fine print they're hiding from you. Your family deserves to keep more of what you earn."
    elif any(w in t for w in ['ai', 'chatgpt', 'robot', 'machine', 'tech', 'software']):
        return "Frame it as: this isn't for tech guys. It's a tool — like your impact driver. You just need to know how to use it."
    elif any(w in t for w in ['health', 'body', 'injur', 'pain', 'doctor', 'medical']):
        return "Frame it as: your body has a retirement date. AI doesn't. Start building your backup before your body forces you to."
    elif any(w in t for w in ['family', 'dad', 'kid', 'child', 'wife', 'father']):
        return "Frame it as: everything you do is for them. AI buys you more time and protects what you've built."
    elif any(w in t for w in ['school', 'degree', 'college', 'education', 'learn']):
        return "Frame it as: you don't need a degree to use AI. You need the right questions. That's it."
    else:
        return "Frame it as: guys like us aren't supposed to know this. That's exactly why you need to."

def build_cards(posts, trends_data):
    cards = []
    topics = []

    for p in posts[:8]:
        title = p['title'] if len(p['title']) <= 70 else p['title'][:67] + '...'
        detail = f"{p['score']:,} upvotes" if p['comments'] == 0 else f"{p['score']:,} upvotes · {p['comments']:,} comments"
        topics.append({'topic': title, 'source': f"r/{p['subreddit']}", 'detail': detail, 'url': p['url']})

    if trends_data.get('rising'):
        for kw in trends_data['rising'][:3]:
            topics.append({'topic': kw, 'source': 'Google Trends', 'detail': 'Rising search this week', 'url': f"https://trends.google.com/trends/explore?q={kw.replace(' ','+')}&geo=US"})

    # Fallback: use main trend keywords if still no topics
    if not topics and trends_data.get('trends'):
        for t in trends_data['trends'][:5]:
            topics.append({'topic': t['keyword'], 'source': 'Google Trends', 'detail': f"Interest score: {t['interest']}", 'url': f"https://trends.google.com/trends/explore?q={t['keyword'].replace(' ','+')}&geo=US"})

    # Last resort fallback topics so cards are never empty
    if not topics:
        fallback_topics = [
            ("AI tools for blue collar workers", "https://www.reddit.com/r/artificial/top"),
            ("How ChatGPT is changing trade jobs", "https://www.reddit.com/r/ChatGPT/top"),
            ("Automation and the skilled trades", "https://www.reddit.com/r/BlueCollar/top"),
            ("Financial tips for working dads", "https://www.reddit.com/r/personalfinance/top"),
            ("AI replacing workers — what's real", "https://www.reddit.com/r/technology/top"),
        ]
        for title, url in fallback_topics:
            topics.append({'topic': title, 'source': 'Evergreen Topic', 'detail': 'Always relevant to your audience', 'url': url})

    used_hooks = []
    for i, t in enumerate(topics[:5]):
        available = [h for h in HOOK_TEMPLATES if h not in used_hooks]
        hook = random.choice(available)
        used_hooks.append(hook)
        hook_text = hook.replace('[TOPIC]', t['topic'].lower().rstrip('.').rstrip('?'))
        cards.append({
            'n': i + 1,
            'topic': t['topic'],
            'hook': hook_text,
            'angle': spin(t['topic']),
            'source': t['source'],
            'detail': t['detail'],
            'url': t['url'],
        })
    return cards

# ─── HTML ─────────────────────────────────────────────────────────────────────

def build_html(cards, posts, trends_data, youtube_videos):
    now = datetime.now()
    date_str = now.strftime("%A, %B %d, %Y")
    time_str = now.strftime("%I:%M %p UTC")

    def cards_html():
        if not cards:
            return '<div class="muted" style="font-size:13px;padding:12px">No topics today — check back tomorrow.</div>'
        out = ''
        for c in cards:
            out += f'''
<div class="card">
  <div class="card-num">#{c['n']}</div>
  <div class="card-source">{c['source']} &middot; {c['detail']}</div>
  <div class="card-topic">{c['topic']}</div>
  <div class="card-block">
    <div class="label">HOOK — say this first</div>
    <div class="hook">&ldquo;{c['hook']}&rdquo;</div>
  </div>
  <div class="card-block">
    <div class="label">YOUR ANGLE</div>
    <div class="body">{c['angle']}</div>
  </div>
  <div class="card-block">
    <div class="label">CLOSE WITH</div>
    <div class="body muted">Follow for more — I built something free for guys like you. Link in bio.</div>
  </div>
  <a href="{c['url']}" target="_blank" class="src-link">View source &rarr;</a>
</div>'''
        return out

    def trending_html():
        if not posts:
            return '<div class="muted" style="font-size:13px;padding:12px">Reddit data unavailable today.</div>'
        out = ''
        for p in posts[:10]:
            score_display = f"{p['score']:,}" if p['score'] != 100 else '▲'
            meta = f"r/{p['subreddit']}"
            if p['comments']:
                meta += f" &middot; {p['comments']:,} comments"
            out += f'''
<a href="{p['url']}" target="_blank" class="trend-row">
  <div class="trend-score">{score_display}</div>
  <div>
    <div class="trend-title">{p['title']}</div>
    <div class="trend-meta">{meta}</div>
  </div>
</a>'''
        return out

    def youtube_html():
        if not youtube_videos:
            return '<div class="muted" style="font-size:13px;padding:12px">Add YOUTUBE_API_KEY as a GitHub secret to enable YouTube research.</div>'
        out = ''
        for v in youtube_videos[:6]:
            out += f'''
<a href="{v['url']}" target="_blank" class="trend-row">
  <div class="trend-score" style="color:#ff4444;min-width:42px">&#9654;</div>
  <div>
    <div class="trend-title">{v['title']}</div>
    <div class="trend-meta">{v['channel']} &middot; Search: {v['query']}</div>
  </div>
</a>'''
        return out

    def gtrends_html():
        if not trends_data.get('trends'):
            return '<div class="muted" style="font-size:13px">Google Trends data unavailable — check back tomorrow.</div>'
        out = ''
        for t in trends_data['trends']:
            w = min(100, int(t['interest']))
            out += f'''
<div class="grow">
  <div class="gkw">{t['keyword']}</div>
  <div class="gbar-bg"><div class="gbar" style="width:{w}%"></div></div>
  <div class="gscore">{t['interest']}</div>
</div>'''
        return out

    def rising_html():
        if not trends_data.get('rising'):
            return ''
        out = ''
        for kw in trends_data['rising']:
            out += f'<span class="tag">{kw}</span>'
        return out

    yt_section = ''
    if youtube_videos or not YOUTUBE_API_KEY:
        yt_section = f'''
  <div class="sec">
    <div class="sec-title">What's Getting Views on YouTube</div>
    {youtube_html()}
  </div>'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NexGen Content Engine</title>
<link href="https://fonts.googleapis.com/css2?family=Oswald:wght@400;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{{--bg:#0D0D0D;--s:#161616;--s2:#1e1e1e;--o:#E8700A;--od:rgba(232,112,10,0.12);--t:#e8e8e8;--m:#888;--b:#2a2a2a}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--t);font-family:'Inter',sans-serif;min-height:100vh}}
a{{color:inherit;text-decoration:none}}

.header{{background:var(--s);border-bottom:1px solid var(--b);padding:14px 20px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:99}}
.logo{{font-family:'Oswald',sans-serif;font-size:18px;font-weight:700}}.logo span{{color:var(--o)}}
.hdate{{font-size:12px;color:var(--m)}}
.badge{{background:var(--o);color:#fff;font-size:10px;font-weight:700;padding:3px 10px;border-radius:20px;letter-spacing:1px}}

.wrap{{max-width:860px;margin:0 auto;padding:24px 16px}}
.sec{{margin-bottom:40px}}
.sec-title{{font-family:'Oswald',sans-serif;font-size:12px;font-weight:600;color:var(--o);letter-spacing:2px;text-transform:uppercase;margin-bottom:16px;display:flex;align-items:center;gap:10px}}
.sec-title::after{{content:'';flex:1;height:1px;background:var(--b)}}

.card{{background:var(--s);border:1px solid var(--b);border-left:3px solid var(--o);border-radius:6px;padding:20px;margin-bottom:14px;position:relative}}
.card-num{{position:absolute;top:-11px;left:14px;background:var(--o);color:#fff;font-family:'Oswald',sans-serif;font-size:12px;font-weight:700;padding:2px 10px;border-radius:20px}}
.card-source{{font-size:11px;color:var(--m);letter-spacing:1px;text-transform:uppercase;margin-top:8px;margin-bottom:10px}}
.card-topic{{font-family:'Oswald',sans-serif;font-size:19px;font-weight:600;line-height:1.3;margin-bottom:16px}}
.card-block{{margin-bottom:12px}}
.label{{font-size:10px;font-weight:600;color:var(--o);letter-spacing:2px;text-transform:uppercase;margin-bottom:6px}}
.hook{{font-size:15px;font-style:italic;line-height:1.5;background:var(--od);padding:12px;border-radius:4px}}
.body{{font-size:14px;color:#ccc;line-height:1.5}}
.muted{{color:var(--m)}}
.src-link{{display:inline-block;margin-top:10px;font-size:12px;color:var(--o)}}
.src-link:hover{{text-decoration:underline}}

.trend-row{{display:flex;align-items:flex-start;gap:14px;padding:12px;background:var(--s);border:1px solid var(--b);border-radius:6px;margin-bottom:8px;transition:border-color 0.2s}}
.trend-row:hover{{border-color:var(--o)}}
.trend-score{{font-family:'Oswald',sans-serif;font-size:15px;font-weight:700;color:var(--o);min-width:52px;text-align:right;flex-shrink:0}}
.trend-title{{font-size:14px;line-height:1.4;margin-bottom:3px}}
.trend-meta{{font-size:11px;color:var(--m)}}

.grow{{display:flex;align-items:center;gap:12px;margin-bottom:10px}}
.gkw{{font-size:13px;min-width:160px;color:var(--t)}}
.gbar-bg{{flex:1;background:var(--s2);border-radius:2px;height:6px}}
.gbar{{background:var(--o);height:6px;border-radius:2px}}
.gscore{{font-size:12px;color:var(--m);min-width:28px;text-align:right}}

.tags{{display:flex;flex-wrap:wrap;gap:8px}}
.tag{{background:var(--od);border:1px solid var(--o);color:var(--o);font-size:12px;padding:4px 12px;border-radius:20px}}

.influencer-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}}
.inf-card{{background:var(--s);border:1px solid var(--b);border-radius:6px;padding:14px}}
.inf-name{{font-family:'Oswald',sans-serif;font-size:15px;font-weight:600;margin-bottom:4px}}
.inf-niche{{font-size:12px;color:var(--o);margin-bottom:8px}}
.inf-tip{{font-size:12px;color:var(--m);line-height:1.4}}

.footer{{text-align:center;padding:24px;font-size:12px;color:var(--m);border-top:1px solid var(--b);margin-top:20px}}

@media(max-width:600px){{.gkw{{min-width:110px;font-size:12px}}.card-topic{{font-size:16px}}.influencer-grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body>

<div class="header">
  <div class="logo">NexGen <span>Content Engine</span></div>
  <div class="hdate">{date_str}</div>
  <div class="badge">DAILY</div>
</div>

<div class="wrap">

  <div class="sec">
    <div class="sec-title">Record This Now</div>
    {cards_html()}
  </div>

  <div class="sec">
    <div class="sec-title">Trending In Your Space This Week</div>
    {trending_html()}
  </div>

  {yt_section}

  <div class="sec">
    <div class="sec-title">AI &amp; Work — Google Trends</div>
    {gtrends_html()}
  </div>

  {'<div class="sec"><div class="sec-title">Rising Searches This Week</div><div class="tags">' + rising_html() + '</div></div>' if trends_data.get('rising') else ''}

  <div class="sec">
    <div class="sec-title">Adjacent Influencers — Watch These</div>
    <div class="influencer-grid">
      <div class="inf-card"><div class="inf-name">AI Educators</div><div class="inf-niche">AI for regular people</div><div class="inf-tip">Search YouTube: "AI tools for beginners 2025" — watch what hooks they open with and steal the angle, not the content.</div></div>
      <div class="inf-card"><div class="inf-name">Blue Collar Creators</div><div class="inf-niche">Trades &amp; skilled work</div><div class="inf-tip">Search: "blue collar success story" on TikTok. Note what comment sections are saying — those are your hooks.</div></div>
      <div class="inf-card"><div class="inf-name">Dad Content</div><div class="inf-niche">Fatherhood &amp; family</div><div class="inf-tip">Search: "working dad advice" on YouTube. Highest view counts tell you exactly what resonates with your audience.</div></div>
      <div class="inf-card"><div class="inf-name">Personal Finance</div><div class="inf-niche">Money stress &amp; bills</div><div class="inf-tip">Search: "how to negotiate bills" or "reading your paycheck" — these are AI use cases your audience desperately needs.</div></div>
      <div class="inf-card"><div class="inf-name">Anti-Work / Hustle</div><div class="inf-niche">Job frustration content</div><div class="inf-tip">r/antiwork top posts show exactly what blue collar workers are angry about. That anger is your content fuel.</div></div>
    </div>
  </div>

</div>

<div class="footer">
  NexGen Caveman Content Engine &middot; Updated {date_str} at {time_str} &middot; Built for Charlie
</div>

</body>
</html>'''

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print("NexGen Content Engine starting...")

    print("Fetching Reddit (RSS)...")
    posts = fetch_reddit(SUBREDDITS, limit=5)
    print(f"  {len(posts)} posts fetched")

    print("Fetching Google Trends...")
    trends = fetch_trends()
    print(f"  {len(trends.get('trends', []))} trend keywords, {len(trends.get('rising', []))} rising")

    print("Fetching YouTube...")
    youtube = fetch_youtube(YOUTUBE_SEARCHES)
    print(f"  {len(youtube)} YouTube videos fetched")

    print("Building content cards...")
    cards = build_cards(posts, trends)
    print(f"  {len(cards)} cards generated")

    print("Generating HTML...")
    html = build_html(cards, posts, trends, youtube)

    os.makedirs('dashboard', exist_ok=True)
    with open('dashboard/index.html', 'w', encoding='utf-8') as f:
        f.write(html)

    print("Done. dashboard/index.html generated.")

if __name__ == '__main__':
    main()
