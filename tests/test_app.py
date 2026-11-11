import os
import tempfile
import unittest
os.environ['CAREERPILOT_DATA']=tempfile.mkdtemp()
from fastapi.testclient import TestClient
from app.core import sponsorship,assess,region
from app.documents import tailor,pdf_bytes
from app.main import app,TOKEN

class CoreTests(unittest.TestCase):
    def test_sponsorship_negation(self):
        self.assertEqual(sponsorship('We do not provide visa sponsorship.')['status'],'explicitly unavailable')
        self.assertEqual(sponsorship('Visa sponsorship available.')['status'],'explicitly offered')
        self.assertEqual(sponsorship('We offer relocation assistance.')['status'],'not stated')
    def test_priority(self):
        self.assertEqual(region('Berlin, Germany')[1],0)
        self.assertEqual(region('Tokyo, Japan')[1],1)
    def test_pdf(self):
        self.assertTrue(pdf_bytes('Name\n\nExperience & qualifications').startswith(b'%PDF'))
    def test_api_workflow_and_csrf(self):
        with TestClient(app) as c:
            job={'title':'Cloud Security Engineer','company':'Fixture employer','location':'Germany','apply_url':'https://example.com/jobs/1','description':'Visa sponsorship available. Requires 8 years experience with Cloud Security.'}
            self.assertEqual(c.post('/api/jobs',json=job).status_code,403)
            r=c.post('/api/jobs',json=job,headers={'X-CareerPilot-Token':TOKEN});self.assertEqual(r.status_code,200)
            j=c.get('/api/jobs').json()[0];self.assertTrue(j['assessment']['experience_review'])
            self.assertEqual(j['assessment']['sponsorship']['status'],'explicitly offered')
            self.assertEqual(c.post('/api/jobs',json=job,headers={'X-CareerPilot-Token':TOKEN}).status_code,200)
            self.assertEqual(len(c.get('/api/jobs').json()),1)
    def test_private_host_blocked(self):
        with TestClient(app) as c:self.assertEqual(c.get('/',headers={'host':'evil.example'}).status_code,403)

class DocumentTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_verified_facts(self):
        p={'name':'Candidate','skills':['Cloud Security'],'facts':[{'id':'a','section':'Experience','text':'Managed a verified cloud project.'}]}
        d=await tailor(p,{'title':'Security Engineer','company':'Example','description':'Cloud Security and Kubernetes'})
        self.assertIn(p['facts'][0]['text'],d['cv']);self.assertNotIn('Kubernetes',d['cv'])
        self.assertEqual(d['fact_ids'],['a'])

if __name__=='__main__':unittest.main()

class ConnectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_board_mapping(self):
        import httpx
        from app.connectors import board
        def handle(request):
            return httpx.Response(200,json={'jobs':[{'id':123,'title':'Security Engineer','location':{'name':'Germany'},'content':'<p>Visa sponsorship available</p>','absolute_url':'https://example.com/123'}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            rows=await board(client,{'type':'greenhouse','slug':'fixture'})
        self.assertEqual(rows[0]['apply_url'],'https://example.com/123')
        self.assertIn('Visa sponsorship',rows[0]['description'])
