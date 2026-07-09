"""
TARS Semantic Trigger Classifier

Matching strategy (in order):
  1. Exact phrase match - any 2+ word phrase from the trigger description found verbatim → fires
  2. Strong single keyword - one word ≥ 7 chars from the description → fires
  3. Keyword pair - two or more shorter keywords from the description → fires
  4. No match → pass

This eliminates the false positives from single short-word matches while keeping
high recall on clear trigger phrases. Fast, zero-model, runs continuously.
"""

import re
import time


STOPWORDS = {
    "this", "that", "with", "from", "they", "will", "just", "what", "when",
    "then", "them", "than", "have", "been", "says", "said", "some", "very",
    "also", "only", "even", "back", "take", "make", "like", "time", "well",
    "good", "know", "want", "need", "does", "here", "there", "their", "about",
    "would", "could", "should", "going", "doing", "being", "having", "these",
    "those", "your", "mine", "ours", "come", "goes", "went", "made", "said",
    "actually", "basically", "literally", "really", "honestly", "someone",
    "person", "people",
}

# Prefix patterns to strip from trigger descriptions
_PREFIX = re.compile(
    r"^(someone\s+says?|a\s+person\s+(just\s+)?says?|someone\s+just\s+says?)\s*",
    re.IGNORECASE,
)


def _clean(text: str) -> str:
    return re.sub(r"[^\w\s']", " ", text.lower()).strip()


def _extract_phrases_and_keywords(description: str):
    """
    Returns (phrases, keywords) where:
      - phrases: list of 2+ word strings to check as substrings
      - keywords: set of individual words ≥ 4 chars, excluding stopwords
    """
    phrases = []
    keywords = set()

    # Split on commas - each item is a candidate phrase
    for item in description.split(","):
        item = _PREFIX.sub("", item.strip().lower())
        item = _clean(item)
        if not item:
            continue

        words = item.split()
        if len(words) >= 2:
            phrases.append(item)

        # Collect individual keywords from every item
        for w in words:
            if len(w) >= 4 and w not in STOPWORDS:
                keywords.add(w)

    return phrases, keywords


class TARSClassifier:
    def __init__(self):
        self._cooldowns: dict[str, float] = {}
        print("Classifier ready.")

    def classify(self, sentence: str, triggers: list[dict]) -> str | None:
        s = _clean(sentence)

        for trigger in triggers:
            name = trigger["name"]
            cooldown = trigger.get("cooldown", 10)

            # Cooldown check first - cheapest gate
            now = time.time()
            if now - self._cooldowns.get(name, 0) <= cooldown:
                continue

            description = trigger.get("description", "")
            phrases, keywords = _extract_phrases_and_keywords(description)

            matched = False

            # ── Tier 1: exact phrase match ────────────────────────────────────
            for phrase in phrases:
                if phrase in s:
                    matched = True
                    break

            # ── Tier 2 & 3: keyword matching ──────────────────────────────────
            if not matched and keywords:
                s_words = set(s.split())
                common = keywords & s_words

                # Tier 2: one long, specific word (≥7 chars) is enough
                strong = {k for k in common if len(k) >= 7}
                if strong:
                    matched = True

                # Tier 3: two or more shorter keywords together
                elif len(common) >= 2:
                    matched = True

            if matched:
                self._cooldowns[name] = now
                return name

        return None
