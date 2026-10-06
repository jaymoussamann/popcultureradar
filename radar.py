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
        and len({item["source"] for item in topic["news"]}) <= 1
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
