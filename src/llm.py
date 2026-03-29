"""LLM-backed summarization and embedding for source code files and functions."""

from __future__ import annotations

import os

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import HumanMessage, SystemMessage


_SYSTEM_PROMPT = (
    'You are a senior software engineer. '
    'When given the content of a source code file, respond with a concise '
    'plain-text summary (3-8 sentences) that describes: what the file does, '
    'the key classes or functions it exposes, and any notable design decisions. '
    'Do not include markdown, headings, or code blocks in your response.'
)

_chat_model = ChatOpenAI(
    model=os.getenv('OPENAI_CHAT_MODEL', 'gpt-5.4-mini'),
    temperature=0,
)

_embedding_model = OpenAIEmbeddings(
    model=os.getenv('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small'),
)


def summarize_file(path: str, content: str) -> str:
    """
    Call the LLM to produce a plain-text summary of a source code file.

    Args:
        path: The relative file path (used as context in the prompt).
        content: The full text content of the file.

    Returns:
        A concise natural-language description of the file.
    """
    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=f'File: {path}\n\n```\n{content}\n```'),
    ]
    response = _chat_model.invoke(messages)
    return str(response.content).strip()


def embed_text(text: str) -> list[float]:
    """
    Produce a vector embedding for the given text using the configured
    OpenAI embeddings model.

    Args:
        text: The text to embed (typically a file summary).

    Returns:
        A list of floats representing the embedding vector.
    """
    return _embedding_model.embed_query(text)


_FUNCTION_SYSTEM_PROMPT = (
    'You are a senior software engineer. '
    'When given a function or method from a source code file, respond with a concise '
    'plain-text description (1-3 sentences) that describes what the function does, '
    'its parameters, and what it returns. '
    'Do not include markdown, headings, or code blocks in your response.'
)


def summarize_function(path: str, name: str, body: str) -> str:
    """
    Call the LLM to produce a plain-text summary of a single function or method.

    Args:
        path: The relative file path (used as context in the prompt).
        name: The function or method name.
        body: The full source text of the function.

    Returns:
        A concise natural-language description of the function.
    """
    messages = [
        SystemMessage(content=_FUNCTION_SYSTEM_PROMPT),
        HumanMessage(content=f'File: {path}\nFunction: {name}\n\n```\n{body}\n```'),
    ]
    response = _chat_model.invoke(messages)
    return str(response.content).strip()
