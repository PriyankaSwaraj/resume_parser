import streamlit as st
import google.generativeai as genai
import pdfplumber
import docx
import io
import json
import re
import time

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Resume Pattern Analyzer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;500;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Background */
.stApp {
    background: #0f0f17;
    color: #e8e8f0;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: #15151f;
    border-right: 1px solid #2a2a3d;
}

/* Cards */
.card {
    background: #1a1a28;
    border: 1px solid #2a2a3d;
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1.2rem;
}

.card-accent {
    border-left: 3px solid #7c6af7;
}

/* Score ring */
.score-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
    padding: 1.2rem 0;
}

.score-value {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 3.5rem;
    font-weight: 700;
    background: linear-gradient(135deg, #7c6af7, #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    line-height: 1;
}

.score-label {
    font-size: 0.8rem;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 0.1em;
}

/* Section headers */
.section-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1rem;
    font-weight: 600;
    color: #a78bfa;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.8rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

/* Tags */
.tag {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 500;
    margin: 0.2rem;
}
.tag-green  { background: #1a3329; color: #4ade80; border: 1px solid #2d5a42; }
.tag-yellow { background: #2d2910; color: #facc15; border: 1px solid #4a400a; }
.tag-red    { background: #2d1515; color: #f87171; border: 1px solid #5a2020; }
.tag-purple { background: #221a3d; color: #a78bfa; border: 1px solid #3d2d70; }
.tag-blue   { background: #0f1f3d; color: #60a5fa; border: 1px solid #1a3060; }

/* Pattern items */
.pattern-item {
    padding: 0.75rem 1rem;
    border-radius: 8px;
    margin-bottom: 0.5rem;
    font-size: 0.88rem;
    line-height: 1.5;
}
.pattern-good    { background: #0f1f18; border-left: 3px solid #4ade80; }
.pattern-warning { background: #1f1a0f; border-left: 3px solid #facc15; }
.pattern-bad     { background: #1f0f0f; border-left: 3px solid #f87171; }
.pattern-insight { background: #110f1f; border-left: 3px solid #a78bfa; }

/* Upload area */
[data-testid="stFileUploader"] {
    border: 2px dashed #2a2a3d !important;
    border-radius: 12px !important;
    background: #15151f !important;
    transition: border-color 0.2s;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #7c6af7, #6d5ce6) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    padding: 0.6rem 2rem !important;
    font-size: 0.9rem !important;
    transition: opacity 0.2s !important;
}
.stButton > button:hover { opacity: 0.88 !important; }

/* Text input */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    background: #15151f !important;
    border: 1px solid #2a2a3d !important;
    color: #e8e8f0 !important;
    border-radius: 8px !important;
    font-family: 'Inter', sans-serif !important;
}

/* Progress bar */
.stProgress > div > div > div {
    background: linear-gradient(90deg, #7c6af7, #a78bfa) !important;
}

/* Expander */
.streamlit-expanderHeader {
    background: #1a1a28 !important;
    border: 1px solid #2a2a3d !important;
    border-radius: 8px !important;
    color: #e8e8f0 !important;
}

/* Divider */
hr { border-color: #2a2a3d !important; }

/* Info/warning boxes */
.stAlert { border-radius: 8px !important; }

h1, h2, h3 { font-family: 'Space Grotesk', sans-serif !important; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ──────────────────────────────────────────────────────────────────

def extract_text_from_pdf(file_bytes: bytes) -> str:
    text = ""
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    return text.strip()


def extract_text_from_docx(file_bytes: bytes) -> str:
    doc = docx.Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_text(uploaded_file) -> str:
    name = uploaded_file.name.lower()
    data = uploaded_file.read()
    if name.endswith(".pdf"):
        return extract_text_from_pdf(data)
    elif name.endswith(".docx"):
        return extract_text_from_docx(data)
    else:  # plain text
        return data.decode("utf-8", errors="ignore")


ANALYSIS_PROMPT = """You are an elite career coach and talent expert with 15+ years of experience. Analyze the resume below and identify HIDDEN patterns — things most people miss — along with actionable feedback.

Return ONLY a valid JSON object (no markdown, no code fences) with this exact structure:

{{
  "overall_score": <integer 0-100>,
  "candidate_level": "<Junior|Mid|Senior|Executive>",
  "primary_domain": "<e.g. Software Engineering, Data Science, Marketing>",
  "executive_summary": "<2-3 sentence honest assessment>",
  
  "hidden_patterns": [
    {{
      "type": "<good|warning|bad|insight>",
      "title": "<short title>",
      "detail": "<concrete observation with specifics from the resume>"
    }}
  ],
  
  "strengths": ["<specific strength>", ...],
  "red_flags": ["<specific concern>", ...],
  
  "ats_analysis": {{
    "score": <integer 0-100>,
    "issues": ["<issue>", ...],
    "keywords_missing": ["<keyword>", ...]
  }},
  
  "career_trajectory": {{
    "pattern": "<e.g. Steady climber|Job hopper|Career pivoter|Specialist deepener>",
    "avg_tenure_months": <integer>,
    "observation": "<what the career arc reveals>"
  }},
  
  "writing_quality": {{
    "score": <integer 0-100>,
    "issues": ["<issue>", ...],
    "strong_bullets": ["<example of good bullet>"],
    "weak_bullets": ["<example of weak bullet>"]
  }},
  
  "skill_gaps": ["<missing skill relevant to their domain>", ...],
  
  "top_recommendations": [
    {{"priority": "high|medium", "action": "<specific, actionable recommendation>"}}
  ],
  
  "verdict": "<one punchy sentence — what this resume signals to a hiring manager>"
}}

Resume:
{resume_text}
"""


def analyze_resume(api_key: str, resume_text: str, job_description: str = "") -> dict:

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1"
    )

    text_to_analyze = resume_text

    if job_description.strip():
        text_to_analyze += (
            "\n\n--- JOB DESCRIPTION ---\n"
            + job_description
        )

    prompt = ANALYSIS_PROMPT.format(
        resume_text=text_to_analyze[:5000]
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",

        messages=[
            {
                "role": "system",
                "content": (
                    "You analyze resumes and return ONLY valid JSON."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],

        temperature=0.3,
        max_tokens=1200
    )

    raw = response.choices[0].message.content.strip()

    raw = re.sub(r"^```json", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()

    return json.loads(raw)


def score_color(score: int) -> str:
    if score >= 75:
        return "#4ade80"
    elif score >= 50:
        return "#facc15"
    else:
        return "#f87171"


def render_pattern(p: dict):
    css_class = {
        "good": "pattern-good",
        "warning": "pattern-warning",
        "bad": "pattern-bad",
        "insight": "pattern-insight",
    }.get(p.get("type", "insight"), "pattern-insight")
    emoji = {"good": "✅", "warning": "⚠️", "bad": "🚩", "insight": "💡"}.get(p.get("type", "insight"), "💡")
    st.markdown(
        f'<div class="pattern-item {css_class}"><strong>{emoji} {p["title"]}</strong><br>{p["detail"]}</div>',
        unsafe_allow_html=True,
    )


api_key = st.secrets.get("GEMINI_API_KEY", "")
job_description = ""


# ── Main ──────────────────────────────────────────────────────────────────────

st.markdown(
    "<h1 style='font-family:Space Grotesk;font-size:2rem;margin-bottom:0.2rem;'>"
    "🔍 Resume Pattern Analyzer</h1>"
    "<p style='color:#666;font-size:0.95rem;margin-bottom:1.5rem;'>"
    "Uncover hidden patterns, red flags, and career signals in any resume.</p>",
    unsafe_allow_html=True,
)

uploaded_file = st.file_uploader(
    "Upload Resume (PDF, DOCX, or TXT)",
    type=["pdf", "docx", "txt"],
    label_visibility="visible",
)

if uploaded_file:
    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        analyze_btn = st.button("🚀 Analyze Resume")
    with col_info:
        st.markdown(
            f"<div style='padding-top:0.6rem;color:#666;font-size:0.85rem;'>"
            f"📄 {uploaded_file.name}</div>",
            unsafe_allow_html=True,
        )

    if analyze_btn:
        if not api_key:
            st.error("Please enter your Gemini API key in the sidebar.")
            st.stop()

        with st.spinner("Extracting resume text…"):
            try:
                resume_text = extract_text(uploaded_file)
            except Exception as e:
                st.error(f"Could not read file: {e}")
                st.stop()

        if len(resume_text) < 100:
            st.error("Could not extract meaningful text from the file. Try a different format.")
            st.stop()

        progress = st.progress(0, text="Sending to Gemini 1.5 Flash…")
        for i in range(1, 60):
            time.sleep(0.02)
            progress.progress(i, text="Analyzing patterns…")

        try:
            result = analyze_resume(api_key, resume_text, job_description)
        except json.JSONDecodeError:
            st.error("Gemini returned an unexpected format. Please try again.")
            st.stop()
        except Exception as e:
            st.error(f"API error: {e}")
            st.stop()

        for i in range(60, 101):
            time.sleep(0.01)
            progress.progress(i, text="Building report…")
        progress.empty()

        # ── Results layout ─────────────────────────────────────────────────

        # Row 1: score + meta + verdict
        r1a, r1b = st.columns([1, 3])

        with r1a:
            score = result.get("overall_score", 0)
            color = score_color(score)
            st.markdown(
                f"""<div class='card' style='text-align:center;'>
                    <div class='score-container'>
                        <div class='score-value' style='background:linear-gradient(135deg,{color},{color}bb);
                             -webkit-background-clip:text;'>{score}</div>
                        <div class='score-label'>Overall Score</div>
                    </div>
                    <div style='margin-top:0.5rem;'>
                        <span class='tag tag-purple'>{result.get("candidate_level","—")}</span>
                        <span class='tag tag-blue'>{result.get("primary_domain","—")}</span>
                    </div>
                </div>""",
                unsafe_allow_html=True,
            )

        with r1b:
            traj = result.get("career_trajectory", {})
            st.markdown(
                f"""<div class='card card-accent'>
                    <div class='section-title'>📝 Executive Summary</div>
                    <p style='margin:0;line-height:1.7;'>{result.get("executive_summary","—")}</p>
                    <div style='margin-top:1rem;padding-top:1rem;border-top:1px solid #2a2a3d;'>
                        <span style='color:#888;font-size:0.82rem;'>Career pattern: </span>
                        <strong style='color:#a78bfa;'>{traj.get("pattern","—")}</strong>
                        &nbsp;·&nbsp;
                        <span style='color:#888;font-size:0.82rem;'>Avg tenure: </span>
                        <strong>{traj.get("avg_tenure_months","?")}&nbsp;mo</strong>
                    </div>
                    <div style='margin-top:0.5rem;color:#aaa;font-size:0.85rem;'>{traj.get("observation","")}</div>
                </div>""",
                unsafe_allow_html=True,
            )

        # Verdict banner
        st.markdown(
            f"""<div style='background:#221a3d;border:1px solid #3d2d70;border-radius:10px;
                padding:1rem 1.5rem;margin-bottom:1.2rem;font-size:0.95rem;'>
                💬 <strong>Hiring-manager verdict:</strong>&nbsp;
                <em style='color:#c4b5fd;'>{result.get("verdict","—")}</em>
            </div>""",
            unsafe_allow_html=True,
        )

        # Row 2: hidden patterns
        st.markdown("<div class='section-title' style='font-size:1.05rem;'>🕵️ Hidden Patterns</div>", unsafe_allow_html=True)
        patterns = result.get("hidden_patterns", [])
        if patterns:
            cols = st.columns(2)
            for i, p in enumerate(patterns):
                with cols[i % 2]:
                    render_pattern(p)
        else:
            st.info("No hidden patterns identified.")

        st.markdown("---")

        # Row 3: strengths + red flags
        c3a, c3b = st.columns(2)
        with c3a:
            st.markdown("<div class='section-title'>✅ Strengths</div>", unsafe_allow_html=True)
            for s in result.get("strengths", []):
                st.markdown(f"<div class='pattern-item pattern-good'>• {s}</div>", unsafe_allow_html=True)

        with c3b:
            st.markdown("<div class='section-title'>🚩 Red Flags</div>", unsafe_allow_html=True)
            for r in result.get("red_flags", []):
                st.markdown(f"<div class='pattern-item pattern-bad'>• {r}</div>", unsafe_allow_html=True)

        st.markdown("---")

        # Row 4: ATS + writing quality
        c4a, c4b = st.columns(2)

        with c4a:
            ats = result.get("ats_analysis", {})
            ats_score = ats.get("score", 0)
            st.markdown(
                f"""<div class='card'>
                    <div class='section-title'>🤖 ATS Compatibility
                        <span style='margin-left:auto;font-size:1.1rem;color:{score_color(ats_score)};
                              font-family:Space Grotesk;font-weight:700;'>{ats_score}/100</span>
                    </div>""",
                unsafe_allow_html=True,
            )
            st.progress(ats_score / 100)
            for issue in ats.get("issues", []):
                st.markdown(f"<div class='pattern-item pattern-warning'>⚠️ {issue}</div>", unsafe_allow_html=True)
            missing_kw = ats.get("keywords_missing", [])
            if missing_kw:
                st.markdown("<div style='margin-top:0.8rem;color:#888;font-size:0.82rem;'>Missing keywords:</div>", unsafe_allow_html=True)
                for kw in missing_kw:
                    st.markdown(f"<span class='tag tag-yellow'>{kw}</span>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with c4b:
            wq = result.get("writing_quality", {})
            wq_score = wq.get("score", 0)
            st.markdown(
                f"""<div class='card'>
                    <div class='section-title'>✍️ Writing Quality
                        <span style='margin-left:auto;font-size:1.1rem;color:{score_color(wq_score)};
                              font-family:Space Grotesk;font-weight:700;'>{wq_score}/100</span>
                    </div>""",
                unsafe_allow_html=True,
            )
            st.progress(wq_score / 100)
            for issue in wq.get("issues", []):
                st.markdown(f"<div class='pattern-item pattern-warning'>⚠️ {issue}</div>", unsafe_allow_html=True)
            if wq.get("weak_bullets"):
                with st.expander("See example weak bullet"):
                    st.markdown(f"> {wq['weak_bullets'][0]}")
            if wq.get("strong_bullets"):
                with st.expander("See example strong bullet"):
                    st.markdown(f"> {wq['strong_bullets'][0]}")
            st.markdown("</div>", unsafe_allow_html=True)

        # Row 5: skill gaps
        gaps = result.get("skill_gaps", [])
        if gaps:
            st.markdown("---")
            st.markdown("<div class='section-title'>🧩 Skill Gaps</div>", unsafe_allow_html=True)
            for g in gaps:
                st.markdown(f"<span class='tag tag-red'>{g}</span>", unsafe_allow_html=True)

        # Row 6: recommendations
        st.markdown("---")
        st.markdown("<div class='section-title'>🎯 Top Recommendations</div>", unsafe_allow_html=True)
        recs = result.get("top_recommendations", [])
        for rec in recs:
            priority = rec.get("priority", "medium")
            tag_class = "tag-red" if priority == "high" else "tag-yellow"
            st.markdown(
                f"""<div class='pattern-item pattern-insight'>
                    <span class='tag {tag_class}' style='margin-right:0.5rem;'>{priority.upper()}</span>
                    {rec.get("action","—")}
                </div>""",
                unsafe_allow_html=True,
            )

        # Raw JSON toggle
        with st.expander("🔧 Raw JSON response"):
            st.json(result)

else:
    # Empty state
    st.markdown(
        """
        <div style='text-align:center;padding:4rem 2rem;color:#444;'>
            <div style='font-size:3rem;margin-bottom:1rem;'>📄</div>
            <div style='font-size:1.1rem;font-weight:500;color:#555;'>Drop a resume to get started</div>
            <div style='font-size:0.85rem;margin-top:0.5rem;'>Supports PDF, DOCX, and plain text</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


