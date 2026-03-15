from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class GenerateCvRequest(BaseModel):
    job_description: str = Field(min_length=20)
    story_json_override: Optional[Dict[str, Any]] = None


class SkillGroup(BaseModel):
    category: str
    selected_skills: List[str] = Field(min_length=1)


class ExperienceSelection(BaseModel):
    company: str
    role: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None
    selected_bullets: List[str] = Field(min_length=3, max_length=3)
    custom_bullet: str


class EducationSelection(BaseModel):
    institution: str
    degree: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None
    selected_bullets: List[str] = Field(min_length=3, max_length=3)


class GeneratedCv(BaseModel):
    professional_summary: str
    ats_keywords: List[str]
    skills: List[SkillGroup] = Field(min_length=2, max_length=2)
    work_experiences: List[ExperienceSelection] = Field(min_length=2, max_length=2)
    education: List[EducationSelection] = Field(min_length=2, max_length=2)


class GenerateCvResponse(BaseModel):
    cv: GeneratedCv


class GenerateCoverLetterRequest(BaseModel):
    job_description: str = Field(min_length=20)
    generated_cv: Dict[str, Any]
    story_json_override: Optional[Dict[str, Any]] = None


class GenerateCoverLetterResponse(BaseModel):
    cover_letter: str
