# URL http://localhost:8501/#news-dashboard

"""Streamlit dashboard for browsing and triaging ingested news articles."""

import html
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from db import get_articles, init_db, update_article_status

STATUS_OPTIONS = ["new", "watching", "story lead"]
DEFAULT_LOOKBACK_DAYS = 60
STATUS_COLORS = {
    "new": "#3B82F6",
    "watching": "#F59E0B",
    "story lead": "#10B981",
}

st.set_page_config(page_title="News Dashboard", page_icon="📰", layout="wide")
init_db()

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

.block-container {
    padding-top: 2.5rem;
    padding-bottom: 3rem;
    max-width: 1200px;
}

h1 {
    font-weight: 700;
    letter-spacing: -0.02em;
    margin-bottom: 0.1rem;
}

.article-count {
    display: inline-block;
    background: #EEF2FF;
    color: #4F46E5;
    font-size: 0.85rem;
    font-weight: 600;
    padding: 0.25rem 0.75rem;
    border-radius: 999px;
    margin-bottom: 1.5rem;
}

section[data-testid="stSidebar"] {
    border-right: 1px solid #ECECF1;
}
section[data-testid="stSidebar"] h2 {
    font-size: 0.95rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #6B7280;
    font-weight: 700;
}

.table-header {
    text-transform: uppercase;
    font-size: 0.72rem;
    letter-spacing: 0.06em;
    color: #8A8F98;
    font-weight: 700;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid #ECECF1;
    margin-bottom: 0.5rem;
}

.tag-pill {
    display: inline-block;
    background: #F1F5F9;
    color: #475569;
    font-size: 0.75rem;
    font-weight: 500;
    padding: 0.15rem 0.6rem;
    border-radius: 999px;
    margin: 0 0.25rem 0.25rem 0;
}

.article-title a {
    color: #1F2430;
    font-weight: 600;
    text-decoration: none;
}
.article-title a:hover {
    color: #4F46E5;
    text-decoration: underline;
}
.article-meta {
    color: #9AA0AC;
    font-size: 0.85rem;
}

.tagline {
    color: #6B7280;
    font-size: 0.9rem;
    margin-bottom: 1.25rem;
}

div[data-baseweb="select"] > div, .stTextInput input {
    border-radius: 8px !important;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def load_articles():
    """Load all articles from the DB into a DataFrame, with a few columns normalized."""
    articles = get_articles({})
    df = pd.DataFrame(articles)
    if df.empty:
        return df
    df["tags"] = df["tags"].fillna("")
    df["notes"] = df["notes"].fillna("")
    df["published_date"] = df["published_date"].fillna("")
    df["published_dt"] = pd.to_datetime(df["published_date"], errors="coerce", utc=True)
    df["fetched_dt"] = pd.to_datetime(df["fetched_date"], errors="coerce", utc=True)
    return df


def humanize_delta(dt):
    """Return a short relative-time string like '3 hours ago' for a UTC timestamp."""
    seconds = int((datetime.now(timezone.utc) - dt).total_seconds())
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = hours // 24
    return f"{days} day{'s' if days != 1 else ''} ago"


def save_article(article_id, status_key, notes_key):
    """on_change callback: persist the current status + notes widget values for a row.

    The keys can be briefly missing if the app redeployed (wiping session_state)
    while a stale browser tab still had the old widgets queued up — skip rather
    than crash the page in that case; the user just needs to refresh and retry.
    """
    if status_key not in st.session_state or notes_key not in st.session_state:
        st.warning("Session expired — please refresh the page and try again.")
        return

    status = st.session_state[status_key]
    notes = st.session_state[notes_key]
    update_article_status(article_id, status, notes)


def check_password():
    """Gate the app behind a password from st.secrets, remembered for the rest of the session."""
    if st.session_state.get("password_correct"):
        return

    st.title("📰 News Dashboard")
    entered = st.text_input("Password", type="password", key="password_input")
    if entered:
        if entered == st.secrets.get("password"):
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("Incorrect password")
    st.stop()


check_password()

st.title("📰 News Dashboard")

df = load_articles()

if df.empty:
    st.info("No articles in the database yet. Run ingest.py to pull some in.")
    st.stop()

last_fetched = df["fetched_dt"].dropna().max()
if pd.notna(last_fetched):
    st.markdown(
        f'<div class="tagline">🕐 Last updated {humanize_delta(last_fetched)}</div>',
        unsafe_allow_html=True,
    )

# --- Filters ---
st.sidebar.header("Filters")

sources = sorted(df["source"].dropna().unique())
selected_sources = st.sidebar.multiselect("Source", sources)

all_tags = sorted(
    {tag.strip() for tags in df["tags"] if tags for tag in tags.split(",") if tag.strip()}
)
selected_tags = st.sidebar.multiselect("Tag", all_tags)

today = date.today()
valid_dates = df["published_dt"].dropna()
if not valid_dates.empty:
    min_date = valid_dates.min().date()
    max_date = max(valid_dates.max().date(), today)
else:
    min_date = max_date = today

default_start = max(min_date, today - timedelta(days=DEFAULT_LOOKBACK_DAYS))

# date_input keeps whatever the user last picked across reruns, so if new
# articles get ingested (pushing max_date forward) we have to explicitly
# nudge the stored selection forward too, rather than relying on `value=`.
# min_value stays the true data min so the picker can still be widened by hand.
if "date_range_max_seen" not in st.session_state:
    st.session_state["date_range_max_seen"] = max_date
    st.session_state["date_range_filter"] = (default_start, max_date)
elif max_date > st.session_state["date_range_max_seen"]:
    prev_start, prev_end = st.session_state["date_range_filter"]
    if prev_end == st.session_state["date_range_max_seen"]:
        prev_end = max_date
    st.session_state["date_range_filter"] = (prev_start, prev_end)
    st.session_state["date_range_max_seen"] = max_date

date_range = st.sidebar.date_input(
    "Published date range",
    min_value=min_date,
    max_value=max_date,
    key="date_range_filter",
)

# --- Apply filters ---
filtered = df.copy()

if selected_sources:
    filtered = filtered[filtered["source"].isin(selected_sources)]

if selected_tags:
    def has_selected_tag(tags_str):
        row_tags = {t.strip() for t in tags_str.split(",") if t.strip()}
        return bool(row_tags & set(selected_tags))

    filtered = filtered[filtered["tags"].apply(has_selected_tag)]

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
    start_ts = pd.Timestamp(start_date, tz="UTC")
    end_ts = pd.Timestamp(end_date, tz="UTC") + pd.Timedelta(days=1)
    filtered = filtered[
        filtered["published_dt"].isna()
        | ((filtered["published_dt"] >= start_ts) & (filtered["published_dt"] < end_ts))
    ]

filtered = filtered.sort_values("published_dt", ascending=False, na_position="last")

st.markdown(
    f'<span class="article-count">Showing {len(filtered)} of {len(df)} articles</span>',
    unsafe_allow_html=True,
)

# --- Table ---
COLUMN_WIDTHS = [3, 1.3, 1.3, 1.6, 1.3, 2.2]

header_cols = st.columns(COLUMN_WIDTHS)
for col, label in zip(header_cols, ["Title", "Source", "Published", "Tags", "Status", "Notes"]):
    col.markdown(f'<div class="table-header">{label}</div>', unsafe_allow_html=True)

for row in filtered.itertuples():
    status_key = f"status_{row.id}"
    notes_key = f"notes_{row.id}"
    current_status = row.status if row.status in STATUS_OPTIONS else STATUS_OPTIONS[0]
    row_key = f"row_{row.id}"

    st.markdown(
        f"<style>.st-key-{row_key} {{ border-left: 3px solid {STATUS_COLORS[current_status]}; "
        f"padding: 0.6rem 0 0.6rem 0.9rem; margin-bottom: 0.3rem; }}</style>",
        unsafe_allow_html=True,
    )

    with st.container(key=row_key):
        cols = st.columns(COLUMN_WIDTHS)

        title = html.escape(row.title)
        url = html.escape(row.url, quote=True)
        cols[0].markdown(
            f'<div class="article-title"><a href="{url}" target="_blank" '
            f'rel="noopener noreferrer">{title}</a></div>',
            unsafe_allow_html=True,
        )
        cols[1].markdown(f'<span class="article-meta">{html.escape(row.source)}</span>', unsafe_allow_html=True)
        published = html.escape(row.published_date.split("T")[0]) if row.published_date else "—"
        cols[2].markdown(f'<span class="article-meta">{published}</span>', unsafe_allow_html=True)

        tag_list = [t.strip() for t in row.tags.split(",") if t.strip()]
        if tag_list:
            tags_html = "".join(f'<span class="tag-pill">{html.escape(t)}</span>' for t in tag_list)
        else:
            tags_html = '<span class="article-meta">—</span>'
        cols[3].markdown(tags_html, unsafe_allow_html=True)

        cols[4].selectbox(
            "Status",
            STATUS_OPTIONS,
            index=STATUS_OPTIONS.index(current_status),
            key=status_key,
            label_visibility="collapsed",
            on_change=save_article,
            args=(row.id, status_key, notes_key),
        )

        cols[5].text_input(
            "Notes",
            value=row.notes,
            key=notes_key,
            label_visibility="collapsed",
            on_change=save_article,
            args=(row.id, status_key, notes_key),
        )
