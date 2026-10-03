from aitihasik_katha.utils.nepali import bookish_words, long_sentences, nepali_punctuation, stray_characters


def test_full_stops_after_nepali_become_purna_biram():
    assert nepali_punctuation("यो राम्रो छ. अर्को वाक्य छ.") == "यो राम्रो छ। अर्को वाक्य छ।"


def test_full_stops_in_english_numbers_and_links_are_left_alone():
    text = "Photo by Mr. Shah. Read more at nepal.com. Price 4.5 rupees. यो नेपाली छ."

    assert nepali_punctuation(text) == "Photo by Mr. Shah. Read more at nepal.com. Price 4.5 rupees. यो नेपाली छ।"


def test_question_marks_and_existing_purna_biram_are_untouched():
    assert nepali_punctuation("के हो? यो हो।") == "के हो? यो हो।"


def test_bookish_words_are_reported_with_the_plain_word():
    found = bookish_words("किंवदन्ती अनुसार यो राजा दिवंगत भए")

    assert any(f.startswith("किंवदन्ती") and "भनिन्छ" in f for f in found)
    assert any(f.startswith("दिवंगत") and "मरिसकेका" in f for f in found)


def test_plain_spoken_nepali_has_no_bookish_words():
    assert bookish_words("मान्छेहरू भन्छन् राजाले चरा उडाउन रोक लगाए") == []


def test_long_sentences_are_found():
    text = "छोटो वाक्य छ। " + " ".join(["शब्द"] * 15) + "। फेरि छोटो।"

    assert long_sentences(text) == [" ".join(["शब्द"] * 15)]


def test_letters_from_other_scripts_are_found():
    assert stray_characters("चङ्गा र पिङबिनाको दसैँ त अधուրो नै हुन्छ") == ["ո", "ւ", "ր"]


def test_nepali_english_digits_and_punctuation_are_not_stray():
    assert stray_characters("दसैँ 2026 — Dashain! #Nepal @aitihasik_katha ? । 🪁") == []
