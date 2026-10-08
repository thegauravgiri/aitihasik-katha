import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

from aitihasik_katha.services import music_service
from aitihasik_katha.services.music_service import (
    MOOD_EPIC,
    MOOD_HERITAGE,
    MOOD_MYSTIC,
    MOOD_TENSION,
    MOOD_TRIUMPHANT,
    detect_mood,
    get_background_music,
    _find_local_track_for_mood,
)


def test_detect_mood_default():
    assert detect_mood() == MOOD_TENSION
    assert detect_mood("", "") == MOOD_TENSION
    assert detect_mood("completely neutral random text without keywords") == MOOD_TENSION


def test_detect_mood_keywords():
    assert detect_mood("The Secret Origins of Football in Nepal") == MOOD_HERITAGE
    assert detect_mood("नेपालको फुटबल र राणाकालीन खेल") == MOOD_HERITAGE
    assert detect_mood("नालापानीको लडाइँ र बलभद्र कुँवरको वीरता") == MOOD_EPIC
    assert detect_mood("The Great Siege and Epic Battle of Nalapani") == MOOD_EPIC
    assert detect_mood("काठमाडौँको तान्त्रिक मन्दिर र जीवित देवी कुमारी") == MOOD_MYSTIC
    assert detect_mood("Sacred Tantric Temple and Ancient Curse") == MOOD_MYSTIC
    assert detect_mood("२००७ सालको क्रान्ति र प्रजातन्त्रको घोषणा") == MOOD_TRIUMPHANT
    assert detect_mood("The Democratic Revolution and Fall of Rana Regime") == MOOD_TRIUMPHANT
    assert detect_mood("आफ्नै Prime Minister ढाल्न राजा पिकनिकको बहाना बनाएर भागेका थिए") == MOOD_TENSION
    assert detect_mood("The Secret Royal Palace Plot and Escape") == MOOD_TENSION


def test_detect_mood_from_plan():
    plan = {
        "angle": "Frontline battle and military siege",
        "reason": "soldiers at war",
        "beats": ["clash of swords", "fortress assault"],
    }
    assert detect_mood(plan=plan) == MOOD_EPIC


def test_find_local_track_from_catalog(tmp_path):
    track_file = tmp_path / "custom_heritage.ogg"
    track_file.write_bytes(b"x" * 2000)

    catalog = {
        "tracks": [
            {
                "filename": "custom_heritage.ogg",
                "mood": MOOD_HERITAGE,
                "title": "Custom Heritage",
            }
        ]
    }
    (tmp_path / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")

    found = _find_local_track_for_mood(tmp_path, MOOD_HERITAGE)
    assert found == str(track_file)


def test_find_local_track_by_filename(tmp_path):
    track_file = tmp_path / "epic_war_drums.mp3"
    track_file.write_bytes(b"x" * 2000)

    found = _find_local_track_for_mood(tmp_path, MOOD_EPIC)
    assert found == str(track_file)


def test_get_background_music_cached_hit(tmp_path, monkeypatch):
    existing_track = tmp_path / "cinematic_ambient_tension.wav"
    existing_track.write_bytes(b"x" * 5000)

    # requests.get should not be called if local track exists
    mock_get = MagicMock()
    monkeypatch.setattr(requests, "get", mock_get)

    result = get_background_music(
        topic="दरबार हत्याकाण्ड र षड्यन्त्र",
        music_dir=tmp_path,
    )

    assert result == str(existing_track)
    mock_get.assert_not_called()


def test_get_background_music_downloads_and_registers(tmp_path, monkeypatch):
    fake_audio_content = [b"a" * 1024, b"b" * 1024]

    mock_resp = MagicMock()
    mock_resp.iter_content.return_value = fake_audio_content
    mock_resp.raise_for_status = MagicMock()

    mock_get = MagicMock(return_value=mock_resp)
    monkeypatch.setattr(requests, "get", mock_get)

    result = get_background_music(
        topic="The Secret Origins of Football in Nepal",
        music_dir=tmp_path,
    )

    assert result is not None
    assert Path(result).exists()
    assert Path(result).stat().st_size == 2048

    catalog_file = tmp_path / "catalog.json"
    assert catalog_file.exists()
    catalog_data = json.loads(catalog_file.read_text(encoding="utf-8"))
    assert len(catalog_data["tracks"]) == 1
    assert catalog_data["tracks"][0]["mood"] == MOOD_HERITAGE


def test_get_background_music_download_fail_fallback(tmp_path, monkeypatch):
    # A generic audio file exists in tmp_path
    generic_track = tmp_path / "some_existing_track.wav"
    generic_track.write_bytes(b"y" * 2000)

    mock_get = MagicMock(side_effect=requests.RequestException("Network offline"))
    monkeypatch.setattr(requests, "get", mock_get)

    result = get_background_music(
        topic="काठमाडौँको तान्त्रिक मन्दिर",
        music_dir=tmp_path,
    )

    # Should fall back to generic_track
    assert result == str(generic_track)


def test_get_background_music_download_fail_no_fallback(tmp_path, monkeypatch):
    mock_get = MagicMock(side_effect=requests.RequestException("Network offline"))
    monkeypatch.setattr(requests, "get", mock_get)

    result = get_background_music(
        topic="काठमाडौँको तान्त्रिक मन्दिर",
        music_dir=tmp_path,
    )

    assert result is None
