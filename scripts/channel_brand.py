"""Visible channel identity, independent of topic history and narration."""
BRAND = "ملفات غامضه"

def display_title(topic, limit=100):
    topic=' '.join(str(topic or '').split()).strip()
    title=topic if topic.startswith(BRAND+' | ') or topic==BRAND else BRAND+' | '+topic
    return title[:limit].rstrip()
