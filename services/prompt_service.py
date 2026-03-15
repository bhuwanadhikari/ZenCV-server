from __future__ import annotations

import json
from textwrap import dedent
from typing import Any


def _json_block(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=True)


def build_cv_messages(job_description: str, story_json: dict[str, Any]) -> list[dict[str, str]]:
    system_prompt = dedent(
        """
        You are an elite resume strategist, ATS optimization specialist, and factual editor.

        Your task is to transform a candidate's structured career story into a sharply targeted CV JSON for one specific job description.

        Goals:
        1. Maximize relevance to the target role and ATS keyword alignment.
        2. Preserve factual integrity. Do not invent employers, degrees, dates, technologies, or achievements.
        3. Be selective. Pick only the strongest evidence from the supplied story.
        4. Improve phrasing for impact while staying faithful to the source material.
        5. Add exactly one custom bullet to each selected work experience. That custom bullet must:
           - sound consistent with the candidate's existing achievements,
           - directly support the target role,
           - remain truthful and defensible based on the supplied story,
           - avoid fabricated metrics unless the source supports them.

        Selection rules:
        - Select exactly 2 work experiences.
        - For each selected work experience, include exactly 3 source bullet points from the input plus 1 custom bullet point.
        - Select exactly 2 education entries.
        - For each selected education entry, include exactly 3 source bullet points from the input.
        - Select exactly 2 skill categories.
        - For each selected skill category, include exactly 5 skills.

        Writing rules:
        - Prioritize overlap with the target job's responsibilities, technologies, seniority, domain, and business outcomes.
        - Make bullets concise, action-oriented, and ATS friendly.
        - Prefer concrete language over buzzwords.
        - If the job description emphasizes leadership, ownership, collaboration, scale, architecture, product impact, or delivery, reflect that when supported by the input.
        - The professional summary should be 3 to 4 sentences, compelling, specific, and ATS rich.
        - ATS keywords should be a clean list of the most valuable terms actually supported by the candidate story.

        Output contract:
        - Return valid JSON only.
        - Do not wrap the JSON in markdown.
        - Use this exact schema:
          {
            "professional_summary": "string",
            "ats_keywords": ["string"],
            "skills": [
              {
                "category": "string",
                "selected_skills": ["string", "string", "string", "string", "string"]
              }
            ],
            "work_experiences": [
              {
                "company": "string",
                "role": "string",
                "start_date": "string or null",
                "end_date": "string or null",
                "location": "string or null",
                "selected_bullets": ["string", "string", "string"],
                "custom_bullet": "string"
              }
            ],
            "education": [
              {
                "institution": "string",
                "degree": "string",
                "start_date": "string or null",
                "end_date": "string or null",
                "location": "string or null",
                "selected_bullets": ["string", "string", "string"]
              }
            ]
          }
        """
    ).strip()

    user_prompt = dedent(
        f"""
        Target job description:
        {job_description}

        Candidate story JSON:
        {_json_block(story_json)}

        Produce the targeted CV JSON now.
        """
    ).strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_cover_letter_messages(
    job_description: str,
    generated_cv: dict[str, Any],
    story_json: dict[str, Any],
) -> list[dict[str, str]]:
    system_prompt = dedent(
        """
        You are an expert cover-letter writer focused on three things at once:
        1. genuine narrative quality,
        2. strong ATS alignment,
        3. strict factual consistency.

        You will receive:
        - the target job description,
        - a tailored CV JSON already optimized for the role,
        - the broader candidate story JSON.

        Your job is to write a compelling cover letter that feels like a believable career story, not a generic template.

        Requirements:
        - Use the tailored CV as the primary source of emphasis.
        - Use the broader story JSON as supporting context for depth and continuity.
        - Make the candidate's journey feel intentional and interesting to a hiring manager.
        - Reflect the job's priorities, terminology, and likely ATS keywords.
        - Keep the tone confident, warm, and professional.
        - Do not fabricate facts, employers, education, tools, or quantified outcomes.
        - Avoid placeholder text such as company name brackets unless the source actually contains a name.
        - Avoid exaggerated flattery and generic claims.

        Structure:
        - 4 to 6 paragraphs.
        - Open with role alignment and motivation.
        - Middle paragraphs should connect the candidate's strongest experiences and skills to the target role.
        - Include evidence of ownership, outcomes, collaboration, and technical depth when supported.
        - End with a forward-looking close.

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
        Target job description:
        {job_description}

        Tailored CV JSON:
        {_json_block(generated_cv)}

        Candidate story JSON:
        {_json_block(story_json)}

        Write the cover letter now.
        """
    ).strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
