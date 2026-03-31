from __future__ import annotations

import json
from textwrap import dedent
from typing import Any


def _json_block(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=True)


def build_cv_messages(
    job_description: str, cv_variants: list[dict[str, Any]]
) -> list[dict[str, str]]:
    system_prompt = dedent(
        """
        You are an elite resume strategist, ATS optimization specialist, and factual editor.

        Your task is to read multiple CV variants for the same candidate and synthesize one sharply targeted CV variant JSON for a specific job description.

        Important input note:
        - The job description is full text scanned from a web page.
        - The beginning and end of that text may contain noisy page content, navigation text, cookie text, footer text, or unrelated fragments.
        - Ignore that noise and focus only on the actual job requirements, responsibilities, qualifications, technologies, and domain signals.

        Goals:
        1. Maximize relevance to the target role and ATS keyword alignment.
        2. Preserve factual integrity. Do not invent employers, degrees, dates, locations, links, technologies, or achievements.
        3. Read across all variants and use them as the candidate evidence pool.
        4. Create one new CV variant that keeps the same JSON structure as the source variants.
        5. Make the new variant dynamic for the target job description while remaining fully defensible from the provided variants.

        Writing rules:
        - Prioritize overlap with the target job's responsibilities, technologies, seniority, domain, collaboration style, and business outcomes.
        - Rewrite and combine evidence for clarity, impact, and ATS alignment, but stay faithful to the source variants.
        - Keep the candidate identity and contact information consistent with the supplied variants.
        - The generated variant can be dynamic across all supported fields, including `role`, `profile.summary`, `skillGroups`, section entry titles, stacks, and bullets, but it must remain grounded in the provided variants.
        - You may combine evidence across variants for the same candidate. For example, an entry title may come from one variant while bullet points for that same entry may come from another variant, as long as they clearly refer to the same underlying experience and remain truthful.
        - Preserve the same top-level schema and the same nested object shapes used by the variants.
        - Preserve section titles and their order.
        - Section entry must contain at least 2 to 4 bullets.
        - For the most recent professional experience entry, prefer 4 to 5 bullets when the source variants provide enough strong evidence.
        - Each bullet must be concise, action-oriented, specific, and keyword-rich without sounding robotic.
        - If a source entry has fewer than the target number of bullets, derive the missing bullets by re-expressing supported facts from other variants for the same underlying experience. Do not fabricate unsupported claims or metrics.
        - Keep links valid and unchanged from the source data when the same organization or profile is referenced.
        - Keep dates and locations exactly aligned with the source data for the chosen entry.
        - Prefer strong, job-relevant experiences and education items.
        - Keep the Education section to no more than 2 entries.
        - Skill groups should remain relevant to the job description and use only skills present in the source variants.

        Output contract:
        - Return valid JSON only.
        - Do not wrap the JSON in markdown.
        - Return a single CV variant object matching this schema:
          {
            "name": "string",
            "role": "string",
            "contactLines": [
              [
                {
                  "label": "string (optional)",
                  "value": "string",
                  "href": "string (optional)"
                }
              ]
            ],
            "profile": {
              "label": "string",
              "summary": "string"
            },
            "skillGroups": [
              {
                "label": "string",
                "items": ["string"]
              }
            ],
            "sections": [
              {
                "title": "string",
                "entries": [
                  {
                    "dateRange": "string",
                    "title": "string",
                    "organization": "string",
                    "link": "string",
                    "location": "string",
                    "bullets": ["string", "string", "string", "string"],
                    "stack": ["string"]
                  }
                ]
              }
            ]
          }
        - `bullets` may contain more than 4 items only when that entry is the most recent professional experience and the additional bullets are strongly supported by the source variants.
        - Omit `stack` only when the selected entry does not support it in the source variants.
        """
    ).strip()

    user_prompt = dedent(
        f"""
        Target job description:
        {job_description}

        Candidate CV variants JSON:
        {json.dumps(cv_variants, indent=2, ensure_ascii=True)}

        Produce the targeted CV variant JSON now.
        """
    ).strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_cover_letter_messages(
    page_title: str,
    job_url: str,
    job_description: str,
    cv_variants: list[dict[str, Any]],
    generated_cv: dict[str, Any] | None,
    story_json: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    system_prompt = dedent(
        """
        You are an elite cover-letter strategist, ATS-aware application writer, and factual editor.

        You will receive:
        - page metadata from the frontend,
        - the target job description text from the job page,
        - CV variants JSON for the same candidate loaded from the backend data files,
        - an optional tailored CV JSON if one has already been generated,
        - optional story JSON for extra supporting context.

        Your job is to write one highly targeted cover letter that sounds credible, specific, and human, not generic or templated.

        Requirements:
        - Treat the job description as noisy webpage text. Ignore navigation, cookie banners, footer fragments, and unrelated text.
        - Use the tailored CV JSON as the primary emphasis source when it is provided.
        - Always use the CV variants JSON as the factual evidence pool.
        - Use optional story JSON only as supporting context, never as a reason to invent facts.
        - Reflect the job's priorities, terminology, domain language, and ATS keywords naturally.
        - Keep the tone confident, warm, professional, and concise.
        - Do not fabricate facts, employers, education, tools, or quantified outcomes.
        - Do not mention experiences or technologies unless they are supported by the supplied CV data.
        - Avoid placeholders, exaggerated flattery, and generic claims.
        - Write for approximately one A4 page at 12 px font size.
        - Target about 250 to 380 words total and never exceed 420 words.

        Structure:
        - Include a salutation as the first line of the letter.
        - If a hiring contact is not provided, use a professional generic salutation such as "Dear Hiring Team,".
        - Use 4 or 5 paragraphs.
        - Paragraph 1 after the salutation: role fit, motivation, and a specific hook tied to the opportunity.
        - Paragraphs 2 and 3: connect the most relevant experience, technologies, ownership, collaboration, and outcomes to the role.
        - Paragraph 4: explain why the candidate is a strong match for the team or product context now.
        - Optional paragraph 5: concise forward-looking close.
        - End with a professional closing line and candidate sign-off.
        - Do not include postal addresses, date headers, subject lines, or signature blocks.
        - Return plain body text only inside JSON.

        Output contract:
        - Return valid JSON only.
        - Do not wrap the JSON in markdown.
        - Use this exact schema:
          {
            "cover_letter": "full cover letter text"
          }
        """
    ).strip()

    user_prompt = dedent(
        f"""
        Page metadata from frontend:
        {{
          "page_title": {json.dumps(page_title, ensure_ascii=True)},
          "job_url": {json.dumps(job_url, ensure_ascii=True)}
        }}

        Target job description:
        {job_description}

        Candidate CV variants JSON:
        {json.dumps(cv_variants, indent=2, ensure_ascii=True)}

        Tailored CV JSON:
        {_json_block(generated_cv) if generated_cv is not None else "null"}

        Candidate story JSON:
        {_json_block(story_json) if story_json is not None else "null"}

        Write the cover letter now.
        """
    ).strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_job_description_extraction_prompt(
    text_content: str,
) -> list[dict[str, str]]:
    """
    Build messages for LLM to extract job description details from plain text.
    Extracts: job description, company, position, date, address, full/part-time, and all relevant details.
    """
    system_prompt = dedent(
        """
        You are an expert at cleaning noisy webpage text while preserving the original job posting content.

        Your task is to carefully read the provided text, which may include noise such as navigation menus, cookie banners, headers, footers, ads, repeated UI labels, unrelated links, or other non-job-related fragments.

        Your goal is not to summarize, rewrite, or reinterpret the posting. Your goal is only to remove the noise and keep the actual job-related content.

        Instructions
        Keep all job-related relevant information from the given noisy webpage text.
        Keep the original wording, formatting, and terminology of the job posting as much as possible.
        Keep the job description exactly as it appears in the source text.
        Do not rewrite, paraphrase, shorten, or improve the text.
        Do not create new text.
        Do not convert the content into a summarized job summary.
        Do not extract only selected sections while discarding valid company-related content.
        Keep company name and anything related to the company, including:
        company introduction
        company details
        team details
        culture statements
        mission/vision
        benefits
        role context
        Remove only content that is clearly noise or unrelated to the actual job posting, such as:
        navigation items
        cookie/privacy banners
        footer links
        login/signup prompts
        social sharing text
        ads
        recommendation widgets
        duplicated layout text
        unrelated webpage fragments
        If something appears to belong to the actual job posting, keep it.
        Do not fabricate or infer missing information.
        Output requirements
        Return only the cleaned job posting text.
        Preserve the structure of the original posting as much as possible.
        Keep headings, bullet points, and paragraph breaks when present.
        Do not add explanations, labels, commentary, or metadata outside the cleaned text.
        Goal

        The output should be the original job-posting content with webpage noise removed, so it can be used directly for further processing.
        """
    ).strip()

    user_prompt = dedent(
        f"""
        Please extract and organize the job posting information from the following text:

        ---
        {text_content}
        ---

        Provide the extracted job details in a well-organized, readable format.
        """
    ).strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
