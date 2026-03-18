"""KF-TestMaker — テスト問題を作成し、難易度分析付きPDFを生成するアプリ。"""

import streamlit as st

st.set_page_config(
    page_title="KF-TestMaker",
    page_icon="📝",
    layout="wide",
)

from components.header import render_header
from components.footer import render_footer
from components.i18n import t

import pandas as pd
import textstat
from io import BytesIO
from fpdf import FPDF
from datetime import date
import os

# --- Header ---
render_header()


def analyze_difficulty(text: str) -> dict:
    """Analyze text difficulty using textstat metrics."""
    fk_grade = textstat.flesch_kincaid_grade(text)
    flesch_score = textstat.flesch_reading_ease(text)
    word_count = textstat.lexicon_count(text, removepunct=True)
    sentence_count = textstat.sentence_count(text)

    # Map to difficulty level
    if fk_grade <= 4:
        level = t("difficulty_easy")
        color = "#4CAF50"
    elif fk_grade <= 8:
        level = t("difficulty_medium")
        color = "#FF9800"
    elif fk_grade <= 12:
        level = t("difficulty_hard")
        color = "#F44336"
    else:
        level = t("difficulty_very_hard")
        color = "#9C27B0"

    return {
        "fk_grade": round(fk_grade, 1),
        "flesch_score": round(flesch_score, 1),
        "word_count": word_count,
        "sentence_count": sentence_count,
        "level": level,
        "color": color,
    }


def generate_test_pdf(questions: list[dict], title: str, include_answers: bool) -> bytes:
    """Generate a test PDF with optional answers."""
    pdf = FPDF()
    pdf.add_page()

    # Font setup
    font_name = "Helvetica"
    font_path = None
    local_font = os.path.join(os.path.dirname(__file__), "NotoSansJP-Regular.ttf")
    if os.path.exists(local_font):
        font_path = local_font
    else:
        candidates = [
            "C:/Windows/Fonts/msgothic.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJKjp-Regular.otf",
        ]
        for c in candidates:
            if os.path.exists(c):
                font_path = c
                break

    if font_path:
        pdf.add_font("JP", "", font_path, uni=True)
        font_name = "JP"

    # Title
    pdf.set_font(font_name, size=18)
    pdf.cell(0, 15, title, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(3)

    # Date and instructions
    pdf.set_font(font_name, size=10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 7, f"{t('test_date')}: {date.today().strftime('%Y-%m-%d')}", new_x="LMARGIN", new_y="NEXT")

    if include_answers:
        pdf.set_text_color(200, 0, 0)
        pdf.cell(0, 7, t("answer_sheet_label"), new_x="LMARGIN", new_y="NEXT")

    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)

    # Questions
    for i, q in enumerate(questions, 1):
        # Check if we need a new page
        if pdf.get_y() > 250:
            pdf.add_page()

        # Question number and text
        pdf.set_font(font_name, size=12)
        question_text = f"{t('question_prefix')} {i}. {q['question']}"
        pdf.multi_cell(0, 7, question_text)
        pdf.ln(2)

        # Choices
        pdf.set_font(font_name, size=11)
        choices = [q.get("choice_a", ""), q.get("choice_b", ""), q.get("choice_c", ""), q.get("choice_d", "")]
        labels = ["A", "B", "C", "D"]

        for label, choice in zip(labels, choices):
            if choice.strip():
                prefix = ""
                if include_answers and label == q.get("correct_answer", ""):
                    pdf.set_text_color(200, 0, 0)
                    prefix = " ✓"
                else:
                    pdf.set_text_color(0, 0, 0)
                pdf.cell(0, 7, f"  {label}) {choice}{prefix}", new_x="LMARGIN", new_y="NEXT")

        pdf.set_text_color(0, 0, 0)

        if include_answers and q.get("explanation", "").strip():
            pdf.ln(2)
            pdf.set_font(font_name, size=10)
            pdf.set_text_color(0, 100, 0)
            pdf.multi_cell(0, 6, f"{t('explanation_label')}: {q['explanation']}")
            pdf.set_text_color(0, 0, 0)

        pdf.ln(5)

    # Footer
    pdf.set_font(font_name, size=8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 5, f"{t('total_questions')}: {len(questions)}", new_x="LMARGIN", new_y="NEXT", align="R")

    buffer = BytesIO()
    pdf.output(buffer)
    return buffer.getvalue()


# --- Main Content ---

# Initialize session state for questions
if "questions" not in st.session_state:
    st.session_state.questions = []

st.markdown(f"### {t('create_test')}")

# Test title
test_title = st.text_input(t("test_title"), value=t("default_test_title"))

st.markdown("---")

# --- Add question form ---
st.markdown(f"#### {t('add_question')}")

with st.form("add_question_form", clear_on_submit=True):
    question_text = st.text_area(t("question_text"), height=80)

    col1, col2 = st.columns(2)
    with col1:
        choice_a = st.text_input(t("choice_a"))
        choice_c = st.text_input(t("choice_c"))
    with col2:
        choice_b = st.text_input(t("choice_b"))
        choice_d = st.text_input(t("choice_d"))

    col_ans, col_exp = st.columns([1, 3])
    with col_ans:
        correct_answer = st.selectbox(t("correct_answer"), ["A", "B", "C", "D"])
    with col_exp:
        explanation = st.text_input(t("explanation_label"))

    add_submitted = st.form_submit_button(t("add_question_btn"), type="primary")

if add_submitted and question_text.strip():
    st.session_state.questions.append({
        "question": question_text.strip(),
        "choice_a": choice_a.strip(),
        "choice_b": choice_b.strip(),
        "choice_c": choice_c.strip(),
        "choice_d": choice_d.strip(),
        "correct_answer": correct_answer,
        "explanation": explanation.strip(),
    })
    st.success(t("question_added"))
    st.rerun()

# --- Bulk edit with data_editor ---
if st.session_state.questions:
    st.markdown("---")
    st.markdown(f"#### {t('edit_questions')} ({len(st.session_state.questions)} {t('questions_count')})")

    df = pd.DataFrame(st.session_state.questions)
    df.index = range(1, len(df) + 1)
    df.index.name = "#"

    edited_df = st.data_editor(
        df,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "question": st.column_config.TextColumn(t("question_text"), width="large"),
            "choice_a": st.column_config.TextColumn("A"),
            "choice_b": st.column_config.TextColumn("B"),
            "choice_c": st.column_config.TextColumn("C"),
            "choice_d": st.column_config.TextColumn("D"),
            "correct_answer": st.column_config.SelectboxColumn(
                t("correct_answer"), options=["A", "B", "C", "D"], width="small"
            ),
            "explanation": st.column_config.TextColumn(t("explanation_label")),
        },
        key="question_editor",
    )

    # Sync back edited data
    st.session_state.questions = edited_df.to_dict("records")

    # --- Difficulty Analysis ---
    st.markdown("---")
    st.markdown(f"#### {t('difficulty_analysis')}")

    analyses = []
    for i, q in enumerate(st.session_state.questions, 1):
        if q.get("question", "").strip():
            # Combine question + choices for analysis
            full_text = q["question"]
            for c in ["choice_a", "choice_b", "choice_c", "choice_d"]:
                if q.get(c, "").strip():
                    full_text += " " + q[c]
            analysis = analyze_difficulty(full_text)
            analysis["number"] = i
            analysis["question_preview"] = q["question"][:50] + ("..." if len(q["question"]) > 50 else "")
            analyses.append(analysis)

    if analyses:
        # Summary metrics
        col1, col2, col3 = st.columns(3)
        avg_grade = sum(a["fk_grade"] for a in analyses) / len(analyses)
        avg_flesch = sum(a["flesch_score"] for a in analyses) / len(analyses)

        with col1:
            st.metric(t("avg_fk_grade"), f"{avg_grade:.1f}")
        with col2:
            st.metric(t("avg_flesch_score"), f"{avg_flesch:.1f}")
        with col3:
            st.metric(t("total_questions"), str(len(analyses)))

        # Difficulty distribution
        level_counts = {}
        for a in analyses:
            level_counts[a["level"]] = level_counts.get(a["level"], 0) + 1

        st.markdown(f"**{t('difficulty_distribution')}**")
        for level, count in level_counts.items():
            bar_len = int(count / len(analyses) * 20)
            pct = count / len(analyses) * 100
            st.text(f"  {level}: {'█' * bar_len}{'░' * (20 - bar_len)} {count} ({pct:.0f}%)")

        # Per-question detail
        with st.expander(t("per_question_detail")):
            for a in analyses:
                st.markdown(
                    f"**Q{a['number']}** | {a['question_preview']} | "
                    f"FK Grade: {a['fk_grade']} | Flesch: {a['flesch_score']} | "
                    f":{a['color']}[{a['level']}]"
                )

    # --- PDF Generation ---
    st.markdown("---")
    st.markdown(f"#### {t('generate_pdfs')}")

    col1, col2 = st.columns(2)

    with col1:
        if st.button(t("generate_test_pdf"), type="primary", use_container_width=True):
            pdf_bytes = generate_test_pdf(st.session_state.questions, test_title, include_answers=False)
            st.download_button(
                label=t("download_test_pdf"),
                data=pdf_bytes,
                file_name=f"test_{date.today().strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
            )

    with col2:
        if st.button(t("generate_answer_pdf"), use_container_width=True):
            pdf_bytes = generate_test_pdf(st.session_state.questions, test_title, include_answers=True)
            st.download_button(
                label=t("download_answer_pdf"),
                data=pdf_bytes,
                file_name=f"test_answers_{date.today().strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
            )

else:
    st.info(t("no_questions_yet"))

# --- Footer ---
render_footer(libraries=["textstat", "fpdf2"])
