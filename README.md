# Tactify — AI Soccer Coaching Analysis

Upload footage of a player or play → get professional coaching feedback powered by Claude AI.

## Quick Start (local)

1. **Install Python 3.11+** — https://python.org/downloads

2. **Open Terminal, navigate to this folder:**
   ```
   cd ~/tactify
   ```

3. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```

4. **Set your API key:**
   ```
   cp .env.example .env
   ```
   Then open `.env` and replace `your_api_key_here` with your actual key from https://console.anthropic.com/settings/keys

5. **Run the app:**
   ```
   streamlit run app.py
   ```
   It will open automatically in your browser at http://localhost:8501

## Deploy (free shareable link via Streamlit Cloud)

1. Push this folder to a GitHub repository (must be public or you must have Streamlit Cloud access)
2. Go to https://share.streamlit.io
3. Click "New app" → connect your GitHub repo → set main file to `app.py`
4. Add your `ANTHROPIC_API_KEY` under "Advanced settings → Secrets"
5. Click Deploy → you get a public URL to share

## What it does

- Upload a JPG/PNG image or MP4/MOV video clip of a soccer player
- Set context: position, play type, age group
- Claude AI analyzes the footage against a knowledge base of professional coaching frameworks
- Returns a structured report: observations, strengths, improvements, drills, professional reference
