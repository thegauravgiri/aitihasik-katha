import re
import unicodedata

# Bookish words that read like a textbook when spoken. Each maps to what people actually say.
BOOKISH_WORDS = {
    "किंवदन्ती": "भनिन्छ / कथा अनुसार",
    "जनविश्वास": "मान्छेले विश्वास गर्छन्",
    "जनश्रुति": "भनिन्छ",
    "संस्थागत": "सुरु गरेको / लागू गरेको",
    "दर्शाउँछ": "देखाउँछ",
    "दर्शाउँथ्यो": "देखाउँथ्यो",
    "विराजमान": "छ",
    "दिवंगत": "मरिसकेका",
    "प्रतिबन्ध": "रोक",
    "अवशेष": "बाँकी रहेको कुरा",
    "सांस्कृतिक": "हाम्रो संस्कृतिको",
    "ऐतिहासिक रूपमा": "इतिहासमा",
    "अत्यन्तै": "धेरै",
    "तत्कालीन": "त्यतिबेलाका",
    "सर्वप्रथम": "सबैभन्दा पहिला",
    "उल्लेखनीय": "ठूलो",
    "पुनर्स्थापना": "फेरि बनाउनु",
    "अवलम्बन": "अपनाउनु",
    "प्रचलन": "चलन",
    "सम्भव": "हुन सक्ने",
    "समेत": "पनि",
    "निमित्त": "लागि",
    "तथा": "र",
    "अर्थात्": "मतलब",
    "फलस्वरूप": "त्यसैले",
    "उक्त": "त्यो",
    "सञ्चालन": "चलाउनु",
    "आयोजना": "कार्यक्रम",
    "अनुशरण": "पछ्याउनु",
    "वर्णन": "भनाइ",
    "प्रतिज्ञा": "कसम",
    "रहस्यमय": "अचम्मको",
    "अनौठो": "अचम्मको",
}

_DEVANAGARI = r"ऀ-ॿ"
_SENTENCE_END = re.compile(rf"(?<=[{_DEVANAGARI}])\.(?=\s|$)")


def nepali_punctuation(text: str) -> str:
    """Use the purna biram (।) instead of a full stop after Nepali (Devanagari) sentences.
    A full stop after English words, numbers or URLs is left alone."""
    return _SENTENCE_END.sub("।", text)


def bookish_words(text: str) -> list[str]:
    """The bookish words found in `text`, each with the plain word to use instead."""
    return [f"{word} (say: {plain})" for word, plain in BOOKISH_WORDS.items() if word in text]


def long_sentences(text: str, max_words: int = 12) -> list[str]:
    """Sentences too long to speak in one breath or show as one shot."""
    sentences = [s.strip() for s in re.split(r"[.!?।]+", text) if s.strip()]
    return [s for s in sentences if len(s.split()) > max_words]


def stray_characters(text: str) -> list[str]:
    """Letters from other scripts (a model glitch such as an Armenian or Thai letter inside a Nepali
    word). Only Devanagari and Latin letters belong in a script or caption."""
    stray = []
    for char in text:
        if unicodedata.category(char).startswith("L") and not unicodedata.name(char, "").startswith(("DEVANAGARI", "LATIN")):
            if char not in stray:
                stray.append(char)
    return stray
