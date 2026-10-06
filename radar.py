import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
import re
import html

# ============================================================
# POP CULTURE RADAR - VERSION 0.5
# News + Google Trends + YouTube + Recency + Topic Signals
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
        root = ET.fromstring(download(GOOGLE_TRENDS_URL))
        trends = []

        for item in root.findall(".//item"):
            title = item.findtext("title")
            link = item.findtext("link")

            if title:
                trends.append({
                    "type": "google",
                    "source": "Google Trends UK",
                    "title": html.unescape(title.strip()),
                    "link": link or ""
                })

        return trends

    except Exception as error:
        print(f"Could not read Google Trends: {error}")
        return []


# ============================================================
# YOUTUBE
# ============================================================

def find_youtube_channel_id(handle):
    try:
        page = download(
            f"https://www.youtube.com/{handle}"
        ).decode("utf-8", errors="ignore")

        patterns = [
            r'"channelId":"(UC[a-zA-Z0-9_-]{20,})"',
            r'"externalId":"(UC[a-zA-Z0-9_-]{20,})"',
            r'channel_id=(UC[a-zA-Z0-9_-]{20,})'
        ]

        for pattern in patterns:
            match = re.search(pattern, page)

            if match:
                return match.group(1)

        return None

    except Exception as error:
        print(f"Could not resolve {handle}: {error}")
        return None


def get_youtube_feed(channel_name, handle):
    channel_id = find_youtube_channel_id(handle)

    if not channel_id:
        print(f"    Could not find channel ID for {handle}")
        return []

    feed_url = (
        "https://www.youtube.com/feeds/videos.xml"
        f"?channel_id={channel_id}"
    )

    try:
        root = ET.fromstring(download(feed_url))

        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "yt": "http://www.youtube.com/xml/schemas/2015"
        }

        videos = []

        for entry in root.findall("atom:entry", ns):

            title = entry.findtext(
                "atom:title",
                default="",
                namespaces=ns
            )

            video_id = entry.findtext(
                "yt:videoId",
                default="",
                namespaces=ns
            )

            published = entry.findtext(
                "atom:published",
                default="",
                namespaces=ns
            )

            if title:
                videos.append({
                    "type": "youtube",
                    "source": channel_name,
                    "title": html.unescape(title.strip()),
                    "link": (
                        f"https://www.youtube.com/watch?v={video_id}"
                        if video_id else ""
                    ),
                    "published": published
                })

        return videos

    except Exception as error:
        print(
            f"Could not read YouTube feed for "
            f"{channel_name}: {error}"
        )
        return []


# ============================================================
# TEXT / TOPIC MATCHING
# ============================================================

def important_words(text):
    words = re.findall(
        r"[A-Za-z0-9']+",
        text.lower()
    )

    return [
        word for word in words
        if (
            len(word) > 3
            and word not in IGNORE_WORDS
            and not word.isdigit()
        )
    ]


def match_strength(title_a, title_b):
    """
    Returns:
    0 = no useful match
    1 = possible match
    2 = strong match
    """

    words_a = set(important_words(title_a))
    words_b = set(important_words(title_b))

    shared = words_a.intersection(words_b)

    if len(shared) >= 2:
        return 2

    if len(shared) == 1:
        word = next(iter(shared))

        # A long distinctive word/name can still be useful.
        if len(word) >= 8:
            return 1

    return 0


# ============================================================
# RECENCY
# ============================================================

def youtube_age_days(video):
    published = video.get("published", "")

    if not published:
        return 999

    try:
        published_time = datetime.fromisoformat(
            published.replace("Z", "+00:00")
        )

        now = datetime.now(timezone.utc)

        difference = now - published_time

        return max(0, difference.total_seconds() / 86400)

    except Exception:
        return 999


def youtube_recency_score(video):
    age = youtube_age_days(video)

    if age <= 1:
        return 20

    if age <= 3:
        return 15

    if age <= 7:
        return 8

    return 0


def recency_label(video):
    age = youtube_age_days(video)

    if age <= 1:
        return "TODAY"

    if age <= 3:
        return "LAST 3 DAYS"

    if age <= 7:
        return "THIS WEEK"

    return "OLDER"


# ============================================================
# START RADAR
# ============================================================

print()
print("=" * 72)
print("🔥 POP CULTURE RADAR 0.5")
print("Topic + Momentum Engine")
print("=" * 72)
print()


# ============================================================
# COLLECT NEWS
# ============================================================

all_news = []

for source, url in NEWS_FEEDS:
    print(f"Scanning {source}...")

    stories = get_news_feed(source, url)

    print(f"  Found {len(stories)} stories")

    all_news.extend(stories)


# ============================================================
# COLLECT GOOGLE
# ============================================================

print()
print("Scanning Google Trends UK...")

google_trends = get_google_trends()

print(f"  Found {len(google_trends)} trends")


# ============================================================
# COLLECT YOUTUBE
# ============================================================

print()
print("Scanning YouTube creator watchlist...")

all_youtube = []

for channel_name, handle in YOUTUBE_CHANNELS:

    print(f"  Scanning {channel_name}...")

    videos = get_youtube_feed(
        channel_name,
        handle
    )

    print(f"    Found {len(videos)} videos")

    all_youtube.extend(videos)


recent_youtube = [
    video
    for video in all_youtube
    if youtube_age_days(video) <= 7
]


print()
print("-" * 72)
print(f"News stories: {len(all_news)}")
print(f"Google trends: {len(google_trends)}")
print(f"YouTube videos collected: {len(all_youtube)}")
print(f"YouTube videos from last 7 days: {len(recent_youtube)}")
print("-" * 72)


# ============================================================
# NEWS WORD FREQUENCY
# ============================================================

news_word_counts = Counter()

for story in all_news:
    news_word_counts.update(
        set(important_words(story["title"]))
    )


# ============================================================
# BUILD CANDIDATES
#
# IMPORTANT:
# Candidates can now originate from NEWS, GOOGLE OR YOUTUBE.
# ============================================================

candidates = []

for story in all_news:
    candidates.append({
        "title": story["title"],
        "origin": "news",
        "origin_item": story
    })

for trend in google_trends:
    candidates.append({
        "title": trend["title"],
        "origin": "google",
        "origin_item": trend
    })

for video in recent_youtube:
    candidates.append({
        "title": video["title"],
        "origin": "youtube",
        "origin_item": video
    })


# ============================================================
# SCORE CANDIDATES
# ============================================================

scored_candidates = []

for candidate in candidates:

    title = candidate["title"]
    words = set(important_words(title))

    matching_news = []
    matching_google = []
    matching_youtube = []

    # NEWS MATCHES

    for story in all_news:
        strength = match_strength(
            title,
            story["title"]
        )

        if strength > 0:
            matching_news.append(story)

    # GOOGLE MATCHES

    for trend in google_trends:
        strength = match_strength(
            title,
            trend["title"]
        )

        if strength > 0:
            matching_google.append(trend)

    # YOUTUBE MATCHES - RECENT ONLY

    for video in recent_youtube:
        strength = match_strength(
            title,
            video["title"]
        )

        if strength > 0:
            matching_youtube.append(video)

    # --------------------------------------------
    # NEWS SCORE
    # --------------------------------------------

    news_sources = {
        item["source"]
        for item in matching_news
    }

    news_score = min(
        len(news_sources) * 8,
        32
    )

    # Also reward repeated meaningful terms
    frequency_bonus = min(
        sum(
            news_word_counts[word]
            for word in words
        ),
        15
    )

    # --------------------------------------------
    # GOOGLE SCORE
    # --------------------------------------------

    google_score = min(
        len(matching_google) * 20,
        40
    )

    # --------------------------------------------
    # YOUTUBE SCORE
    # --------------------------------------------

    youtube_score = 0

    youtube_channels = set()

    for video in matching_youtube:

        youtube_channels.add(
            video["source"]
        )

        youtube_score += youtube_recency_score(
            video
        )

    # Extra reward when separate creators
    # discuss the same subject.
    if len(youtube_channels) >= 2:
        youtube_score += 15

    if len(youtube_channels) >= 3:
        youtube_score += 10

    youtube_score = min(
        youtube_score,
        60
    )

    # --------------------------------------------
    # CROSS-PLATFORM BONUS
    # --------------------------------------------

    platforms = 0

    if matching_news:
        platforms += 1

    if matching_google:
        platforms += 1

    if matching_youtube:
        platforms += 1

    cross_platform_bonus = 0

    if platforms == 2:
        cross_platform_bonus = 15

    elif platforms == 3:
        cross_platform_bonus = 30

    total_score = (
        news_score
        + frequency_bonus
        + google_score
        + youtube_score
        + cross_platform_bonus
    )

    scored_candidates.append({
        "title": title,
        "origin": candidate["origin"],
        "origin_item": candidate["origin_item"],
        "score": total_score,
        "news_score": news_score,
        "frequency_bonus": frequency_bonus,
        "google_score": google_score,
        "youtube_score": youtube_score,
        "platforms": platforms,
        "news": matching_news,
        "google": matching_google,
        "youtube": matching_youtube
    })


scored_candidates.sort(
    key=lambda item: item["score"],
    reverse=True
)


# ============================================================
# REMOVE NEAR-DUPLICATE TOPICS
# ============================================================

final_topics = []

for candidate in scored_candidates:

    duplicate = False

    for existing in final_topics:

        if match_strength(
            candidate["title"],
            existing["title"]
        ) >= 2:
            duplicate = True
            break

    if not duplicate:
        final_topics.append(candidate)

    if len(final_topics) >= 20:
        break


# ============================================================
# DISPLAY HELPERS
# ============================================================

def heat(score):

    if score >= 80:
        return "🔥🔥🔥🔥🔥"

    if score >= 60:
        return "🔥🔥🔥🔥"

    if score >= 40:
        return "🔥🔥🔥"

    if score >= 25:
        return "🔥🔥"

    return "🔥"


def print_topic(number, topic):

    print()
    print(
        f"{number}. {topic['title']}"
    )

    print(
        f"   MOMENTUM: {heat(topic['score'])} "
        f"({topic['score']})"
    )

    signals = []

    if topic["news"]:
        signals.append(
            f"News ({len(topic['news'])})"
        )

    if topic["google"]:
        signals.append(
            f"Google ({len(topic['google'])})"
        )

    if topic["youtube"]:
        signals.append(
            f"YouTube ({len(topic['youtube'])})"
        )

    print(
        "   Signals: "
        + (
            " + ".join(signals)
            if signals
            else "single-source"
        )
    )

    # Show useful YouTube evidence

    shown_videos = set()

    for video in topic["youtube"]:

        identifier = (
            video["source"],
            video["title"]
        )

        if identifier in shown_videos:
            continue

        shown_videos.add(identifier)

        print(
            f"   ▶️ {video['source']}: "
            f"{video['title']} "
            f"[{recency_label(video)}]"
        )

        if len(shown_videos) >= 3:
            break

    # Show useful news evidence

    shown_news = set()

    for story in topic["news"]:

        identifier = (
            story["source"],
            story["title"]
        )

        if identifier in shown_news:
            continue

        shown_news.add(identifier)

        print(
            f"   📰 {story['source']}: "
            f"{story['title']}"
        )

        if len(shown_news) >= 2:
            break

    # Google evidence

    shown_google = set()

    for trend in topic["google"]:

        if trend["title"] in shown_google:
            continue

        shown_google.add(
            trend["title"]
        )

        print(
            f"   🔎 Google: "
            f"{trend['title']}"
        )

        if len(shown_google) >= 2:
            break


# ============================================================
# HOT RIGHT NOW
# ============================================================

print()
print()
print("=" * 72)
print("🔥 HOT RIGHT NOW")
print("Topics with the strongest current signals")
print("=" * 72)

hot_topics = [
    topic
    for topic in final_topics
    if (
        topic["score"] >= 25
        and topic["platforms"] >= 1
    )
]

for number, topic in enumerate(
    hot_topics[:10],
    start=1
):
    print_topic(number, topic)


# ============================================================
# CREATOR SIGNALS
# ============================================================

print()
print()
print("=" * 72)
print("⚡ CREATOR SIGNALS")
print("Fresh subjects appearing on your YouTube watchlist")
print("=" * 72)

creator_topics = [
    topic
    for topic in final_topics
    if topic["youtube"]
]

for number, topic in enumerate(
    creator_topics[:10],
    start=1
):
    print_topic(number, topic)


# ============================================================
# EARLY SIGNALS
#
# YouTube activity without strong news coverage can be
# particularly interesting for spotting subjects early.
# ============================================================

print()
print()
print("=" * 72)
print("👀 EARLY SIGNALS")
print("Creator activity that may not yet have broad news coverage")
print("=" * 72)

early_topics = [
    topic
    for topic in final_topics
    if (
        topic["youtube"]
        and len(topic["news"]) <= 1
    )
]

for number, topic in enumerate(
    early_topics[:10],
    start=1
):
    print_topic(number, topic)


# ============================================================
# RECENT CREATOR ACTIVITY
# ============================================================

print()
print()
print("=" * 72)
print("▶️ RECENT CREATOR ACTIVITY — LAST 7 DAYS")
print("=" * 72)

recent_youtube.sort(
    key=lambda video: video.get(
        "published",
        ""
    ),
    reverse=True
)

for video in recent_youtube:

    print()
    print(
        f"{recency_label(video)} | "
        f"{video['source']}"
    )

    print(
        f"   {video['title']}"
    )

    print(
        f"   {video['link']}"
    )


print()
print("=" * 72)
print("Radar complete.")
print("=" * 72)
