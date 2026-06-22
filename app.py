import streamlit as st
import json
import re
import time
from groq import Groq
import PyPDF2
import docx
import io
from collections import Counter
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ResumeIQ · AI Agent",
    page_icon="🧠",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* Main background */
.main .block-container { padding-top: 2rem; max-width: 1200px; }

/* Score ring */
.score-ring {
    width: 120px; height: 120px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 2rem; font-weight: 700;
    margin: 0 auto 1rem;
    box-shadow: 0 0 30px rgba(99,102,241,0.4);
}

/* Metric cards */
.metric-card {
    background: linear-gradient(135deg, #1e2530 0%, #252d3a 100%);
    border: 1px solid #2d3748;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
    transition: transform 0.2s, box-shadow 0.2s;
}
.metric-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(0,0,0,0.3);
}

/* Skill badges */
.skill-badge {
    display: inline-block;
    background: #312e81;
    color: #a5b4fc !important;
    border: 1px solid #4f46e5;
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 0.8rem;
    font-weight: 500;
    margin: 3px;
    font-family: 'JetBrains Mono', monospace;
}

/* Pattern insight boxes */
.pattern-box {
    background: linear-gradient(135deg, #1a1f2e 0%, #1e2840 100%);
    border-left: 3px solid #6366f1;
    border-radius: 0 8px 8px 0;
    padding: 1rem 1.25rem;
    margin: 0.75rem 0;
    font-size: 0.9rem;
    color: #cbd5e1;
}
.pattern-box.warning { border-left-color: #f59e0b; }
.pattern-box.success { border-left-color: #10b981; }
.pattern-box.danger  { border-left-color: #ef4444; }

/* Hero header */
.hero {
    background: linear-gradient(135deg, #0f1117 0%, #1a1f36 50%, #0f1117 100%);
    border: 1px solid #2d3748;
    border-radius: 16px;
    padding: 2.5rem;
    text-align: center;
    margin-bottom: 2rem;
    position: relative;
    overflow: hidden;
}
.hero::before {
    content: '';
    position: absolute;
    top: -50%; left: -50%;
    width: 200%; height: 200%;
    background: radial-gradient(ellipse at center, rgba(99,102,241,0.08) 0%, transparent 60%);
    pointer-events: none;
}
.hero h1 { font-size: 2.4rem; font-weight: 700; color: #f1f5f9; margin: 0 0 0.5rem; }
.hero p  { color: #94a3b8; font-size: 1.05rem; margin: 0; }
.hero .accent { color: #818cf8; }

/* Section titles */
.section-title {
    font-size: 1.15rem;
    font-weight: 600;
    color: #e2e8f0;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #2d3748;
    margin-bottom: 1rem;
}

/* Timeline items */
.timeline-item {
    border-left: 2px solid #4f46e5;
    padding: 0.75rem 0 0.75rem 1.25rem;
    margin-bottom: 0.75rem;
    position: relative;
}
.timeline-item::before {
    content: '';
    width: 10px; height: 10px;
    background: #6366f1;
    border-radius: 50%;
    position: absolute;
    left: -6px; top: 1rem;
}
.timeline-date { font-size: 0.75rem; color: #6366f1; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
.timeline-title { font-weight: 600; color: #f1f5f9; margin: 0.25rem 0 0.1rem; }
.timeline-sub { color: #94a3b8; font-size: 0.85rem; }

/* Tab styling */
.stTabs [data-baseweb="tab-list"] { gap: 0.5rem; border-bottom: 1px solid #2d3748; }
.stTabs [data-baseweb="tab"] {
    background: transparent;
    color: #64748b;
    border-radius: 8px 8px 0 0;
    font-weight: 500;
    padding: 0.6rem 1.2rem;
}
.stTabs [aria-selected="true"] {
    background: #1e2530 !important;
    color: #818cf8 !important;
    border-bottom: 2px solid #6366f1 !important;
}

/* Upload area */
.uploadedFile { border-radius: 10px; }

/* Hide streamlit branding and sidebar toggle */
#MainMenu, footer, header { visibility: hidden; }
section[data-testid="stSidebar"] { display: none; }
button[data-testid="collapsedControl"] { display: none; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_text_from_pdf(file_bytes):
    reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)

def extract_text_from_docx(file_bytes):
    doc = docx.Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs)

def extract_text_from_txt(file_bytes):
    return file_bytes.decode("utf-8", errors="ignore")

def extract_resume_text(uploaded_file):
    raw = uploaded_file.read()
    name = uploaded_file.name.lower()
    if name.endswith(".pdf"):  return extract_text_from_pdf(raw)
    if name.endswith(".docx"): return extract_text_from_docx(raw)
    return extract_text_from_txt(raw)

def call_groq(client, messages, model, temperature=0.3, max_tokens=4096):
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content

def clean_json(text):
    """Strip markdown code fences and return clean JSON string."""
    text = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
    return text


# ── Prompts ───────────────────────────────────────────────────────────────────

PARSE_PROMPT = """You are an expert resume parser. Extract ALL information from the resume text below and return ONLY a valid JSON object — no prose, no markdown fences.

Schema:
{
  "name": "",
  "email": "",
  "phone": "",
  "location": "",
  "linkedin": "",
  "github": "",
  "portfolio": "",
  "summary": "",
  "total_experience_years": 0,
  "experience": [
    {"title": "", "company": "", "duration": "", "start_year": 0, "end_year": 0, "description": ""}
  ],
  "education": [
    {"degree": "", "institution": "", "year": 0, "gpa": "", "honors": ""}
  ],
  "skills": {
    "technical": [],
    "soft": [],
    "tools": [],
    "languages": [],
    "frameworks": [],
    "certifications": []
  },
  "projects": [
    {"name": "", "description": "", "tech_stack": [], "impact": ""}
  ],
  "achievements": [],
  "publications": [],
  "volunteer": []
}

Resume:
"""

FEEDBACK_PROMPT = """You are a senior career coach and recruiter with 15+ years experience. Analyze this parsed resume JSON and provide deeply actionable feedback.

Return ONLY a valid JSON object:
{
  "overall_score": 0,
  "grade": "",
  "executive_summary": "",
  "section_scores": {
    "contact_info": {"score": 0, "max": 10, "comment": ""},
    "summary": {"score": 0, "max": 10, "comment": ""},
    "experience": {"score": 0, "max": 30, "comment": ""},
    "skills": {"score": 0, "max": 20, "comment": ""},
    "education": {"score": 0, "max": 15, "comment": ""},
    "projects": {"score": 0, "max": 10, "comment": ""},
    "achievements": {"score": 0, "max": 5, "comment": ""}
  },
  "strengths": [],
  "critical_improvements": [
    {"issue": "", "why_it_matters": "", "fix": "", "priority": "high|medium|low"}
  ],
  "ats_compatibility": {
    "score": 0,
    "issues": [],
    "keywords_missing": []
  },
  "action_verbs_analysis": {
    "found": [],
    "weak_verbs": [],
    "suggestions": []
  },
  "quantification_score": 0,
  "readability_score": 0,
  "career_level": ""
}

Resume JSON:
"""

PATTERN_PROMPT = """You are a behavioral data scientist specializing in career intelligence. Analyze this resume JSON and uncover hidden patterns, trends, and insights a human reviewer would miss.

Return ONLY a valid JSON object:
{
  "career_trajectory": {
    "pattern": "",
    "velocity": "",
    "direction": "",
    "pivots": []
  },
  "skill_evolution": {
    "emerging_skills": [],
    "declining_skills": [],
    "core_skills": [],
    "skill_gaps": [],
    "future_recommendation": ""
  },
  "experience_patterns": {
    "avg_tenure_months": 0,
    "job_hopping_risk": "",
    "promotion_indicators": [],
    "industry_diversity": ""
  },
  "personality_signals": {
    "work_style": "",
    "leadership_indicators": [],
    "collaboration_signals": [],
    "innovation_signals": []
  },
  "market_positioning": {
    "target_roles": [],
    "salary_band": "",
    "competitive_advantages": [],
    "market_gaps": []
  },
  "hidden_insights": [],
  "red_flags": [],
  "green_flags": [],
  "career_prediction": ""
}

Resume JSON:
"""


# ── Config — paste your values here ────────────────────────────────────────────────────────

GROQ_API_KEY = st.secrets["GROQ_API_KEY"]   
MODEL        = "llama-3.3-70b-versatile"
TARGET_ROLE  = ""                       # optional e.g. "Senior ML Engineer"

# ────────────────────────────────────────────────────────────────────────────

groq_key     = GROQ_API_KEY
model_choice = MODEL
target_role  = TARGET_ROLE
run_parse = run_feedback = run_patterns = True


# ── Main ──────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="hero">
  <h1>🧠 Resume<span class="accent">IQ</span></h1>
  <p>AI-powered resume parsing · deep feedback · hidden pattern discovery</p>
</div>
""", unsafe_allow_html=True)

uploaded = st.file_uploader(
    "Drop your resume here",
    type=["pdf", "docx", "txt"],
    help="PDF, DOCX, or TXT — max 10 MB",
)

if uploaded and groq_key:
    client = Groq(api_key=groq_key)

    with st.spinner("📖 Extracting text from resume..."):
        resume_text = extract_resume_text(uploaded)

    if not resume_text.strip():
        st.error("Could not extract text. Try a different format.")
        st.stop()

    st.success(f"✅ Extracted **{len(resume_text.split())} words** from `{uploaded.name}`")

    # ── Run Agent ────────────────────────────────────────────────────────────
    parsed_data = feedback_data = pattern_data = None

    if run_parse:
        with st.status("🤖 Agent parsing resume…", expanded=True) as status:
            st.write("Sending to Groq LLM…")
            raw = call_groq(client,
                [{"role": "user", "content": PARSE_PROMPT + resume_text}],
                model_choice)
            try:
                parsed_data = json.loads(clean_json(raw))
                st.write("✅ Resume parsed successfully")
            except json.JSONDecodeError:
                st.error("JSON parse error — raw model output shown below")
                st.code(raw)
            status.update(label="✅ Parse complete", state="complete")

    if run_feedback and parsed_data:
        extra = f"\n\nTarget Role Context: {target_role}" if target_role else ""
        with st.status("📊 Generating feedback…", expanded=True) as status:
            raw = call_groq(client,
                [{"role": "user", "content": FEEDBACK_PROMPT + json.dumps(parsed_data) + extra}],
                model_choice, temperature=0.4)
            try:
                feedback_data = json.loads(clean_json(raw))
                st.write("✅ Feedback generated")
            except:
                st.error("Could not parse feedback JSON"); st.code(raw)
            status.update(label="✅ Feedback ready", state="complete")

    if run_patterns and parsed_data:
        with st.status("🔍 Discovering hidden patterns…", expanded=True) as status:
            raw = call_groq(client,
                [{"role": "user", "content": PATTERN_PROMPT + json.dumps(parsed_data)}],
                model_choice, temperature=0.5)
            try:
                pattern_data = json.loads(clean_json(raw))
                st.write("✅ Patterns discovered")
            except:
                st.error("Could not parse pattern JSON"); st.code(raw)
            status.update(label="✅ Patterns found", state="complete")

    # ── Tabs ─────────────────────────────────────────────────────────────────
    tabs = st.tabs(["👤 Profile", "📊 Feedback", "🔍 Patterns", "📄 Raw"])

    # ── TAB 1: PROFILE ────────────────────────────────────────────────────────
    with tabs[0]:
        if parsed_data:
            p = parsed_data
            c1, c2, c3 = st.columns([1,1,1])
            with c1:
                st.markdown(f"""
                <div class='metric-card'>
                  <div style='color:#94a3b8;font-size:0.8rem;'>CANDIDATE</div>
                  <div style='font-size:1.4rem;font-weight:700;color:#f1f5f9;margin-top:4px;'>{p.get('name','—')}</div>
                  <div style='color:#94a3b8;font-size:0.85rem;margin-top:4px;'>{p.get('email','')}</div>
                  <div style='color:#94a3b8;font-size:0.85rem;'>{p.get('location','')}</div>
                </div>""", unsafe_allow_html=True)
            with c2:
                st.markdown(f"""
                <div class='metric-card'>
                  <div style='color:#94a3b8;font-size:0.8rem;'>EXPERIENCE</div>
                  <div style='font-size:2rem;font-weight:700;color:#818cf8;margin-top:4px;'>{p.get('total_experience_years','?')} <span style='font-size:1rem;color:#94a3b8;'>yrs</span></div>
                  <div style='color:#94a3b8;font-size:0.85rem;margin-top:4px;'>{len(p.get('experience',[]))} roles · {len(p.get('education',[]))} degrees</div>
                </div>""", unsafe_allow_html=True)
            with c3:
                links = []
                if p.get('linkedin'): links.append(f"<a href='{p['linkedin']}' style='color:#818cf8;'>LinkedIn</a>")
                if p.get('github'):   links.append(f"<a href='{p['github']}'   style='color:#818cf8;'>GitHub</a>")
                if p.get('portfolio'):links.append(f"<a href='{p['portfolio']}' style='color:#818cf8;'>Portfolio</a>")
                st.markdown(f"""
                <div class='metric-card'>
                  <div style='color:#94a3b8;font-size:0.8rem;'>LINKS</div>
                  <div style='margin-top:8px;line-height:2;'>{'<br>'.join(links) if links else '<span style="color:#4a5568;">None found</span>'}</div>
                </div>""", unsafe_allow_html=True)

            # Summary
            if p.get('summary'):
                st.markdown("<div class='section-title'>Professional Summary</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='pattern-box success'>{p['summary']}</div>", unsafe_allow_html=True)

            # Skills
            skills = p.get('skills', {})
            if any(skills.values()):
                st.markdown("<div class='section-title'>Skills</div>", unsafe_allow_html=True)
                for category, items in skills.items():
                    if items:
                        badges = " ".join(f"<span class='skill-badge'>{s}</span>" for s in items)
                        st.markdown(f"<div style='margin-bottom:0.75rem;'><span style='color:#4a5568;font-size:0.75rem;text-transform:uppercase;letter-spacing:0.08em;'>{category.replace('_',' ')}</span><br>{badges}</div>", unsafe_allow_html=True)

            # Experience
            exp = p.get('experience', [])
            if exp:
                st.markdown("<div class='section-title'>Experience</div>", unsafe_allow_html=True)
                for e in exp:
                    st.markdown(f"""
                    <div class='timeline-item'>
                      <div class='timeline-date'>{e.get('duration','')}</div>
                      <div class='timeline-title'>{e.get('title','')}</div>
                      <div class='timeline-sub'>{e.get('company','')}</div>
                      <div style='color:#64748b;font-size:0.83rem;margin-top:4px;'>{e.get('description','')[:200]}{'…' if len(e.get('description',''))>200 else ''}</div>
                    </div>""", unsafe_allow_html=True)

            # Education
            edu = p.get('education', [])
            if edu:
                st.markdown("<div class='section-title'>Education</div>", unsafe_allow_html=True)
                for e in edu:
                    gpa = f" · GPA {e['gpa']}" if e.get('gpa') else ""
                    st.markdown(f"""
                    <div class='timeline-item'>
                      <div class='timeline-date'>{e.get('year','')}</div>
                      <div class='timeline-title'>{e.get('degree','')}</div>
                      <div class='timeline-sub'>{e.get('institution','')}{gpa}</div>
                    </div>""", unsafe_allow_html=True)

    # ── TAB 2: FEEDBACK ───────────────────────────────────────────────────────
    with tabs[1]:
        if feedback_data:
            f = feedback_data
            score = f.get('overall_score', 0)
            grade = f.get('grade', 'N/A')
            color = "#10b981" if score >= 75 else "#f59e0b" if score >= 50 else "#ef4444"

            c1, c2 = st.columns([1, 2])
            with c1:
                st.markdown(f"""
                <div class='metric-card' style='text-align:center;'>
                  <div style='font-size:4rem;font-weight:800;color:{color};line-height:1;'>{score}</div>
                  <div style='font-size:1.5rem;color:#94a3b8;margin-top:4px;'>Grade: <b style='color:{color};'>{grade}</b></div>
                  <div style='color:#64748b;font-size:0.8rem;margin-top:8px;'>Overall Resume Score</div>
                </div>""", unsafe_allow_html=True)

                # Mini scores
                for k, v in f.get('section_scores', {}).items():
                    pct = int(v['score'] / v['max'] * 100) if v['max'] else 0
                    bar_color = "#10b981" if pct >= 70 else "#f59e0b" if pct >= 40 else "#ef4444"
                    st.markdown(f"""
                    <div style='margin-bottom:10px;'>
                      <div style='display:flex;justify-content:space-between;font-size:0.8rem;color:#94a3b8;margin-bottom:3px;'>
                        <span>{k.replace('_',' ').title()}</span><span>{v['score']}/{v['max']}</span>
                      </div>
                      <div style='background:#1e2530;border-radius:4px;height:6px;'>
                        <div style='width:{pct}%;height:6px;background:{bar_color};border-radius:4px;'></div>
                      </div>
                    </div>""", unsafe_allow_html=True)

            with c2:
                st.markdown(f"<div class='pattern-box success'><b>Executive Summary:</b><br>{f.get('executive_summary','')}</div>", unsafe_allow_html=True)

                # Career level
                if f.get('career_level'):
                    st.markdown(f"<div class='pattern-box'><b>🎯 Career Level:</b> {f['career_level']}</div>", unsafe_allow_html=True)

                # Strengths
                strengths = f.get('strengths', [])
                if strengths:
                    st.markdown("<div class='section-title'>✅ Strengths</div>", unsafe_allow_html=True)
                    for s in strengths:
                        st.markdown(f"<div class='pattern-box success'>✓ {s}</div>", unsafe_allow_html=True)

                # Improvements
                improvements = f.get('critical_improvements', [])
                if improvements:
                    st.markdown("<div class='section-title'>⚡ Critical Improvements</div>", unsafe_allow_html=True)
                    for imp in improvements:
                        p_color = {"high":"danger","medium":"warning","low":""}.get(imp.get('priority',''), "")
                        st.markdown(f"""
                        <div class='pattern-box {p_color}'>
                          <b>🔸 {imp.get('issue','')}</b>
                          <div style='margin-top:6px;color:#94a3b8;font-size:0.85rem;'><i>Why it matters:</i> {imp.get('why_it_matters','')}</div>
                          <div style='margin-top:4px;color:#a5b4fc;font-size:0.85rem;'><i>Fix:</i> {imp.get('fix','')}</div>
                          <div style='margin-top:4px;'><span style='background:#1e2530;padding:2px 8px;border-radius:10px;font-size:0.7rem;color:#94a3b8;'>Priority: {imp.get('priority','').upper()}</span></div>
                        </div>""", unsafe_allow_html=True)

            # ATS Section
            ats = f.get('ats_compatibility', {})
            if ats:
                st.markdown("---")
                st.markdown("<div class='section-title'>🤖 ATS Compatibility</div>", unsafe_allow_html=True)
                a1, a2 = st.columns(2)
                with a1:
                    ats_score = ats.get('score', 0)
                    ats_col = "#10b981" if ats_score >= 70 else "#f59e0b" if ats_score >= 40 else "#ef4444"
                    st.markdown(f"<div class='metric-card' style='text-align:center;'><div style='font-size:2.5rem;font-weight:700;color:{ats_col};'>{ats_score}%</div><div style='color:#94a3b8;'>ATS Score</div></div>", unsafe_allow_html=True)
                    for issue in ats.get('issues', []):
                        st.markdown(f"<div class='pattern-box warning'>⚠ {issue}</div>", unsafe_allow_html=True)
                with a2:
                    missing_kw = ats.get('keywords_missing', [])
                    if missing_kw:
                        st.markdown("<b style='color:#94a3b8;font-size:0.85rem;'>Missing Keywords:</b>", unsafe_allow_html=True)
                        badges = " ".join(f"<span class='skill-badge' style='background:#3b1f1f;color:#fca5a5;border-color:#7f1d1d;'>{k}</span>" for k in missing_kw)
                        st.markdown(badges, unsafe_allow_html=True)

            # Quantification score chart
            q_score = f.get('quantification_score', 0)
            r_score = f.get('readability_score', 0)
            if q_score or r_score:
                st.markdown("---")
                fig = go.Figure(go.Bar(
                    x=["Quantification", "Readability", "ATS"],
                    y=[q_score, r_score, ats.get('score', 0)],
                    marker_color=["#6366f1", "#8b5cf6", "#a78bfa"],
                    text=[f"{v}%" for v in [q_score, r_score, ats.get('score', 0)]],
                    textposition="outside",
                ))
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#94a3b8", height=280,
                    yaxis=dict(range=[0, 110], gridcolor="#1e2530"),
                    xaxis=dict(gridcolor="#1e2530"),
                    margin=dict(t=20, b=20, l=0, r=0),
                )
                st.plotly_chart(fig, use_container_width=True)

    # ── TAB 3: PATTERNS ───────────────────────────────────────────────────────
    with tabs[2]:
        if pattern_data:
            pd_data = pattern_data

            c1, c2 = st.columns(2)
            with c1:
                # Career trajectory
                traj = pd_data.get('career_trajectory', {})
                if traj:
                    st.markdown("<div class='section-title'>🚀 Career Trajectory</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='pattern-box success'><b>Pattern:</b> {traj.get('pattern','')}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='pattern-box'><b>Velocity:</b> {traj.get('velocity','')}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='pattern-box'><b>Direction:</b> {traj.get('direction','')}</div>", unsafe_allow_html=True)
                    for pivot in traj.get('pivots', []):
                        st.markdown(f"<div class='pattern-box warning'>↪ Career Pivot: {pivot}</div>", unsafe_allow_html=True)

                # Experience patterns
                exp_pat = pd_data.get('experience_patterns', {})
                if exp_pat:
                    st.markdown("<div class='section-title'>⏱ Experience Patterns</div>", unsafe_allow_html=True)
                    tenure = exp_pat.get('avg_tenure_months', 0)
                    hopping = exp_pat.get('job_hopping_risk', '')
                    hop_color = "danger" if "high" in hopping.lower() else "warning" if "medium" in hopping.lower() else "success"
                    st.markdown(f"<div class='pattern-box'><b>Avg Tenure:</b> {tenure} months</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='pattern-box {hop_color}'><b>Job Hopping Risk:</b> {hopping}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='pattern-box'><b>Industry Diversity:</b> {exp_pat.get('industry_diversity','')}</div>", unsafe_allow_html=True)
                    for pi in exp_pat.get('promotion_indicators', []):
                        st.markdown(f"<div class='pattern-box success'>⬆ {pi}</div>", unsafe_allow_html=True)

            with c2:
                # Skill evolution
                skill_evo = pd_data.get('skill_evolution', {})
                if skill_evo:
                    st.markdown("<div class='section-title'>📈 Skill Evolution</div>", unsafe_allow_html=True)
                    if skill_evo.get('emerging_skills'):
                        st.markdown("<b style='color:#10b981;font-size:0.85rem;'>Emerging 🔼</b>", unsafe_allow_html=True)
                        st.markdown(" ".join(f"<span class='skill-badge' style='border-color:#10b981;color:#6ee7b7;background:#064e3b;'>{s}</span>" for s in skill_evo['emerging_skills']), unsafe_allow_html=True)
                    if skill_evo.get('core_skills'):
                        st.markdown("<b style='color:#818cf8;font-size:0.85rem;margin-top:8px;display:block;'>Core 💎</b>", unsafe_allow_html=True)
                        st.markdown(" ".join(f"<span class='skill-badge'>{s}</span>" for s in skill_evo['core_skills']), unsafe_allow_html=True)
                    if skill_evo.get('skill_gaps'):
                        st.markdown("<b style='color:#ef4444;font-size:0.85rem;margin-top:8px;display:block;'>Gaps ⚠</b>", unsafe_allow_html=True)
                        st.markdown(" ".join(f"<span class='skill-badge' style='border-color:#ef4444;color:#fca5a5;background:#450a0a;'>{s}</span>" for s in skill_evo['skill_gaps']), unsafe_allow_html=True)
                    if skill_evo.get('future_recommendation'):
                        st.markdown(f"<div class='pattern-box success' style='margin-top:12px;'><b>💡 Recommendation:</b> {skill_evo['future_recommendation']}</div>", unsafe_allow_html=True)

                # Market positioning
                market = pd_data.get('market_positioning', {})
                if market:
                    st.markdown("<div class='section-title'>💼 Market Positioning</div>", unsafe_allow_html=True)
                    if market.get('target_roles'):
                        roles = " ".join(f"<span class='skill-badge' style='background:#1e3a5f;border-color:#3b82f6;color:#93c5fd;'>{r}</span>" for r in market['target_roles'])
                        st.markdown(f"<b style='color:#94a3b8;font-size:0.8rem;'>Best-fit roles:</b><br>{roles}", unsafe_allow_html=True)
                    if market.get('salary_band'):
                        st.markdown(f"<div class='pattern-box success' style='margin-top:8px;'><b>💰 Salary Band:</b> {market['salary_band']}</div>", unsafe_allow_html=True)
                    for adv in market.get('competitive_advantages', []):
                        st.markdown(f"<div class='pattern-box success'>✦ {adv}</div>", unsafe_allow_html=True)

            # Personality signals
            pers = pd_data.get('personality_signals', {})
            if pers:
                st.markdown("---")
                st.markdown("<div class='section-title'>🧬 Personality Signals (from writing patterns)</div>", unsafe_allow_html=True)
                p1, p2, p3 = st.columns(3)
                with p1:
                    st.markdown(f"<div class='metric-card'><b style='color:#818cf8;'>Work Style</b><br><span style='color:#e2e8f0;'>{pers.get('work_style','')}</span></div>", unsafe_allow_html=True)
                with p2:
                    leads = pers.get('leadership_indicators', [])
                    leads_html = "<br>".join("<span style='color:#e2e8f0;font-size:0.85rem;'>• " + l + "</span>" for l in leads[:3])
                    st.markdown(f"<div class='metric-card'><b style='color:#818cf8;'>Leadership Signals</b><br>{leads_html}</div>", unsafe_allow_html=True)
                with p3:
                    inno = pers.get('innovation_signals', [])
                    inno_html = "<br>".join("<span style='color:#e2e8f0;font-size:0.85rem;'>• " + i + "</span>" for i in inno[:3])
                    st.markdown(f"<div class='metric-card'><b style='color:#818cf8;'>Innovation Signals</b><br>{inno_html}</div>", unsafe_allow_html=True)

            # Hidden insights, green/red flags
            st.markdown("---")
            g1, g2 = st.columns(2)
            with g1:
                green = pd_data.get('green_flags', [])
                if green:
                    st.markdown("<div class='section-title'>🟢 Green Flags</div>", unsafe_allow_html=True)
                    for g in green:
                        st.markdown(f"<div class='pattern-box success'>✅ {g}</div>", unsafe_allow_html=True)
            with g2:
                red = pd_data.get('red_flags', [])
                if red:
                    st.markdown("<div class='section-title'>🔴 Red Flags</div>", unsafe_allow_html=True)
                    for r in red:
                        st.markdown(f"<div class='pattern-box danger'>⚠ {r}</div>", unsafe_allow_html=True)

            hidden = pd_data.get('hidden_insights', [])
            if hidden:
                st.markdown("<div class='section-title'>🔮 Hidden Insights</div>", unsafe_allow_html=True)
                for h in hidden:
                    st.markdown(f"<div class='pattern-box' style='border-left-color:#8b5cf6;'>🔍 {h}</div>", unsafe_allow_html=True)

            career_pred = pd_data.get('career_prediction', '')
            if career_pred:
                st.markdown(f"""
                <div style='background:linear-gradient(135deg,#1a1429,#1e2840);border:1px solid #6366f1;border-radius:12px;padding:1.5rem;margin-top:1.5rem;text-align:center;'>
                  <div style='color:#818cf8;font-size:0.8rem;text-transform:uppercase;letter-spacing:0.1em;'>AI Career Prediction</div>
                  <div style='color:#f1f5f9;font-size:1.05rem;margin-top:8px;font-style:italic;'>{career_pred}</div>
                </div>""", unsafe_allow_html=True)

    # ── TAB 4: RAW ────────────────────────────────────────────────────────────
    with tabs[3]:
        if parsed_data:
            st.markdown("**Parsed JSON:**")
            st.json(parsed_data)
        if feedback_data:
            st.markdown("**Feedback JSON:**")
            st.json(feedback_data)
        if pattern_data:
            st.markdown("**Pattern JSON:**")
            st.json(pattern_data)
        st.markdown("**Raw Resume Text:**")
        with st.expander("Show extracted text"):
            st.text(resume_text[:3000] + ("…" if len(resume_text) > 3000 else ""))

elif uploaded and not groq_key:
    st.warning("⬅ Please enter your Groq API key in the sidebar to begin analysis.")
else:
    # Landing state
    st.markdown("""
    <div style='text-align:center;padding:3rem 0;'>
      <div style='font-size:4rem;'>📄</div>
      <div style='color:#94a3b8;font-size:1.1rem;margin-top:1rem;'>Upload a resume to get started</div>
      <div style='color:#4a5568;font-size:0.9rem;margin-top:0.5rem;'>PDF · DOCX · TXT supported</div>
    </div>
    <div style='display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;margin-top:2rem;'>
      <div class='metric-card' style='text-align:center;'>
        <div style='font-size:2rem;'>🔍</div>
        <div style='color:#f1f5f9;font-weight:600;margin-top:8px;'>Smart Parsing</div>
        <div style='color:#64748b;font-size:0.85rem;margin-top:4px;'>Extracts all structured data from any resume format</div>
      </div>
      <div class='metric-card' style='text-align:center;'>
        <div style='font-size:2rem;'>📊</div>
        <div style='color:#f1f5f9;font-weight:600;margin-top:8px;'>Deep Feedback</div>
        <div style='color:#64748b;font-size:0.85rem;margin-top:4px;'>Scored sections, ATS analysis, actionable fixes</div>
      </div>
      <div class='metric-card' style='text-align:center;'>
        <div style='font-size:2rem;'>🧬</div>
        <div style='color:#f1f5f9;font-weight:600;margin-top:8px;'>Hidden Patterns</div>
        <div style='color:#64748b;font-size:0.85rem;margin-top:4px;'>Career trajectory, skill evolution, personality signals</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

