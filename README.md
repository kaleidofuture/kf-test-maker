---
title: kf-test-maker
emoji: 🚀
colorFrom: green
colorTo: blue
sdk: streamlit
sdk_version: 1.44.1
app_file: app.py
pinned: false
---

# KF-TestMaker

> テスト問題を作成し、難易度分析付きPDFを生成するアプリ。

## The Problem

Creating tests takes up to 30 hours for educators — writing questions, balancing difficulty, formatting answer sheets. This app handles it all in one workflow.

## How It Works

1. Enter questions with choices and correct answers via form
2. Bulk-edit questions using the interactive data editor
3. View automatic difficulty analysis (Flesch-Kincaid) with balance distribution
4. Generate and download test paper PDF (questions only) + answer key PDF

## Libraries Used

- **textstat** — Automatic readability / difficulty analysis (Flesch-Kincaid, Flesch Reading Ease)
- **fpdf2** — PDF generation with Unicode support

## Development

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deployment

Hosted on [Hugging Face Spaces](https://huggingface.co/spaces/mitoi/kf-test-maker).

---

Part of the [KaleidoFuture AI-Driven Development Research](https://kaleidofuture.com) — proving that everyday problems can be solved with existing libraries, no AI model required.
