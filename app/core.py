import hashlib
import re
from urllib.parse import urlparse

EUROPE = {'germany','netherlands','france','ireland','sweden','denmark','finland','norway','switzerland','austria','belgium','luxembourg','spain','portugal','italy','poland','czech','estonia','latvia','lithuania','iceland','europe','united kingdom','uk','romania','greece','hungary','slovakia','slovenia','croatia','malta','cyprus','bulgaria','serbia','ukraine'}
ROLES = ('security', 'cyber', 'devsecops', 'technology risk', 'grc', 'technical project', 'technical program', 'cloud engineer', 'it project', 'compliance', 'project manager')

def plain(text):
    import html
    return html.unescape(re.sub('<[^>]+>', ' ', text or ''))

def identity(job):
    return hashlib.sha256(job['apply_url'].split('?')[0].encode()).hexdigest()[:20]

def region(location):
    text = location.lower()
    if any(re.search(r'\b'+re.escape(c)+r'\b', text) for c in EUROPE): return 'Europe', 0
    if 'japan' in text or 'tokyo' in text: return 'Japan', 1
    if 'singapore' in text: return 'Singapore', 2
    if re.search(r'\b(usa|us|united states)\b', text): return 'US', 3
    return 'Other / unclear', 4

def sponsorship(text):
    sentences = re.split(r'(?<=[.!?])\s+|[\r\n]+', text)
    relevant = [s.strip() for s in sentences if re.search(r'sponsor|work authori[sz]|visa|relocation', s, re.I)]
    negative = r'(?:no|not|cannot|unable|without|do not|does not|will not|won.t).{0,65}sponsor|sponsor.{0,45}(?:not available|not provided)|must.{0,35}(?:existing|current).{0,20}(?:work|authori)'
    positive = r'(?:visa|immigration|work permit).{0,30}(?:sponsorship|support|provided)|(?:provide|offer|available|support).{0,35}(?:visa sponsorship|immigration sponsorship)|sponsor.{0,25}(?:visa|work permit)'
    neg = [s for s in relevant if re.search(negative,s,re.I)]
    pos = [s for s in relevant if re.search(positive,s,re.I) and not re.search(negative,s,re.I)]
    if neg and pos: label = 'conditional / conflicting'
    elif neg: label = 'explicitly unavailable'
    elif pos: label = 'explicitly offered'
    else: label = 'not stated'
    return {'status': label, 'evidence': relevant[:8], 'note': 'Relocation alone is not visa sponsorship; employer confirmation is still required.'}

def assess(job, profile):
    jd = plain(job['description']); lower = jd.lower()
    skills = profile.get('skills', [])
    matched = [s for s in skills if s.lower() in lower]
    requirements = [int(x) for x in re.findall(r'(\d{1,2})\s*\+?\s*(?:years|yrs)', lower)]
    minimum = max(requirements, default=None)
    reg, priority = region(job.get('location',''))
    return {'region':reg, 'priority':priority, 'sponsorship':sponsorship(jd), 'matched_skills':matched,
            'profile_skills_not_in_jd':[s for s in skills if s not in matched],
            'experience_mentions':requirements, 'experience_review':bool(minimum and minimum>profile.get('years_experience',6)),
            'fit_score':round(100*len(matched)/max(len(skills),1)), 'score_note':'Profile skill overlap, not an employer ATS score.',
            'language_review':bool(re.search(r'(japanese|german|french).{0,35}(required|fluent|native|business)|(?:fluent|native).{0,25}(japanese|german|french)',lower)),
            'relevant':any(x in job['title'].lower() for x in ROLES)}

def contact_queries(job):
    company=job['company']; title=job['title']
    return [f'"{company}" "{title}" recruiter', f'site:linkedin.com/in "{company}" ("Talent Acquisition" OR "Technical Recruiter")',f'site:linkedin.com/in "{company}" ("Head of Security" OR "Security Engineering Manager" OR "PMO Director")']

def safe_public_url(url):
    import ipaddress
    import socket
    parsed=urlparse(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None,443):
        raise ValueError('Only public HTTPS URLs on port 443 are allowed')
    for result in socket.getaddrinfo(parsed.hostname,443,type=socket.SOCK_STREAM):
        if not ipaddress.ip_address(result[4][0]).is_global: raise ValueError('Private and local network targets are blocked')
    return url
