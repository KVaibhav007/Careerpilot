import asyncio
import json
import os
import sqlite3
import secrets
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from .core import assess,identity,contact_queries,safe_public_url
from .connectors import discover
from .documents import tailor,pdf_bytes

ROOT=Path(__file__).resolve().parent.parent
DATA=Path(os.getenv('CAREERPILOT_DATA',str(ROOT/'runtime')));DATA.mkdir(parents=True,exist_ok=True)
app=FastAPI(title='CareerPilot',version='0.1.0')
TOKEN=secrets.token_urlsafe(32)
scan_lock=asyncio.Lock()

@contextmanager
def db():
    c=sqlite3.connect(DATA/'careerpilot.db');c.row_factory=sqlite3.Row
    c.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, payload TEXT NOT NULL, assessment TEXT NOT NULL, stage TEXT DEFAULT "shortlisted")')
    c.execute('CREATE TABLE IF NOT EXISTS contacts (id INTEGER PRIMARY KEY, job_id TEXT, payload TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS documents (job_id TEXT PRIMARY KEY, payload TEXT)')
    try:yield c;c.commit()
    finally:c.close()

def load(name,example):
    path=DATA/name
    return json.loads((path if path.exists() else ROOT/example).read_text())

def getjob(jid):
    with db() as c:r=c.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
    if not r:raise HTTPException(404,'Job not found')
    return json.loads(r['payload'])

@app.middleware('http')
async def local_guard(request:Request,call_next):
    if request.headers.get('host','').split(':')[0] not in ('127.0.0.1','localhost','testserver'):
        return Response('Local access only',status_code=403)
    if request.method not in ('GET','HEAD','OPTIONS') and request.headers.get('x-careerpilot-token')!=TOKEN:
        return Response('Invalid request token',status_code=403)
    response=await call_next(request);response.headers['X-Content-Type-Options']='nosniff';response.headers['Cache-Control']='no-store'
    return response

@app.get('/',response_class=HTMLResponse)
def home():return (ROOT/'app/index.html').read_text().replace('__TOKEN__',TOKEN)

@app.get('/api/settings')
def settings():return {'profile':load('profile.json','profile.example.json'),'sources':load('sources.json','sources.example.json'),'ai_configured':bool(os.getenv('LLM_MODEL'))}

@app.put('/api/settings')
async def save_settings(request:Request):
    data=await request.json();profile=data['profile'];facts=profile.get('facts',[])
    if len({f['id'] for f in facts})!=len(facts):raise HTTPException(400,'Fact IDs must be unique')
    for key in ('profile','sources'):(DATA/(key+'.json')).write_text(json.dumps(data[key],indent=2))
    with db() as c:
        for row in c.execute('SELECT id,payload FROM jobs').fetchall():
            c.execute('UPDATE jobs SET assessment=? WHERE id=?', (json.dumps(assess(json.loads(row['payload']),profile)),row['id']))
        c.execute('DELETE FROM documents')
    return {'saved':True}

@app.post('/api/scan')
async def scan():
    if scan_lock.locked():raise HTTPException(409,'Scan already running')
    async with scan_lock:
        jobs,errors=await discover(load('sources.json','sources.example.json'));profile=load('profile.json','profile.example.json');count=0
        with db() as c:
            for j in jobs:
                a=assess(j,profile)
                if not a['relevant']:continue
                c.execute('INSERT INTO jobs(id,payload,assessment) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,assessment=excluded.assessment',(identity(j),json.dumps(j),json.dumps(a)));count+=1
        return {'matched':count,'errors':errors}

@app.get('/api/jobs')
def jobs():
    with db() as c:rows=c.execute('SELECT * FROM jobs').fetchall()
    result=[dict(id=r['id'],**json.loads(r['payload']),assessment=json.loads(r['assessment']),stage=r['stage']) for r in rows]
    return sorted(result,key=lambda j:(j['assessment']['priority'],-j['assessment']['fit_score']))

@app.post('/api/jobs')
async def import_job(request:Request):
    j=await request.json()
    if any(not j.get(k) for k in ('title','company','apply_url','description')):raise HTTPException(400,'Title, company, apply URL and JD required')
    if not j['apply_url'].startswith('https://'):raise HTTPException(400,'Use an HTTPS application URL')
    j.setdefault('location','');j['source']='manual';j['fetched_at']=datetime.now(timezone.utc).isoformat();j['status']='manually imported - not verified'
    a=assess(j,load('profile.json','profile.example.json'));jid=identity(j)
    with db() as c:c.execute('INSERT INTO jobs(id,payload,assessment) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,assessment=excluded.assessment',(jid,json.dumps(j),json.dumps(a)))
    return {'id':jid}

@app.patch('/api/jobs/{jid}')
async def stage(jid:str,request:Request):
    getjob(jid);value=(await request.json())['stage']
    if value not in ('shortlisted','prepared','applied','interview','rejected','closed'):raise HTTPException(400,'Invalid stage')
    with db() as c:c.execute('UPDATE jobs SET stage=? WHERE id=?',(value,jid))
    return {'stage':value}

@app.put('/api/jobs/{jid}/description')
async def update_description(jid:str,request:Request):
    job=getjob(jid)
    description=(await request.json()).get('description','')
    if not isinstance(description,str) or not description.strip():
        raise HTTPException(400,'Paste the full job description before saving')
    job['description']=description.strip()
    assessment=assess(job,load('profile.json','profile.example.json'))
    with db() as c:
        c.execute('UPDATE jobs SET payload=?,assessment=? WHERE id=?',(json.dumps(job),json.dumps(assessment),jid))
        c.execute('DELETE FROM documents WHERE job_id=?',(jid,))
    return {'saved':True}

@app.post('/api/jobs/{jid}/verify')
async def verify(jid:str):
    j=getjob(jid)
    try:
        await asyncio.to_thread(safe_public_url,j['apply_url'])
        async with httpx.AsyncClient(timeout=20,follow_redirects=False) as client:r=await client.get(j['apply_url'])
        status='page reachable - vacancy requires review' if r.status_code==200 else ('page removed' if r.status_code in (404,410) else f'needs review: HTTP {r.status_code}')
    except Exception as e:status='verification failed: '+str(e)
    j['status']=status;j['verified_at']=datetime.now(timezone.utc).isoformat()
    with db() as c:c.execute('UPDATE jobs SET payload=? WHERE id=?',(json.dumps(j),jid))
    return {'status':status}

@app.get('/api/jobs/{jid}/contacts')
def contacts(jid:str):
    j=getjob(jid)
    with db() as c:rows=c.execute('SELECT payload FROM contacts WHERE job_id=?',(jid,)).fetchall()
    return {'queries':contact_queries(j),'contacts':[json.loads(r['payload']) for r in rows]}

@app.post('/api/jobs/{jid}/contacts/search')
async def search_contacts(jid:str):
    j=getjob(jid);key=os.getenv('BRAVE_API_KEY')
    if not key:raise HTTPException(400,'Set BRAVE_API_KEY for automated public contact research; search queries remain available without it')
    results=[]
    async with httpx.AsyncClient(timeout=25) as client:
        for q in contact_queries(j):
            r=await client.get('https://api.search.brave.com/res/v1/web/search',params={'q':q,'count':5},headers={'X-Subscription-Token':key});r.raise_for_status()
            results.extend({'title':x['title'],'url':x['url'],'snippet':x.get('description',''),'confidence':'unverified search lead'} for x in r.json().get('web',{}).get('results',[]))
    return {'leads':results,'note':'Search results are leads, not confirmed hiring managers.'}

@app.post('/api/jobs/{jid}/contacts')
async def add_contact(jid:str,request:Request):
    getjob(jid);data=await request.json()
    if not data.get('name') or not data.get('source_url'):raise HTTPException(400,'Name and evidence URL required')
    data['confidence']='user-reviewed relevant contact';data['saved_at']=datetime.now(timezone.utc).isoformat()
    with db() as c:c.execute('INSERT INTO contacts(job_id,payload) VALUES(?,?)',(jid,json.dumps(data)))
    return {'saved':True}

@app.post('/api/jobs/{jid}/documents')
async def documents(jid:str):
    try:result=await tailor(load('profile.json','profile.example.json'),getjob(jid))
    except Exception as e:raise HTTPException(400,str(e))
    with db() as c:c.execute('INSERT OR REPLACE INTO documents VALUES(?,?)',(jid,json.dumps(result)))
    return result

@app.get('/api/jobs/{jid}/documents/{kind}.pdf')
def download(jid:str,kind:str):
    if kind not in ('cv','cover_letter'):raise HTTPException(404)
    with db() as c:r=c.execute('SELECT payload FROM documents WHERE job_id=?',(jid,)).fetchone()
    if not r:raise HTTPException(404,'Generate documents first')
    return Response(pdf_bytes(json.loads(r['payload'])[kind]),media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="{kind}_{jid}.pdf"'})
