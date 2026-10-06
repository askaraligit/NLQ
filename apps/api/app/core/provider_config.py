"""Version-controlled choices for the NLQ language-model provider.

Keep credentials in the environment. This module intentionally contains no API keys.
"""

from typing import Literal

ACTIVE_LLM_PROVIDER: Literal["openai", "nvidia", "anthropic", "local"] = "nvidia"
ACTIVE_LLM_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"
ALLOWED_LLM_MODELS = (ACTIVE_LLM_MODEL,)
LLM_TIMEOUT_SECONDS = 60
LLM_MAX_OUTPUT_TOKENS = 400
