# AgileCV Server

FastAPI backend for generating a tailored CV JSON and cover letter from a job posting.

The service is designed for a browser extension flow:

- extract the job-description text from the current page HTML,
- generate a targeted CV JSON from stored CV variants,
- generate a cover letter using the job description and CV context.

## Before You Start

Create `data/user-profile/cv_variants.json` in the same format as [data/user-profile/cv_variants.example.json](/Users/bhuwan/Documents/projects/intellicv/intellicv-server/data/user-profile/cv_variants.example.json).

This file can contain multiple CV variants for the same candidate. Each variant can have its own:

- profile summary,
- skill groups,
- section titles,
- work experience entries and bullet points,
- job titles,
- employers,
- education entries,
- projects or other supporting sections.

The service uses those variants as the factual source of truth. Based on the target job description, the LLM selects and rewrites the best-matching bullet points, job titles, skills, and supporting evidence, then returns a tailored CV JSON to the frontend.

Also update `.env` with your real `LLM_API_KEY` before starting the server.

## API

- `GET /health`
- `POST /api/job-description/process`
- `POST /api/cv/generate`
- `POST /api/cover-letter/generate`

Interactive docs are available at:

- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
```

The server starts on `http://127.0.0.1:8000` by default.

## Environment Variables

Configured in [.env.example](/Users/bhuwan/Documents/projects/intellicv/intellicv-server/.env.example):

- `LLM_API_KEY`
- `LLM_MODEL` default: `gpt-4.1-mini`
- `LLM_BASE_URL` default: `https://api.openai.com/v1`
- `LLM_TIMEOUT_SECONDS` default: `60`
- `MY_STORY_TXT` default: `data/user-profile/my_story.txt`

Also supported:

- `LLM_INPUT_COST_PER_1M_TOKENS` optional
- `LLM_OUTPUT_COST_PER_1M_TOKENS` optional

Notes:

- `LLM_BASE_URL` can point to OpenAI or another OpenAI-compatible provider.
- If your provider/model pricing is not built into the app, set the optional token-cost variables so request cost estimates can be written to the summary artifact.
- `MY_STORY_TXT` exists in settings today, but the current generation flow uses `story_json_override` from the request body rather than reading that file directly.

## Data Files

The service reads CV source data from:

- [data/user-profile/cv_variants.json](/Users/bhuwan/Documents/projects/intellicv/intellicv-server/data/user-profile/cv_variants.json) when present
- otherwise [data/user-profile/cv_variants.example.json](/Users/bhuwan/Documents/projects/intellicv/intellicv-server/data/user-profile/cv_variants.example.json)

Generated artifacts are stored under:

- `data/generated/<job_url_hash>/`

Artifacts may include:

- `generated_jd.txt`
- `generated_cv.json`
- `generated_cl.txt`
- `generation_summary.md`

`generation_summary.md` appends the generated content plus request token usage and estimated cost for each LLM call.

## Implementation Notes

- CORS is currently open to all origins.
- There is no authentication layer yet.
- Caching is keyed by a hash of `job_url`, not by page title.
- The service currently uses the OpenAI chat-completions API via the official Python client.




