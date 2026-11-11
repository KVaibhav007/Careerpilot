import asyncio
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import httpx
from .core import plain

HEADERS={'User-Agent':'CareerPilot/0.1 personal job research'}
async def board(client, config):
    kind=config['type']; slug=config['slug']
    import re
    if not re.fullmatch(r'[\w-]+',slug): raise ValueError('Invalid board slug')
    if kind=='greenhouse':
        data=(await fetch(client,f'https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true'))['jobs']
        return [dict(title=j['title'],company=slug,location=j['location']['name'],description=plain(j.get('content','')),apply_url=j['absolute_url'],source=kind,external_id=str(j['id'])) for j in data]
    if kind=='lever':
        data=await fetch(client,f'https://api.lever.co/v0/postings/{slug}?mode=json')
        return [dict(title=j['text'],company=slug,location=j.get('categories',{}).get('location',''),description=plain(j.get('descriptionPlain','')+' '+ ' '.join(plain(x.get('content','')) for x in j.get('lists',[]))),apply_url=j['hostedUrl'],source=kind,external_id=j['id']) for j in data]
    if kind=='ashby':
        data=await fetch(client,f'https://api.ashbyhq.com/posting-api/job-board/{slug}')
        return [dict(title=j['title'],company=slug,location=j.get('location',''),description=plain(j.get('descriptionPlain',j.get('descriptionHtml',''))),apply_url=j['jobUrl'],source=kind,external_id=j.get('id','')) for j in data['jobs']]
    raise ValueError('Unsupported board type')

async def fetch(client,url):
    response=await client.get(url);response.raise_for_status();return response.json()

async def discover(config):
    jobs=[]; errors=[]
    async with httpx.AsyncClient(timeout=35,headers=HEADERS) as client:
        for item in config.get('boards',[]):
            try: jobs.extend(await board(client,item))
            except Exception as e: errors.append({'source':item,'error':str(e)})
        if config.get('remoteok'):
            try:
                for j in await fetch(client,'https://remoteok.com/api'):
                    if 'position' in j: jobs.append(dict(title=j['position'],company=j.get('company',''),location=j.get('location',''),description=plain(j.get('description','')),apply_url=j.get('apply_url') or j['url'],source='remoteok',external_id=str(j['id'])))
            except Exception as e: errors.append({'source':'remoteok','error':str(e)})
        if config.get('wwr'):
            try:
                res=await client.get('https://weworkremotely.com/remote-jobs.rss');res.raise_for_status()
                for j in ET.fromstring(res.text).findall('.//item'):
                    title=j.findtext('title','');company,_,role=title.partition(':')
                    jobs.append(dict(title=role.strip() or title,company=company,location='Remote - eligibility unverified',description=plain(j.findtext('description','')),apply_url=j.findtext('link',''),source='wwr',external_id=j.findtext('guid','')))
            except Exception as e: errors.append({'source':'wwr','error':str(e)})
    settings=config.get('jobspy',{})
    if settings.get('enabled'):
        try:
            from jobspy import scrape_jobs
            for country in settings.get('countries',['Germany']):
                for query in ['cybersecurity','technical project manager','DevSecOps','technology risk']:
                    rows=await asyncio.to_thread(scrape_jobs,site_name=settings.get('sites',['indeed']),search_term=query,location=country,country_indeed=country.lower(),results_wanted=settings.get('results_per_query',15),hours_old=168,fetch_description=True)
                    for j in json.loads(rows.to_json(orient='records')):
                        if j.get('job_url'): jobs.append(dict(title=j['title'],company=j.get('company') or '',location=j.get('location') or country,description=plain(j.get('description','')),apply_url=j.get('job_url_direct') or j['job_url'],source='jobspy',external_id=str(j.get('id',''))))
                    for source,error in rows.attrs.get('errors',{}).items():errors.append({'source':source,'error':str(error)})
                    await asyncio.sleep(1)
        except Exception as e: errors.append({'source':'jobspy','error':str(e)})
    stamp=datetime.now(timezone.utc).isoformat()
    for j in jobs:j['fetched_at']=stamp;j['status']='listed - not independently verified'
    return jobs,errors
