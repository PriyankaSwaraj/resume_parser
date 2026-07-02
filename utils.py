import json
import math
from openai import OpenAI
from pydantic import BaseModel, Field


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
    experience_timeline_intervals: list[dict] = Field(default_factory=list)  # [{role, months, type}]

    # ── meta ──
    candidate_name: str = Field(default="Unknown")
    btech_year: int = Field(default=3)   # 2, 3, or 4


#  SYSTEM PROMPT

SYSTEM_PROMPT = """You are a precise resume data extractor for B.Tech student resumes.
Return ONLY a valid JSON object — no markdown, no explanation, no extra keys.

Extract EXACTLY these fields:

total_page_count (int): Number of pages in the resume.

extracted_links_array (array of strings): Every URL/link found (GitHub, LinkedIn, portfolio, Vercel, Netlify, etc.).

raw_email_string (string): The email address found on the resume.

detected_section_headers (array of strings): All section headings found, e.g. ["Education","Projects","Skills","Experience"].

skills_section_keywords (array of strings): ONLY skills listed in the dedicated Skills section.

project_descriptions_text_corpus (string): All text from the Projects section concatenated.

experience_descriptions_text_corpus (string): All text from Experience/Internships section concatenated.

project_titles (array of strings): Title of each project listed.

project_tech_keywords (array of arrays of strings): For each project, the tech keywords used IN THAT PROJECT (same order as project_titles).

architectural_regex_flags (array of booleans): For each project, true if it uses any of: WebSockets, Kafka, Docker, Kubernetes, Redis, CI/CD, gRPC, Microservices, Distributed Systems, AWS, GCP, Azure, Celery, RabbitMQ. Same order as project_titles.

total_bullet_points_count (int): Total bullet points across Projects and Experience sections.

metric_regex_match_count (int): Count of bullet points containing numbers/percentages/ms/users/$. e.g. "40%", "500 users", "200ms".

regex_extracted_numeric_values (array of integers): For each metric bullet, extract the numeric value:
  - Percentages: raw integer (40% -> 40)
  - Users/scale: raw count (500 users -> 500)
  - Latency: ms value (200ms -> 200)
  - 1st place -> 100, Top 10% -> 50

project_count (int): Total number of projects.

code_repository_urls (array of strings): Only GitHub/GitLab repo links for projects.

deployment_live_urls (array of strings): Only live deployment links (Vercel, Netlify, Heroku, AWS link, custom domain for a project).

buzzword_frequency_map (object): Count occurrences of these EXACT words anywhere in the resume:
  ["passionate","detail-oriented","synergy","motivated","hardworking","team player","go-getter","self-starter","results-driven","dynamic","innovative","proactive"]
  Only include words that appear at least once. e.g. {"passionate": 2, "motivated": 1}

domain_classification_vector (array of strings): Map skills_section_keywords to these domains only:
  ["Web Development","AI/ML","DevOps","Web3","CyberSecurity","Mobile","Systems","Data Engineering","UI/UX"]
  List only UNIQUE domains found. e.g. ["Web Development","DevOps"]

experience_timeline_intervals (array of objects): Each experience entry as:
  {"role": "SDE Intern at Google", "months": 3, "type": "internship"}
  type must be one of: "internship", "freelance", "tech_lead", "member"
  Classify campus technical roles as "tech_lead", non-technical club roles as "member".

candidate_name (string): Full name of the candidate.

btech_year (int): 2, 3, or 4. Infer from graduation year or year of study mentioned. Default 3.
"""

#  LLM EXTRACTION

def extract_resume_data(resume_text: str, api_key: str) -> ResumeData:
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=2000,
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Extract data from this resume:\n\n{resume_text[:7000]}"}
        ]
    )
    raw = response.choices[0].message.content
    parsed = json.loads(raw)
    return ResumeData(**parsed)


NOISE_WORDS = {
    "passionate", "detail-oriented", "synergy", "motivated", "hardworking",
    "team player", "go-getter", "self-starter", "results-driven", "dynamic",
    "innovative", "proactive"
}

TIER3_SKILLS = {"golang","go","docker","kubernetes","redis","kafka","grpc","aws","gcp","azure",
                "tensorflow","pytorch","spark","hadoop","elasticsearch","rabbitmq","celery",
                "websockets","microservices","ci/cd","jenkins","terraform"}
TIER2_SKILLS = {"python","java","javascript","typescript","react","nodejs","node.js","sql",
                "mongodb","postgresql","mysql","git","spring","fastapi","flask","django",
                "express","graphql","rest","linux","bash","c#","kotlin","swift"}
TIER1_SKILLS = {"html","css","markdown","bootstrap","figma","canva","xml","json","jquery"}

ARCH_KEYWORDS = {"websockets","kafka","docker","kubernetes","redis","ci/cd","grpc",
                 "microservices","distributed","aws","gcp","azure","celery","rabbitmq"}

ROLE_WEIGHTS = {"internship": 15, "freelance": 10, "tech_lead": 10, "member": 3}

WEIGHTS = {
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
    """Classify a project into Tier 1/2/3 complexity score."""
    if arch_flag:
        return 100 
    kw = {k.lower() for k in tech_keywords}
    
    if kw & TIER3_SKILLS:
        return 100
    
    has_backend = bool(kw & {"nodejs","node.js","express","django","flask","fastapi","spring","java","python","golang"})
    has_db = bool(kw & {"mongodb","postgresql","mysql","sql","redis","firebase","supabase"})
    if has_backend and has_db:
        return 65
    return 25 


def compute_score(data: ResumeData) -> dict:
    eps = 1.0

    # ── 1. S_hygiene ──
    P = max(data.total_page_count, 1)
    links_lower = [l.lower() for l in data.extracted_links_array]
    has_github = any("github" in l for l in links_lower)
    has_linkedin = any("linkedin" in l for l in links_lower)
    L_missing = (0 if has_github else 1) + (0 if has_linkedin else 1)
    email = data.raw_email_string.lower()
    E_generic = 1 if any(c.isdigit() for c in email.split("@")[0]) or \
                     any(w in email for w in ["cool","coder","gamer","noob","pro","god","king","boss"]) else 0
    mandatory = {"education", "projects", "skills"}
    found = {h.lower() for h in data.detected_section_headers}
    X_missing = len(mandatory - found)
    S_hygiene = max(0, 100 - 50 * max(0, P - 1) - 15 * L_missing - 25 * E_generic - 20 * X_missing)

    # ── 2. S_realization 
    declared = set(k.lower().strip() for k in data.skills_section_keywords)
    corpus = (data.project_descriptions_text_corpus + " " + data.experience_descriptions_text_corpus).lower()
    applied = {k for k in declared if k in corpus}
    intersect = declared & applied

    sum_intersect = sum(math.log(_skill_difficulty(k) + 1) for k in intersect)
    sum_declared = sum(math.log(_skill_difficulty(k) + 1) for k in declared) + eps
    S_realization = (sum_intersect / sum_declared) * 100

    # ── 3. S_complexity 
    alpha = 5.0
    if data.project_titles:
        tiers = []
        for i, title in enumerate(data.project_titles):
            tech = data.project_tech_keywords[i] if i < len(data.project_tech_keywords) else []
            arch = data.architectural_regex_flags[i] if i < len(data.architectural_regex_flags) else False
            tiers.append(_project_tier(tech, arch))
        max_cj = max(tiers)
        J = len(data.project_titles)
        S_complexity = min(100, max_cj + alpha * math.log(J + 1))
    else:
        S_complexity = 0.0

    # ── 4. S_impact 
    beta = 12.0
    values = data.regex_extracted_numeric_values or []
    S_impact = min(100, beta * sum(math.log10(v + 1) for v in values if v > 0))

    # ── 5. S_production ──
    J_total = max(data.project_count, 1)
    J_code = len(data.code_repository_urls)
    J_deploy = len(data.deployment_live_urls)
    S_production = ((J_code + J_deploy) / (2 * J_total)) * 100

    # ── 6. S_clarity ──
    omega = 15
    bmap = data.buzzword_frequency_map or {}
    deduction = omega * sum(math.log(count + 1) for count in bmap.values() if count > 0)
    S_clarity = max(0, 100 - deduction)

    # ── 7. S_domain ──
    unique_domains = len(set(data.domain_classification_vector))
    total_skills = len(data.skills_section_keywords) + eps
    S_domain = 100 * (1 - unique_domains / total_skills)
    S_domain = max(0, min(100, S_domain))

    # ── 8. S_velocity ──
    velocity_sum = sum(
        e.get("months", 0) * ROLE_WEIGHTS.get(e.get("type", "member"), 3)
        for e in data.experience_timeline_intervals
    )
    S_velocity = min(100, velocity_sum)

    # ── FINAL SCORE ──
    year = data.btech_year if data.btech_year in WEIGHTS else 3
    W = WEIGHTS[year]

    S_final = (
        W["hyg"]  * S_hygiene +
        W["real"] * S_realization +
        W["comp"] * S_complexity +
        W["imp"]  * S_impact +
        W["prod"] * S_production +
        W["clar"] * S_clarity +
        W["dom"]  * S_domain +
        W["vel"]  * S_velocity
    )
    S_final = round(min(100, max(0, S_final)), 2)

    return {
        "final_score": S_final,
        "btech_year": year,
        "weights": W,
        "S_hygiene": round(S_hygiene, 2),
        "S_realization": round(S_realization, 2),
        "S_complexity": round(S_complexity, 2),
        "S_impact": round(S_impact, 2),
        "S_production": round(S_production, 2),
        "S_clarity": round(S_clarity, 2),
        "S_domain": round(S_domain, 2),
        "S_velocity": round(S_velocity, 2),
    
        "L_missing": L_missing,
        "E_generic": E_generic,
        "X_missing": X_missing,
        "buzzwords_found": bmap,
    }
