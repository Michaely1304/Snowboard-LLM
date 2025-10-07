# Snowboard-LLM
A two-part project:
1. **snowboard_scraper_starter** – automated data collection of snowboard specs.
2. **snowboard_guru** – rule-based + LLM snowboard recommender (in progress).

# Snowboard Guru 🏂 — Conversational Recommender

A professional, from-scratch project to recommend the right snowboard based on rider profile (boot size, weight, height, skill, style, terrain). v0 uses a rules+ranking engine with a Gradio chat UI; later phases add RAG and LLM dialogue.

## Quickstart
```bash
python -m venv .venv
# activate venv, then
pip install -r requirements.txt
python -m src.app.gradio_app
