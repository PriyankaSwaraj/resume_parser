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
        background: linear-gradient(135deg, #16a34a, #4ade80);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .flag-box {
        background: #f0fdf4;
        border: 1px solid #bbf7d0;
        border-radius: 10px;
        padding: 0.6rem 1rem;
        margin: 0.3rem 0;
        font-size: 0.95rem;
        color: #14532d;
    }
    div[data-testid="metric-container"] {
        background: #f0fdf4;
        border: 1px solid #86efac;
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
    with st.spinner("Extracting resume data with LLM..."):
        resume_data = extract_resume_data(raw_text, api_key)
    with st.spinner("Computing scores..."):
        score_data = compute_score(resume_data)
    st.session_state["raw_text"] = raw_text
    st.session_state["resume_data"] = resume_data
    st.session_state["score_data"] = score_data


st.markdown('<p class="main-header">🎓 CS Resume Scorer</p>', unsafe_allow_html=True)
st.caption("Upload your resume PDF and get an instant score across 8 engineering dimensions.")

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
        score_color = "#16a34a"
        grade_label = "🏆 Strong Profile"
    elif final_score >= 55:
        score_color = "#4ade80"
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
        <div style="text-align:center; background:#f0fdf4; border-radius:16px; padding:2rem 1rem; border: 2px solid {score_color};">
            <div style="font-size:0.9rem; color:#4b5563; letter-spacing:0.1em; text-transform:uppercase;">Final Score</div>
            <div style="font-size:4rem; font-weight:900; color:{score_color}; line-height:1.1;">{final_score}</div>
            <div style="font-size:0.8rem; color:#6b7280;">/ 100</div>
            <div style="margin-top:0.5rem; font-size:1rem; font-weight:600; color:{score_color};">{grade_label}</div>
            <div style="margin-top:0.4rem; font-size:0.8rem; color:#6b7280;">Year {score_data['btech_year']} B.Tech weights applied</div>
        </div>
        """, unsafe_allow_html=True)

    with col_info:
        st.markdown("#### 👤 Candidate")
        st.metric("Name", resume_data.candidate_name)
        st.metric("B.Tech Year", f"Year {resume_data.btech_year}")
        st.metric("Total Projects", resume_data.project_count)
        st.metric("Skills Listed", len(resume_data.skills_section_keywords))

    with col_flags:
        st.markdown("#### 🔍 Quick Signals")
        flags = [
            ("GitHub link present", any("github" in l.lower() for l in resume_data.extracted_links_array)),
            ("LinkedIn link present", any("linkedin" in l.lower() for l in resume_data.extracted_links_array)),
            ("Professional email", score_data["E_generic"] == 0),
            ("Single page resume", resume_data.total_page_count == 1),
            ("Standard sections found", score_data["X_missing"] == 0),
            ("Has live deployments", len(resume_data.deployment_live_urls) > 0),
            ("Has metric bullets", resume_data.metric_regex_match_count > 0),
            ("No buzzwords found", len(resume_data.buzzword_frequency_map) == 0),
        ]
        for label, present in flags:
            icon = "✅" if present else "❌"
            bg = "#dcfce7" if present else "#fef2f2"
            st.markdown(f'<div class="flag-box" style="background:{bg};">{icon} {label}</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📋 Score Breakdown (8 Components)")

    W = score_data["weights"]
    components = [
        ("🏗️ Structural Hygiene",    "S_hygiene",     W["hyg"],  "Page count, links, email, section headers."),
        ("🔗 Tech-Stack Realization", "S_realization", W["real"], "Skills listed vs. skills actually used in projects."),
        ("⚙️ Project Complexity",    "S_complexity",  W["comp"], "Architectural tier of your best project + volume bonus."),
        ("📈 Quantifiable Impact",   "S_impact",      W["imp"],  "Log-weighted magnitude of metrics in your bullet points."),
        ("🚀 Production Readiness",  "S_production",  W["prod"], "GitHub repos + live deployment links per project."),
        ("🔇 Linguistic Clarity",    "S_clarity",     W["clar"], "Penalises buzzwords like 'passionate', 'hardworking'."),
        ("🎯 Domain Specialisation", "S_domain",      W["dom"],  "Rewards focus — fewer domains across more skills = better."),
        ("⏱️ Chronological Velocity","S_velocity",    W["vel"],  "Internships, freelance, club roles weighted by duration."),
    ]

    for label, key, weight, hint in components:
        raw = score_data[key]
        weighted = round(raw * weight, 2)
        c1, c2, c3 = st.columns([3, 0.8, 0.8])
        with c1:
            st.markdown(f"**{label}** `weight: {int(weight*100)}%`")
            st.caption(hint)
            st.progress(min(raw / 100, 1.0), text=f"{raw} / 100")
        with c2:
            st.metric("Raw", f"{raw}")
        with c3:
            st.metric("Weighted", f"{weighted}")
        st.markdown("")

    st.markdown("---")
    st.markdown("### 🧮 Final Score")
    cols = st.columns(len(components) + 1)
    for i, (label, key, weight, _) in enumerate(components):
        short = label.split()[1]
        cols[i].metric(short, f"{round(score_data[key] * weight, 1)}")
    cols[-1].metric("🏁 Final", f"{final_score} / 100")

    # Warnings
    st.markdown("---")
    if score_data["L_missing"] > 0:
        st.warning(f"⚠️ {score_data['L_missing']} primary link(s) missing — add GitHub and LinkedIn.")
    if score_data["E_generic"] == 1:
        st.warning("⚠️ Email appears unprofessional (contains numbers or slang). Use firstname.lastname@gmail.com format.")
    if score_data["X_missing"] > 0:
        st.warning(f"⚠️ {score_data['X_missing']} mandatory section(s) missing — ensure Education, Projects, and Skills headings are present.")
    if resume_data.total_page_count > 1:
        st.warning(f"⚠️ Resume is {resume_data.total_page_count} pages — B.Tech resumes should be 1 page.")
    if score_data["buzzwords_found"]:
        words = ", ".join(f"'{w}' x{c}" for w, c in score_data["buzzwords_found"].items())
        st.warning(f"⚠️ Buzzwords detected: {words}. Replace with technical achievements.")
    if score_data["S_realization"] < 50:
        st.warning("⚠️ Many skills listed are not found in project descriptions — only list skills you have actually used.")
    if score_data["S_complexity"] < 65:
        st.warning("⚠️ No Tier 3 project detected. Add a system using Docker, Redis, Kafka, WebSockets, or cloud infra.")
    if score_data["S_production"] < 50:
        st.warning("⚠️ Low production score — add GitHub links and live deployment URLs for each project.")

    if resume_data.skills_section_keywords:
        st.markdown("---")
        st.markdown("### 🛠️ Detected Skills")
        skill_html = " ".join([
            f'<span style="background:#dcfce7; color:#14532d; padding:0.25rem 0.6rem; border-radius:20px; font-size:0.82rem; margin:0.2rem; display:inline-block;">{s}</span>'
            for s in resume_data.skills_section_keywords
        ])
        st.markdown(skill_html, unsafe_allow_html=True)

    if resume_data.domain_classification_vector:
        st.markdown("**Detected Domains:**")
        domain_html = " ".join([
            f'<span style="background:#bbf7d0; color:#14532d; padding:0.25rem 0.8rem; border-radius:20px; font-size:0.82rem; margin:0.2rem; display:inline-block; font-weight:600;">{d}</span>'
            for d in set(resume_data.domain_classification_vector)
        ])
        st.markdown(domain_html, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Dashboard 2: Resume Data
# ─────────────────────────────────────────────
elif dashboard == "🗂️ Dashboard 2: Resume Data":

    st.markdown("### 🗂️ Extracted Resume Data")
    st.caption("Raw data extracted by the LLM — fed directly into the scoring formulas.")

    structured_output = {
        "candidate": {
            "name": resume_data.candidate_name,
            "btech_year": resume_data.btech_year,
        },
        "hygiene": {
            "total_page_count": resume_data.total_page_count,
            "extracted_links": resume_data.extracted_links_array,
            "email": resume_data.raw_email_string,
            "section_headers": resume_data.detected_section_headers,
        },
        "skills": {
            "section_keywords": resume_data.skills_section_keywords,
            "count": len(resume_data.skills_section_keywords),
            "domain_vector": resume_data.domain_classification_vector,
        },
        "projects": {
            "count": resume_data.project_count,
            "titles": resume_data.project_titles,
            "tech_per_project": resume_data.project_tech_keywords,
            "arch_flags": resume_data.architectural_regex_flags,
            "code_repos": resume_data.code_repository_urls,
            "live_deployments": resume_data.deployment_live_urls,
        },
        "impact": {
            "total_bullets": resume_data.total_bullet_points_count,
            "metric_bullets": resume_data.metric_regex_match_count,
            "numeric_values_extracted": resume_data.regex_extracted_numeric_values,
        },
        "clarity": {
            "buzzword_frequency_map": resume_data.buzzword_frequency_map,
        },
        "experience": {
            "timeline": resume_data.experience_timeline_intervals,
        },
        "scores": {
            "final": score_data["final_score"],
            "year_weights_applied": score_data["btech_year"],
            "S_hygiene": score_data["S_hygiene"],
            "S_realization": score_data["S_realization"],
            "S_complexity": score_data["S_complexity"],
            "S_impact": score_data["S_impact"],
            "S_production": score_data["S_production"],
            "S_clarity": score_data["S_clarity"],
            "S_domain": score_data["S_domain"],
            "S_velocity": score_data["S_velocity"],
        }
    }

    json_str = json.dumps(structured_output, indent=2)
    st.code(json_str, language="json")

    st.download_button(
        label="⬇️ Download JSON",
        data=json_str,
        file_name=f"{resume_data.candidate_name.replace(' ', '_')}_resume_data.json",
        mime="application/json",
        use_container_width=True,
    )
