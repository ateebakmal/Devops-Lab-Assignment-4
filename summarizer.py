"""
Dependency-free extractive summarizer.

Scores every sentence by the frequency of its (non-stopword) terms, then
returns the top-N sentences in their original order. This keeps the Docker
image small and avoids downloading an ML model at runtime, which matters on
a 1 GB free-tier EC2 instance.
"""
import re
from collections import Counter

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "also", "am", "an",
    "and", "any", "are", "aren't", "as", "at", "be", "because", "been", "before",
    "being", "below", "between", "both", "but", "by", "can", "can't", "cannot",
    "could", "couldn't", "did", "didn't", "do", "does", "doesn't", "doing",
    "don't", "down", "during", "each", "few", "for", "from", "further", "had",
    "hadn't", "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll",
    "he's", "her", "here", "here's", "hers", "herself", "him", "himself", "his",
    "how", "how's", "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is",
    "isn't", "it", "it's", "its", "itself", "just", "let's", "me", "more", "most",
    "mustn't", "my", "myself", "no", "nor", "not", "of", "off", "on", "once",
    "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over",
    "own", "said", "same", "say", "says", "shan't", "she", "she'd", "she'll",
    "she's", "should", "shouldn't", "so", "some", "such", "than", "that",
    "that's", "the", "their", "theirs", "them", "themselves", "then", "there",
    "there's", "these", "they", "they'd", "they'll", "they're", "they've",
    "this", "those", "through", "to", "too", "under", "until", "up", "very",
    "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were", "weren't",
    "what", "what's", "when", "when's", "where", "where's", "which", "while",
    "who", "who's", "whom", "why", "why's", "will", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves",
}

# Split on sentence-ending punctuation followed by whitespace + a capital/quote/digit.
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[\"'\u201c\u2018(]?[A-Z0-9])")
_WORD_RE = re.compile(r"[a-z][a-z'\-]+")


def split_sentences(text: str) -> list:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    parts = [s.strip() for s in _SENTENCE_RE.split(text)]
    return [s for s in parts if len(s) > 1]


def summarize(text: str, max_sentences: int = 5) -> str:
    """Return an extractive summary of `text` of at most `max_sentences`."""
    sentences = split_sentences(text)
    if not sentences:
        return ""
    if len(sentences) <= max_sentences:
        return " ".join(sentences)

    # Term frequencies across the whole article, ignoring stopwords.
    freq = Counter()
    for sentence in sentences:
        for word in _WORD_RE.findall(sentence.lower()):
            if word not in STOPWORDS:
                freq[word] += 1
    if not freq:
        return " ".join(sentences[:max_sentences])

    peak = max(freq.values())
    norm = {w: c / peak for w, c in freq.items()}

    scored = []
    for index, sentence in enumerate(sentences):
        words = [w for w in _WORD_RE.findall(sentence.lower()) if w not in STOPWORDS]
        if not words:
            continue
        # Average term weight, so long sentences are not automatically favoured.
        score = sum(norm.get(w, 0.0) for w in words) / len(words)
        # Mild lead bias: journalism puts the key facts in the opening sentences.
        if index < 3:
            score *= 1.25
        # Penalise very short or very long fragments.
        if len(words) < 5 or len(words) > 60:
            score *= 0.5
        scored.append((score, index, sentence))

    if not scored:
        return " ".join(sentences[:max_sentences])

    top = sorted(scored, key=lambda item: item[0], reverse=True)[:max_sentences]
    return " ".join(sentence for _, _, sentence in sorted(top, key=lambda item: item[1]))
