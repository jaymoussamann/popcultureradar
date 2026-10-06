import io
import contextlib
from datetime import datetime, timezone

import streamlit as st

st.set_page_config(
    page_title="Pop Culture Radar",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
.block-container {max-width: 1050px; padding-top: 2rem; padding-bottom: 4rem;}
[data-testid="stMetric"] {background: rgba(127,127,127,0.08); padding: 14px; border-radius: 14px;}
.radar-card {
    border: 1px solid rgba(127,127,127,0.25);
    border-radius: 18px;
    padding: 20px 22px;
    margin: 12px 0 18px 0;
}
.radar-title {font-size: 1.2rem; font-weight: 700; margin-bottom: 8px;}
.radar-meta {opacity: 0.75; margin-bottom: 10px;}
.move-cover {font-weight: 800; font-size: 1.05rem;}
.move-investigate {font-weight: 800; font-size: 1.05rem;}
.move-watch {font-weight: 800; font-size: 1.05rem;}
.small-note {opacity: 0.7; font-size: 0.9rem;}
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=900, show_spinner=False)
def run_radar():
    # Importing radar runs the existing collection/scoring engine.
    # Capture its console output so the web app stays clean.
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        import radar
    return radar.ranked_opportunities, radar.final_topics

def source_links(topic):
    links = []
    seen = set()
    for item in topic.get("items", []):
        url = item.get("link", "")
        source = item.get("source", "")
        title = item.get("title", "")
        key = (source, url)
        if url and key not in seen:
            seen.add(key)
            links.append((source, title, url))
    return links

def render_card(item):
    topic = item["topic"]
    move = item["move"]

    if move == "COVER NOW":
        move_label = "🚨 COVER NOW"
        css_class = "move-cover"
    elif move == "INVESTIGATE":
        move_label = "🔎 INVESTIGATE"
        css_class = "move-investigate"
    else:
        move_label = "👀 WATCH"
        css_class = "move-watch"

    st.markdown(
        f"""
        <div class="radar-card">
          <div class="{css_class}">{move_label}</div>
          <div class="radar-title">{topic['title']}</div>
          <div class="radar-meta">
            {item['label']} · {item['confidence']} confidence · Priority {item['priority']}
          </div>
          <b>Signals:</b>
          📰 {item['news_count']} news &nbsp;·&nbsp;
          ▶️ {item['youtube_count']} creators &nbsp;·&nbsp;
          🔎 {item['google_count']} search
          <br><br>
          <b>Why it's here:</b><br>
          {item['explanation']}
        </div>
        """,
        unsafe_allow_html=True,
    )

    links = source_links(topic)
    if links:
        with st.expander("View sources"):
            for source, title, url in links[:6]:
                st.markdown(f"**{source}** — [{title}]({url})")

st.title("🔥 Pop Culture Radar")
st.caption(
    "Entertainment news, creator activity and search signals — ranked into simple editorial decisions."
)

top_left, top_mid, top_right = st.columns(3)
top_left.metric("Mode", "Live radar")
top_mid.metric("Refresh", "15 min")
top_right.metric("Updated", datetime.now(timezone.utc).strftime("%H:%M UTC"))

if st.button("↻ Refresh radar", type="primary"):
    st.cache_data.clear()
    st.rerun()

try:
    with st.spinner("Scanning entertainment signals…"):
        opportunities, final_topics = run_radar()
except Exception as error:
    st.error("The radar could not refresh right now.")
    st.exception(error)
    st.stop()

cover = [x for x in opportunities if x["move"] == "COVER NOW"]
investigate = [x for x in opportunities if x["move"] == "INVESTIGATE"]
watch = [x for x in opportunities if x["move"] == "WATCH"]

st.markdown("---")
st.header("🚨 Cover now")
st.caption("Strongest independently confirmed opportunities.")
if not cover:
    st.info("Nothing has reached Cover Now status in this refresh.")
for item in cover:
    render_card(item)

st.markdown("---")
st.header("🔎 Investigate")
st.caption("Promising leads worth researching before committing.")
if not investigate:
    st.info("No Investigate leads in this refresh.")
for item in investigate:
    render_card(item)

st.markdown("---")
st.header("👀 Watch")
st.caption("Early signals waiting for more confirmation.")
if not watch:
    st.info("No Watch signals in this refresh.")
for item in watch:
    render_card(item)

st.markdown("---")
st.caption("Pop Culture Radar v1.3 · Refreshes automatically from the same radar engine you built.")
