import re

from app.domain.job import OfferLanguage

ARABIC_LETTER = re.compile(r"[\u0600-\u06FF]")
WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
MIN_HITS = 5
MIN_LEAD = 1.5
MIN_ARABIC_SHARE = 0.3

# Small, frequent words that belong to one language only. Words shared by two of these
# languages ("des" in French and German, "in" in English and German) are left out on purpose.
FRENCH_WORDS = """
le la les et du une pour avec dans sur au aux est par de un en ou ce cette mes nos leur où
plus sous chez
"""
ENGLISH_WORDS = """
the and of to for with on at is as by from or my our this that their into using built
developed
"""
GERMAN_WORDS = """
der die das und mit für von zu im den dem ein eine ist auf bei sowie oder ich wir einer eines
nach über
"""
STOPWORDS: dict[OfferLanguage, frozenset[str]] = {
    "fr": frozenset(FRENCH_WORDS.split()),
    "en": frozenset(ENGLISH_WORDS.split()),
    "de": frozenset(GERMAN_WORDS.split()),
}


def detect_language(text: str) -> OfferLanguage | None:
    """The language a text is written in, among the supported ones, or None when unsure.

    Counting frequent small words is enough to tell French, English and German apart in a CV;
    technical terms are the same in every language, so they do not count.
    """
    letters = [character for character in text if character.isalpha()]
    if letters:
        arabic = sum(bool(ARABIC_LETTER.match(character)) for character in letters)
        if arabic / len(letters) >= MIN_ARABIC_SHARE:
            return "ar"
    words = [word.casefold() for word in WORD.findall(text)]
    scores = {
        language: sum(word in vocabulary for word in words)
        for language, vocabulary in STOPWORDS.items()
    }
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    (best, best_score), (_, second_score) = ranked[0], ranked[1]
    if best_score < MIN_HITS or best_score < MIN_LEAD * second_score:
        return None
    return best
