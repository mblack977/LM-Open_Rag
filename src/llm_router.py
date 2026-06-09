import logging
from typing import Tuple

from .lm_studio_client import LMStudioClient

logger = logging.getLogger(__name__)

# Queries below this NLP complexity score route to the fast LLM in auto mode.
COMPLEXITY_THRESHOLD = 0.35

# These query intents always route to the fast LLM regardless of score.
_FAST_INTENTS = {"factual_lookup"}


class LLMRouter:
    """
    Selects fast or large LLM client based on NLP complexity score,
    query planner intent, and optional user override.
    """

    def __init__(self, fast_client: LMStudioClient, large_client: LMStudioClient):
        self._fast = fast_client
        self._large = large_client

    def select_client(
        self,
        plan_intent: str,
        nlp_complexity: float,
        user_override: str = "auto",
    ) -> Tuple[LMStudioClient, str]:
        """
        Returns (client, tier) where tier is 'fast' or 'large'.

        user_override values: 'auto' | 'fast' | 'large'
        """
        if user_override == "fast":
            logger.debug("LLM route: fast (user forced)")
            return self._fast, "fast"

        if user_override == "large":
            logger.debug("LLM route: large (user forced)")
            return self._large, "large"

        # Auto routing: intent beats score for definitive cases
        if plan_intent in _FAST_INTENTS:
            logger.debug("LLM route: fast (intent=%s)", plan_intent)
            return self._fast, "fast"

        if nlp_complexity < COMPLEXITY_THRESHOLD:
            logger.debug("LLM route: fast (complexity=%.3f)", nlp_complexity)
            return self._fast, "fast"

        logger.debug("LLM route: large (complexity=%.3f, intent=%s)", nlp_complexity, plan_intent)
        return self._large, "large"
