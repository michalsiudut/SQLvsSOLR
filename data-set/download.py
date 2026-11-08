import json
import csv
from datasets import load_dataset
from tqdm import tqdm

TARGET = 500_000
OUTPUT = "wikipedia.csv"

# Kategorie tematyczne tworzone na podstawie treści
TOPICS = {
    "sports": ["football", "basketball", "tennis", "sport", "athlete"],
    "science": ["science", "physics", "chemistry", "biology"],
    "geography": ["country", "city", "river", "mountain"],
    "history": ["war", "historical", "century", "empire"],
    "politics": ["government", "president", "political", "election"],
    "culture": ["music", "artist", "film", "literature"],
}

def extract_text(data):
    """Wyciąga tekst z sekcji artykułu."""
    result = []

    def walk(obj):
        if isinstance(obj, dict):
            if isinstance(obj.get("value"), str):
                result.append(obj["value"])

            for key, value in obj.items():
                if key != "value":
                    walk(value)

        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return ""

    walk(data)
    return " ".join(result)


def classify_topic(title, text):
    content = (title + " " + text[:3000]).lower()

    for category, keywords in TOPICS.items():
        if any(word in content for word in keywords):
            return category

    return "other"


def classify_type(infobox):
    if isinstance(infobox, str):
        try:
            infobox = json.loads(infobox)
        except json.JSONDecodeError:
            infobox = []

    if isinstance(infobox, list) and infobox:
        name = infobox[0].get("name", "").lower()

        if "person" in name or "biography" in name:
            return "person"
        if "location" in name or "place" in name:
            return "location"
        if "organization" in name or "company" in name:
            return "organization"
        if "event" in name or "competition" in name:
            return "event"
        if "film" in name or "book" in name:
            return "media"

    return "general"


print("Connecting to Hugging Face...")

dataset = load_dataset(
    "wikimedia/structured-wikipedia",
    "enwiki_namespace_0",
    split="train",
    streaming=True
)

print("Downloading and processing articles...")

count = 0
total_chars = 0
topics = set()
types = set()

with open(OUTPUT, "w", newline="", encoding="utf-8") as file:

    writer = csv.DictWriter(
        file,
        fieldnames=[
            "id",
            "title",
            "text",
            "topic",
            "article_type",
            "date_modified"
        ]
    )

    writer.writeheader()

    for row in tqdm(dataset):

        title = row.get("name") or ""
        text = extract_text(row.get("sections"))

        # Dodajemy abstrakt, jeżeli istnieje
        abstract = row.get("abstract") or ""
        text = abstract + " " + text

        text = " ".join(text.split())

        # Minimum 300 znaków
        if len(text) < 300:
            continue

        topic = classify_topic(title, text)
        article_type = classify_type(row.get("infoboxes"))

        writer.writerow({
            "id": row["identifier"],
            "title": title,
            "text": text[:5000],
            "topic": topic,
            "article_type": article_type,
            "date_modified": row.get("date_modified")
        })

        count += 1
        total_chars += min(len(text), 5000)

        topics.add(topic)
        types.add(article_type)

        if count >= TARGET:
            break

print("\n========== DATASET REPORT ==========")
print(f"Records: {count}")
print(f"Average text length: {total_chars / count:.2f}")
print(f"Topics: {topics}")
print(f"Article types: {types}")
print(f"Output file: {OUTPUT}")

if count < TARGET:
    print("WARNING: Not enough records!")

if total_chars / count < 300:
    print("WARNING: Average text length below 300!")

if len(topics) < 2 or len(types) < 2:
    print("WARNING: Not enough category values!")

print("====================================")