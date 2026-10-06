import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
import re
import html

# ============================================================
# POP CULTURE RADAR - VERSION 1.0
# News + Google Trends + YouTube + Ranked Editorial Opportunities
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
print("🔥 POP CULTURE RADAR 1.0")
print("Ranked Editorial Opportunities + Independent Source Momentum")
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


# Words that are common in entertainment headlines but are too broad to
# prove that two stories concern the same subject.
GENERIC_TOPIC_WORDS = {
    "office", "hollywood", "actor", "actress", "director", "producer",
    "studio", "studios", "television", "streaming", "netflix", "amazon",
    "apple", "disney", "paramount", "warner", "bros", "universal",
    "review", "reviews", "interview", "exclusive", "report", "reports",
    "box", "office", "cast", "casting", "role", "roles", "award", "awards",
    "trailer", "teaser", "clip", "clips", "watch", "reaction", "reactions",
    "ending", "scene", "scenes", "story", "stories", "news", "update",
    "updates", "reveals", "revealed", "explains", "talks", "working",
    "worked", "work", "biggest", "ever"
}


def normalized_topic_words(text):
    """Important words with broad entertainment vocabulary removed."""
    return {
        word
        for word in important_words(text)
        if word not in GENERIC_TOPIC_WORDS
    }


def entity_tokens(text):
    """
    Pull out likely names/titles from headline casing and quoted phrases.

    This is intentionally lightweight: it gives us entity awareness without
    needing an API, model, or third-party NLP package.
    """
    entities = set()

    # Anything inside straight or curly quotation marks is often a title.
    quoted_chunks = re.findall(
        r"[\"'‘’“”]([^\"'‘’“”]{2,80})[\"'‘’“”]",
        text
    )

    for chunk in quoted_chunks:
        words = normalized_topic_words(chunk)
        entities.update(words)

    # Capitalised words are often people, programmes, films, franchises, etc.
    capitalized = re.findall(r"\b[A-Z][A-Za-z0-9'-]{3,}\b", text)

    for word in capitalized:
        normalized = word.lower().strip("'")
        if (
            normalized not in IGNORE_WORDS
            and normalized not in GENERIC_TOPIC_WORDS
            and not normalized.isdigit()
        ):
            entities.add(normalized)

    return entities


def topic_similarity(title_a, title_b):
    """Return a conservative 0..1 similarity score for two titles."""
    words_a = normalized_topic_words(title_a)
    words_b = normalized_topic_words(title_b)

    if not words_a or not words_b:
        return 0.0

    shared = words_a & words_b

    if not shared:
        return 0.0

    coverage = max(
        len(shared) / len(words_a),
        len(shared) / len(words_b)
    )

    union = words_a | words_b
    jaccard = len(shared) / len(union)

    entities_a = entity_tokens(title_a)
    entities_b = entity_tokens(title_b)
    shared_entities = entities_a & entities_b

    entity_bonus = min(len(shared_entities) * 0.18, 0.36)

    return min(
        1.0,
        (coverage * 0.62)
        + (jaccard * 0.28)
        + entity_bonus
    )


def same_topic(title_a, title_b):
    """
    Decide whether two headlines are genuinely about the same subject.

    v0.8 deliberately removes the old rule that allowed one long shared word
    to merge two topics. That rule caused false matches such as:
      Digger / Tom Cruise  <->  Creed Bratton / The Office / Primetime
    simply because both headlines contained 'office'.

    A match now needs either:
      * multiple meaningful shared words, or
      * a likely shared named entity plus supporting overlap.
    """
    words_a = normalized_topic_words(title_a)
    words_b = normalized_topic_words(title_b)
    shared = words_a & words_b

    entities_a = entity_tokens(title_a)
    entities_b = entity_tokens(title_b)
    shared_entities = entities_a & entities_b

    # Three meaningful words is strong evidence even when phrasing differs.
    if len(shared) >= 3:
        return True

    # Two meaningful words can match when they cover a useful part of a title.
    if len(shared) >= 2 and topic_similarity(title_a, title_b) >= 0.34:
        return True

    # One shared named entity alone is not enough. Require one additional
    # meaningful shared term so generic or ambiguous names cannot bridge topics.
    if shared_entities and len(shared) >= 2:
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

# ============================================================
# CONTENT OPPORTUNITY ENGINE
# ============================================================

COMMERCE_WORDS = {
    "deal", "deals", "discount", "discounts", "sale", "sales",
    "prime", "shopping", "shop", "buy", "price", "prices",
    "cheap", "cheapest", "save", "saving", "savings",
    "percent", "off", "coupon", "coupons", "bargain",
    "beauty", "balm", "cleanser", "serum", "skincare"
}


def is_commerce_topic(topic):
    words = set(important_words(topic["title"]))
    return bool(words & COMMERCE_WORDS)


def opportunity_details(topic):
    news_count = len({item["source"] for item in topic["news"]})
    youtube_count = len({item["source"] for item in topic["youtube"]})
    google_count = len(topic["google"])

    # Strongest cross-platform signal.
    if news_count >= 1 and youtube_count >= 1 and google_count >= 1:
        return (
            "🔥 CROSS-PLATFORM SURGE",
            "HIGH",
            45,
            "News, creator activity and Google search interest are all "
            "pointing at the same subject."
        )

    if news_count >= 1 and youtube_count >= 1:
        return (
            "🔥 CROSSOVER",
            "HIGH",
            38,
            "The subject is appearing across both entertainment news "
            "and watched creators."
        )

    if google_count >= 1 and news_count >= 1:
        return (
            "🔎 SEARCH SURGE",
            "HIGH" if news_count >= 2 else "MEDIUM",
            34,
            "Entertainment-news coverage is being reinforced by "
            "Google search interest."
        )

    if news_count >= 2 and youtube_count == 0:
        confidence = "HIGH" if news_count >= 3 else "MEDIUM"
        return (
            "🔴 NEWS GAP",
            confidence,
            30,
            "Multiple independent entertainment-news sources are covering "
            "this, but none of the watched creators have covered it yet."
        )

    if youtube_count >= 2 and news_count == 0:
        return (
            "⚡ CREATOR-LED",
            "MEDIUM",
            27,
            "Multiple watched creators are discussing this before broad "
            "entertainment-news coverage."
        )

    if youtube_count == 1 and news_count == 0:
        return (
            "🟡 EARLY CREATOR SIGNAL",
            "LOW",
            16,
            "A watched creator is discussing this before broad news "
            "confirmation. Treat it as a lead to watch."
        )

    if google_count >= 1:
        return (
            "🔎 SEARCH-LED",
            "LOW",
            14,
            "Google search interest is visible before strong news or "
            "creator confirmation."
        )

    return (
        "👀 WATCH",
        "LOW",
        0,
        "There is activity around the subject, but not enough independent "
        "confirmation to make it a priority."
    )


def opportunity_score(topic):
    label, confidence, bonus, explanation = opportunity_details(topic)

    score = topic["score"] + bonus

    # Reward independent confirmation.
    news_count = len({item["source"] for item in topic["news"]})
    youtube_count = len({item["source"] for item in topic["youtube"]})

    score += min(news_count, 4) * 3
    score += min(youtube_count, 3) * 3

    # Commerce/deal headlines can dominate entertainment feeds during
    # shopping events. Keep them visible only when other signals make
    # them genuinely noteworthy.
    if is_commerce_topic(topic):
        score -= 45

    return score


def editorial_angle(topic):
    title = topic["title"]
    news_count = len({item["source"] for item in topic["news"]})
    youtube_count = len({item["source"] for item in topic["youtube"]})
    google_count = len(topic["google"])

    if news_count >= 2 and youtube_count == 0:
        return (
            "Explain why this story matters, add context, or find the "
            "angle creators have not covered yet."
        )

    if youtube_count >= 1 and news_count == 0:
        return (
            "Investigate the creator conversation and look for independent "
            "confirmation before committing to coverage."
        )

    if news_count >= 1 and youtube_count >= 1:
        return (
            "Use the news development as the hook and the creator reaction "
            "as evidence of wider audience interest."
        )

    if google_count >= 1:
        return (
            "Find out what people are suddenly searching for and answer "
            "the obvious audience question quickly."
        )

    return "Monitor for a second independent signal before prioritising it."


# Build a ranked shortlist instead of labelling every feed item an opportunity.
ranked_opportunities = []

for topic in final_topics:
    label, confidence, bonus, explanation = opportunity_details(topic)

    news_count = len({item["source"] for item in topic["news"]})
    youtube_count = len({item["source"] for item in topic["youtube"]})
    google_count = len(topic["google"])

    # Require at least one meaningful reason to surface the topic.
    meaningful = (
        news_count >= 2
        or youtube_count >= 1
        or google_count >= 1
    )

    if not meaningful:
        continue

    # Do not promote commerce stories unless they have a non-news signal.
    if is_commerce_topic(topic) and youtube_count == 0 and google_count == 0:
        continue

    ranked_opportunities.append({
        "topic": topic,
        "label": label,
        "confidence": confidence,
        "explanation": explanation,
        "priority": opportunity_score(topic),
        "news_count": news_count,
        "youtube_count": youtube_count,
        "google_count": google_count
    })


ranked_opportunities.sort(
    key=lambda item: (
        item["priority"],
        item["topic"]["score"],
        item["topic"]["unique_sources"]
    ),
    reverse=True
)


print()
print()
print("=" * 72)
print("💡 BEST CONTENT OPPORTUNITIES")
print("Ranked leads worth investigating, not just everything in the feeds")
print("=" * 72)

if not ranked_opportunities:
    print()
    print("No strong content opportunities detected in this run.")

for number, item in enumerate(ranked_opportunities[:7], start=1):
    topic = item["topic"]

    print()
    print(f"{number}. {topic['title']}")
    print(f"   TYPE: {item['label']}")
    print(f"   CONFIDENCE: {item['confidence']}")
    print(f"   PRIORITY SCORE: {item['priority']}")
    print(f"   WHY NOW: {item['explanation']}")
    print(f"   POSSIBLE ANGLE: {editorial_angle(topic)}")
    print(
        f"   SIGNAL MIX: News {item['news_count']} | "
        f"YouTube {item['youtube_count']} | "
        f"Google {item['google_count']}"
    )


print()
print("=" * 72)
print("Radar complete.")
print("=" * 72)
