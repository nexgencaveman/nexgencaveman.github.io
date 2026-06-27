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
    # Trades & blue collar — primary audience
    'Construction', 'electricians', 'HVAC', 'Welding', 'Plumbing', 'carpentry',
    'Truckers', 'BlueCollar', 'tradeswork', 'manufacturing',
    # Working dads & family stress
    'daddit', 'Dads', 'workingdads',
    # Money stress — paycheck to paycheck, not investing
    'personalfinance', 'povertyfinance', 'Frugal', 'survivinginflatoin',
    # Job fear & frustration
    'antiwork', 'jobs', 'layoffs', 'Unemployed',
    # AI topics written for regular people, not developers
    'ChatGPT', 'artificial',
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
    'AI tools for blue collar workers',
    'trades jobs automation threat 2025',
    'working dad struggling financially',
    'how to use ChatGPT to save money',
    'AI replacing electrician plumber construction',
    'blue collar dad financial tips',
    'how regular people use AI',
    'what happens when you cant work anymore trades',
    'electrician plumber HVAC AI automation',
    'truck driver automation job loss',
    'working class AI tools real life',
    'dad working paycheck to paycheck advice',
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
                    'maxResults': 5,
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
    return videos[:20]


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

# Topics that belong to office workers, developers, or startup culture — reject these
OFFICE_GUY_FILTERS = [
    'developer', 'software engineer', 'coder', 'coding', 'programmer', 'programming',
    'startup', 'founder', 'venture', 'vc ', 'saas', 'api ', 'llm', 'model weights',
    'open source', 'github', 'pull request', 'machine learning', 'neural network',
    'data science', 'prompt engineering', 'fine-tun', 'training data',
    'white collar', 'remote work', 'work from home', 'wfh', 'corporate ladder',
    'stock options', 'equity', 'ipo', 'crypto', 'nft', 'web3', 'blockchain',
    'mba', 'linkedin', 'networking event', 'conference', 'keynote',
]

def is_office_content(title):
    t = title.lower()
    return any(w in t for w in OFFICE_GUY_FILTERS)

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
    'job_threat': "Look straight at the camera. Say the hook. Then tell them what you actually think is happening — not what the news says, what YOU think. End with: \"Nobody's preparing for this. I am. Follow and I'll show you how.\" One take. Raw is better.",
    'money': "Look straight at the camera. Tell them about a time you got hit with a bill, a clause, or fine print that felt designed to screw you. Then tell them AI is the thing that evens that fight. You don't need to show anything — your face and your words are the video.",
    'ai_tool': "Look straight at the camera. Tell them one specific thing AI did for you — saved you time, explained something confusing, handled something you dreaded. Keep it real and short. \"I'm not a tech guy. Here's what I did.\" That's it.",
    'family': "Look straight at the camera. Talk like you're telling your brother something important. What does this mean for your kids, your wife, your future? Why does a working dad need to care about this? Honest and direct. No script.",
    'body': "Look straight at the camera. Ask them: \"What's your plan B?\" Pause. Let it sit. Then tell them yours. This is the video that hits hardest because nobody else in this space is saying it out loud.",
    'general': "Look straight at the camera. React to this topic like you're talking to a guy on the job site who hasn't heard about it yet. What does it mean? Why should he care? Keep it under 60 seconds.",
}

SOURCE_EXPLAIN = {
    'Reddit': "This topic is actively being discussed on Reddit right now — meaning real people in your audience are thinking about it this week, not last month.",
    'Google Trends': "This is a rising search term in the US this week — meaning your audience is actively typing this into Google and looking for answers.",
    'YouTube': "Real videos on this topic are getting views right now — meaning demand is proven. People are already watching this content.",
    'Evergreen': "This topic consistently resonates with blue collar dads regardless of the news cycle. It never stops being relevant to your audience.",
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
    for v in youtube_videos[:15]:
        yt_topics.append({'title': v['title'], 'url': v['url'], 'subreddit': f"YouTube · {v['channel']}"})

    # Pull in rising trend topics as additional candidates
    trend_topics = []
    if trends_data.get('rising'):
        for kw in trends_data['rising'][:4]:
            trend_topics.append({'title': kw, 'url': f"https://trends.google.com/trends/explore?q={kw.replace(' ','+')}&geo=US", 'subreddit': 'Google Trends'})

    # Priority: YouTube first (proven views = proven demand), then trends, then Reddit as backup
    candidates = yt_topics + trend_topics + top_posts

    # Fallback pool — always blue collar dad, always on-target
    fallback = [
        {'title': 'Tradesmen: what happens to your income when your body breaks down?', 'url': 'https://reddit.com/r/BlueCollar', 'subreddit': 'Evergreen'},
        {'title': 'AI is coming for overtime — what blue collar workers need to know now', 'url': 'https://reddit.com/r/antiwork', 'subreddit': 'Evergreen'},
        {'title': 'Working dad living paycheck to paycheck — what actually changes things', 'url': 'https://reddit.com/r/povertyfinance', 'subreddit': 'Evergreen'},
        {'title': 'Construction and trades workers on automation: what are you actually worried about?', 'url': 'https://reddit.com/r/Construction', 'subreddit': 'Evergreen'},
        {'title': 'How do you explain to your kids why you work so much and still struggle', 'url': 'https://reddit.com/r/daddit', 'subreddit': 'Evergreen'},
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
        # Hard reject — office/developer content has no place here
        if is_office_content(title):
            print(f"  Filtered (office content): {title[:60]}")
            continue
        used_topics.add(title)

        topic_type = classify_topic(title)
        available_hooks = [h for h in HOOK_BY_TYPE[topic_type] if h not in used_hooks]
        if not available_hooks:
            available_hooks = HOOK_BY_TYPE[topic_type]
        hook = random.choice(available_hooks)
        used_hooks.add(hook)

        short_title = title if len(title) <= 75 else title[:72] + '...'
        raw_source = p['subreddit']
        if 'YouTube' in raw_source:
            src_key = 'YouTube'
            source = raw_source
        elif raw_source == 'Google Trends':
            src_key = 'Google Trends'
            source = 'Google Trends'
        elif raw_source == 'Evergreen':
            src_key = 'Evergreen'
            source = 'Evergreen Topic'
        else:
            src_key = 'Reddit'
            source = f"r/{raw_source}"

        recs.append({
            'n': len(recs) + 1,
            'title': short_title,
            'source': source,
            'src_key': src_key,
            'topic_type': topic_type,
            'hook': hook,
            'what_to_show': WHAT_TO_SHOW[topic_type],
            'why': WHY_THIS_MATTERS[topic_type],
            'src_explain': SOURCE_EXPLAIN[src_key],
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
                'src_key': 'Evergreen',
                'topic_type': topic_type,
                'hook': hook,
                'what_to_show': WHAT_TO_SHOW[topic_type],
                'why': WHY_THIS_MATTERS[topic_type],
                'src_explain': SOURCE_EXPLAIN['Evergreen'],
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
    <span class="rec-source">{r['source']}</span>
  </div>
  <div class="rec-trigger">
    <strong>What sparked this:</strong> <em>{r['title']}</em>
    <div class="rec-src-explain">{r['src_explain']}</div>
  </div>
  <div class="rec-section">
    <div class="rec-label">OPEN WITH THIS — say it straight to camera</div>
    <div class="rec-hook">"{r['hook']}"</div>
  </div>
  <div class="rec-section">
    <div class="rec-label">HOW TO DO IT — talking head, no screen needed</div>
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
  <a href="{r['url']}" target="_blank" class="rec-link">See what sparked this recommendation &rarr;</a>
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

.rec-src-explain{{font-size:12px;color:var(--m);margin-top:6px;line-height:1.5;font-style:normal}}
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

  <div class="section-label">How this works</div>
  <div class="pulse-bar">Every day this tool pulls from three sources: <strong>Reddit</strong> (what your audience is actually saying right now), <strong>Google Trends</strong> (what they're searching for), and <strong>YouTube</strong> (what's already getting views in your space). It scores every topic by how relevant it is to a blue collar dad — job security, money, family, AI, body breaking down. The top 3 become your video recommendations. Every card shows you exactly where the data came from and why that topic was chosen.</div>

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
