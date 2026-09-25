from functools import lru_cache

from google.api_core.exceptions import GoogleAPICallError
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from ..core.settings import settings
from ..storage.vector_store import get_store
from ..utils.retry import retry


@lru_cache(maxsize=1)
def _get_llm() -> ChatGoogleGenerativeAI:
    settings.require("CHAT_MODEL", "GEMINI_API_KEY")
    return ChatGoogleGenerativeAI(
        model=settings.CHAT_MODEL,
        api_key=settings.GEMINI_API_KEY,
    )


story_prompt = PromptTemplate.from_template(
    """
    From the given historical context, generate a compelling, engaging script for a historical documentary video. The text will be directly used to generate a voice-over for the video.
    Therefore, avoid using explicit section headers, bullet points, or labels.
    The script should be immersive, engaging, and fact-based for a general audience of social media users and should be around 1-2 minute long when read aloud.
    Make sure that the script has a clear beginning, middle, and end without containing "Narrator", "Camera", "Title", and similar headings. Just plain text.
    Please avoid response like: "It appears that the provided text...." or "The text seems to be about...." and provide a direct script.

    STRICTLY GENERATE STORY IN NEPALI LANGUAGE

    ## Historical Context:
    {context}
    """
)


def get_context(topic: str | None = None) -> str:
    store = get_store()
    if topic:
        documents = store.get_similar_documents(topic)
    else:
        doc = store.get_random_document()
        documents = store.get_similar_documents(doc["documents"])

    return "---\n".join([document.strip() for document in documents])


@retry(exceptions=(GoogleAPICallError, RuntimeError, ValueError, TypeError), max_attempts=3, delay_seconds=5)
def _invoke(prompt: str) -> object:
    return _get_llm().invoke(prompt)


def generate_story(topic: str | None = None) -> str:
    context = get_context(topic)
    prompt = story_prompt.format(context=context)

    response = _invoke(prompt)
    story = response.content
    if isinstance(story, list):
        for item in story:
            if item.get("type") == "text":
                return item["text"]
    return str(story)
