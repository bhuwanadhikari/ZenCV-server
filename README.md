# IntelliCV Server

FastAPI backend for a browser extension that:

- scans the current browser tab for a job description,
- generates a tailored CV JSON from the user's story JSON,
- generates a cover letter from the tailored CV, the story JSON, and the job description.

## Why FastAPI

FastAPI is a strong choice here because it gives you:

- quick API development with request and response validation,
- easy JSON-first endpoints for extension traffic,
- automatic OpenAPI docs for testing,
- good async support if you later add queues, auth, or persistence.

For this use case, it is a very practical choice.

## Endpoints

- `GET /health`
- `POST /api/cv/generate`
- `POST /api/job-description/process`
- `POST /api/cover-letter/generate`

### CV generate request body

```json
{
  "page_title": "Senior Backend Engineer at Example",
  "job_url": "https://example.com/jobs/backend-engineer",
  "job_description": "Full scanned job description text from the page...",
  "story_json_override": null
}
```

Each `POST /api/cv/generate` call now also writes artifacts to `data/generated/<page_title>/`:

- `generated_cv.json` with the raw generated CV JSON
- `generation_summary.md` with appended JD, CV, and cover letter generations plus request token usage and estimated cost for each LLM task

### Job description process request body

```json
{
  "raw_html": "<html><body><header>...</header><main>Job description...</main><footer>...</footer></body></html>"
}
```

`POST /api/job-description/process` currently cleans the incoming HTML, finds the common parent of the top 5 longest leaf-text elements, and returns newline-separated plain text from that region in both `processed_html` and `processed_text`.
When LLM-based JD extraction is enabled, it also persists the extracted job description and appends it to `generation_summary.md` with request metrics.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
```

## Environment variables

- `LLM_API_KEY`
- `LLM_MODEL`
- `LLM_BASE_URL`
- `LLM_TIMEOUT_SECONDS`
- `LLM_INPUT_COST_PER_1M_TOKENS` (optional)
- `LLM_OUTPUT_COST_PER_1M_TOKENS` (optional)
- `MY_STORY_JSON_PATH`

## Notes

- `LLM_BASE_URL` can point to OpenAI or another OpenAI-compatible provider such as DeepSeek.
- If you use a model or provider without built-in pricing in the app, set `LLM_INPUT_COST_PER_1M_TOKENS` and `LLM_OUTPUT_COST_PER_1M_TOKENS` so the markdown artifact can show an estimated request cost.
- The server currently allows all origins and skips authentication, matching your current development goal.
- Replace `data/my_story.json` with your real story JSON structure and content.
