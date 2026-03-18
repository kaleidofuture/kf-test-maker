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

import csv
import json
import re
import unicodedata
import pandas as pd
from io import BytesIO, StringIO
from fpdf import FPDF
from datetime import date
import os

# --- Header ---
render_header()


# --- Japanese Difficulty Analysis ---

def is_kanji(ch: str) -> bool:
    """Return True if the character is a CJK Unified Ideograph (kanji)."""
    try:
        return "CJK UNIFIED IDEOGRAPH" in unicodedata.name(ch, "")
    except ValueError:
        return False


def analyze_difficulty(text: str) -> dict:
    """Analyze text difficulty using Japanese-appropriate metrics.

    Metrics:
    - Kanji ratio: kanji characters / total characters (excl. whitespace)
    - Average sentence length: characters per sentence
    - Difficulty level derived from these metrics
    """
    # Remove whitespace for character counting
    chars = re.sub(r"\s", "", text)
    total_chars = len(chars)
    if total_chars == 0:
        return {
            "kanji_ratio": 0.0,
            "avg_sentence_len": 0.0,
            "total_chars": 0,
            "sentence_count": 0,
            "level": t("difficulty_easy"),
            "color": "#4CAF50",
        }

    kanji_count = sum(1 for ch in chars if is_kanji(ch))
    kanji_ratio = kanji_count / total_chars

    # Split sentences on Japanese/English sentence-ending punctuation
    sentences = re.split(r"[。！？!?\.\n]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    sentence_count = max(len(sentences), 1)
    avg_sentence_len = total_chars / sentence_count

    # Difficulty scoring: higher kanji ratio + longer sentences = harder
    # Kanji ratio score: 0-0.15 easy, 0.15-0.30 medium, 0.30-0.45 hard, 0.45+ very hard
    # Avg sentence length score: 0-20 easy, 20-40 medium, 40-60 hard, 60+ very hard
    score = 0
    if kanji_ratio >= 0.45:
        score += 3
    elif kanji_ratio >= 0.30:
        score += 2
    elif kanji_ratio >= 0.15:
        score += 1

    if avg_sentence_len >= 60:
        score += 3
    elif avg_sentence_len >= 40:
        score += 2
    elif avg_sentence_len >= 20:
        score += 1

    if score <= 1:
        level = t("difficulty_easy")
        color = "#4CAF50"
    elif score <= 3:
        level = t("difficulty_medium")
        color = "#FF9800"
    elif score <= 4:
        level = t("difficulty_hard")
        color = "#F44336"
    else:
        level = t("difficulty_very_hard")
        color = "#9C27B0"

    return {
        "kanji_ratio": round(kanji_ratio * 100, 1),
        "avg_sentence_len": round(avg_sentence_len, 1),
        "total_chars": total_chars,
        "sentence_count": sentence_count,
        "level": level,
        "color": color,
    }


# --- PDF Font Setup Helper ---

def _setup_pdf_font(pdf: FPDF) -> str:
    """Add a Japanese font to the PDF and return the font name to use."""
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

    return font_name


# --- Collect unique sections in order ---

def _ordered_sections(questions: list[dict]) -> list[str]:
    """Return unique section names in the order they first appear."""
    seen = set()
    result = []
    for q in questions:
        sec = q.get("section", "").strip()
        if sec and sec not in seen:
            seen.add(sec)
            result.append(sec)
    return result


# --- PDF Generation ---

def generate_test_pdf(questions: list[dict], title: str, include_answers: bool) -> bytes:
    """Generate a test PDF with optional answers, grouped by section."""
    pdf = FPDF()
    pdf.add_page()
    font_name = _setup_pdf_font(pdf)

    # Title
    pdf.set_font(font_name, size=18)
    pdf.cell(0, 15, title, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(3)

    # Date and instructions
    pdf.set_font(font_name, size=10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 7, f"{t('test_date')}: {date.today().strftime('%Y-%m-%d')}", new_x="LMARGIN", new_y="NEXT")

    # Total points
    total_points = sum(q.get("points", 10) for q in questions)
    pdf.cell(0, 7, f"{t('total_points')}: {total_points}", new_x="LMARGIN", new_y="NEXT")

    if include_answers:
        pdf.set_text_color(200, 0, 0)
        pdf.cell(0, 7, t("answer_sheet_label"), new_x="LMARGIN", new_y="NEXT")

    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)

    # Group questions by section
    sections = _ordered_sections(questions)
    no_section_qs = [q for q in questions if not q.get("section", "").strip()]

    def _render_questions(qs, start_num):
        num = start_num
        for q in qs:
            if pdf.get_y() > 250:
                pdf.add_page()

            pdf.set_font(font_name, size=12)
            pts = q.get("points", 10)
            question_text = f"{t('question_prefix')} {num}. {q['question']}  ({pts}{t('points_unit')})"
            pdf.multi_cell(0, 7, question_text)
            pdf.ln(2)

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
            num += 1
        return num

    q_num = 1
    # Render sections
    for sec_name in sections:
        if pdf.get_y() > 240:
            pdf.add_page()
        pdf.set_font(font_name, size=14)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(0, 10, f"  {sec_name}", new_x="LMARGIN", new_y="NEXT", fill=True)
        pdf.ln(4)
        sec_qs = [q for q in questions if q.get("section", "").strip() == sec_name]
        q_num = _render_questions(sec_qs, q_num)

    # Questions without a section
    if no_section_qs:
        if sections:
            # Add a generic header only if there were sectioned questions too
            if pdf.get_y() > 240:
                pdf.add_page()
            pdf.set_font(font_name, size=14)
            pdf.set_fill_color(240, 240, 240)
            pdf.cell(0, 10, f"  {t('no_section')}", new_x="LMARGIN", new_y="NEXT", fill=True)
            pdf.ln(4)
        q_num = _render_questions(no_section_qs, q_num)

    # Footer
    pdf.set_font(font_name, size=8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 5, f"{t('total_questions')}: {len(questions)}", new_x="LMARGIN", new_y="NEXT", align="R")

    buffer = BytesIO()
    pdf.output(buffer)
    return buffer.getvalue()


def generate_answer_sheet_pdf(questions: list[dict], title: str) -> bytes:
    """Generate an answer-sheet-only PDF (answer boxes, no question text)."""
    pdf = FPDF()
    pdf.add_page()
    font_name = _setup_pdf_font(pdf)

    # Title
    pdf.set_font(font_name, size=18)
    pdf.cell(0, 15, f"{title} — {t('answer_sheet_title')}", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(3)

    pdf.set_font(font_name, size=10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 7, f"{t('test_date')}: {date.today().strftime('%Y-%m-%d')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"{t('name_field')}: ___________________________", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)

    sections = _ordered_sections(questions)
    no_section_qs = [q for q in questions if not q.get("section", "").strip()]

    def _render_answer_boxes(qs, start_num):
        num = start_num
        for q in qs:
            if pdf.get_y() > 260:
                pdf.add_page()

            pts = q.get("points", 10)
            has_choices = any(q.get(f"choice_{c}", "").strip() for c in ["a", "b", "c", "d"])

            pdf.set_font(font_name, size=11)
            pdf.cell(40, 8, f"{t('question_prefix')} {num}  ({pts}{t('points_unit')})", new_x="END", new_y="TOP")

            if has_choices:
                # Multiple choice circles
                pdf.set_font(font_name, size=11)
                for label in ["A", "B", "C", "D"]:
                    if q.get(f"choice_{label.lower()}", "").strip():
                        pdf.cell(15, 8, f"○{label}", new_x="END", new_y="TOP")
                pdf.ln(10)
            else:
                # Written answer: blank line
                pdf.cell(0, 8, "________________________________", new_x="LMARGIN", new_y="NEXT")
                pdf.ln(4)

            num += 1
        return num

    q_num = 1
    for sec_name in sections:
        if pdf.get_y() > 250:
            pdf.add_page()
        pdf.set_font(font_name, size=13)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(0, 9, f"  {sec_name}", new_x="LMARGIN", new_y="NEXT", fill=True)
        pdf.ln(3)
        sec_qs = [q for q in questions if q.get("section", "").strip() == sec_name]
        q_num = _render_answer_boxes(sec_qs, q_num)

    if no_section_qs:
        if sections:
            if pdf.get_y() > 250:
                pdf.add_page()
            pdf.set_font(font_name, size=13)
            pdf.set_fill_color(240, 240, 240)
            pdf.cell(0, 9, f"  {t('no_section')}", new_x="LMARGIN", new_y="NEXT", fill=True)
            pdf.ln(3)
        q_num = _render_answer_boxes(no_section_qs, q_num)

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

# --- CSV Import / JSON Import-Export ---
st.markdown(f"#### {t('import_export')}")

col_csv, col_json_imp, col_json_exp = st.columns(3)

with col_csv:
    csv_file = st.file_uploader(t("csv_import"), type=["csv"], key="csv_upload")
    if csv_file is not None:
        try:
            text_data = csv_file.getvalue().decode("utf-8-sig")
            reader = csv.DictReader(StringIO(text_data))
            imported = 0
            for row in reader:
                q = {
                    "question": row.get("question", "").strip(),
                    "choice_a": row.get("choice_a", "").strip(),
                    "choice_b": row.get("choice_b", "").strip(),
                    "choice_c": row.get("choice_c", "").strip(),
                    "choice_d": row.get("choice_d", "").strip(),
                    "correct_answer": row.get("correct_answer", "A").strip().upper(),
                    "explanation": row.get("explanation", "").strip(),
                    "points": int(row.get("points", 10) or 10),
                    "section": row.get("section", "").strip(),
                }
                if q["question"]:
                    st.session_state.questions.append(q)
                    imported += 1
            if imported:
                st.success(f"{t('csv_imported')} ({imported})")
                st.rerun()
        except Exception as e:
            st.error(f"{t('csv_import_error')}: {e}")

with col_json_imp:
    json_file = st.file_uploader(t("json_import"), type=["json"], key="json_upload")
    if json_file is not None:
        try:
            data = json.loads(json_file.getvalue().decode("utf-8"))
            if isinstance(data, list):
                # Ensure all questions have required fields
                for q in data:
                    q.setdefault("points", 10)
                    q.setdefault("section", "")
                st.session_state.questions = data
                st.success(f"{t('json_imported')} ({len(data)})")
                st.rerun()
            else:
                st.error(t("json_import_error"))
        except Exception as e:
            st.error(f"{t('json_import_error')}: {e}")

with col_json_exp:
    if st.session_state.questions:
        json_bytes = json.dumps(st.session_state.questions, ensure_ascii=False, indent=2).encode("utf-8")
        st.download_button(
            label=t("json_export"),
            data=json_bytes,
            file_name=f"questions_{date.today().strftime('%Y%m%d')}.json",
            mime="application/json",
        )
    else:
        st.info(t("json_export_empty"))

st.markdown("---")

# --- Add question form ---
st.markdown(f"#### {t('add_question')}")

with st.form("add_question_form", clear_on_submit=True):
    question_text = st.text_area(t("question_text"), height=80)

    col_sec, col_pts = st.columns([3, 1])
    with col_sec:
        section = st.text_input(t("section_label"))
    with col_pts:
        points = st.number_input(t("points_label"), min_value=1, max_value=100, value=10, step=1)

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
        "points": int(points),
        "section": section.strip(),
    })
    st.success(t("question_added"))
    st.rerun()

# --- Bulk edit with data_editor ---
if st.session_state.questions:
    st.markdown("---")

    # Total points display
    total_pts = sum(q.get("points", 10) for q in st.session_state.questions)
    st.markdown(
        f"#### {t('edit_questions')} ({len(st.session_state.questions)} {t('questions_count')}) "
        f"&nbsp;&nbsp; | &nbsp;&nbsp; {t('current_total_points')}: **{total_pts}** / 100 {t('points_unit')}"
    )

    df = pd.DataFrame(st.session_state.questions)
    # Ensure columns exist even if old data lacks them
    for col_name in ["points", "section"]:
        if col_name not in df.columns:
            df[col_name] = 10 if col_name == "points" else ""
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
            "points": st.column_config.NumberColumn(t("points_label"), min_value=1, max_value=100, step=1, width="small"),
            "section": st.column_config.TextColumn(t("section_label"), width="medium"),
        },
        key="question_editor",
    )

    # Sync back edited data
    st.session_state.questions = edited_df.to_dict("records")

    # --- Difficulty Analysis (Japanese metrics) ---
    st.markdown("---")
    st.markdown(f"#### {t('difficulty_analysis')}")

    analyses = []
    for i, q in enumerate(st.session_state.questions, 1):
        if q.get("question", "").strip():
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
        avg_kanji = sum(a["kanji_ratio"] for a in analyses) / len(analyses)
        avg_sent_len = sum(a["avg_sentence_len"] for a in analyses) / len(analyses)

        with col1:
            st.metric(t("avg_kanji_ratio"), f"{avg_kanji:.1f}%")
        with col2:
            st.metric(t("avg_sentence_length"), f"{avg_sent_len:.1f}")
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
                    f"{t('kanji_ratio_label')}: {a['kanji_ratio']}% | "
                    f"{t('avg_sentence_len_label')}: {a['avg_sentence_len']} | "
                    f":{a['color']}[{a['level']}]"
                )

    # --- PDF Generation ---
    st.markdown("---")
    st.markdown(f"#### {t('generate_pdfs')}")

    col1, col2, col3 = st.columns(3)

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

    with col3:
        if st.button(t("generate_answer_sheet_pdf"), use_container_width=True):
            pdf_bytes = generate_answer_sheet_pdf(st.session_state.questions, test_title)
            st.download_button(
                label=t("download_answer_sheet_pdf"),
                data=pdf_bytes,
                file_name=f"answer_sheet_{date.today().strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
            )

else:
    st.info(t("no_questions_yet"))

# --- Footer ---
render_footer(libraries=["fpdf2"])
