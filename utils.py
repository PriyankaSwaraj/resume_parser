import json
import math
from datetime import datetime
from groq import Groq
from pydantic import BaseModel, Field

# ─────────────────────────────────────────────────────────────
#  DATA MODEL
# ─────────────────────────────────────────────────────────────

class ResumeData(BaseModel):
    # ── S_hygiene ──
    total_page_count: int = Field(default=1)
    extracted_links_array: list[str] = Field(default_factory=list)
    raw_email_string: str = Field(default="")
    detected_section_headers: list[str] = Field(default_factory=list)

    # ── S_realization ──
    skills_section_keywords: list[str] = Field(default_factory=list)
    project_descriptions_text_corpus: str = Field(default="")
    experience_descriptions_text_corpus: str = Field(default="")

    # ── S_complexity ──
    project_titles: list[str] = Field(default_factory=list)
    project_tech_keywords: list[list[str]] = Field(default_factory=list)
    architectural_regex_flags: list[bool] = Field(default_factory=list)

    # ── S_impact ──
    total_bullet_points_count: int = Field(default=0)
    metric_regex_match_count: int = Field(default=0)
    regex_extracted_numeric_values: list[int] = Field(default_factory=list)

    # ── S_production ──
    project_count: int = Field(default=0)
    code_repository_urls: list[str] = Field(default_factory=list)
    deployment_live_urls: list[str] = Field(default_factory=list)

    # ── S_clarity ──
    buzzword_frequency_map: dict[str, int] = Field(default_factory=dict)

    # ── S_domain ──
    domain_classification_vector: list[str] = Field(default_factory=list)

    # ── S_velocity ──
    experience_timeline_intervals: list[dict] = Field(default_factory=list)

    # ── meta ──
    candidate_name: str = Field(default="Unknown")
    graduation_year: int = Field(default=0)  


# ─────────────────────────────────────────────────────────────
#  YEAR CALCULATION 
# ─────────────────────────────────────────────────────────────

def calculate_btech_year(graduation_year: int) -> int:
    """
    Calculate B.Tech year from graduation year.
    B.Tech is a 4-year program.
    graduation_year - current_year tells us how many years are left.
    """
    if not graduation_year or graduation_year < 2000:
        return 3  # safe default

    current_year = datetime.now().year
    years_left = graduation_year - current_year

    if years_left >= 3:  return 1   # 1st year
    if years_left == 2:  return 2   # 2nd year
    if years_left == 1:  return 3   # 3rd year
    if years_left <= 0:  return 4   # 4th year / graduated
    return 3  # fallback


# ─────────────────────────────────────────────────────────────
#  SYSTEM PROMPT 
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a deterministic resume data extractor for B.Tech student resumes.
Return ONLY a valid JSON object. No markdown, no explanation, no extra keys, no comments.
Be consistent — extract exactly what is written, do not infer or assume anything not present.

Extract EXACTLY these fields:

candidate_name (string): Full name as written at the top of the resume.

graduation_year (int): The year the candidate will graduate or graduated.
  - Look for "Expected Graduation", "B.Tech (20XX-20XX)", "Batch of 20XX", degree end year.
  - Return ONLY the 4-digit end year e.g. 2026. If not found return 0.

total_page_count (int): Number of pages. Default 1 if unclear.

extracted_links_array (array of strings): Every URL found verbatim — GitHub, LinkedIn, LeetCode, Codeforces, portfolio, Vercel, Netlify, etc. Include ALL links found.

raw_email_string (string): Email address exactly as written. Empty string if not found.

detected_section_headers (array of strings): All section headings exactly as they appear e.g. ["EDUCATION","PROJECTS","TECHNICAL SKILLS","EXPERIENCE"].

skills_section_keywords (array of strings): ONLY skills from the dedicated Skills/Technical Skills section. Do NOT include skills mentioned elsewhere.

project_descriptions_text_corpus (string): ALL text from the Projects section concatenated into one string.

experience_descriptions_text_corpus (string): ALL text from Experience/Internships section concatenated into one string.

project_titles (array of strings): Title of each project, in order listed.

project_tech_keywords (array of arrays of strings): For each project, list ONLY tech keywords explicitly mentioned FOR THAT PROJECT. Same order as project_titles. Use the project's own tech stack, not the skills section.

architectural_regex_flags (array of booleans): For each project, true ONLY if the project explicitly mentions ANY of these: WebSockets, Kafka, Docker, Kubernetes, Redis, CI/CD, gRPC, Microservices, Distributed Systems, AWS, GCP, Azure, Celery, RabbitMQ. Same order as project_titles.

total_bullet_points_count (int): Count of bullet points (lines starting with •, -, *) across Projects AND Experience sections only.

metric_regex_match_count (int): Count of bullet points that contain AT LEAST ONE number, percentage, ms, users, $, Rs, or similar metric. Count bullets, not occurrences.

regex_extracted_numeric_values (array of integers): For each metric bullet, extract ONE representative number using these rules:
  - "40%" → 40
  - "500 users" or "500+ users" → 500
  - "200ms" → 200
  - "1st place" → 100
  - "Top 10%" → 50
  - "Rs 50,000" → 50000
  - Take the LARGEST number if multiple in one bullet.
  - One integer per metric bullet, in order.

project_count (int): Total number of projects listed. Must equal length of project_titles.

code_repository_urls (array of strings): ONLY GitHub or GitLab links that are clearly project repo links. Do NOT include the user's general GitHub profile unless it's the only link.

deployment_live_urls (array of strings): ONLY live deployment links — Vercel, Netlify, Heroku, Railway, Render, AWS hosted apps, custom domains for projects. Do NOT include GitHub Pages unless it's a deployed app.

buzzword_frequency_map (object): Count exact occurrences of these words (case-insensitive) anywhere in the resume:
  passionate, detail-oriented, synergy, motivated, hardworking, team player, go-getter,
  self-starter, results-driven, dynamic, innovative, proactive
  Only include words found at least once. e.g. {"passionate": 2, "motivated": 1}

domain_classification_vector (array of strings): Map skills_section_keywords to domains from this list ONLY:
  ["Web Development","AI/ML","DevOps","Web3","CyberSecurity","Mobile","Systems","Data Engineering","UI/UX"]
  Return UNIQUE domain names only. e.g. ["Web Development","DevOps"]

experience_timeline_intervals (array of objects): Each internship/job/role as:
  {"role": "exact role title and company", "months": integer_duration, "type": "internship"}
  type must be exactly one of: "internship", "freelance", "tech_lead", "member"
  - "internship": any company internship
  - "freelance": freelance or contract work
  - "tech_lead": technical club officer, core tech team, tech head
  - "member": non-technical club role, general committee member
  Calculate months from date range if given (e.g. Jun-Aug = 2 months, May-Aug = 3 months).
  If duration not given, use 2 as default.
"""


# ─────────────────────────────────────────────────────────────
#  LLM EXTRACTION
# ─────────────────────────────────────────────────────────────

def extract_resume_data(resume_text: str, api_key: str) -> ResumeData:
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=2000,
        temperature=0.0,   # deterministic
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Extract data from this resume:\n\n{resume_text[:7000]}"}
        ]
    )
    raw = response.choices[0].message.content
    parsed = json.loads(raw)

    parsed.pop("btech_year", None)

    data = ResumeData(**parsed)

    
    data.btech_year = calculate_btech_year(data.graduation_year)

    return data


# ─────────────────────────────────────────────────────────────
#  SCORING ENGINE  
# ─────────────────────────────────────────────────────────────

TIER3_SKILLS = {"golang","go","docker","kubernetes","redis","kafka","grpc","aws","gcp","azure",
                "tensorflow","pytorch","spark","hadoop","elasticsearch","rabbitmq","celery",
                "websockets","microservices","ci/cd","jenkins","terraform"}
TIER2_SKILLS = {"python","java","javascript","typescript","react","nodejs","node.js","sql",
                "mongodb","postgresql","mysql","git","spring","fastapi","flask","django",
                "express","graphql","rest","linux","bash","c#","kotlin","swift"}

ROLE_WEIGHTS = {"internship": 15, "freelance": 10, "tech_lead": 10, "member": 3}

WEIGHTS = {
    1: {"hyg": 0.30, "real": 0.30, "comp": 0.15, "imp": 0.05, "prod": 0.05, "clar": 0.05, "dom": 0.05, "vel": 0.05},
    2: {"hyg": 0.25, "real": 0.25, "comp": 0.20, "imp": 0.05, "prod": 0.10, "clar": 0.05, "dom": 0.05, "vel": 0.05},
    3: {"hyg": 0.15, "real": 0.20, "comp": 0.25, "imp": 0.10, "prod": 0.15, "clar": 0.05, "dom": 0.05, "vel": 0.05},
    4: {"hyg": 0.05, "real": 0.10, "comp": 0.30, "imp": 0.20, "prod": 0.15, "clar": 0.05, "dom": 0.05, "vel": 0.10},
}


def _skill_difficulty(skill: str) -> int:
    s = skill.lower().strip()
    if s in TIER3_SKILLS: return 10
    if s in TIER2_SKILLS: return 5
    return 2


def _project_tier(tech_keywords: list[str], arch_flag: bool) -> int:
    if arch_flag: return 100
    kw = {k.lower() for k in tech_keywords}
    if kw & TIER3_SKILLS: return 100
    has_backend = bool(kw & {"nodejs","node.js","express","django","flask","fastapi","spring","java","python","golang"})
    has_db = bool(kw & {"mongodb","postgresql","mysql","sql","redis","firebase","supabase"})
    if has_backend and has_db: return 65
    return 25


def compute_score(data: ResumeData) -> dict:
    eps = 1.0

    # ── 1. S_hygiene ──
    P = max(data.total_page_count, 1)
    links_lower = [l.lower() for l in data.extracted_links_array]
    has_github   = any("github"   in l for l in links_lower)
    has_linkedin = any("linkedin" in l for l in links_lower)
    L_missing = (0 if has_github else 1) + (0 if has_linkedin else 1)
    email = data.raw_email_string.lower()
    email_local = email.split("@")[0] if "@" in email else email
    E_generic = 1 if (
        any(c.isdigit() for c in email_local) or
        any(w in email_local for w in ["cool","coder","gamer","noob","pro","god","king","boss"])
    ) else 0
    mandatory = {"education", "projects", "skills"}
    found = {h.lower() for h in data.detected_section_headers}
    # also accept common variants
    if any("technical" in h or "skill" in h for h in found): found.add("skills")
    if any("project" in h for h in found): found.add("projects")
    if any("education" in h or "academic" in h for h in found): found.add("education")
    X_missing = len(mandatory - found)
    S_hygiene = max(0, 100 - 50 * max(0, P - 1) - 15 * L_missing - 25 * E_generic - 20 * X_missing)

    # ── 2. S_realization ──
    declared  = set(k.lower().strip() for k in data.skills_section_keywords)
    corpus    = (data.project_descriptions_text_corpus + " " + data.experience_descriptions_text_corpus).lower()
    applied   = {k for k in declared if k in corpus}
    intersect = declared & applied
    sum_intersect = sum(math.log(_skill_difficulty(k) + 1) for k in intersect)
    sum_declared  = sum(math.log(_skill_difficulty(k) + 1) for k in declared) + eps
    S_realization = (sum_intersect / sum_declared) * 100

    # ── 3. S_complexity ──
    alpha = 5.0
    if data.project_titles:
        tiers = []
        for i, _ in enumerate(data.project_titles):
            tech = data.project_tech_keywords[i] if i < len(data.project_tech_keywords) else []
            arch = data.architectural_regex_flags[i] if i < len(data.architectural_regex_flags) else False
            tiers.append(_project_tier(tech, arch))
        max_cj = max(tiers)
        J = len(data.project_titles)
        S_complexity = min(100, max_cj + alpha * math.log(J + 1))
    else:
        S_complexity = 0.0

    # ── 4. S_impact ──
    beta   = 12.0
    values = data.regex_extracted_numeric_values or []
    S_impact = min(100, beta * sum(math.log10(v + 1) for v in values if v > 0))

    # ── 5. S_production ──
    J_total  = max(data.project_count, 1)
    J_code   = len(data.code_repository_urls)
    J_deploy = len(data.deployment_live_urls)
    S_production = ((J_code + J_deploy) / (2 * J_total)) * 100

    # ── 6. S_clarity ──
    omega  = 15
    bmap   = data.buzzword_frequency_map or {}
    deduction = omega * sum(math.log(cnt + 1) for cnt in bmap.values() if cnt > 0)
    S_clarity = max(0, 100 - deduction)

    # ── 7. S_domain ──
    unique_domains = len(set(data.domain_classification_vector))
    total_skills   = len(data.skills_section_keywords) + eps
    S_domain = max(0, min(100, 100 * (1 - unique_domains / total_skills)))

    # ── 8. S_velocity ──
    velocity_sum = sum(
        e.get("months", 0) * ROLE_WEIGHTS.get(e.get("type", "member"), 3)
        for e in data.experience_timeline_intervals
    )
    S_velocity = min(100, velocity_sum)

    # ── Final ──
    year = data.btech_year if data.btech_year in WEIGHTS else 3
    W    = WEIGHTS[year]

    S_final = (
        W["hyg"]  * S_hygiene     +
        W["real"] * S_realization +
        W["comp"] * S_complexity  +
        W["imp"]  * S_impact      +
        W["prod"] * S_production  +
        W["clar"] * S_clarity     +
        W["dom"]  * S_domain      +
        W["vel"]  * S_velocity
    )
    S_final = round(min(100, max(0, S_final)), 2)

    return {
        "final_score":    S_final,
        "btech_year":     year,
        "graduation_year": data.graduation_year,
        "weights":        W,
        "S_hygiene":      round(S_hygiene, 2),
        "S_realization":  round(S_realization, 2),
        "S_complexity":   round(S_complexity, 2),
        "S_impact":       round(S_impact, 2),
        "S_production":   round(S_production, 2),
        "S_clarity":      round(S_clarity, 2),
        "S_domain":       round(S_domain, 2),
        "S_velocity":     round(S_velocity, 2),
        "L_missing":      L_missing,
        "E_generic":      E_generic,
        "X_missing":      X_missing,
        "buzzwords_found": bmap,
    }
