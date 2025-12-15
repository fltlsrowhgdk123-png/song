import streamlit as st
import pandas as pd
import json, os, sqlite3
from datetime import datetime
import matplotlib.pyplot as plt
import urllib.parse
from openai import OpenAI
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# ======================
# UI 스타일
# ======================
st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #3e2723, #5d4037);
}
.block-container {
    background: #fcfdff;
    border-radius: 22px;
    padding: 2.5rem;
    margin-top: 2.5rem;
    max-width: 900px;
}
.header-card {
    background: linear-gradient(135deg, #a1887f, #8d6e63);
    color: white;
    padding: 2rem;
    border-radius: 20px;
    text-align: center;
}
.section-card {
    background: white;
    border-radius: 18px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
}
.highlight-card {
    background: #f3e5f5;
    border-left: 6px solid #8d6e63;
    padding: 1.2rem;
    border-radius: 14px;
}
</style>
""", unsafe_allow_html=True)

# ======================
# matplotlib (클라우드 안전 설정)
# ======================
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["axes.unicode_minus"] = False

# ======================
# 기본 설정
# ======================
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

sp = spotipy.Spotify(
    auth_manager=SpotifyClientCredentials(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET")
    )
)

DB_FILE = "emotion_music.db"

# ======================
# DB
# ======================
def get_conn():
    return sqlite3.connect(DB_FILE)

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        datetime TEXT,
        emotion TEXT,
        summary TEXT,
        solution TEXT,
        kpop TEXT,
        pop TEXT,
        jpop TEXT
    )
    """)
    conn.commit()
    conn.close()

def save_log(result, songs):
    while len(songs) < 3:
        songs.append(None)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO logs VALUES (?,?,?,?,?,?,?)",
        (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            result["emotion"],
            result["summary"],
            result["solution"],
            songs[0], songs[1], songs[2]
        )
    )
    conn.commit()
    conn.close()

def load_emotion_logs():
    conn = get_conn()
    df = pd.read_sql(
        "SELECT datetime, emotion FROM logs ORDER BY datetime DESC",
        conn
    )
    conn.close()
    return df

# ======================
# GPT (입력 감정 분석 + 음악 추천)
# ======================
def analyze_and_recommend(text):
    prompt = f"""
반드시 JSON만 출력하라.

{{
  "emotion": "",
  "summary": "",
  "solution": "",
  "songs": [
    {{"type":"KPOP","title":"","artist":""}},
    {{"type":"POP","title":"","artist":""}},
    {{"type":"JPOP","title":"","artist":""}}
  ]
}}

문장:
{text}
"""
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6
    )
    return json.loads(res.choices[0].message.content)

# ======================
# GPT (가사 의미 + 추천 이유)
# ======================
def summarize_lyrics(title, artist):
    prompt = f"""
다음 노래에 대해 답하라.

1. 가사의 핵심 감정을 1문장
2. 지금 이 노래를 추천하는 이유 1문장

노래 제목: {title}
가수: {artist}
"""
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )
    return res.choices[0].message.content.strip()

# ======================
# GPT (누적 감정 분석)
# ======================
def analyze_emotion_history(df):
    counts = df["emotion"].value_counts().to_dict()

    prompt = f"""
다음은 한 사용자의 감정 기록 통계다.

Emotion distribution:
{counts}

반드시 JSON만 출력하라.

{{
  "emotion": "dominant emotional state",
  "summary": "overall emotional trend summary",
  "solution": "recommended actions"
}}
"""
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )
    return json.loads(res.choices[0].message.content)

# ======================
# 링크
# ======================
def spotify_exists(title, artist):
    q = f"track:{title} artist:{artist}"
    r = sp.search(q=q, type="track", limit=1)
    return len(r["tracks"]["items"]) > 0

def youtube_url(title, artist):
    q = urllib.parse.quote(f"{title} {artist}")
    return f"https://www.youtube.com/results?search_query={q}"

# ======================
# 시각화 (한글 제거)
# ======================
def plot_emotion_distribution(df):
    fig, ax = plt.subplots()
    df["emotion"].value_counts().plot(kind="bar", ax=ax)
    ax.set_title("Emotion Distribution")
    ax.set_xlabel("Emotion")
    ax.set_ylabel("Count")
    st.pyplot(fig)

# ======================
# UI
# ======================
st.set_page_config(page_title="Emotion-based Music Recommendation", layout="centered")
init_db()

st.markdown("""
<div class="header-card">
<h1>🎧 Music Counseling</h1>
<p>Analyze your emotional state through music</p>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="section-card">✍️ Write how you feel</div>', unsafe_allow_html=True)

text = st.text_area("", height=120, label_visibility="collapsed")
run = st.button("Analyze", use_container_width=True)

if run and text.strip():
    result = analyze_and_recommend(text)

    st.subheader("🎵 Recommended Music")

    songs = []
    for s in result["songs"]:
        if spotify_exists(s["title"], s["artist"]):
            songs.append(f"{s['title']} - {s['artist']}")

    for song in songs:
        title, artist = song.split(" - ", 1)
        st.markdown(f"### 🎶 {title} / {artist}")
        st.markdown(f"[▶ Listen on YouTube]({youtube_url(title, artist)})")
        st.caption(summarize_lyrics(title, artist))

    save_log(result, songs)
    st.success("Saved successfully")

st.divider()
st.subheader("📊 Emotion History")

df = load_emotion_logs()
if not df.empty:
    st.dataframe(df)
    plot_emotion_distribution(df)

    analysis = analyze_emotion_history(df)

    st.markdown(f"""
<div class="highlight-card">
<b>🧠 Current State</b><br>
{analysis["emotion"]}<br><br>
<b>📌 Summary</b><br>
{analysis["summary"]}<br><br>
<b>🧭 Recommendation</b><br>
{analysis["solution"]}
</div>
""", unsafe_allow_html=True)
else:
    st.info("No records yet.")

st.divider()
st.caption(
    "⚠️ This analysis is for reference only. Final decisions are your responsibility."
)
