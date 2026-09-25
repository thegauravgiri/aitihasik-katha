import random
from datetime import timedelta
from functools import lru_cache

from google.api_core.exceptions import GoogleAPICallError
from google.cloud import texttospeech
from moviepy import AudioFileClip
from ..core.logging import get_logger
from ..core.settings import settings
from ..utils.retry import retry


VOICE_PROMPTS = [
    "Clear, engaging storytelling voice with a fast pace, confident tone, crisp pronunciation, and strong emphasis on hook words for high retention.",
    "Cinematic documentary-style voice with a fast pace, authoritative tone, sharp articulation, and impactful emphasis on key moments.",
    "High-energy viral shorts voice with fast-paced delivery, dynamic rhythm, strong hooks, and punchy emphasis to retain attention instantly.",
    "Clear educational voice with a fast pace, confident tone, precise pronunciation, and structured emphasis for quick understanding.",
    "Dramatic storytelling voice with a fast pace, mysterious tone, cinematic flow, and suspense-driven emphasis.",
    "Smooth but engaging narration voice with a fast pace, warm tone, and clear articulation designed for continuous attention.",
    "Epic cinematic voice with a fast pace, powerful tone, strong dramatic emphasis, and trailer-like intensity.",
    "Neutral professional voice with a fast pace, clear articulation, and factual delivery suitable for concise historical explanations.",
    "Hook-optimized voice with fast opening delivery, sharp clarity, and strong emphasis on curiosity-driven words to grab attention immediately.",
    "Natural creator-style voice with a fast, expressive tone, smooth flow, and engaging emphasis for viral storytelling content.",
]


logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _get_client() -> texttospeech.TextToSpeechClient:
    return texttospeech.TextToSpeechClient()


def get_audio_duration(audio_filepath: str) -> timedelta:
    audio_clip = AudioFileClip(audio_filepath)
    duration = timedelta(seconds=audio_clip.duration)
    audio_clip.close()
    return duration


@retry(exceptions=(GoogleAPICallError,), max_attempts=3, delay_seconds=5)
def _synthesize_speech(
    synthesis_input: texttospeech.SynthesisInput,
    voice: texttospeech.VoiceSelectionParams,
    audio_config: texttospeech.AudioConfig,
):
    return _get_client().synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config,
    )


def generate_audio(text: str, output_path: str) -> str:
    """Generate an MP3 audio file from plain text narration."""
    settings.require("AUDIO_MODEL")
    voice_prompt = random.choice(VOICE_PROMPTS)
    logger.info("Using voice prompt: %s", voice_prompt)
    synthesis_input = texttospeech.SynthesisInput(text=text, prompt=voice_prompt)

    voice = texttospeech.VoiceSelectionParams(
        language_code="ne-NP",
        name="Charon",
        model_name=settings.AUDIO_MODEL,
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
    )

    response = _synthesize_speech(synthesis_input, voice, audio_config)

    with open(output_path, "wb") as out:
        out.write(response.audio_content)
        logger.info("Audio content written to %s", output_path)

    return output_path
