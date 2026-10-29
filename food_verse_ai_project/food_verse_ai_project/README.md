# Food Verse AI — Multimodal Food Intelligence Agent

**Skill Wallet Capstone Project 3**  
A Streamlit prototype for food recognition/nutrition awareness, freshness visual review, kitchen hygiene checklists, pantry recipe ideas, and a personalized 7-day meal planner.

## Features

- Demo mode works without API credentials.
- Optional Gemini or Groq vision-model integration for food, freshness, and kitchen-image analysis.
- Optional AI-generated recipe ideas.
- Estimated nutrition metrics and macro chart.
- Freshness warning language that avoids treating image analysis as proof of safety.
- Kitchen checklist with image review and video upload/playback (video-frame analysis is not enabled).
- Mifflin–St Jeor BMR/TDEE estimate, goal-based calorie starting point, 7-day schedule, grocery checklist, CSV export.
- No external database or persistent storage required.

## Run locally

Python 3.10–3.12 is recommended for widest dependency compatibility.

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

## API configuration

Use the sidebar. Select **Gemini** or **Groq**, paste an API key into the password field, and optionally choose a model. Keys are held in Streamlit session state/input memory and are not saved to a file by this application. Do not commit API keys to GitHub.

- Gemini uses the `google-genai` SDK.
- Groq uses the `groq` SDK and a vision-capable model for image tasks. If a model is unavailable to your account, use demo mode or select a supported model in the sidebar.

## Deploy to Streamlit Community Cloud

1. Create a GitHub repository and upload `app.py`, `requirements.txt`, and `README.md`.
2. In Streamlit Community Cloud, create an app from that repository and select `app.py`.
3. Deploy. Demo mode runs without secrets.
4. For API usage, you may enter a key in the app sidebar each session. For a shared deployment, prefer Streamlit Secrets and server-side configuration rather than asking users to paste a shared key. Never expose a shared API key in a public frontend.

## Important limitations

This is a capstone prototype, not a validated medical, nutrition, food inspection, or HACCP system.

- Image-based portion and nutrient estimates can be inaccurate; recipes, brands, oils, and portion weights change results.
- Allergen absence cannot be established from an image. Always inspect labels and confirm ingredients.
- Photos cannot reliably detect pathogens, toxins, internal spoilage, or time-temperature abuse. Never taste suspect food to test it; when in doubt, discard.
- A single kitchen photo cannot establish regulatory compliance or verify invisible practices. Human inspection, temperature logs, cleaning records, and local regulations remain necessary.
- The meal schedule is a flexible template. It does not verify meal calories, macro totals, medical suitability, or allergy safety.
- The score is heuristic, not a clinically validated health score.
- For real production use, add automated tests, structured validation (e.g. Pydantic), rate limits, logging without sensitive data, model/version controls, and domain-expert review.

## Suggested project structure

```text
food-verse-ai/
├── app.py
├── requirements.txt
└── README.md
```
