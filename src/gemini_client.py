import asyncio
import os
from typing import Dict, List, Optional


class GeminiClient:
    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self._model_name = model or os.getenv("GEMINI_CHAT_MODEL") or "gemini-1.5-flash"
        self._api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self._api_key:
            raise ValueError(
                "GEMINI_API_KEY is required for Gemini. "
                "Set it via environment variable or provider settings."
            )

    async def chat(
        self, messages: List[Dict[str, str]], temperature: float = 0.2, max_tokens: int = 800
    ) -> str:
        return await asyncio.to_thread(self._chat_sync, messages, temperature, max_tokens)

    def _chat_sync(
        self, messages: List[Dict[str, str]], temperature: float, max_tokens: int
    ) -> str:
        import google.generativeai as genai

        genai.configure(api_key=self._api_key)
        model = genai.GenerativeModel(self._model_name)

        system_parts: List[str] = []
        history: List[Dict] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_parts.append(content)
                continue
            gemini_role = "user" if role == "user" else "model"
            history.append({"role": gemini_role, "parts": [content]})

        # Prepend collected system text to the first user turn
        if system_parts and history:
            system_text = "\n\n".join(system_parts)
            for item in history:
                if item["role"] == "user":
                    item["parts"][0] = f"{system_text}\n\n{item['parts'][0]}"
                    break

        generation_config = genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        if len(history) <= 1:
            content = history[0]["parts"][0] if history else ""
            response = model.generate_content(content, generation_config=generation_config)
        else:
            chat_session = model.start_chat(history=history[:-1])
            response = chat_session.send_message(
                history[-1]["parts"][0], generation_config=generation_config
            )

        return response.text
