import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
import re

# -----------------------------------
# POP CULTURE RADAR - VERSION 0.1
# -----------------------------------

FEEDS = [
    ("Variety", "https://variety.com/feed/"),
    ("Deadline", "https://deadline.com/feed/"),
    ("Hollywood Reporter", "https://www.hollywoodreporter.com/feed/"),
    ("Rolling Stone", "https://www.rollingstone.com/tv-movies/feed/"),
]

IGNORE_WORDS = {
    "the", "and", "for", "with", "that", "this", "from",
    "has", "have", "will", "about", "after", "into",
    "their", "they", "its", "are", "was", "who", "why",
    "how", "new", "says", "over", "more", "his", "her",
    "film", "movie", "tv"
}


def get_feed(source, url):
    """Download headlines from an RSS feed."""

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)

        stories = []

        for item in root.findall(".//item"):
            title = item.findtext("title")
            link = item.findtext("link")

            if title:
                stories.append({
                    "source": source,
                    "title": title.strip(),
                    "link": link or ""
                })

        return stories

    except Exception as error:
        print(f"Could not read {source}: {error}")
        return []


def important_words(text):
    """Extract useful words from a headline."""

    words = re.findall(r"[A-Za-z0-9']+", text.lower())

    return [
        word for word in words
        if len(word) > 3 and word not in IGNORE_WORDS
    ]


print()
print("=" * 60)
print("🔥 POP CULTURE RADAR")
print("=" * 60)
print()

all_stories = []

for source, url in FEEDS:

    print(f"Scanning {source}...")

    stories = get_feed(source, url)

    print(f"  Found {len(stories)} stories")

    all_stories.extend(stories)


print()
print(f"Total stories scanned: {len(all_stories)}")
print()


# Count words appearing across headlines

word_counts = Counter()

for story in all_stories:
    words = set(important_words(story["title"]))
    word_counts.update(words)


# Give each story a basic trend score

ranked_stories = []

for story in all_stories:

    words = important_words(story["title"])

    score = sum(word_counts[word] for word in set(words))

    ranked_stories.append({
        **story,
        "score": score
    })


ranked_stories.sort(
    key=lambda story: story["score"],
    reverse=True
)


# Show the top 20

print("=" * 60)
print("📈 TODAY'S POP CULTURE RADAR")
print("=" * 60)

seen_titles = set()
position = 1

for story in ranked_stories:

    title_key = story["title"].lower()

    if title_key in seen_titles:
        continue

    seen_titles.add(title_key)

    print()
    print(f"{position}. {story['title']}")
    print(f"   Trend score: {story['score']}")
    print(f"   Source: {story['source']}")
    print(f"   {story['link']}")

    position += 1

    if position > 20:
        break


print()
print("=" * 60)
print("Radar complete.")
print("=" * 60)
