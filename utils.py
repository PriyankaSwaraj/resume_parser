import json
import numpy as np
from pydantic import BaseModel, Field
from groq import Groq


class ResumeData(BaseModel):
    name: str = Field(default="Unknown Candidate")
    gpa: float = Field(default=0.0)
    gpa_scale: float = Field(default=10.0)
    degree: str = Field(default="")
    is_cs_related_degree: bool = Field(default=False)
    has_ds_algo: bool = Field(default=False)
    has_discrete_math: bool = Field(default=False)
    complex_projects: int = Field(default=0)
    simple_projects: int = Field(default=0)
    tech_skills: list[str] = Field(default_factory=list)
    has_internship: bool = Field(default=False)
    is_top_company_internship: bool = Field(default=False)
    competitive_achievements_count: int = Field(default=0)
    quantifiable_metrics_count: int = Field(default=0)
    action_verb_bullet_count: int = Field(default=0)
    weak_phrase_count: int = Field(default=0)
    has_standard_sections: bool = Field(default=False)
    employment_gap_months: int = Field(default=0)


SYSTEM_PROMPT = """You are a precise ATS resume parser for Indian college student resumes.
Extract the requested fields and return ONLY a valid JSON object — no markdown, no explanations.

Rules:
- name: Full name of the candidate.
- gpa: Numeric GPA if present, else 0.0.
- gpa_scale: The denominator. Default 10.0 for Indian universities, 4.0 for US.
- degree: Full degree name as written (e.g. "B.Tech Computer Science").
- is_cs_related_degree: true if degree is CS, IT, ECE, Software Engineering, Data Science, or related tech field.
- has_ds_algo: true if DSA, Data Structures, Algorithms, LeetCode, or competitive programming appears.
- has_discrete_math: true if Discrete Math, Logic, Graph Theory, Combinatorics appears.
- complex_projects: count of complex engineering projects (ML systems, compilers, OS, blockchain, embedded, distributed systems).
- simple_projects: count of basic web apps, CRUD apps, landing pages, portfolio sites, tutorial projects.
- tech_skills: all programming languages, frameworks, databases, tools explicitly listed.
- has_internship: true if any internship at any company is present.
- is_top_company_internship: true if internship is at a well-known company (Google, Microsoft, Amazon, Flipkart, Swiggy, Zomato, Razorpay, FAANG, Infosys, TCS, Wipro, HCL, Accenture, or similar recognized tech company).
- competitive_achievements_count: count of hackathon wins, competitive programming placements, published papers, open-source contributions.
- quantifiable_metrics_count: count of bullet points with concrete numbers (e.g. "reduced latency by 40%", "served 10k users", "managed 5L budget").
- action_verb_bullet_count: count of bullet points starting with strong action verbs (Optimized, Built, Architected, Implemented, Designed, Developed, Deployed, Led, Reduced, Improved, Automated, Created, Engineered, Launched, Scaled).
- weak_phrase_count: count of bullet points starting with weak phrases like "Responsible for", "Helped with", "Worked on", "Assisted in", "Was involved in".
- has_standard_sections: true if resume clearly contains standard sections like Education, Experience/Internships, Projects, Skills.
- employment_gap_months: total months of unexplained gap between education end and internship/job start. 0 if no gap or still studying.
"""


def extract_resume_data(resume_text: str, api_key: str) -> ResumeData:
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=1000,
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Parse this resume:\n\n{resume_text[:6000]}"}
        ]
    )
    raw_json = response.choices[0].message.content
    parsed = json.loads(raw_json)
    return ResumeData(**parsed)


LOW_LEVEL_LANGUAGES = {"c", "c++", "rust", "java", "go"}


def compute_score(data: ResumeData) -> dict:

    # ── 1. FORMATTING & STRUCTURAL INTEGRITY (max 15 pts) ──
    structure_score = 10.0 if data.has_standard_sections else 3.0
    formatting_score = round(structure_score, 2)

    # ── 2. ACADEMIC BASELINE (max 20 pts) ──
    gpa_scale = data.gpa_scale if data.gpa_scale > 0 else 10.0
    gpa_ratio = min(data.gpa / gpa_scale, 1.0)
    gpa_curve = gpa_ratio ** 2
    theory_bonus = (0.5 * float(data.has_ds_algo)) + (0.5 * float(data.has_discrete_math))
    degree_bonus = 1.0 if data.is_cs_related_degree else 0.6
    academic_score = round(((0.6 * gpa_curve) + (0.25 * theory_bonus) + (0.15 * degree_bonus)) * 20, 2)

    # ── 3. SKILL CORE DENSITY (max 20 pts) ──
    n = len(data.tech_skills)
    # logistic curve: optimal zone 6-12, plateau after 20, no bonus beyond 30
    logistic = 1.0 / (1.0 + np.exp(-0.4 * (n - 10)))
    # keyword stuffing penalty: if > 25 skills, apply soft penalty
    stuffing_penalty = max(0.0, (n - 25) * 0.015)
    skills_score = round(float(np.clip(logistic - stuffing_penalty, 0.0, 1.0)) * 20, 2)

    # ── 4. PROJECT & EXECUTION QUALITY (max 20 pts) ──
    raw_project = (data.complex_projects * 1.0) + (data.simple_projects * 0.4)
    project_score_norm = min(raw_project / 3.0, 1.0)
    low_level_penalty = 0.0
    if data.complex_projects > 0:
        candidate_langs = {s.lower().strip() for s in data.tech_skills}
        if not bool(candidate_langs & LOW_LEVEL_LANGUAGES):
            low_level_penalty = 0.15
    project_score = round(float(np.clip(project_score_norm - low_level_penalty, 0.0, 1.0)) * 20, 2)

    # ── 5. QUANTITATIVE IMPACT & LANGUAGE (max 15 pts) ──
    quant_norm = min(data.quantifiable_metrics_count / 6.0, 1.0)
    action_norm = min(data.action_verb_bullet_count / 8.0, 1.0)
    weak_penalty = min(data.weak_phrase_count * 0.08, 0.3)
    impact_score = round(float(np.clip((0.6 * quant_norm + 0.4 * action_norm - weak_penalty), 0.0, 1.0)) * 15, 2)

    # ── 6. EXPERIENCE & CAREER VELOCITY (max 10 pts) ──
    internship_val = 0.0
    if data.has_internship:
        internship_val = 0.7
    if data.is_top_company_internship:
        internship_val = 1.0
    gap_penalty = min(data.employment_gap_months * 0.04, 0.3)
    achievement_norm = min(np.log1p(data.competitive_achievements_count) / np.log1p(5), 1.0)
    velocity_score = round(float(np.clip((0.6 * internship_val + 0.4 * float(achievement_norm) - gap_penalty), 0.0, 1.0)) * 10, 2)

    # ── GLOBAL AGGREGATION ──
    raw_total = formatting_score + academic_score + skills_score + project_score + impact_score + velocity_score

    # bonus: high quantifiable impact
    bonus = 0.0
    if data.quantifiable_metrics_count >= 5:
        bonus = 3.0
    elif data.quantifiable_metrics_count >= 3:
        bonus = 1.5

    final_score = float(np.clip(raw_total + bonus, 0.0, 100.0))

    return {
        "final_score": round(final_score, 2),
        "formatting_score": formatting_score,
        "academic_score": academic_score,
        "skills_score": skills_score,
        "project_score": project_score,
        "impact_score": impact_score,
        "velocity_score": velocity_score,
        "bonus": bonus,
        "gpa_curve": round(float(gpa_curve), 4),
        "theory_score": round(theory_bonus, 4),
        "internship_flag": internship_val,
        "achievement_score": round(float(achievement_norm), 4),
        "low_level_penalty": low_level_penalty,
        "gap_penalty": round(gap_penalty, 4),
        "stuffing_penalty": round(float(stuffing_penalty), 4),
    }
