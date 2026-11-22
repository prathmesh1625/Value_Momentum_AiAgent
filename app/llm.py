"""Thin wrapper around Groq (via LangChain) so every agent calls the LLM the same way."""
from __future__ import annotations

import time
from functools import lru_cache
from typing import TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel

from app import config

T = TypeVar("T", bound=BaseModel)


class LLMNotConfigured(RuntimeError):
    pass


@lru_cache(maxsize=1)
def get_llm() -> ChatGroq:
    if not config.GROQ_API_KEY:
        raise LLMNotConfigured(
            "GROQ_API_KEY is not set. Copy .env.example to .env and add your free key "
            "from https://console.groq.com/keys"
        )
    return ChatGroq(model=config.GROQ_MODEL, temperature=0, api_key=config.GROQ_API_KEY, max_retries=2)


def structured(schema: type[T], system: str, user: str, attempts: int = 3) -> T:
    """Ask the LLM to answer in the shape of a Pydantic model. Retries on malformed output."""
    llm = get_llm().with_structured_output(schema)
    last_err: Exception | None = None
    for i in range(attempts):
        try:
            result = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
            if result is not None:
                return result
        except Exception as e:  # Groq free tier: tool-call validation errors and 429s happen
            last_err = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"LLM failed to return a valid {schema.__name__}: {last_err}")


def text(system: str, user: str) -> str:
    resp = get_llm().invoke([SystemMessage(content=system), HumanMessage(content=user)])
    return str(resp.content).strip()
