# CareerPilot

A local personal job-search workspace for cybersecurity, cloud security, GRC, DevSecOps and technical project management. Geographic ranking: Europe, Japan, Singapore, US, then other locations. Worldwide is a targeting scope, not a guarantee of exhaustive coverage.

## Run

Python 3.11 or later:

```sh
python -m venv .venv
source .venv/bin/activate
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. Alternatively: `docker compose up --build`.

1. Open **Verified profile & sources**. Replace the example identity and facts with your own verified profile. No private CV is included in this repository.
2. Configure Greenhouse, Lever and Ashby board slugs. Example slugs are examples, not sponsorship recommendations.
3. Enable WWR RSS, Remote OK, or optional JobSpy searches as needed. Follow source terms and limits. JobSpy failures are displayed; an empty result is not treated as proof of no openings.
4. Click **Find jobs**, or import a full JD with an employer URL from any portal.
5. Review sponsorship evidence, location and experience flags. The experience detector flags numeric mentions conservatively; it does not distinguish every required/preferred qualification.
6. Open a job, research contacts, generate and review the CV and cover letter, then download the PDFs and apply at the employer portal.

## Implemented

- Persistent SQLite tracking and URL deduplication; regional ordering.
- Greenhouse, Lever and Ashby connectors, WWR RSS, Remote OK JSON, optional JobSpy adapter.
- Manual import for any JD, including sources without supported automated access.
- Conservative sponsorship classification with supporting text; relocation alone is not sponsorship.
- Public contact search queries and optional Brave Search results; reviewed contacts with evidence URLs.
- Per-JD CV and cover-letter PDF generation, with exact verified facts preserved.
- Optional OpenAI-compatible AI ranking (including local Ollama); invalid fact IDs are rejected.
- Local host checks, mutation token protection, escaped rendering and blocked private-network verification targets.
- Status tracking and page-reachability checks. HTTP 200 is deliberately not labelled a confirmed open vacancy.

## Optional AI and contact search

Copy `.env.example` to `.env`. Docker reads it. For a direct Python launch, export these variables yourself (the app does not auto-load .env). Set LLM_MODEL, LLM_BASE_URL and optionally LLM_API_KEY. An Ollama OpenAI-compatible endpoint can use `http://localhost:11434/v1` with an installed model. Hosted providers receive the supplied profile and JD; local storage does not imply local inference.

Without AI the app ranks existing evidence locally and creates a conservative template letter. With AI it ranks fact IDs; it does not freely rewrite or invent achievements. This is intentional, and less flexible than a fully generative CV editor.

Set BRAVE_API_KEY for public contact research. Search results are unverified leads; the user reviews people before saving. HUNTER_API_KEY is reserved for a future integration and is **not implemented**. No automatic emails, guessed contact addresses, LinkedIn connections or application submissions.

## Source coverage

| Source | Current support |
|---|---|
| Greenhouse / Lever / Ashby | Configured company boards |
| LinkedIn / Indeed / other JobSpy boards | Optional adapter; availability varies |
| WWR / Remote OK | RSS / JSON feed |
| Careerhound / AIApply / FlexJobs / Wellfound / Dynamite / Crossover / YC | Manual JD import; no universal authenticated connector |
| Eneba / Spiralyze / Roamless / Unlayer / Swans | Supported ATS connector when applicable, otherwise manual import |
| Repass | Unresolved source; manual import only |

## Limits and next work

This first version does not scan all employers worldwide, verify immigration eligibility, guarantee exact hiring-manager identity, or rewrite CV facts with AI. Language and sponsorship heuristics require human review. Search snippets may be stale. Application deadlines and complex eligibility rules currently remain in the original JD rather than dedicated extracted fields. User-added contacts need independent identity verification. A company-wide sponsorship policy is not evidence that every role sponsors.

The UI currently supports document preview/download, not editing generated text. The next iteration should add provenance-backed JD extraction, richer region/language filtering, professional-email lookup, editable document previews, saved contact leads, scheduled refresh and independently verified vacancy status.

Run only locally: do not expose this unauthenticated personal workspace to the internet. Source documents and job pages are untrusted; no page content is executed as shell code. Network target validation reduces SSRF exposure but is not a production egress proxy. Runtime data, CVs and credentials are gitignored. The dependency ranges should be locked and audited before wider deployment.

## Test

```sh
python -m unittest discover -s tests -v
```

## Upstream review and reuse

This repository is original integration code; it does not copy the reviewed repositories wholesale. Optional `python-jobspy` is MIT licensed; preserve applicable notices when distributing dependencies. FastAPI/httpx/ReportLab and other dependencies retain their own licences.

Reviewed candidates: [JobSpy](https://github.com/speedyapply/JobSpy), [Resume Matcher](https://github.com/srbhr/Resume-Matcher), [AIHawk](https://github.com/feder-cr/Jobs_Applier_AI_Agent), [career-ops](https://github.com/career-ops-hq/career-ops), [JobAppAgent](https://github.com/vaibhavarora14/job-application-agent), [resume-jd-tailor](https://github.com/ki11e6/resume-jd-tailor), [freehire](https://github.com/strelov1/freehire). VedantSagare/job-application-agent was not copied because no licence was identified during review.
