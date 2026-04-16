"""Shared Groq client utilities for pipeline agents."""

import os
from dotenv import load_dotenv
from groq import Groq

_client = None


def get_groq_client() -> Groq:
    """Return a lazily initialized Groq client."""
    global _client

    if _client is None:
        load_dotenv(override=False)
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY environment variable is not set. "
                "Set it before running LLM-powered pipeline steps."
            )
        _client = Groq(api_key=api_key)

    return _client
