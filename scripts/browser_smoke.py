"""Exercise the dashboard with synthetic data and no external applications."""
import json
import os
import tempfile
import threading
import time

os.environ['CAREERPILOT_DATA'] = tempfile.mkdtemp(prefix='careerpilot-browser-')
import uvicorn
from playwright.sync_api import sync_playwright
from app.main import app

server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=8123, log_level='error'))
thread = threading.Thread(target=server.run, daemon=True)
thread.start()
try:
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    if not server.started:
        raise RuntimeError('Test server failed to start')
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto('http://127.0.0.1:8123')
        page.get_by_role('button', name='Verified profile & sources').click()
        profile = {'name': 'Test Candidate', 'email': 'test@example.com', 'headline': 'Cloud Security Engineer',
                   'years_experience': 6, 'skills': ['Cloud Security', 'DevSecOps'],
                   'facts': [{'id': 'e1', 'section': 'Experience', 'text': 'Delivered verified cloud security improvements.'},
                             {'id': 'd1', 'section': 'Education', 'text': 'MSc Cybersecurity'}]}
        page.locator('#profile').fill(json.dumps(profile))
        page.get_by_role('button', name='Save', exact=True).click()
        page.get_by_role('button', name='Import any JD').click()
        for selector, value in {'#title': 'Cloud Security Engineer', '#company': 'Test Employer', '#location': 'Germany',
                                '#url': 'https://example.com/job', '#jd': 'Cloud Security and DevSecOps. Visa sponsorship available.'}.items():
            page.locator(selector).fill(value)
        page.get_by_role('button', name='Add job', exact=True).click()
        page.locator('#list article').first.click()
        page.get_by_role('button', name='Prepare CV + cover letter').click()
        page.get_by_role('heading', name='Review your application package').wait_for()
        for name in ['Download CV PDF', 'Download letter PDF']:
            with page.expect_download() as event:
                page.get_by_role('link', name=name).click()
            with open(event.value.path(), 'rb') as document:
                assert document.read(5) == b'%PDF-'
            print('PASS:', name)
        assert not errors, errors
        browser.close()
        print('PASS: browser profile, JD import, document preview and downloads')
finally:
    server.should_exit = True
    thread.join(timeout=5)
