#!/usr/bin/env python3
"""Bake index.template.html → index.html with dynamic values."""
import os, re, json, datetime, urllib.request, urllib.parse
from xml.etree import ElementTree as ET

CAREER_START = datetime.date.fromisoformat(os.environ['CAREER_START'])
AXA_HIRE     = datetime.date.fromisoformat(os.environ['AXA_HIRE'])
GH_USER      = os.environ['GH_USER']
MEDIUM_HANDLE = os.environ['MEDIUM_HANDLE']
GH_TOKEN     = os.environ.get('GH_TOKEN', '')
TODAY        = datetime.date.today()

BROWSER_UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

def years_plus(start):
    years = (TODAY - start).days / 365.25
    return f'{int(years)}+'

def http_get(url, headers=None):
    h = {'User-Agent': BROWSER_UA, 'Accept': '*/*'}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    return urllib.request.urlopen(req, timeout=30).read()

def gh_api(path):
    h = {'Accept': 'application/vnd.github+json'}
    if GH_TOKEN:
        h['Authorization'] = f'Bearer {GH_TOKEN}'
    return json.loads(http_get(f'https://api.github.com{path}', h))

# ---- Compute time-based tokens ----
years_exp = years_plus(CAREER_START)
years_axa = years_plus(AXA_HIRE)

# ---- GitHub stats ----
repos = gh_api(f'/users/{GH_USER}/repos?per_page=100&type=public')
own = [r for r in repos if not r['fork']]
public_repos = len(own)
total_stars = sum(r['stargazers_count'] for r in own)
latest_iso = max((r['pushed_at'] for r in own), default=None)

def relative_time(iso_z):
    if not iso_z:
        return 'unknown'
    dt = datetime.datetime.fromisoformat(iso_z.replace('Z', '+00:00'))
    delta = datetime.datetime.now(datetime.timezone.utc) - dt
    days = delta.days
    if days == 0:
        hours = delta.seconds // 3600
        return f'{hours}h ago' if hours > 0 else 'just now'
    if days < 30:
        return f'{days}d ago'
    if days < 365:
        return f'{days // 30}mo ago'
    return f'{days // 365}y ago'

gh_latest_push_rel = relative_time(latest_iso)

# ---- Medium RSS — primary fetch + rss2json fallback ----
def fetch_medium_items():
    """Try direct RSS first; fall back to rss2json.com if Medium 403s the runner IP."""
    feed_url = f'https://medium.com/feed/@{MEDIUM_HANDLE}'
    # Attempt 1: direct
    try:
        xml = http_get(feed_url)
        root = ET.fromstring(xml)
        items = []
        for item in root.findall('.//item')[:5]:
            items.append({
                'title': (item.findtext('title') or '').strip(),
                'link': (item.findtext('link') or '').split('?')[0],
            })
        if items:
            print(f'  Medium fetched directly: {len(items)} items')
            return items
    except Exception as e:
        print(f'  direct Medium fetch failed: {e!r}; trying rss2json.com')
    # Attempt 2: rss2json.com (free tier, no auth)
    try:
        api_url = f'https://api.rss2json.com/v1/api.json?rss_url={urllib.parse.quote(feed_url)}'
        data = json.loads(http_get(api_url))
        if data.get('status') == 'ok':
            items = [
                {'title': it['title'], 'link': it['link'].split('?')[0]}
                for it in data.get('items', [])[:5]
            ]
            print(f'  Medium fetched via rss2json: {len(items)} items')
            return items
    except Exception as e:
        print(f'  rss2json fallback also failed: {e!r}')
    print('  no Medium items — section will show placeholder')
    return []

medium_items = fetch_medium_items()
medium_count = len(medium_items)
posts_html_lines = []
for it in medium_items:
    title_safe = it['title'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    posts_html_lines.append(f'        <li><a href="{it["link"]}" target="_blank" rel="noopener">{title_safe}</a></li>')
medium_posts_html = '\n'.join(posts_html_lines) if posts_html_lines else '        <li>No posts yet</li>'

# ---- Apply token replacements ----
with open('index.template.html') as f:
    html = f.read()

substitutions = {
    'YEARS_EXP': years_exp,
    'YEARS_AXA': years_axa,
    'GH_REPOS': str(public_repos),
    'GH_STARS': str(total_stars),
    'GH_LATEST_PUSH_REL': gh_latest_push_rel,
    'MEDIUM_COUNT': str(medium_count),
    'MEDIUM_POSTS_HTML': medium_posts_html,
    'LAST_UPDATED': TODAY.isoformat(),
}

for token, value in substitutions.items():
    html = html.replace(f'{{{{{token}}}}}', value)

leftovers = re.findall(r'\{\{(\w+)\}\}', html)
if leftovers:
    print(f'  WARN unreplaced tokens: {set(leftovers)}', flush=True)

with open('index.html', 'w') as f:
    f.write(html)

# ---- Keep sitemap.xml <lastmod> fresh (freshness signal for search + AI crawlers) ----
try:
    with open('sitemap.xml') as f:
        sm = f.read()
    sm_new = re.sub(r'<lastmod>.*?</lastmod>', f'<lastmod>{TODAY.isoformat()}</lastmod>', sm)
    if sm_new != sm:
        with open('sitemap.xml', 'w') as f:
            f.write(sm_new)
        print(f'  sitemap.xml lastmod -> {TODAY.isoformat()}')
except FileNotFoundError:
    print('  sitemap.xml not found — skipped lastmod refresh')

print(f'baked: years_exp={years_exp} years_axa={years_axa} repos={public_repos} stars={total_stars} latest={gh_latest_push_rel} medium_count={medium_count}')
