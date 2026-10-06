import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
import re
import html

# ------------------------------------------------
# POP CULTURE RADAR - VERSION 0.4
# News + Google Trends + YouTube Creator Watchlist
# ------------------------------------------------

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
    "season", "episode", "star", "stars", "official",
    "trailer", "video", "reaction", "reacts"
}


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


def get_news_feed(source, url):
    try:
        root = ET.fromstring(download(url))

        stories = []

        for item in root.findall(".//item"):
            title = item.findtext("title")
            link = item.findtext("link")

            if title:
                stories.append({
                    "source": source,
                    "title": html.unescape(title.strip()),
                    "link": link or ""
                })

        return stories

    except Exception as error:
        print(f"Could not read {source}: {error}")
        return []


def get_google_trends():
    try:
        root = ET.fromstring(download(GOOGLE_TRENDS_URL))

        trends = []

        for item in root.findall(".//item"):
            title = item.findtext("title")
            link = item.findtext("link")

            if title:
                trends.append({
                    "title": html.unescape(title.strip()),
                    "link": link or ""
                })

        return trends

    except Exception as error:
        print(f"Could not read Google Trends: {error}")
        return []


def find_youtube_channel_id(handle):
    """
    Visit a YouTube @handle page and discover
    the underlying UC... channel ID.
    """

    try:
        url = f"https://www.youtube.com/{handle}"

        page = download(url).decode(
            "utf-8",
            errors="ignore"
        )

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
        print(
            f"Could not resolve YouTube handle "
            f"{handle}: {error}"
        )
        return None


def get_youtube_feed(channel_name, handle):
    """
    Resolve a YouTube handle and collect the
    channel's latest uploads from its Atom feed.
    """

    channel_id = find_youtube_channel_id(handle)

    if not channel_id:
        print(f"  Could not find channel ID for {handle}")
        return []

    feed_url = (
        "https://www.youtube.com/feeds/videos.xml"
        f"?channel_id={channel_id}"
    )

    try:
        root = ET.fromstring(download(feed_url))

        namespace = {
            "atom": "http://www.w3.org/2005/Atom",
            "yt": "http://www.youtube.com/xml/schemas/2015"
        }

        videos = []

        for entry in root.findall("atom:entry", namespace):

            title = entry.findtext(
                "atom:title",
                default="",
                namespaces=namespace
            )

            video_id = entry.findtext(
                "yt:videoId",
                default="",
                namespaces=namespace
            )

            published = entry.findtext(
                "atom:published",
                default="",
                namespaces=namespace
            )

            if title:
                videos.append({
                    "channel": channel_name,
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


def strict_match(title_a, title_b):
    """
    Conservative topic matching.

    Two or more meaningful shared words are
    normally required.

    A single distinctive long word can match,
    which helps with titles such as Superman,
    Bridgerton or Oppenheimer.
    """

    words_a = set(important_words(title_a))
    words_b = set(important_words(title_b))

    if not words_a or not words_b:
        return False

    shared = words_a.intersection(words_b)

    if len(shared) >= 2:
        return True

    if len(shared) == 1:
        word = next(iter(shared))

        if len(word) >= 8:
            return True

    return False


print()
print("=" * 70)
print("🔥 POP CULTURE RADAR 0.4")
print("News + Google Trends + YouTube Creator Signals")
print("=" * 70)
print()


# ------------------------------------------------
# NEWS
# ------------------------------------------------

all_stories = []

for source, url in NEWS_FEEDS:

    print(f"Scanning {source}...")

    stories = get_news_feed(source, url)

    print(f"  Found {len(stories)} stories")

    all_stories.extend(stories)


# ------------------------------------------------
# GOOGLE
# ------------------------------------------------

print()
print("Scanning Google Trends UK...")

google_trends = get_google_trends()

print(
    f"  Found {len(google_trends)} "
    f"trending searches"
)


# ------------------------------------------------
# YOUTUBE
# ------------------------------------------------

print()
print("Scanning YouTube creator watchlist...")

youtube_videos = []

for channel_name, handle in YOUTUBE_CHANNELS:

    print(f"  Scanning {channel_name}...")

    videos = get_youtube_feed(
        channel_name,
        handle
    )

    print(f"    Found {len(videos)} recent videos")

    youtube_videos.extend(videos)


print()
print("-" * 70)
print(f"Entertainment stories: {len(all_stories)}")
print(f"Google trends: {len(google_trends)}")
print(f"YouTube videos: {len(youtube_videos)}")
print("-" * 70)
print()


# ------------------------------------------------
# NEWS SIGNAL
# ------------------------------------------------

word_counts = Counter()

for story in all_stories:
    word_counts.update(
        set(important_words(story["title"]))
    )


# ------------------------------------------------
# SCORE EACH STORY
# ------------------------------------------------

ranked_stories = []

for story in all_stories:

    story_words = set(
        important_words(story["title"])
    )

    news_score = sum(
        word_counts[word]
        for word in story_words
    )

    matching_google = []

    for trend in google_trends:

        if strict_match(
            story["title"],
            trend["title"]
        ):
            matching_google.append(
                trend["title"]
            )

    matching_youtube = []

    for video in youtube_videos:

        if strict_match(
            story["title"],
            video["title"]
        ):
            matching_youtube.append(video)

    # Cross-platform confirmation is valuable.
    google_boost = min(
        len(matching_google) * 20,
        40
    )

    youtube_channels = {
        video["channel"]
        for video in matching_youtube
    }

    # Reward multiple independent creators.
    youtube_boost = min(
        len(youtube_channels) * 15,
        45
    )

    total_score = (
        news_score
        + google_boost
        + youtube_boost
    )

    ranked_stories.append({
        **story,
        "news_score": news_score,
        "google_matches": matching_google,
        "google_boost": google_boost,
        "youtube_matches": matching_youtube,
        "youtube_boost": youtube_boost,
        "score": total_score
    })


ranked_stories.sort(
    key=lambda story: story["score"],
    reverse=True
)


# ------------------------------------------------
# RESULTS
# ------------------------------------------------

print("=" * 70)
print("📈 TODAY'S POP CULTURE RADAR")
print("=" * 70)

seen_titles = set()
position = 1

for story in ranked_stories:

    key = story["title"].lower()

    if key in seen_titles:
        continue

    seen_titles.add(key)

    print()
    print(f"{position}. {story['title']}")
    print(f"   RADAR SCORE: {story['score']}")
    print(
        f"   📰 News signal: "
        f"{story['news_score']}"
    )

    if story["google_matches"]:

        print(
            f"   🔎 Google confirmation: "
            f"+{story['google_boost']}"
        )

        for trend in story["google_matches"][:3]:
            print(f"      ↳ {trend}")

    else:
        print("   🔎 Google confirmation: none")

    if story["youtube_matches"]:

        print(
            f"   ▶️ YouTube confirmation: "
            f"+{story['youtube_boost']}"
        )

        shown = set()

        for video in story["youtube_matches"]:

            identifier = (
                video["channel"],
                video["title"]
            )

            if identifier in shown:
                continue

            shown.add(identifier)

            print(
                f"      ↳ {video['channel']}: "
                f"{video['title']}"
            )

            if len(shown) >= 3:
                break

    else:
        print("   ▶️ YouTube confirmation: none")

    print(f"   Source: {story['source']}")
    print(f"   {story['link']}")

    position += 1

    if position > 20:
        break


# ------------------------------------------------
# YOUTUBE WATCHLIST OUTPUT
# ------------------------------------------------

print()
print("=" * 70)
print("▶️ LATEST VIDEOS FROM YOUR YOUTUBE WATCHLIST")
print("=" * 70)

for video in youtube_videos:

    print()
    print(
        f"{video['channel']}: "
        f"{video['title']}"
    )

    if video["published"]:
        print(f"   Published: {video['published']}")

    print(f"   {video['link']}")


# ------------------------------------------------
# GOOGLE OUTPUT
# ------------------------------------------------

print()
print("=" * 70)
print("🔎 CURRENT GOOGLE TRENDS UK")
print("=" * 70)

for number, trend in enumerate(
    google_trends[:20],
    start=1
):
    print(f"{number}. {trend['title']}")


print()
print("=" * 70)
print("Radar complete.")
print("=" * 70)
