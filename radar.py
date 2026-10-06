import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
import re
import html

# ============================================================
# POP CULTURE RADAR - VERSION 0.6
# News + Google Trends + YouTube + Topic Clustering
# ============================================================

NEWS_FEEDS = [
    ("Variety", "https://variety.com/feed/"),
    ("Deadline", "https://deadline.com/feed/"),
    ("Hollywood Reporter", "https://www.hollywoodreporter.com/feed/"),
    ("Rolling Stone", "https://www.rollingstone.com/tv-movies/feed/"),
]

GOOGLE_TRENDS_URL = "https://trends.google.com/trending/rss?geo=GB"

YOUTUBE_CHANNELS = [
    ("The Rest Is Entertainment", "@TheRestIsEntertainment"),
    ("Screen Rant", "@ScreenRant"),
    ("Dan Cashio Reacts", "@dancashioreacts"),
]

IGNORE_WORDS = {
    "the", "and", "for", "with", "that", "this", "from",
    "has", "have", "will", "about", "after", "into",
    "their", "they", "its", "are", "was", "who", "why",
    "how", "new", "says", "over", "more", "his", "her",
    "film", "movie", "movies", "show", "shows", "series",
    "season", "episode", "episodes", "star", "stars",
    "official", "trailer", "video", "reaction", "reacts",
    "watching", "first", "time", "latest", "explained",
    "best", "worst", "really", "your", "what", "when",
    "where", "which", "could", "would", "should", "being",
    "gets", "just", "than", "then", "them", "these",
    "those", "here", "there", "also", "very"
}


# ============================================================
# DOWNLOAD
# ============================================================

def download(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 Chrome/120 Safari/537.36"
            )
        }
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read()


# ============================================================
# NEWS
# ============================================================

def get_news_feed(source, url):
    try:
        root = ET.fromstring(download(url))
        stories = []

        for item in root.findall(".//item"):
            title = item.findtext("title")
            link = item.findtext("link")

            if title:
                stories.append({
                    "type": "news",
                    "source": source,
                    "title": html.unescape(title.strip()),
                    "link": link or ""
                })

        return stories

    except Exception as error:
        print(f"Could not read {source}: {error}")
        return []


# ============================================================
# GOOGLE TRENDS
# ============================================================

def get_google_trends():
    try:
