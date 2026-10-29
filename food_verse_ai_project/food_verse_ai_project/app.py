import os
import json
import math
import random
from typing import Any, Dict, List, Optional

import streamlit as st
import pandas as pd
import plotly.express as px
from PIL import Image

APP_NAME = "Food Verse AI"
st.set_page_config(page_title=APP_NAME, page_icon="🥗", layout="wide", initial_sidebar_state="expanded")

# ---------- Styling ----------
st.markdown("""
<style>
:root { --fv-green:#b7f34a; --fv-ink:#152018; --fv-muted:#647067; }
.block-container {padding-top: 1.6rem; max-width: 1450px;}
.hero {padding: 1.6rem 1.8rem; border-radius: 24px; background: linear-gradient(120deg,#17251c 0%,#28462f 60%,#6c9634 100%); color: white; margin-bottom: 1rem;}
.hero h1 {font-size: 2.45rem; margin: 0 0 .35rem 0; letter-spacing:-.04em;}
.hero p {font-size: 1.02rem; opacity:.92; margin:0;}
.pill {display:inline-block; background:#e9f8ce; color:#243a14; padding:.25rem .65rem; border-radius:999px; font-weight:700; font-size:.8rem; margin:.2rem .2rem .2rem 0;}
.small-muted {color:#68746b; font-size:.9rem;}
.metric-card {background:#f5f8f1; border:1px solid #e2e9dc; padding:1rem; border-radius:16px;}
div[data-testid="stMetric"] {background:#f5f8f1; border:1px solid #e2e9dc; padding:14px 16px; border-radius:16px;}
section[data-testid="stSidebar"] {background:#f7faF3;}
</style>
""", unsafe_allow_html=True)

# ---------- Data contracts and helpers ----------
FOOD_ESTIMATES = {
    "balanced bowl": {"calories": 520, "protein": 28, "carbs": 62, "fat": 16, "fiber": 10},
    "salad": {"calories": 310, "protein": 12, "carbs": 28, "fat": 17, "fiber": 9},
    "pizza": {"calories": 680, "protein": 27, "carbs": 78, "fat": 28, "fiber": 4},
    "rice and curry": {"calories": 560, "protein": 18, "carbs": 82, "fat": 16, "fiber": 8},
    "sandwich": {"calories": 430, "protein": 22, "carbs": 45, "fat": 17, "fiber": 6},
    "fruit plate": {"calories": 220, "protein": 3, "carbs": 55, "fat": 1, "fiber": 8},
}
ALLERGENS = ["milk", "dairy", "peanut", "tree nut", "wheat", "gluten", "soy", "egg", "fish", "shellfish", "sesame"]

def safe_json(text: str) -> Optional[Dict[str, Any]]:
    """Extract a JSON object from model output without assuming fenced formatting."""
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError:
        return None

def call_vision_model(image: Image.Image, prompt: str, provider: str, api_key: str, model: str) -> Optional[Dict[str, Any]]:
    """Optional Gemini/Groq vision integration. Returns parsed JSON or None on any failure."""
    try:
        if provider == "Gemini":
            from google import genai
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model or "gemini-2.5-flash",
                contents=[prompt, image],
                config={"response_mime_type": "application/json"}
            )
            return safe_json(response.text or "")
        # Groq supports vision models through OpenAI-compatible API; send resized image as data URI.
        import base64, io
        from groq import Groq
        buf = io.BytesIO()
        image.convert("RGB").save(buf, format="JPEG", quality=85)
        encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model or "meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}}
            ]}],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        return safe_json(response.choices[0].message.content or "")
    except Exception as exc:
        st.warning(f"AI provider unavailable; using demonstration mode. Details: {type(exc).__name__}: {exc}")
        return None

def demo_food_analysis(label: str) -> Dict[str, Any]:
    key = label.lower()
    profile = next((v for k, v in FOOD_ESTIMATES.items() if k in key), FOOD_ESTIMATES["balanced bowl"])
    return {
        "dish_name": label or "Mixed meal (demo estimate)",
        "cuisine": "Estimated from visible ingredients",
        "ingredients": ["Visible primary ingredients (verify manually)", "Cooking oil / seasoning may be present"],
        "portion_g": 350,
        "nutrition": profile,
        "allergens": ["Could not reliably verify from image; check ingredients and labels"],
        "health_score": 72,
        "notes": "Demonstration estimate only. Image-based portion and nutrition estimates can be substantially inaccurate."
    }

def demo_freshness(item: str) -> Dict[str, Any]:
    return {
        "item": item or "Unknown perishable food",
        "freshness_stage": "Moderately Fresh",
        "action": "Inspect closely and use promptly if storage history is safe",
        "storage": "Keep refrigerated at 4°C or below where appropriate; separate raw meat from ready-to-eat foods.",
        "visual_signs": ["Visual-only demo result; no validated spoilage classifier is connected."],
        "confidence": "Low (demonstration mode)"
    }

def demo_kitchen() -> Dict[str, Any]:
    return {
        "score": 75,
        "checks": [
            {"indicator": "Hair restraint", "status": "Review", "detail": "Confirm all food handlers have effective hair restraints."},
            {"indicator": "Glove / hand hygiene", "status": "Review", "detail": "Gloves do not replace handwashing; verify the workflow."},
            {"indicator": "Surface sanitation", "status": "Review", "detail": "Verify sanitizer concentration and contact time."},
            {"indicator": "Cross-contamination", "status": "Review", "detail": "Keep raw animal products physically separated from ready-to-eat produce."},
        ],
        "disclaimer": "Demo checklist only; a single image cannot establish regulatory compliance."
    }

def nutrition_score(n: Dict[str, Any]) -> int:
    calories = max(0, float(n.get("calories", 0) or 0))
    protein = max(0, float(n.get("protein", 0) or 0))
    fiber = max(0, float(n.get("fiber", 0) or 0))
    sugar = max(0, float(n.get("sugar", 0) or 0))
    score = 55 + min(protein, 35) * 0.55 + min(fiber, 15) * 1.1 - max(0, calories - 500) / 45 - sugar * 0.25
    return int(max(1, min(100, round(score))))

def calculate_tdee(age: int, gender: str, weight: float, height: float, activity: str) -> Dict[str, float]:
    # Mifflin-St Jeor estimate. Gender coefficient is a model assumption; this is not clinical advice.
    coefficient = 5 if gender == "Male" else (-161 if gender == "Female" else -78)
    bmr = 10 * weight + 6.25 * height - 5 * age + coefficient
    factors = {"Sedentary": 1.2, "Lightly active": 1.375, "Moderately active": 1.55, "Very active": 1.725, "Extra active": 1.9}
    return {"bmr": max(0, bmr), "tdee": max(0, bmr * factors.get(activity, 1.2))}

def meal_schedule(calories: int, diet: str, goal: str) -> List[Dict[str, Any]]:
    templates = {
        "Balanced": [
            ("Oats, yogurt and fruit", "Dal, rice, seasonal vegetables", "Paneer/tofu wrap", "Chickpea salad"),
            ("Egg/tofu scramble and toast", "Rajma, rice and salad", "Fruit and nuts", "Vegetable khichdi with curd"),
            ("Poha with peas", "Chickpea bowl", "Yogurt or soy yogurt", "Roti, dal and vegetables"),
        ],
        "Vegan": [
            ("Oats with soy milk and banana", "Chickpea quinoa bowl", "Roasted chana and fruit", "Tofu, roti and vegetables"),
            ("Peanut-butter toast and fruit", "Rajma rice with salad", "Soy yogurt", "Lentil soup and wholegrain toast"),
            ("Tofu scramble and toast", "Lentil and vegetable bowl", "Hummus with carrots", "Chickpea curry and rice"),
        ],
        "Keto": [
            ("Paneer/tofu scramble with greens", "Cauliflower rice bowl", "Nuts and cucumber", "Grilled paneer/tofu with vegetables"),
            ("Unsweetened yogurt or tofu bowl", "Salad with eggs/tofu and olive oil", "Cheese or nuts (if suitable)", "Zucchini noodles with protein"),
            ("Omelette or tofu scramble", "Low-carb vegetable bowl", "Seeds and cucumber", "Paneer/tofu with sautéed greens"),
        ],
        "Diabetic-Friendly": [
            ("Unsweetened oats with nuts", "Dal, modest wholegrain roti and vegetables", "Plain yogurt and nuts", "Protein with non-starchy vegetables"),
            ("Besan chilla with vegetables", "Beans, salad and a modest grain portion", "Apple with nut butter", "Vegetable soup and paneer/tofu"),
            ("Egg/tofu and vegetable scramble", "Wholegrain roti, dal and salad", "Roasted chana", "Fish/paneer/tofu with vegetables"),
        ],
    }
    items = templates.get(diet, templates["Balanced"])
    days = []
    for i in range(7):
        breakfast, lunch, snack, dinner = items[i % len(items)]
        days.append({"Day": f"Day {i+1}", "Breakfast": breakfast, "Lunch": lunch, "Snack": snack, "Dinner": dinner})
    return days

def grocery_list(days: List[Dict[str, Any]]) -> List[str]:
    common = ["Seasonal vegetables", "Leafy greens", "Fresh fruit", "Onions, tomatoes, garlic, ginger", "Whole grains / rice / roti ingredients", "Lentils and beans", "Protein source suited to your diet", "Nuts / seeds (if safe)", "Cooking oil and basic spices"]
    return common

# ---------- Sidebar / configuration ----------
with st.sidebar:
    st.markdown("## 🥗 Food Verse AI")
    st.caption("Multimodal food intelligence")
    page = st.radio("Navigate", [
        "Overview", "Food Recognition & Nutrition", "Freshness & Spoilage",
        "Kitchen Hygiene", "Smart Recipe Coach", "Personalized Meal Planner"
    ])
    st.divider()
    st.markdown("### AI configuration")
    provider = st.selectbox("Vision provider", ["Demo mode (no API)", "Gemini", "Groq"])
    api_key = ""
    model = ""
    if provider != "Demo mode (no API)":
        api_key = st.text_input(f"{provider} API key", type="password", help="Used only for this app session; do not commit keys to source control.")
        model = st.text_input("Model override (optional)", value="gemini-2.5-flash" if provider == "Gemini" else "meta-llama/llama-4-scout-17b-16e-instruct")
    st.caption("API keys are not written to disk by this app.")
    st.divider()
    st.caption("Safety note: AI output is an estimate, not a substitute for food-safety inspection or professional nutrition advice.")

def analyze_image(image: Image.Image, prompt: str, demo: Dict[str, Any]) -> Dict[str, Any]:
    if provider != "Demo mode (no API)" and api_key.strip():
        result = call_vision_model(image, prompt, provider, api_key.strip(), model.strip())
        if result is not None:
            return result
    return demo

# ---------- Header ----------
st.markdown(f"""
<div class="hero">
  <h1>🥗 Food Verse AI</h1>
  <p>Multimodal food intelligence for nutrition awareness, freshness checks, kitchen safety and smarter meal planning.</p>
  <div style="margin-top:.75rem">
    <span class="pill">Food intelligence</span><span class="pill">Nutrition</span><span class="pill">Kitchen safety</span><span class="pill">Meal planning</span>
  </div>
</div>
""", unsafe_allow_html=True)

if page == "Overview":
    st.subheader("Your kitchen, with more context.")
    st.write("Explore five connected workflows. Use demo mode to test the interface without credentials, or add a supported vision-model API key in the sidebar.")
    cols = st.columns(3)
    cards = [
        ("📸", "Food recognition", "Dish identification, ingredient hypotheses and nutrition estimates."),
        ("🍓", "Freshness diagnostic", "Visual cues to inspect, with clear limitations around spoilage."),
        ("🧼", "Kitchen hygiene", "Checklist-style review of visible safety indicators."),
        ("👩‍🍳", "Recipe coach", "Turn pantry ingredients into practical meal ideas."),
        ("🎯", "Meal planner", "Estimate BMR/TDEE and draft a flexible 7-day plan."),
        ("🔒", "Privacy-first demo", "No database required; API keys stay in session memory.")
    ]
    for i, (emoji, title, desc) in enumerate(cards):
        with cols[i % 3]:
            st.markdown(f"<div class='metric-card'><h3>{emoji} {title}</h3><p>{desc}</p></div>", unsafe_allow_html=True)
    st.info("Important: demo outputs are illustrative. Visual inspection alone cannot reliably establish food safety, detect pathogens, or certify regulatory compliance.")

elif page == "Food Recognition & Nutrition":
    st.subheader("Food Recognition & Nutrition Audit")
    st.write("Upload a meal photo. Model results and nutrient values are estimates; confirm ingredients, weights and product labels for accuracy.")
    uploaded = st.file_uploader("Upload meal photo", type=["jpg", "jpeg", "png", "webp"], key="food_img")
    portion = st.number_input("Approximate portion size (grams)", min_value=1, max_value=3000, value=350, step=25)
    if uploaded:
        image = Image.open(uploaded).convert("RGB")
        st.image(image, caption="Uploaded meal", use_container_width=True)
        prompt = f"""Analyze this meal image for nutrition awareness. Return ONLY JSON with keys: dish_name (string), cuisine (string), ingredients (array of strings), portion_g (number), nutrition (object with calories, protein, carbs, fat, fiber in numeric units kcal/g), allergens (array of possible allergens or uncertainties), health_score (integer 1-100), notes (string). Estimate conservatively. Do not claim allergens are absent based only on an image. Use portion_g={portion}. State uncertainty in notes."""
        result = analyze_image(image, prompt, demo_food_analysis("balanced bowl"))
        nutrition = result.get("nutrition", {}) if isinstance(result, dict) else {}
        try:
            scale = float(portion) / max(1, float(result.get("portion_g", portion)))
        except Exception:
            scale = 1.0
        if provider == "Demo mode (no API)" or not api_key.strip():
            scale = 1.0
        st.markdown(f"### {result.get('dish_name', 'Meal analysis')}")
        st.caption(f"Cuisine: {result.get('cuisine', 'Not identified')} · Estimated portion: {result.get('portion_g', portion)} g")
        st.write("**Ingredients identified / hypothesized**")
        st.write(", ".join(map(str, result.get("ingredients", ["Not available"]))))
        keys = [("Calories", "calories", "kcal"), ("Protein", "protein", "g"), ("Carbohydrates", "carbs", "g"), ("Fat", "fat", "g"), ("Fiber", "fiber", "g")]
        cols = st.columns(5)
        values = []
        for col, (label, key, unit) in zip(cols, keys):
            val = float(nutrition.get(key, 0) or 0) * scale
            values.append({"Nutrient": label, "Amount": val, "Unit": unit})
            col.metric(label, f"{val:.0f} {unit}" if unit == "kcal" else f"{val:.1f} {unit}")
        left, right = st.columns([1.2, 1])
        with left:
            df = pd.DataFrame([{"Macro": "Protein", "grams": float(nutrition.get("protein", 0) or 0) * scale},
                               {"Macro": "Carbohydrates", "grams": float(nutrition.get("carbs", 0) or 0) * scale},
                               {"Macro": "Fat", "grams": float(nutrition.get("fat", 0) or 0) * scale},
                               {"Macro": "Fiber", "grams": float(nutrition.get("fiber", 0) or 0) * scale}])
            st.plotly_chart(px.bar(df, x="Macro", y="grams", title="Estimated nutrients (g)", color="Macro"), use_container_width=True)
        with right:
            score = int(result.get("health_score", nutrition_score(nutrition)) or nutrition_score(nutrition))
            st.metric("Composite health score", f"{score}/100")
            st.progress(max(0, min(100, score)) / 100)
            st.write("**Allergen alerts / uncertainty**")
            for allergen in result.get("allergens", ["Not assessed"]):
                st.warning(str(allergen))
        if result.get("notes"):
            st.info(str(result["notes"]))
        st.caption("Nutrition values can vary widely by recipe, cooking method and portion size. This score is a heuristic, not a validated clinical metric.")

elif page == "Freshness & Spoilage":
    st.subheader("Food Freshness & Spoilage Diagnostic")
    st.warning("A photo cannot reliably detect pathogens, toxins, internal spoilage or unsafe time-temperature history. When in doubt, discard; never taste food to test safety.")
    uploaded = st.file_uploader("Upload raw ingredient / perishable food photo", type=["jpg", "jpeg", "png", "webp"], key="fresh_img")
    item = st.selectbox("Food category", ["Fruit", "Vegetable", "Raw meat / poultry", "Fish / seafood", "Dairy", "Leftovers", "Other"])
    if uploaded:
        image = Image.open(uploaded).convert("RGB")
        st.image(image, caption="Uploaded item", use_container_width=True)
        prompt = f"""Assess only visible visual cues in this image of {item}. Return JSON keys: item, freshness_stage (Fresh|Moderately Fresh|Spoiled), action, storage, visual_signs (array), confidence. Never claim food is safe based only on appearance. If meat, seafood, dairy or leftovers are involved, emphasize time-temperature history and official food safety guidance. Do not recommend consuming suspicious food."""
        result = analyze_image(image, prompt, demo_freshness(item))
        stage = result.get("freshness_stage", "Uncertain")
        if stage == "Fresh":
            st.success(f"Visual assessment: {stage}")
        elif stage == "Spoiled":
            st.error(f"Visual assessment: {stage}")
        else:
            st.warning(f"Visual assessment: {stage}")
        st.markdown(f"**Item:** {result.get('item', item)}")
        st.markdown(f"**Suggested action:** {result.get('action', 'Use caution and verify storage history.')}")
        st.markdown(f"**Storage guidance:** {result.get('storage', 'Follow food-specific storage guidance.')}")
        st.markdown("**Visible cues**")
        for cue in result.get("visual_signs", []):
            st.write(f"- {cue}")
        st.caption(f"Confidence: {result.get('confidence', 'Not supplied')} · AI assessment is not a food-safety certification.")

elif page == "Kitchen Hygiene":
    st.subheader("Kitchen Hygiene & Food Safety Compliance")
    st.write("Review a still image or a selected video frame. This prototype does not perform continuous video surveillance or validated PPE detection.")
    media_type = st.radio("Input type", ["Image", "Video"], horizontal=True)
    if media_type == "Image":
        uploaded = st.file_uploader("Upload kitchen image", type=["jpg", "jpeg", "png", "webp"], key="kitchen_img")
        if uploaded:
            image = Image.open(uploaded).convert("RGB")
            st.image(image, caption="Kitchen image", use_container_width=True)
            prompt = """Review this kitchen image for visible food-safety indicators. Return JSON keys: score (0-100), checks (array of objects with indicator, status [Pass|Review|Violation|Not visible], detail), disclaimer. Assess hair restraint, glove/hand hygiene only if observable, surface sanitation only if observable, and raw-vs-ready-to-eat separation. Do not infer invisible practices or certify compliance."""
            result = analyze_image(image, prompt, demo_kitchen())
            score = int(result.get("score", 0) or 0)
            st.metric("Visible-indicator review score", f"{score}%")
            st.progress(max(0, min(100, score)) / 100)
            checks = result.get("checks", [])
            if checks:
                st.dataframe(pd.DataFrame(checks), use_container_width=True, hide_index=True)
            st.info(result.get("disclaimer", "This is not a regulatory inspection."))
    else:
        video = st.file_uploader("Upload kitchen video (MP4/MOV)", type=["mp4", "mov", "avi", "mkv"], key="kitchen_video")
        if video:
            st.video(video)
            st.info("For this lightweight cloud prototype, upload and playback are supported. Video-frame sampling and temporal hazard detection are not enabled. Export a representative frame and upload it under Image for a visual review.")
    st.caption("Use local food-safety regulations, documented temperature logs, sanitation records and trained human inspection for compliance decisions.")

elif page == "Smart Recipe Coach":
    st.subheader("Smart Kitchen Recipe Assistant")
    ingredients = st.text_area("What ingredients do you have?", placeholder="e.g. paneer, tomatoes, spinach, rice, chickpeas, yogurt")
    diet = st.selectbox("Diet preference", ["No restriction", "Vegetarian", "Vegan", "Keto", "Diabetic-Friendly"])
    cuisine = st.selectbox("Cuisine direction", ["Any", "Indian", "Mediterranean", "East Asian", "Mexican", "Quick comfort food"])
    time_limit = st.slider("Maximum cooking time (minutes)", 10, 120, 35, 5)
    if st.button("Generate recipe ideas", type="primary"):
        if not ingredients.strip():
            st.error("Add at least one ingredient to continue.")
        elif provider != "Demo mode (no API)" and api_key.strip():
            recipe_prompt = f"""Create 3 practical recipes using these pantry ingredients: {ingredients}. Diet: {diet}. Cuisine: {cuisine}. Maximum time: {time_limit} minutes. Include title, servings, cooking time, difficulty, ingredients with approximate amounts, numbered steps, substitutions, and food safety notes. Return JSON {{\"recipes\":[...]}}."""
            # Text-only recipe generation uses Gemini or Groq chat.
            try:
                if provider == "Gemini":
                    from google import genai
                    client = genai.Client(api_key=api_key.strip())
                    resp = client.models.generate_content(model=model.strip() or "gemini-2.5-flash", contents=recipe_prompt)
                    payload = safe_json(resp.text or "")
                else:
                    from groq import Groq
                    client = Groq(api_key=api_key.strip())
                    resp = client.chat.completions.create(model=model.strip() or "llama-3.3-70b-versatile", messages=[{"role":"user","content":recipe_prompt}], response_format={"type":"json_object"})
                    payload = safe_json(resp.choices[0].message.content or "")
                recipes = (payload or {}).get("recipes", [])
            except Exception as exc:
                st.warning(f"Recipe AI unavailable ({type(exc).__name__}); showing demo recipe.")
                recipes = []
        else:
            recipes = []
        if not recipes:
            recipes = [{
                "title": "Flexible Pantry Skillet",
                "servings": 2,
                "cooking_time": min(time_limit, 30),
                "difficulty": "Easy",
                "ingredients": [x.strip() for x in ingredients.split(",") if x.strip()] + ["Oil, salt and spices as needed"],
                "steps": ["Wash produce and prepare ingredients.", "Cook aromatics and firm vegetables in a pan.", "Add the main protein or legumes and cook thoroughly.", "Season, adjust texture with water or stock, and serve."],
                "substitutions": ["Use tofu, beans or paneer according to your diet.", "Use herbs, lemon or spices to adjust flavour."],
                "food_safety": "Keep raw animal products separate and cook them to a safe internal temperature."
            }]
        for recipe in recipes:
            with st.expander(f"🍲 {recipe.get('title', 'Recipe idea')} · {recipe.get('cooking_time', time_limit)} min", expanded=True):
                st.write(f"**Servings:** {recipe.get('servings', 2)} · **Difficulty:** {recipe.get('difficulty', 'Easy')}")
                st.write("**Ingredients**")
                for ing in recipe.get("ingredients", []):
                    st.write(f"- {ing}")
                st.write("**Method**")
                for i, step in enumerate(recipe.get("steps", []), 1):
                    st.write(f"{i}. {step}")
                st.write("**Substitutions**")
                for sub in recipe.get("substitutions", []):
                    st.write(f"- {sub}")
                if recipe.get("food_safety"):
                    st.caption(f"Food safety: {recipe['food_safety']}")

elif page == "Personalized Meal Planner":
    st.subheader("Personalized Meal Planner")
    st.write("Estimates use the Mifflin–St Jeor equation and activity multipliers. They are starting points, not medical nutrition prescriptions.")
    with st.form("profile_form"):
        c1, c2, c3 = st.columns(3)
        age = c1.number_input("Age (years)", min_value=18, max_value=100, value=25)
        gender = c2.selectbox("Equation coefficient", ["Female", "Male", "Neutral / not specified"])
        weight = c3.number_input("Weight (kg)", min_value=25.0, max_value=300.0, value=70.0, step=0.5)
        c4, c5, c6 = st.columns(3)
        height = c4.number_input("Height (cm)", min_value=100.0, max_value=240.0, value=170.0, step=0.5)
        activity = c5.selectbox("Activity level", ["Sedentary", "Lightly active", "Moderately active", "Very active", "Extra active"])
        diet = c6.selectbox("Dietary pattern", ["Balanced", "Vegan", "Keto", "Diabetic-Friendly"])
        goal = st.selectbox("Fitness goal", ["Maintenance", "Fat Loss", "Muscle Gain"])
        constraints = st.text_input("Allergies / exclusions (optional)", placeholder="e.g. peanuts, lactose, shellfish")
        submitted = st.form_submit_button("Calculate targets & build 7-day plan", type="primary")
    if submitted:
        result = calculate_tdee(int(age), gender, float(weight), float(height), activity)
        tdee = result["tdee"]
        target = tdee
        if goal == "Fat Loss":
            target = max(1200, tdee - 400)
        elif goal == "Muscle Gain":
            target = tdee + 250
        c1, c2, c3 = st.columns(3)
        c1.metric("Estimated BMR", f"{result['bmr']:.0f} kcal/day")
        c2.metric("Estimated TDEE", f"{tdee:.0f} kcal/day")
        c3.metric("Starting calorie target", f"{target:.0f} kcal/day")
        st.caption(f"Goal: {goal} · Diet: {diet} · Exclusions noted: {constraints or 'None supplied'}")
        days = meal_schedule(int(target), diet, goal)
        st.dataframe(pd.DataFrame(days), use_container_width=True, hide_index=True)
        st.markdown("### Grocery checklist")
        for item in grocery_list(days):
            st.checkbox(item, key=f"grocery_{item}")
        st.download_button("Download 7-day plan (CSV)", data=pd.DataFrame(days).to_csv(index=False), file_name="food_verse_7_day_meal_plan.csv", mime="text/csv")
        st.info("This prototype does not calculate verified meal-level calories or automatically enforce all allergies. Review every ingredient, especially for allergies, pregnancy, diabetes, kidney disease or other clinical needs.")

st.divider()
st.caption("Food Verse AI · Skill Wallet Capstone Project 3 · Prototype. AI-generated outputs can be wrong; use trained human judgement for food safety and health decisions.")
