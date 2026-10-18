"""Model-agnostic global weather assistant.
Supports ANY local model (Ollama, LM Studio, vLLM) and ANY cloud API (Gemini, Groq, OpenAI, DeepSeek)
using the universal OpenAI-compatible chat completions standard with Tool Calling.
"""
from __future__ import annotations

import json
import os
import sqlite3
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .service import get_current_weather
from .tools import TOOLS_SPEC, execute_tool

SYSTEM_PROMPT = """You are a global weather assistant.
You provide accurate, localized weather conditions, forecasts, and safety advisories for places worldwide.

GUIDELINES:
1. Always use your available tools (`get_current_weather`, `get_forecast`, `check_weather_risk`, `search_locations`) to retrieve ground-truth or model-estimated data before answering. Do not guess or fabricate weather numbers.
2. Consider elevation, terrain, and local conditions when relevant. Ask for a country when a place name is ambiguous.
3. Reply in the user's language when possible.
4. Always clearly communicate whether values are 'model-estimated' or 'forecast'.
5. Include a brief reminder that official emergency warnings come from the local meteorological or emergency-management authority.
"""


class WeatherAgent:
    def __init__(
        self,
        con: sqlite3.Connection,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int = 45,
    ):
        self.con = con
        # Auto-detect or default to environment variables
        self.base_url = (
            base_url
            or os.environ.get("LLM_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL")
            or "http://localhost:11434/v1"  # Default to local Ollama
        ).rstrip("/")
        
        self.api_key = (
            api_key
            or os.environ.get("LLM_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GROQ_API_KEY")
            or "none"
        )
        
        self.model = (
            model
            or os.environ.get("LLM_MODEL")
            or ("llama3.2" if "localhost" in self.base_url else "gemini-1.5-flash")
        )
        self.timeout = timeout

    def _call_llm(self, messages: list[dict], with_tools: bool = True) -> dict:
        """Send chat completion request to any OpenAI-compatible API endpoint."""
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
        }
        if with_tools:
            payload["tools"] = TOOLS_SPEC
            payload["tool_choice"] = "auto"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        req = Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM API Error (HTTP {exc.code}): {err_body}")
        except URLError as exc:
            raise ConnectionError(
                f"Could not connect to LLM at {self.base_url}: {exc.reason}\n"
                "Tip: If running locally, make sure Ollama or LM Studio is running. "
                "Or set LLM_BASE_URL and LLM_API_KEY for cloud models (Groq/Gemini/OpenAI)."
            )

    def run(self, user_prompt: str, verbose: bool = True) -> str:
        """Run the autonomous agent loop with multi-turn tool calling."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        max_turns = 5
        for turn in range(max_turns):
            response = self._call_llm(messages, with_tools=True)
            choice = response["choices"][0]
            message = choice["message"]
            messages.append(message)

            tool_calls = message.get("tool_calls")
            if not tool_calls:
                # No more tools needed; return the final answer
                return message.get("content", "").strip()

            # Execute all requested tools
            for tc in tool_calls:
                fn = tc.get("function", {})
                fn_name = fn.get("name")
                call_id = tc.get("id", "call_default")
                
                try:
                    args = json.loads(fn.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}

                if verbose:
                    print(f"  -> Calling tool: {fn_name}({args})")

                # Execute Python function
                result_str = execute_tool(self.con, fn_name, args)

                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": fn_name,
                    "content": result_str,
                })

        # Final pass without tools if loop hit limit
        final = self._call_llm(messages, with_tools=False)
        return final["choices"][0]["message"].get("content", "").strip()


def _extract_location_from_text(text: str) -> str:
    """Extract location name from natural English/Nepali sentence."""
    import re
    # Patterns like "weather in Namche Bazaar", "for Lukla", "at Pokhara"
    patterns = [
        r'\b(?:in|at|for|of|near)\s+([A-Za-z\s]+?)(?:\?|\.|\!|\s*$)',
        r'([A-Za-z\s]+?)\s+(?:weather|forecast|rain|temperature)',
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            # Ignore common query words
            if candidate.lower() not in ("what", "how", "the", "current", "live"):
                return candidate
    return text.strip().rstrip("?.!")


def direct_weather_fallback(con: sqlite3.Connection, query: str) -> str:
    """Zero-LLM fallback: provides structured instant weather directly from service layer."""
    loc_query = _extract_location_from_text(query)
    result = get_current_weather(con, query=loc_query)
    if "error" in result and loc_query != query:
        result = get_current_weather(con, query=query)

    if "error" in result:
        return f"Error: {result['error']}"

    return (
        f"--- Live Weather for {result['name']} ({result['district']}, {result['province']}, {result.get('country_code', '')}) ---\n"
        f"Elevation: {result['elevation_m']} m\n"
        f"Condition: {result['condition']}\n"
        f"Temperature: {result['temperature_c']} °C\n"
        f"Humidity: {result['humidity_pct']} %\n"
        f"Precipitation: {result['precipitation_mm']} mm\n"
        f"Wind Speed: {result['wind_speed_kmh']} km/h\n"
        f"Source: {result['source']} ({result['data_kind']})\n"
        f"Recorded At: {result['valid_at']}\n"
        f"Status: {result['status']}\n"
        "Official Warning Source: your local meteorological or emergency-management authority\n"
    )

