import json
import os
import streamlit as st
from pypdf import PdfReader
import io

from utils import extract_resume_data, compute_score

st.set_page_config(
    page_title="CS Resume Scorer",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .main-header {
        font-size: 2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #6366f1, #8b5cf6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .flag-box {
        background: #1e1e2e;
        border-radius: 10px;
        padding: 0.6rem 1rem;
        margin: 0.3rem 0;
        font-size: 0.95rem;
    }
    div[data-testid="metric-container"] {
        background: #1a1a2e;
        border: 1px solid #2d2d3f;
        border-radius: 10px;
        padding: 0.5rem 1rem;
    }
</style>
""", unsafe_allow_html=True)

api_key = os.environ.get("GROQ_API_KEY", "")

with st.sidebar:
    st.markdown("## 🎓 CS Resume Scorer")
    st.divider()
    uploaded_file = st.file_uploader("Upload Resume PDF", type=["pdf"])
    st.divider()
    dashboard = st.radio(
        "Select Dashboard",
        ["📊 Dashboard 1: Score", "🗂️ Dashboard 2: Resume Data"],
        index=0,
    )
    st.divider()
    if st.button("🗑️ Clear", use_container_width=True):
        for key in ["resume_data", "score_data", "raw_text", "processed_file"]:
            st.session_state.pop(key, None)
        st.rerun()


def extract_pdf_text(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n".join(pages).strip()


def run_pipeline(file_bytes: bytes, api_key: str):
    with st.spinner("Reading your resume..."):
        raw_text = extract_pdf_text(file_bytes)
    if not raw_text:
        st.error("Could not read this PDF. Make sure it is not a scanned image.")
        return
    with st.spinner("Analysing resume..."):
        resume_data = extract_resume_data(raw_text, api_key)
    score_data = compute_score(resume_data)
    st.session_state["raw_text"] = raw_text
    st.session_state["resume_data"] = resume_data
    st.session_state["score_data"] = score_data


st.markdown('<p class="main-header">🎓 CS Resume Scorer</p>', unsafe_allow_html=True)
st.caption("Upload your resume PDF and get an instant ATS score based on your academics, projects, and experience.")

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    file_id = hash(file_bytes)
    if st.session_state.get("processed_file") != file_id:
        if not api_key:
            st.error("⚠️ `GROQ_API_KEY` environment variable is not set. Run: `export GROQ_API_KEY=gsk_...`")
            st.stop()
        st.session_state["processed_file"] = file_id
        run_pipeline(file_bytes, api_key)
else:
    if "resume_data" not in st.session_state:
        st.info("👈 Upload your resume PDF from the sidebar to get started.")
        st.stop()

if "resume_data" not in st.session_state or "score_data" not in st.session_state:
    st.stop()

resume_data = st.session_state["resume_data"]
score_data = st.session_state["score_data"]


# ─────────────────────────────────────────────
# Dashboard 1: Score
# ─────────────────────────────────────────────
if dashboard == "📊 Dashboard 1: Score":

    final_score = score_data["final_score"]

    if final_score >= 75:
        score_color = "#22c55e"
        grade_label = "🏆 Strong Profile"
    elif final_score >= 55:
        score_color = "#6366f1"
        grade_label = "✅ Good Profile"
    elif final_score >= 35:
        score_color = "#f59e0b"
        grade_label = "⚠️ Average Profile"
    else:
        score_color = "#ef4444"
        grade_label = "❌ Needs Work"

    st.markdown("---")

    col_score, col_info, col_flags = st.columns([1.2, 1.5, 1.5])

    with col_score:
        st.markdown(f"""
        <div style="text-align:center; background:#1a1a2e; border-radius:16px; padding:2rem 1rem; border: 2px solid {score_color};">
            <div style="font-size:0.9rem; color:#9ca3af; letter-spacing:0.1em; text-transform:uppercase;">ATS Score</div>
            <div style="font-size:4rem; font-weight:900; color:{score_color}; line-height:1.1;">{final_score}</div>
            <div style="font-size:0.8rem; color:#6b7280;">/ 100</div>
            <div style="margin-top:0.5rem; font-size:1rem; font-weight:600; color:{score_color};">{grade_label}</div>
        </div>
        """, unsafe_allow_html=True)

    with col_info:
        st.markdown("#### 👤 Candidate")
        gpa_display = f"{resume_data.gpa} / {resume_data.gpa_scale}" if resume_data.gpa > 0 else "Not listed"
        st.metric("Name", resume_data.name)
        st.metric("GPA", gpa_display)
        st.metric("Degree", resume_data.degree if resume_data.degree else "Not listed")
        st.metric("Total Projects", resume_data.complex_projects + resume_data.simple_projects)

    with col_flags:
        st.markdown("#### 🚩 Key Signals")
        flags = [
            ("Standard resume sections", resume_data.has_standard_sections),
            ("CS related degree", resume_data.is_cs_related_degree),
            ("Data Structures & Algorithms", resume_data.has_ds_algo),
            ("Discrete Math", resume_data.has_discrete_math),
            ("Has internship", resume_data.has_internship),
            ("Top company internship", resume_data.is_top_company_internship),
            ("Competitive achievements", resume_data.competitive_achievements_count > 0),
            ("Quantifiable impact bullets", resume_data.quantifiable_metrics_count > 0),
        ]
        for label, present in flags:
            icon = "✅" if present else "❌"
            bg = "#162032" if present else "#1f1220"
            st.markdown(f'<div class="flag-box" style="background:{bg};">{icon} {label}</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📋 Score Breakdown")

    components = [
        ("🗂️ Formatting & Structure", score_data["formatting_score"], 15,
         "Are standard sections present? Can the ATS read your resume cleanly?"),
        ("🎓 Academics", score_data["academic_score"], 20,
         "GPA, CS degree, and theory knowledge (DSA, Discrete Math)."),
        ("🛠️ Skills", score_data["skills_score"], 20,
         "Breadth of your tech stack. Too few or too many both hurt."),
        ("💻 Projects", score_data["project_score"], 20,
         "Complex projects count more. Claiming hard projects without relevant languages gets penalised."),
        ("📈 Impact & Language", score_data["impact_score"], 15,
         "Numbers and percentages in bullets. Strong action verbs. Weak phrases reduce this score."),
        ("🏢 Experience", score_data["velocity_score"], 10,
         "Internship quality, competition wins, and career progression."),
    ]

    for label, score, max_score, hint in components:
        pct = score / max_score
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(f"**{label}**")
            st.caption(hint)
            st.progress(pct, text=f"{score} / {max_score}")
        with c2:
            st.metric("", f"{score}/{max_score}")
        st.markdown("")

    st.markdown("---")
    st.markdown("### 🧮 Final Score")

    m1, m2, m3 = st.columns(3)
    raw_total = sum([score_data["formatting_score"], score_data["academic_score"],
                     score_data["skills_score"], score_data["project_score"],
                     score_data["impact_score"], score_data["velocity_score"]])
    m1.metric("Base Score", f"{round(raw_total, 1)}")
    m2.metric("Bonus", f"+{score_data['bonus']}")
    m3.metric("Final Score", f"{score_data['final_score']} / 100")

    if score_data["bonus"] > 0:
        st.success(f"🎁 +{score_data['bonus']} bonus points for {resume_data.quantifiable_metrics_count} quantifiable impact bullets.")
    if score_data["low_level_penalty"] > 0:
        st.warning("⚠️ Complex projects detected but no low-level language (C, C++, Rust, Java, Go) found — project score reduced.")
    if score_data["gap_penalty"] > 0:
        st.warning(f"⚠️ Employment gap of {resume_data.employment_gap_months} months detected — experience score reduced.")
    if resume_data.weak_phrase_count > 0:
        st.warning(f"⚠️ {resume_data.weak_phrase_count} weak phrase(s) found ('Responsible for...', 'Helped with...'). Replace with strong action verbs.")
    if score_data["stuffing_penalty"] > 0:
        st.warning("⚠️ Too many skills listed — ATS may flag this as keyword stuffing. Keep to 15–20 quality skills.")
    if not resume_data.has_standard_sections:
        st.error("❌ Standard sections (Education, Projects, Skills, Experience) not clearly detected. Use standard headings.")

    if resume_data.tech_skills:
        st.markdown("---")
        st.markdown("### 🛠️ Detected Skills")
        skill_html = " ".join([
            f'<span style="background:#2d2d4e; padding:0.25rem 0.6rem; border-radius:20px; font-size:0.82rem; margin:0.2rem; display:inline-block;">{s}</span>'
            for s in resume_data.tech_skills
        ])
        st.markdown(skill_html, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Dashboard 2: Resume Data
# ─────────────────────────────────────────────
elif dashboard == "🗂️ Dashboard 2: Resume Data":

    st.markdown("### 🗂️ Resume Data")
    st.caption("Here are all the details we picked up from your resume.")

    structured_output = {
        "candidate": {
            "name": resume_data.name,
            "degree": resume_data.degree,
            "gpa": resume_data.gpa,
            "gpa_scale": resume_data.gpa_scale,
            "is_cs_related_degree": resume_data.is_cs_related_degree,
        },
        "academics": {
            "has_ds_algo": resume_data.has_ds_algo,
            "has_discrete_math": resume_data.has_discrete_math,
        },
        "projects": {
            "complex": resume_data.complex_projects,
            "simple": resume_data.simple_projects,
            "total": resume_data.complex_projects + resume_data.simple_projects,
        },
        "skills": {
            "tech_stack": resume_data.tech_skills,
            "count": len(resume_data.tech_skills),
        },
        "experience": {
            "has_internship": resume_data.has_internship,
            "is_top_company_internship": resume_data.is_top_company_internship,
            "competitive_achievements": resume_data.competitive_achievements_count,
            "employment_gap_months": resume_data.employment_gap_months,
        },
        "resume_quality": {
            "has_standard_sections": resume_data.has_standard_sections,
            "quantifiable_bullets": resume_data.quantifiable_metrics_count,
            "action_verb_bullets": resume_data.action_verb_bullet_count,
            "weak_phrase_count": resume_data.weak_phrase_count,
        },
        "ats_score": {
            "final": score_data["final_score"],
            "formatting": score_data["formatting_score"],
            "academics": score_data["academic_score"],
            "skills": score_data["skills_score"],
            "projects": score_data["project_score"],
            "impact": score_data["impact_score"],
            "experience": score_data["velocity_score"],
            "bonus": score_data["bonus"],
        }
    }

    json_str = json.dumps(structured_output, indent=2)
    st.code(json_str, language="json")

    st.download_button(
        label="⬇️ Download JSON",
        data=json_str,
        file_name=f"{resume_data.name.replace(' ', '_')}_resume.json",
        mime="application/json",
        use_container_width=True,
    )

