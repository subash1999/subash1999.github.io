#!/usr/bin/env python3
"""Bake index.template.html → index.html with dynamic values.

Tokens replaced:
  {{YEARS_EXP}}          — years since CAREER_START (env), e.g. "6+"
  {{YEARS_AXA}}          — formatted: "Sep 2023 — Present (X+ years)"
  {{GH_REPOS}}           — public repo count via api.github.com
  {{GH_STARS}}           — sum of stargazers across own public repos
  {{GH_LATEST_PUSH_REL}} — relative time of latest push, e.g. "2d ago"
  {{MEDIUM_COUNT}}       — number of items in Medium RSS
  {{MEDIUM_POSTS_HTML}}  — <li> list of 5 most-recent Medium posts
  {{LAST_UPDATED}}       — today's date, ISO format

Inputs (env):
  CAREER_START   — ISO date (e.g. 2019-09-01)
  AXA_HIRE       — ISO date (e.g. 2023-09-16)
  GH_USER        — GitHub username (e.g. subash1999)
  MEDIUM_HANDLE  — Medium handle without @ (e.g. subash.niroula4455)
  GH_TOKEN       — optional; GitHub Actions secrets.GITHUB_TOKEN. Boosts API rate limit.
"""
import os, re, json, datetime, urllib.request
from xml.etree import ElementTree as ET

CAREER_START = datetime.date.fromisoformat(os.environ['CAREER_START'])
AXA_HIRE     = datetime.date.fromisoformat(os.environ['AXA_HIRE'])
GH_USER      = os.environ['GH_USER']
MEDIUM_HANDLE = os.environ['MEDIUM_HANDLE']
GH_TOKEN     = os.environ.get('GH_TOKEN', '')
TODAY        = datetime.date.today()

def years_plus(start):
    years = (TODAY - start).days / 365.25
    return f'{int(years)}+'

def http_get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    return urllib.request.urlopen(req, timeout=20).read()

def gh_api(path):
    h = {'Accept': 'application/vnd.github+json', 'User-Agent': 'bake-portfolio'}
    if GH_TOKEN:
        h['Authorization'] = f'Bearer {GH_TOKEN}'
    return json.loads(http_get(f'https://api.github.com{path}', h))

# ---- Compute tokens ----
years_exp = years_plus(CAREER_START)
years_axa_int = int((TODAY - AXA_HIRE).days / 365.25)
years_axa_plus = f'{years_axa_int}+'
axa_start_label = AXA_HIRE.strftime('%b %Y')  # "Sep 2023"

# GitHub stats
repos = gh_api(f'/users/{GH_USER}/repos?per_page=100&type=public')
public_repos = sum(1 for r in repos if not r['fork'])  # exclude forks
total_stars = sum(r['stargazers_count'] for r in repos if not r['fork'])

# Latest push across own repos (exclude forks)
own = [r for r in repos if not r['fork']]
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

# Medium RSS
rss_xml = http_get(f'https://medium.com/feed/@{MEDIUM_HANDLE}')
rss_root = ET.fromstring(rss_xml)
items = rss_root.findall('.//item')[:5]
medium_count = len(items)
medium_posts_html_lines = []
for item in items:
    title = (item.findtext('title') or '').strip()
    # strip ?source=rss tracking
    link = (item.findtext('link') or '').split('?')[0]
    # Escape HTML
    title_safe = title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    medium_posts_html_lines.append(f'        <li><a href="{link}" target="_blank" rel="noopener">{title_safe}</a></li>')
medium_posts_html = '\n'.join(medium_posts_html_lines) if medium_posts_html_lines else '        <li>No posts yet</li>'

last_updated = TODAY.isoformat()

# ---- Compose AXA tenure text ----
years_axa_text = f'{axa_start_label} — Present ({years_axa_plus} years)'

# ---- Apply token replacements ----
with open('index.template.html') as f:
    html = f.read()

substitutions = {
    'YEARS_EXP': years_exp,
    'YEARS_AXA': years_axa_plus,
    'YEARS_AXA_TEXT': years_axa_text,
    'GH_REPOS': str(public_repos),
    'GH_STARS': str(total_stars),
    'GH_LATEST_PUSH_REL': gh_latest_push_rel,
    'MEDIUM_COUNT': str(medium_count),
    'MEDIUM_POSTS_HTML': medium_posts_html,
    'LAST_UPDATED': last_updated,
}

for token, value in substitutions.items():
    html = html.replace(f'{{{{{token}}}}}', value)

# Sanity: any tokens left?
leftovers = re.findall(r'\{\{(\w+)\}\}', html)
if leftovers:
    print(f'WARN unreplaced tokens: {set(leftovers)}', flush=True)

with open('index.html', 'w') as f:
    f.write(html)

print(f'baked: years_exp={years_exp} years_axa={years_axa_plus} repos={public_repos} stars={total_stars} latest={gh_latest_push_rel} medium={medium_count}')
