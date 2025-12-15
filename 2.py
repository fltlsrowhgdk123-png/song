import streamlit as st
import pandas as pd
import json, os, sqlite3
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import urllib.parse
from openai import OpenAI
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# ======================
# 🌈 UI 스타일
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
# 한글 폰트
# ======================
font_path = "C:/Windows/Fonts/malgun.ttf"
if os.path.exists(font_path):
    font_prop = fm.FontProperties(fname=font_path)
    plt.rcParams["font.family"] = font_prop.get_name()
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
    # ✅ 방법 1: 무조건 3칸 채움
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
# GPT
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

def summarize_lyrics(title, artist):
    prompt = f"""
노래 가사의 핵심 감정을 1문장,
추천 이유를 1문장으로 설명하라.

노래: {title}
가수: {artist}
"""
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )
    return res.choices[0].message.content.strip()

# ======================
# 시각화
# ======================
def plot_emotion_distribution(df):
    fig, ax = plt.subplots()
    df["emotion"].value_counts().plot(kind="bar", ax=ax)
    ax.set_title("감정 분포")
    st.pyplot(fig)

# ======================
# UI
# ======================
st.set_page_config(page_title="감정 기반 음악 추천", layout="centered")
init_db()

st.markdown("""
<div class="header-card">
<h1>🎧 감정 기반 음악 추천</h1>
<p>당신의 감정을 분석해 음악과 심리 방향을 제안합니다</p>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="section-card">✍️ 지금 감정을 적어보세요</div>', unsafe_allow_html=True)

text = st.text_area(
    "",
    placeholder="예: 곧 방학이라 신난다!",
    height=120,
    label_visibility="collapsed"
)

run = st.button("분석 실행", use_container_width=True)

if run and text.strip():
    result = analyze_and_recommend(text)

    st.markdown('<div class="highlight-card">', unsafe_allow_html=True)
    st.subheader("🧠 감정 분석")
    st.write(f"**감정:** {result['emotion']}")
    st.write(result["summary"])
    st.write(f"👉 {result['solution']}")
    st.markdown('</div>', unsafe_allow_html=True)

    st.subheader("🎵 추천 음악")

    songs = []
    for s in result["songs"]:
        if spotify_exists(s["title"], s["artist"]):
            songs.append(f"{s['title']} - {s['artist']}")

    for song in songs:
        title, artist = song.split(" - ", 1)
        st.write(f"**{title}** / {artist}")
        st.markdown(f"[▶ 유튜브에서 듣기]({youtube_url(title, artist)})")
        st.caption(summarize_lyrics(title, artist))

    save_log(result, songs)
    st.success("기록 저장 완료")

st.divider()
st.subheader("📊 감정 기록")

df = load_emotion_logs()
if not df.empty:
    st.dataframe(df)
    plot_emotion_distribution(df)
else:
    st.info("아직 기록이 없습니다.")

st.divider()
st.caption(
    "⚠️ 본 분석과 권장 사항은 참고용이며, "
    "정확한 판단과 결정의 책임은 사용자 본인에게 있습니다."
)
