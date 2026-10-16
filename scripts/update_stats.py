import datetime as dt
import html
import json
import os
import pathlib
import urllib.request

TOKEN = os.environ.get('PROFILE_STATS_TOKEN')
LOGIN = os.environ.get('PROFILE_LOGIN', 'tatopirtakhia')
if not TOKEN:
    raise SystemExit('Add the PROFILE_STATS_TOKEN repository secret before running this workflow.')

def query(document, variables):
    req = urllib.request.Request('https://api.github.com/graphql',
        data=json.dumps({'query': document, 'variables': variables}).encode(),
        headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json', 'User-Agent': 'profile-stats'})
    with urllib.request.urlopen(req, timeout=60) as response:
        payload = json.load(response)
    if payload.get('errors'):
        # Do not print response data or credentials to the workflow log.
        raise RuntimeError('GitHub GraphQL failed. Check token permissions and organization SSO authorization.')
    return payload['data']

account = query('query($login:String!){viewer{login} user(login:$login){createdAt}}', {'login': LOGIN})
if account['viewer']['login'].lower() != LOGIN.lower():
    raise SystemExit('The secret must belong to the profile owner so private contributions are visible.')
created = dt.datetime.fromisoformat(account['user']['createdAt'].replace('Z', '+00:00'))
now = dt.datetime.now(dt.timezone.utc)
counts = {}
for year in range(created.year, now.year + 1):
    start = max(created, dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc))
    end = min(now, dt.datetime(year, 12, 31, 23, 59, 59, tzinfo=dt.timezone.utc))
    data = query('''query($login:String!,$from:DateTime!,$to:DateTime!){
      user(login:$login){contributionsCollection(from:$from,to:$to){
        totalCommitContributions
      }}
    }''', {'login': LOGIN, 'from': start.isoformat(), 'to': end.isoformat()})
    counts[year] = data['user']['contributionsCollection']['totalCommitContributions']

# Count commits only. restrictedContributionsCount also includes non-commit
# activity and must never be added to a commit count.
rows = [('All years', sum(counts.values())),
        (str(now.year), counts.get(now.year, 0)),
        (str(now.year - 1), counts.get(now.year - 1, 0))]
parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="640" height="258" viewBox="0 0 640 258" role="img" aria-labelledby="title desc">',
    '<title id="title">GitHub commit contributions</title>',
    '<desc id="desc">Authenticated commit contribution counts across repositories accessible to the profile owner.</desc>',
    '<rect width="640" height="258" rx="16" fill="#0d1117"/>',
    '<g font-family="Segoe UI,Arial,sans-serif">',
    '<text x="28" y="40" fill="#a78bfa" font-size="22" font-weight="600">GitHub commit contributions</text>',
    '<text x="28" y="66" fill="#8b949e" font-size="13">Public + private repositories accessible to the token</text>']
for index, (label, value) in enumerate(rows):
    y = 108 + index * 38
    parts.append(f'<text x="28" y="{y}" fill="#c9d1d9" font-size="17">{html.escape(label)}</text>')
    parts.append(f'<text x="610" y="{y}" text-anchor="end" fill="#22d3ee" font-size="22" font-weight="600">{value:,}</text>')
parts.extend([f'<text x="28" y="235" fill="#8b949e" font-size="12">Updated {now:%Y-%m-%d %H:%M} UTC · GitHub contribution rules apply</text>', '</g></svg>'])
pathlib.Path('assets').mkdir(exist_ok=True)
pathlib.Path('assets/github-stats.svg').write_text('\n'.join(parts), encoding='utf-8')
print('Updated commit contribution card; no repository names or token data were published.')
