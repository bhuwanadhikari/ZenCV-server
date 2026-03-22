from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class GenerateCvRequest(BaseModel):
    page_title: str = Field(min_length=1)
    job_url: str = Field(min_length=1)
    job_description: str = Field(min_length=20)
    story_json_override: Optional[Dict[str, Any]] = None


class ProcessCvHtmlRequest(BaseModel):
    raw_html: str = Field(min_length=1)


class ProcessedCvHtmlResponse(BaseModel):
    processed_text: str
    processed_html: str


class CvContactItem(BaseModel):
    label: Optional[str] = None
    value: str
    href: Optional[str] = None


class CvEntry(BaseModel):
    dateRange: str
    title: str
    organization: str
    link: str
    location: str
    bullets: List[str]
    stack: Optional[List[str]] = None


class CvSection(BaseModel):
    title: str
    entries: List[CvEntry]


class CvProfile(BaseModel):
    label: str
    summary: str


class CvSkillGroup(BaseModel):
    label: str
    items: List[str]


class CvData(BaseModel):
    name: str
    role: str
    contactLines: List[List[CvContactItem]]
    profile: CvProfile
    skillGroups: List[CvSkillGroup]
    sections: List[CvSection]


class SkillGroup(BaseModel):
    category: str
    selected_skills: List[str] = Field(min_length=1)


class ExperienceSelection(BaseModel):
    company: str
    role: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None
    selected_bullets: List[str] = Field(min_length=2, max_length=6)
    custom_bullet: str


class EducationSelection(BaseModel):
    institution: str
    degree: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None
    selected_bullets: List[str] = Field(min_length=2, max_length=6)


class GeneratedCv(BaseModel):
    professional_summary: str
    ats_keywords: List[str]
    skills: List[SkillGroup] = Field(min_length=2, max_length=2)
    work_experiences: List[ExperienceSelection] = Field(min_length=2, max_length=2)
    education: List[EducationSelection] = Field(min_length=2, max_length=2)


class GenerateCvResponse(BaseModel):
    cv: GeneratedCv


class GenerateCoverLetterRequest(BaseModel):
    page_title: str = Field(min_length=1)
    job_url: str = Field(min_length=1)
    job_description: str = Field(min_length=20)
    generated_cv: Optional[Dict[str, Any]] = None
    story_json_override: Optional[Dict[str, Any]] = None


class GenerateCoverLetterResponse(BaseModel):
    cover_letter: str
