# 🚀 Deploying InvestMate AI to Streamlit Community Cloud

This guide walks you through deploying **InvestMate AI** on [Streamlit Community Cloud](https://share.streamlit.io/) for free with automated SSL/HTTPS and zero maintenance.

---

### Step 1: Push Code to GitHub

1. Create a new repository on [GitHub](https://github.com/new) named `investmate-ai`.
2. In your terminal inside the `Investmate` project directory, run:
```bash
git init
git add .
git commit -m "Deploy: InvestMate AI initial release"
git branch -M main
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/investmate-ai.git
git push -u origin main
```

*(Note: Your `.env` and `investmate.db` are automatically ignored by `.gitignore` to protect your API keys.)*

---

### Step 2: Deploy on Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io/) and sign in with your GitHub account.
2. Click **"New app"**.
3. Select:
   - **Repository:** `YOUR_GITHUB_USERNAME/investmate-ai`
   - **Branch:** `main`
   - **Main file path:** `app.py`
4. Expand **"Advanced settings..."** (or click on **Settings** $\rightarrow$ **Secrets** after creating the app).
5. In the **Secrets** box, paste your API keys:

```toml
# Streamlit Community Cloud Secrets
GROQ_API_KEY = "your_groq_api_key_here"
ELEVENLABS_API_KEY = "your_elevenlabs_api_key_here"
ELEVENLABS_VOICE_ID = "EXAVITQu4vr4xnSDxMaL"
LLM_MODEL = "qwen/qwen3.8-27b"
BASE_CURRENCY = "INR"
VOICE_ENABLED = "true"
```

6. Click **"Deploy!"**.

---

### Step 3: Done! 

Streamlit Community Cloud will:
- Automatically read `packages.txt` and install Linux audio codecs (`libsndfile1`, `ffmpeg`).
- Automatically read `requirements.txt` and install dependencies.
- Auto-initialize the SQLite database and seed real Indian market data.
- Provide you with a permanent public link: `https://YOUR_APP_NAME.streamlit.app`
