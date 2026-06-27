#!/usr/bin/env python3
"""
NexGen Caveman Content Engine
Runs daily via GitHub Actions — tells Charlie exactly what to record today.
Target: blue collar dads who think AI isn't for them. Body wearing out. No backup plan.
"""

import requests
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

# ─── CONFIG ───────────────────────────────────────────────────────────────────

SUBREDDITS = [
    'artificial', 'ChatGPT', 'technology', 'Futurology',
    'Construction', 'electricians', 'HVAC', 'Welding', 'Plumbing', 'carpentry', 'Truckers', 'BlueCollar',
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

# What your audience is actually searching and watching on YouTube
YOUTUBE_SEARCHES = [
    'AI tools for workers',
    'blue collar automation 2025',
    'ChatGPT real life use',
    'AI replace blue collar jobs',
    'working dad financial tips',
    'how to use AI to save money',
    'trade jobs and technology',
]

# ─── DATA FETCHING ────────────────────────────────────────────────────────────

def fetch_reddit(subreddits, limit=5):
    posts = []
    for sub in subreddits:
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
                for entry in root.findall('.//atom:entry', ns):
                    title_el = entry.find('atom:title', ns)
                    link_el = entry.find('atom:link', ns)
                    if title_el is None:
                        continue
                    title = (title_el.text or '').strip()
                    url_post = link_el.get('href', '') if link_el is not None else ''
                    if len(title) > 15:
                        posts.append({'title': title, 'url': url_post, 'subreddit': sub})
            time.sleep(0.5)
        except Exception as e:
            print(f"  Reddit r/{sub}: {e}")
    seen = set()
    unique = []
    for p in posts:
        if p['title'] not in seen:
            seen.add(p['title'])
            unique.append(p)
    return unique[:40]

def fetch_youtube():
    """
    Returns top-performing YouTube videos for Charlie's audience topics.
    Each video proves demand: real people searched for and watched this.
    That makes it a validated content idea, not a guess.
    """
    if not YOUTUBE_API_KEY:
        print("  YOUTUBE_API_KEY not set — skipping")
        return []
    videos = []
    seen_titles = set()
    for query in YOUTUBE_SEARCHES:
        try:
            r = requests.get(
                'https://www.googleapis.com/youtube/v3/search',
                params={
                    'part': 'snippet',
                    'q': query,
                    'type': 'video',
                    'order': 'viewCount',
                    'publishedAfter': '2024-06-01T00:00:00Z',
                    'maxResults': 3,
                    'relevanceLanguage': 'en',
                    'regionCode': 'US',
                    'key': YOUTUBE_API_KEY,
                },
                timeout=10,
            )
            if r.status_code == 200:
                for item in r.json().get('items', []):
                    title = item['snippet']['title']
                    if title in seen_titles:
                        continue
                    seen_titles.add(title)
                    vid_id = item['id']['videoId']
                    videos.append({
                        'title': title,
                        'channel': item['snippet']['channelTitle'],
                        'url': f"https://www.youtube.com/watch?v={vid_id}",
                        'query': query,
                    })
            time.sleep(0.3)
        except Exception as e:
            print(f"  YouTube '{query}': {e}")
    return videos[:12]


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
                rising = related[kw0]['rising']['query'].head(5).tolist()
        except:
            pass
        return {'trends': sorted(trends, key=lambda x: x['interest'], reverse=True), 'rising': rising}
    except Exception as e:
        print(f"  Trends error: {e}")
        return {'trends': [], 'rising': []}

# ─── RECOMMENDATION ENGINE ────────────────────────────────────────────────────

# Every topic is scored by how relevant it is to a blue collar dad
BLUE_COLLAR_SIGNALS = [
    'job', 'work', 'employ', 'laid off', 'fired', 'replace', 'automat', 'wage', 'pay', 'salary',
    'overtime', 'union', 'trade', 'skill', 'construction', 'electrician', 'hvac', 'weld', 'plumb',
    'truck', 'mechanic', 'physical', 'body', 'injur', 'money', 'debt', 'bill', 'financ', 'afford',
    'family', 'dad', 'father', 'kid', 'child', 'wife', 'mortgage', 'rent', 'insurance',
    'ai', 'chatgpt', 'robot', 'tech', 'automat', 'software', 'tool',
]

def relevance_score(title):
    t = title.lower()
    return sum(1 for s in BLUE_COLLAR_SIGNALS if s in t)

def classify_topic(title):
    t = title.lower()
    if any(w in t for w in ['job', 'employ', 'hired', 'fired', 'laid off', 'replac', 'automat', 'work']):
        return 'job_threat'
    if any(w in t for w in ['money', 'pay', 'wage', 'salary', 'debt', 'bill', 'financ', 'afford', 'cost', 'broke']):
        return 'money'
    if any(w in t for w in ['ai', 'chatgpt', 'robot', 'machine', 'tech', 'software', 'tool', 'gpt']):
        return 'ai_tool'
    if any(w in t for w in ['family', 'dad', 'father', 'kid', 'child', 'wife', 'parent']):
        return 'family'
    if any(w in t for w in ['health', 'body', 'injur', 'pain', 'doctor', 'medical', 'physic']):
        return 'body'
    return 'general'

# Maps each topic type to a proven hook pattern for Charlie's audience
HOOK_BY_TYPE = {
    'job_threat': [
        "They're not going to tell you this at work. But I will.",
        "I asked AI what jobs are gone in 5 years. The answer will piss you off.",
        "Your foreman knows this is coming. Your company knows. Do you?",
        "The guys who keep their jobs through this aren't the smartest. They're the most prepared.",
        "I'm not here to scare you. But if you're in the trades and you're not paying attention, someone else is.",
    ],
    'money': [
        "They write these things to confuse you on purpose. AI read it in 30 seconds.",
        "I gave AI my last three bills and asked it to find the overcharges. Watch what it found.",
        "You work too hard for them to take that much. Here's how AI helps you keep more of it.",
        "Your company has attorneys reviewing everything. You have Google. That's not a fair fight.",
        "I used AI to read a contract that was designed to screw my family. Here's what it found.",
    ],
    'ai_tool': [
        "I know you think this isn't for you. I thought the same thing.",
        "You've already used AI. You just didn't know what it could actually do for you.",
        "This isn't for tech guys. This is for guys who work and need things done.",
        "I'm going to show you one thing you can do with AI today that will save you an hour this week.",
        "Guys in the office are using this to do in 10 minutes what takes you a day. That's the problem.",
    ],
    'family': [
        "Everything I do is for them. That's why I started learning this.",
        "My kids aren't going to inherit my back problems. That's the whole point.",
        "Your family doesn't need you to be a tech guy. They need you to not be the last to know.",
        "I work with my hands. My backup plan is my brain. AI is how I'm building it.",
        "The scariest day isn't retirement. It's the day your body says stop before you're ready.",
    ],
    'body': [
        "Your body has a retirement date. AI doesn't. That's the whole conversation.",
        "I watched guys I know get hurt and have nothing to fall back on. I'm not doing that.",
        "You can't lift forever. You know that. What's the plan when you can't?",
        "The trades will always need guys. But the guys who last are the ones who work smarter.",
        "I started learning this because I don't want to be the guy who had no backup.",
    ],
    'general': [
        "Nobody's telling blue collar guys about this. Here's what you need to know.",
        "I'm just a guy who works with his hands. This is what I figured out.",
        "They built this for tech people. I'm showing you how to use it for real life.",
        "This took me 10 minutes to learn and it's already saved me more than that.",
        "If you're a working dad and you're not using AI yet, this is where you start.",
    ],
}

WHAT_TO_SHOW = {
    'job_threat': "Pull up a news article about it on your phone. Read one line out loud. Then say: \"Here's what that actually means for guys who work with their hands.\" No script needed — just react honestly.",
    'money': "Open ChatGPT on screen. Paste in a bill, a contract clause, or a fine print paragraph. Ask it to explain it like you're not a lawyer. Show the answer. That's the whole video.",
    'ai_tool': "Do one real thing with AI on camera. Don't explain it first — just do it, then explain what just happened. Guys need to see the result before they believe the tool is real.",
    'family': "Talk to the camera like you're talking to a buddy at a job site. No script. What does this mean for your family? Why does it matter to you personally? That's the whole video.",
    'body': "Talk directly to camera. What's your backup plan? When did you start thinking about it? Be honest. Guys in the trades feel this but nobody's saying it out loud — you saying it is the video.",
}

WHY_THIS_MATTERS = {
    'job_threat': "Blue collar workers are the most worried about AI replacing them — and the least informed about how to respond. That gap is your content.",
    'money': "Your audience is getting overcharged, underprotected, and confused by paperwork designed to confuse them. AI is the equalizer. That's your whole brand.",
    'ai_tool': "\"AI is not for guys like me\" is the #1 barrier your audience has. Every time you break that belief, you earn their trust and their follow.",
    'family': "Working dads don't want content about hustle or grinding. They want to protect what they've built. Lead with that and you own the room.",
    'body': "This is the core fear your audience won't say out loud. Body breaks down, no backup plan, family suffers. You naming it is the most powerful thing you can do.",
    'general': "This touches something your audience is already thinking about. Your job is to connect it to their real life — trades, family, money — in plain language.",
}

def build_recommendations(posts, trends_data, youtube_videos):
    # Score and sort reddit posts by relevance to blue collar dad
    scored = [(relevance_score(p['title']), p) for p in posts]
    scored.sort(key=lambda x: x[0], reverse=True)
    top_posts = [p for _, p in scored[:12]]

    # Pull in high-performing YouTube titles as topic candidates
    # If people are watching it, Charlie's audience wants it
    yt_topics = []
    for v in youtube_videos[:6]:
        yt_topics.append({'title': v['title'], 'url': v['url'], 'subreddit': f"YouTube · {v['channel']}"})

    # Pull in rising trend topics as additional candidates
    trend_topics = []
    if trends_data.get('rising'):
        for kw in trends_data['rising'][:4]:
            trend_topics.append({'title': kw, 'url': f"https://trends.google.com/trends/explore?q={kw.replace(' ','+')}&geo=US", 'subreddit': 'Google Trends'})

    # Combine — reddit (what they're saying) + youtube (what they're watching) + trends (what they're searching)
    candidates = top_posts + yt_topics + trend_topics

    # Fallback pool if Reddit blocked entirely
    fallback = [
        {'title': 'AI tools are replacing workers across major industries in 2025', 'url': 'https://reddit.com/r/technology', 'subreddit': 'Evergreen'},
        {'title': 'How to use ChatGPT to read a contract or legal document', 'url': 'https://reddit.com/r/ChatGPT', 'subreddit': 'Evergreen'},
        {'title': 'Blue collar workers: what skills are actually safe from automation?', 'url': 'https://reddit.com/r/BlueCollar', 'subreddit': 'Evergreen'},
        {'title': 'I was overcharged on my medical bill — here is how I fought back', 'url': 'https://reddit.com/r/personalfinance', 'subreddit': 'Evergreen'},
        {'title': 'What happens to working dads when their body gives out too early', 'url': 'https://reddit.com/r/Dads', 'subreddit': 'Evergreen'},
    ]
    if not candidates:
        candidates = fallback

    used_topics = set()
    used_hooks = set()
    recs = []

    for p in candidates:
        if len(recs) >= 3:
            break
        title = p['title']
        if title in used_topics:
            continue
        used_topics.add(title)

        topic_type = classify_topic(title)
        available_hooks = [h for h in HOOK_BY_TYPE[topic_type] if h not in used_hooks]
        if not available_hooks:
            available_hooks = HOOK_BY_TYPE[topic_type]
        hook = random.choice(available_hooks)
        used_hooks.add(hook)

        short_title = title if len(title) <= 75 else title[:72] + '...'
        source = p['subreddit']
        if source not in ('Google Trends', 'Evergreen'):
            source = f"r/{source}"

        recs.append({
            'n': len(recs) + 1,
            'title': short_title,
            'source': source,
            'topic_type': topic_type,
            'hook': hook,
            'what_to_show': WHAT_TO_SHOW[topic_type],
            'why': WHY_THIS_MATTERS[topic_type],
            'url': p['url'],
        })

    # If we got fewer than 3, fill from fallback
    if len(recs) < 3:
        for p in fallback:
            if len(recs) >= 3:
                break
            if p['title'] in used_topics:
                continue
            used_topics.add(p['title'])
            topic_type = classify_topic(p['title'])
            hook = random.choice(HOOK_BY_TYPE[topic_type])
            recs.append({
                'n': len(recs) + 1,
                'title': p['title'],
                'source': 'Evergreen Topic',
                'topic_type': topic_type,
                'hook': hook,
                'what_to_show': WHAT_TO_SHOW[topic_type],
                'why': WHY_THIS_MATTERS[topic_type],
                'url': p['url'],
            })

    return recs

# ─── HTML ─────────────────────────────────────────────────────────────────────

TYPE_LABELS = {
    'job_threat': 'JOB THREAT',
    'money': 'MONEY & FINE PRINT',
    'ai_tool': 'AI DEMO',
    'family': 'FAMILY PROTECTION',
    'body': 'BODY & BACKUP PLAN',
    'general': 'AUDIENCE INSIGHT',
}

def build_youtube_section(youtube_videos):
    if not youtube_videos:
        return ''
    rows = ''
    for v in youtube_videos[:8]:
        rows += f'''
<a href="{v['url']}" target="_blank" class="yt-row">
  <div class="yt-icon">&#9654;</div>
  <div>
    <div class="yt-title">{v['title']}</div>
    <div class="yt-meta">{v['channel']} &middot; searched: {v['query']}</div>
  </div>
</a>'''
    return f'''<div class="section-label">Proven demand — people are already watching this</div>
<div class="yt-note">These are real videos getting real views on topics your audience cares about. This is what demand looks like. Make your version.</div>
{rows}'''


def build_html(recs, trends_data, youtube_videos):
    now = datetime.now()
    date_str = now.strftime("%A, %B %d, %Y")
    time_str = now.strftime("%I:%M %p UTC")

    # Build trend strip separately to avoid backslash-in-f-string error
    if trends_data.get('trends'):
        pills = ''
        for t in trends_data['trends']:
            hot_class = ' hot' if t['interest'] > 5 else ''
            pills += f'<div class="trend-pill{hot_class}"><span class="kw">{t["keyword"]}</span><span class="score">{t["interest"]}</span></div>'
        trend_strip_section = f'<div class="section-label">Search volume this week</div><div class="trend-strip">{pills}</div>'
    else:
        trend_strip_section = ''

    # Top trend data for the "What your guys are searching" strip
    top_trend = trends_data['trends'][0] if trends_data.get('trends') else None
    top_trend_line = ''
    if top_trend:
        top_trend_line = f'<div class="pulse-bar">This week\'s top search from your audience: <strong>"{top_trend["keyword"]}"</strong> — interest score {top_trend["interest"]} out of 100. That\'s the temperature of your market right now.</div>'

    rising_line = ''
    if trends_data.get('rising'):
        keywords = ', '.join(f'"{k}"' for k in trends_data['rising'][:4])
        rising_line = f'<div class="pulse-bar" style="margin-top:10px">Rising searches this week: {keywords}. These are the words your audience is using — mirror them in your hooks.</div>'

    def rec_cards():
        out = ''
        for r in recs:
            type_label = TYPE_LABELS.get(r['topic_type'], 'TOPIC')
            out += f'''
<div class="rec-card">
  <div class="rec-header">
    <span class="rec-num">VIDEO {r['n']}</span>
    <span class="rec-type">{type_label}</span>
    <span class="rec-source">Source: {r['source']}</span>
  </div>
  <div class="rec-trigger">What's happening out there: <em>{r['title']}</em></div>
  <div class="rec-section">
    <div class="rec-label">OPEN WITH THIS</div>
    <div class="rec-hook">"{r['hook']}"</div>
  </div>
  <div class="rec-section">
    <div class="rec-label">WHAT TO DO ON CAMERA</div>
    <div class="rec-body">{r['what_to_show']}</div>
  </div>
  <div class="rec-section">
    <div class="rec-label">WHY THIS HITS FOR YOUR GUYS</div>
    <div class="rec-body rec-why">{r['why']}</div>
  </div>
  <div class="rec-section">
    <div class="rec-label">CLOSE EVERY VIDEO WITH</div>
    <div class="rec-body rec-close">"Follow for more — I built something free for guys like you. Link in bio."</div>
  </div>
  <a href="{r['url']}" target="_blank" class="rec-link">See what sparked this &rarr;</a>
</div>'''
        return out

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NexGen Content Engine</title>
<link href="https://fonts.googleapis.com/css2?family=Oswald:wght@400;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{{--bg:#0D0D0D;--s:#161616;--s2:#1e1e1e;--o:#E8700A;--od:rgba(232,112,10,0.10);--t:#e8e8e8;--m:#888;--b:#2a2a2a;--g:#2a3a1a;--go:#5a9a2a}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--t);font-family:'Inter',sans-serif;min-height:100vh}}
a{{color:inherit;text-decoration:none}}

.header{{background:var(--s);border-bottom:2px solid var(--o);padding:14px 20px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:99}}
.logo{{font-family:'Oswald',sans-serif;font-size:18px;font-weight:700}}.logo span{{color:var(--o)}}
.hdate{{font-size:12px;color:var(--m)}}
.badge{{background:var(--o);color:#fff;font-size:10px;font-weight:700;padding:3px 10px;border-radius:20px;letter-spacing:1px}}

.wrap{{max-width:820px;margin:0 auto;padding:28px 16px}}

.pulse-bar{{background:var(--s);border-left:3px solid var(--o);padding:12px 16px;border-radius:0 6px 6px 0;font-size:13px;color:#ccc;line-height:1.5}}
.pulse-bar strong{{color:var(--o)}}

.section-label{{font-family:'Oswald',sans-serif;font-size:11px;font-weight:600;color:var(--o);letter-spacing:2.5px;text-transform:uppercase;margin:36px 0 16px;display:flex;align-items:center;gap:10px}}
.section-label::after{{content:'';flex:1;height:1px;background:var(--b)}}

.rec-card{{background:var(--s);border:1px solid var(--b);border-radius:8px;padding:0;margin-bottom:20px;overflow:hidden}}
.rec-header{{display:flex;align-items:center;gap:10px;padding:12px 16px;background:var(--s2);border-bottom:1px solid var(--b);flex-wrap:wrap}}
.rec-num{{font-family:'Oswald',sans-serif;font-size:13px;font-weight:700;color:#fff;background:var(--o);padding:3px 10px;border-radius:20px}}
.rec-type{{font-family:'Oswald',sans-serif;font-size:11px;font-weight:600;color:var(--o);letter-spacing:1.5px;text-transform:uppercase}}
.rec-source{{font-size:11px;color:var(--m);margin-left:auto}}
.rec-trigger{{padding:14px 16px 10px;font-size:13px;color:var(--m);border-bottom:1px solid var(--b)}}
.rec-trigger em{{color:#bbb;font-style:normal}}

.rec-section{{padding:14px 16px;border-bottom:1px solid var(--b)}}
.rec-section:last-of-type{{border-bottom:none}}
.rec-label{{font-size:10px;font-weight:600;color:var(--o);letter-spacing:2px;text-transform:uppercase;margin-bottom:8px}}
.rec-hook{{font-size:17px;font-style:italic;line-height:1.5;background:var(--od);border-left:3px solid var(--o);padding:12px 14px;border-radius:0 4px 4px 0;color:#fff}}
.rec-body{{font-size:14px;color:#ccc;line-height:1.6}}
.rec-why{{color:#bbb;font-size:13px}}
.rec-close{{color:var(--m);font-size:13px;font-style:italic}}
.rec-link{{display:block;padding:10px 16px;font-size:12px;color:var(--o);background:var(--s2);border-top:1px solid var(--b)}}
.rec-link:hover{{text-decoration:underline}}

.trend-strip{{display:flex;gap:10px;flex-wrap:wrap;margin-top:16px}}
.trend-pill{{background:var(--s2);border:1px solid var(--b);border-radius:20px;padding:6px 14px;font-size:12px;display:flex;align-items:center;gap:8px}}
.trend-pill .kw{{color:var(--t)}}
.trend-pill .score{{color:var(--o);font-family:'Oswald',sans-serif;font-weight:700}}
.trend-pill.hot{{border-color:var(--o)}}

.yt-note{{font-size:13px;color:var(--m);margin-bottom:12px;line-height:1.5}}
.yt-row{{display:flex;align-items:flex-start;gap:12px;padding:11px 14px;background:var(--s);border:1px solid var(--b);border-radius:6px;margin-bottom:8px;transition:border-color 0.2s}}
.yt-row:hover{{border-color:#ff4444}}
.yt-icon{{font-size:16px;color:#ff4444;flex-shrink:0;padding-top:2px}}
.yt-title{{font-size:14px;line-height:1.4;margin-bottom:3px}}
.yt-meta{{font-size:11px;color:var(--m)}}

.footer{{text-align:center;padding:28px;font-size:12px;color:var(--m);border-top:1px solid var(--b);margin-top:16px}}

@media(max-width:600px){{.rec-hook{{font-size:15px}}.rec-header{{gap:6px}}}}
</style>
</head>
<body>

<div class="header">
  <div class="logo">NexGen <span>Content Engine</span></div>
  <div class="hdate">{date_str}</div>
  <div class="badge">DAILY</div>
</div>

<div class="wrap">

  <div class="section-label">What your audience is feeling right now</div>
  {top_trend_line}
  {rising_line}

  <div class="section-label">Record one of these today</div>
  {rec_cards()}

  {trend_strip_section}

  {build_youtube_section(youtube_videos)}

</div>

<div class="footer">
  NexGen Caveman Content Engine &middot; {date_str} at {time_str} &middot; Built for Charlie
</div>

</body>
</html>'''

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print("NexGen Content Engine starting...")

    print("Fetching Reddit...")
    posts = fetch_reddit(SUBREDDITS, limit=5)
    print(f"  {len(posts)} posts fetched")

    print("Fetching Google Trends...")
    trends = fetch_trends()
    print(f"  {len(trends.get('trends', []))} trend keywords, {len(trends.get('rising', []))} rising")

    print("Fetching YouTube...")
    youtube = fetch_youtube()
    print(f"  {len(youtube)} YouTube videos fetched")

    print("Building recommendations...")
    recs = build_recommendations(posts, trends, youtube)
    print(f"  {len(recs)} video recommendations built")

    print("Generating HTML...")
    html = build_html(recs, trends, youtube)

    os.makedirs('dashboard', exist_ok=True)
    with open('dashboard/index.html', 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Done. {len(recs)} recommendations generated.")

if __name__ == '__main__':
    main()
