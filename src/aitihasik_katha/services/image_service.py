from functools import lru_cache

from google.api_core.exceptions import GoogleAPICallError
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from PIL import Image
from vertexai.preview.vision_models import ImageGenerationModel

from ..core.logging import get_logger
from ..core.settings import settings
from ..utils.retry import retry


@lru_cache(maxsize=1)
def _get_generation_model() -> ImageGenerationModel:
    settings.require("IMAGE_MODEL")
    return ImageGenerationModel.from_pretrained(settings.IMAGE_MODEL)


@lru_cache(maxsize=1)
def _get_chain():
    settings.require("IMAGE_CHAT_MODEL", "GEMINI_API_KEY")
    llm = ChatGoogleGenerativeAI(
        model=settings.IMAGE_CHAT_MODEL,
        api_key=settings.GEMINI_API_KEY,
    )
    return prompt_template | llm | StrOutputParser()


prompt_template = PromptTemplate.from_template(
    """
You are an expert prompt engineer for AI image generation.

Your task is to convert a historical narrative into a highly specific cinematic image prompt.

The story and current scene might be in any other language than English, but your job is to craft a prompt in English.

Full story (context only, do not summarize):
{full_story}

Current scene (focus here):
{current_scene}

Instructions:
- Focus ONLY on the current scene
- Extract key visual elements: characters, actions, setting, time period
- Be very specific about:
  - clothing
  - architecture
  - lighting
  - mood
  - camera framing (e.g., close-up, wide shot)
- Ensure historical accuracy
- Make each scene visually distinct
- Avoid generic descriptions
- No text or captions
- English Language Only

Output format:
A single, highly detailed image generation prompt (no explanations).
"""
)

logger = get_logger(__name__)


@retry(
    exceptions=(GoogleAPICallError, RuntimeError, ValueError, TypeError),
    max_attempts=5,
    delay_seconds=5,
    backoff_keywords=("quota", "rate"),
    backoff_delay_seconds=30,
)
def generate_image_prompt(current_scene: str, full_story: str) -> str:
    return _get_chain().invoke(
        {
            "full_story": full_story,
            "current_scene": current_scene,
        }
    )


@retry(exceptions=(GoogleAPICallError, RuntimeError, ValueError, TypeError), max_attempts=3, delay_seconds=30)
def _generate_image_with_retry(prompt: str, output_path: str) -> str:
    images = _get_generation_model().generate_images(
        prompt=prompt,
        number_of_images=1,
        aspect_ratio="9:16",
        negative_prompt="",
        person_generation="allow_all",
        safety_filter_level=None,
        add_watermark=True,
    )
    images[0].save(output_path)
    return output_path


def generate_image(current_scene: str, full_story: str, output_path: str) -> str:
    prompt = generate_image_prompt(current_scene=current_scene, full_story=full_story)
    try:
        return _generate_image_with_retry(prompt, output_path)
    except (GoogleAPICallError, RuntimeError, ValueError, TypeError) as exc:
        logger.warning("Using fallback image after image generation retries were exhausted: %s", exc)
        fail_safe_image = Image.new("RGB", (768, 1408), color="black")
        fail_safe_image.save(output_path)
        return output_path
