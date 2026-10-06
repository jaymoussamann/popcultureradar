import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
import re
import html

# ============================================================
# POP CULTURE RADAR - VERSION 0.7
# News + Google Trends + YouTube + Source Diversity
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
print("🔥 POP CULTURE RADAR 0.7")
print("Topic Clustering + Independent Source Momentum")
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
# TOPIC CLUSTERING + SCORING
# ============================================================

# v0.6 groups near-duplicate headlines/videos into one subject before
# scoring. This prevents several videos from the same creator from
# appearing as separate "hot" topics and rewards independent sources.

ALL_ITEMS = all_news + google_trends + recent_youtube


def item_key(item):
    return (
        item.get("type", ""),
        item.get("source", ""),
        item.get("title", ""),
        item.get("link", "")
    )


def topic_similarity(title_a, title_b):
    """Return a 0..1 similarity score for two titles."""
    words_a = set(important_words(title_a))
    words_b = set(important_words(title_b))

    if not words_a or not words_b:
        return 0.0

    shared = words_a & words_b

    if not shared:
        return 0.0

    # Coverage is deliberately asymmetric-friendly: two titles can be
    # about the same subject even if one is much longer than the other.
    coverage = max(
        len(shared) / len(words_a),
        len(shared) / len(words_b)
    )

    union = words_a | words_b
    jaccard = len(shared) / len(union)

    distinctive_bonus = 0.0
    if any(len(word) >= 8 for word in shared):
        distinctive_bonus = 0.12

    return min(1.0, (coverage * 0.70) + (jaccard * 0.30) + distinctive_bonus)


def same_topic(title_a, title_b):
    words_a = set(important_words(title_a))
    words_b = set(important_words(title_b))
    shared = words_a & words_b

    if len(shared) >= 3:
        return True

    if len(shared) >= 2 and topic_similarity(title_a, title_b) >= 0.42:
        return True

    # One very distinctive shared name/term can join short titles,
    # but only when one title is itself short enough to be specific.
    if len(shared) == 1:
        word = next(iter(shared))
        # A distinctive shared subject can connect differently worded headlines.
        if len(word) >= 6 and min(len(words_a), len(words_b)) <= 6:
            return True

    return False


def cluster_items(items):
    clusters = []

    for item in items:
        best_cluster = None
        best_similarity = 0.0

        for cluster in clusters:
            # Compare with every member, not just the first headline.
            similarities = [
                topic_similarity(item["title"], member["title"])
                for member in cluster["items"]
            ]

            similarity = max(similarities) if similarities else 0.0

            if similarity > best_similarity and any(
                same_topic(item["title"], member["title"])
                for member in cluster["items"]
            ):
                best_similarity = similarity
                best_cluster = cluster

        if best_cluster is None:
            clusters.append({"items": [item]})
        else:
            # Avoid exact duplicate feed entries.
            existing = {item_key(member) for member in best_cluster["items"]}
            if item_key(item) not in existing:
                best_cluster["items"].append(item)

    return clusters


def representative_title(cluster):
    items = cluster["items"]

    # Prefer a news headline for readability, then Google, then YouTube.
    type_priority = {"news": 0, "google": 1, "youtube": 2}

    ranked = sorted(
        items,
        key=lambda item: (
            type_priority.get(item.get("type"), 9),
            -len(important_words(item.get("title", ""))),
            len(item.get("title", ""))
        )
    )

    return ranked[0]["title"] if ranked else "Untitled topic"


def score_cluster(cluster):
    items = cluster["items"]

    news = [item for item in items if item.get("type") == "news"]
    google = [item for item in items if item.get("type") == "google"]
    youtube = [item for item in items if item.get("type") == "youtube"]

    news_sources = {item["source"] for item in news}
    youtube_channels = {item["source"] for item in youtube}

    # Independent publishers matter more than repeated stories from one feed.
    news_score = min(len(news_sources) * 10, 40)

    # Google is a separate public-interest confirmation signal.
    google_score = min(len(google) * 20, 40)

    # One creator is one signal, regardless of how many videos they publish.
    # A single creator can surface an early lead, but cannot make a topic "hot"
    # by posting repeatedly.
    youtube_score = min(len(youtube_channels) * 12, 36)

    if youtube:
        freshest = max(youtube_recency_score(video) for video in youtube)
        youtube_score += min(freshest // 2, 10)

    youtube_score = min(youtube_score, 40)

    platforms = sum(bool(group) for group in (news, google, youtube))

    cross_platform_bonus = 0
    if platforms == 2:
        cross_platform_bonus = 18
    elif platforms == 3:
        cross_platform_bonus = 35

    # A topic discussed by several independent sources gets an extra lift.
    unique_sources = len(news_sources) + len(youtube_channels)
    if google:
        unique_sources += 1

    source_diversity_bonus = min(max(unique_sources - 1, 0) * 3, 15)

    # Repeated items from the same publisher/creator add no momentum.
    repetition_bonus = 0

    total_score = (
        news_score
        + google_score
        + youtube_score
        + cross_platform_bonus
        + source_diversity_bonus
        + repetition_bonus
    )

    return {
        "title": representative_title(cluster),
        "score": total_score,
        "news_score": news_score,
        "google_score": google_score,
        "youtube_score": youtube_score,
        "platforms": platforms,
        "unique_sources": unique_sources,
        "news": news,
        "google": google,
        "youtube": youtube,
        "items": items
    }


topic_clusters = cluster_items(ALL_ITEMS)

final_topics = [
    score_cluster(cluster)
    for cluster in topic_clusters
]

final_topics.sort(
    key=lambda topic: (
        topic["score"],
        topic["platforms"],
        topic["unique_sources"]
    ),
    reverse=True
)

# Keep the output focused.
final_topics = final_topics[:30]

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
            f"News ({len({item['source'] for item in topic['news']})} sources)"
        )

    if topic["google"]:
        signals.append(
            f"Google ({len(topic['google'])})"
        )

    if topic["youtube"]:
        signals.append(
            f"YouTube ({len({item['source'] for item in topic['youtube']})} creators)"
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
print("Clustered topics with the strongest independent signals")
print("=" * 72)

hot_topics = [
    topic
    for topic in final_topics
    if (
        topic["score"] >= 30
        and (
            topic["platforms"] >= 2
            or topic["unique_sources"] >= 2
        )
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
    if (
        topic["youtube"]
        and (
            len({item["source"] for item in topic["youtube"]}) >= 2
            or topic["platforms"] >= 2
        )
    )
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
        and topic["platforms"] == 1
        and len({item["source"] for item in topic["youtube"]}) == 1
    )
]

balanced_early_topics = []
early_creator_counts = Counter()

for topic in early_topics:
    creators = {item["source"] for item in topic["youtube"]}
    creator = next(iter(creators)) if len(creators) == 1 else None

    if creator and early_creator_counts[creator] >= 3:
        continue

    balanced_early_topics.append(topic)

    if creator:
        early_creator_counts[creator] += 1

    if len(balanced_early_topics) >= 10:
        break

for number, topic in enumerate(
    balanced_early_topics,
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
