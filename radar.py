import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
import re
import html

# -----------------------------------
# POP CULTURE RADAR - VERSION 0.2
# Entertainment News + Google Trends
# -----------------------------------

NEWS_FEEDS = [
    ("Variety", "https://variety.com/feed/"),
    ("Deadline", "https://deadline.com/feed/"),
    ("Hollywood Reporter", "https://www.hollywoodreporter.com/feed/"),
    ("Rolling Stone", "https://www.rollingstone.com/tv-movies/feed/"),
]

# Google Trends RSS
# GB = United Kingdom. We can add US and other countries later.
GOOGLE_TRENDS_URL = (
    "https://trends.google.com/trending/rss?geo=GB"
)

IGNORE_WORDS = {
    "the", "and", "for", "with", "that", "this", "from",
    "has", "have", "will", "about", "after", "into",
    "their", "they", "its", "are", "was", "who", "why",
    "how", "new", "says", "over", "more", "his", "her",
    "film", "movie", "movies", "show", "shows", "series",
    "season", "episode", "star", "stars"
}


def download_xml(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read()


def get_news_feed(source, url):
    """Download entertainment headlines."""

    try:
        root = ET.fromstring(download_xml(url))

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
    """Get Google's current UK trending searches."""

    try:
        root = ET.fromstring(download_xml(GOOGLE_TRENDS_URL))

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


def important_words(text):
    words = re.findall(r"[A-Za-z0-9']+", text.lower())

    return [
        word for word in words
        if len(word) > 3 and word not in IGNORE_WORDS
    ]


def trend_matches_story(trend_title, story_title):
    """
    Decide whether a Google trend genuinely matches
    an entertainment headline.

    We deliberately use strict rules to avoid false
    matches caused by generic words or numbers.
    """

    trend_words = important_words(trend_title)
    story_words = important_words(story_title)

    # Ignore numbers completely when matching.
    trend_words = [
        word for word in trend_words
        if not word.isdigit()
    ]

    story_words = [
        word for word in story_words
        if not word.isdigit()
    ]

    if not trend_words or not story_words:
        return False

    trend_set = set(trend_words)
    story_set = set(story_words)

    shared = trend_set.intersection(story_set)

    # -----------------------------------
    # RULE 1
    # Multi-word Google trends need at
    # least TWO matching meaningful words.
    #
    # Example:
    # "Andrew Garfield"
    # matches a headline containing
    # "Andrew Garfield".
    # -----------------------------------

    if len(trend_set) >= 2:
        return len(shared) >= 2

    # -----------------------------------
    # RULE 2
    # A one-word Google trend must be a
    # reasonably distinctive word.
    #
    # This allows things such as:
    # "Beyonce"
    # "Wicked"
    # "Superman"
    #
    # but avoids tiny/generic matches.
    # -----------------------------------

    if len(trend_set) == 1:

        word = next(iter(trend_set))

        if len(word) < 6:
            return False

        return word in story_set

    return False


print()
print("=" * 65)
print("🔥 POP CULTURE RADAR 0.2")
print("Entertainment News + Google Trends")
print("=" * 65)
print()


# -----------------------------------
# COLLECT ENTERTAINMENT NEWS
# -----------------------------------

all_stories = []

for source, url in NEWS_FEEDS:

    print(f"Scanning {source}...")

    stories = get_news_feed(source, url)

    print(f"  Found {len(stories)} stories")

    all_stories.extend(stories)


# -----------------------------------
# COLLECT GOOGLE TRENDS
# -----------------------------------

print()
print("Scanning Google Trends UK...")

google_trends = get_google_trends()

print(f"  Found {len(google_trends)} trending searches")


print()
print(f"Entertainment stories scanned: {len(all_stories)}")
print(f"Google trends scanned: {len(google_trends)}")
print()


# -----------------------------------
# FIND COMMON WORDS IN NEWS
# -----------------------------------

word_counts = Counter()

for story in all_stories:
    words = set(important_words(story["title"]))
    word_counts.update(words)


# -----------------------------------
# SCORE STORIES
# -----------------------------------

ranked_stories = []

for story in all_stories:

    words = important_words(story["title"])

    news_score = sum(
        word_counts[word]
        for word in set(words)
    )

    matching_trends = []

    for trend in google_trends:

        if trend_matches_story(
            trend["title"],
            story["title"]
        ):
            matching_trends.append(trend["title"])

    # Google confirmation gives a large boost.
    google_boost = len(matching_trends) * 20

    total_score = news_score + google_boost

    ranked_stories.append({
        **story,
        "news_score": news_score,
        "google_boost": google_boost,
        "matching_trends": matching_trends,
        "score": total_score
    })


ranked_stories.sort(
    key=lambda story: story["score"],
    reverse=True
)


# -----------------------------------
# DISPLAY RESULTS
# -----------------------------------

print("=" * 65)
print("📈 TODAY'S POP CULTURE RADAR")
print("=" * 65)

seen_titles = set()
position = 1

for story in ranked_stories:

    title_key = story["title"].lower()

    if title_key in seen_titles:
        continue

    seen_titles.add(title_key)

    print()
    print(f"{position}. {story['title']}")
    print(f"   RADAR SCORE: {story['score']}")
    print(f"   News signal: {story['news_score']}")

    if story["google_boost"] > 0:
        print(f"   🔥 GOOGLE TREND MATCH: +{story['google_boost']}")

        for trend in story["matching_trends"][:3]:
            print(f"      ↳ {trend}")
    else:
        print("   Google trend match: none")

    print(f"   Source: {story['source']}")
    print(f"   {story['link']}")

    position += 1

    if position > 20:
        break


# -----------------------------------
# ALSO SHOW GOOGLE'S RAW TRENDS
# -----------------------------------

print()
print("=" * 65)
print("🔎 CURRENT GOOGLE TRENDS UK")
print("=" * 65)

for number, trend in enumerate(
    google_trends[:20],
    start=1
):
    print(f"{number}. {trend['title']}")


print()
print("=" * 65)
print("Radar complete.")
print("=" * 65)
