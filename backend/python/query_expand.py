"""
Query expansion using Ollama LLM.
Expands vague user queries into multiple specific search queries + hints.
Falls back gracefully if Ollama is unavailable.
"""

import json
import urllib.request
import urllib.error

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_TIMEOUT = 15  # seconds
DEFAULT_MODEL = "llama3.2:3b"

EXPANSION_PROMPT = """You are a search query expander. Given a user's search query, generate 3-5 specific search queries that would help find the document they're looking for. Also extract any hints about file types, people, projects, or topics.

Respond ONLY with valid JSON in this exact format:
{{"queries": ["query1", "query2", "query3"], "hints": {{"people": [], "topics": [], "file_types": [], "projects": []}}}}

User query: "{query}"

JSON response:"""


def expand_query(query, model=None):
    """
    Expand a user query using Ollama LLM.

    Returns:
        dict with keys:
            - queries: list of expanded query strings
            - hints: dict with people, topics, file_types, projects
            - used_llm: bool indicating if LLM was used
    """
    fallback = {
        "queries": [query],
        "hints": {"people": [], "topics": [], "file_types": [], "projects": []},
        "used_llm": False,
    }

    try:
        payload = json.dumps({
            "model": model or DEFAULT_MODEL,
            "prompt": EXPANSION_PROMPT.format(query=query),
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": 256,
            },
        }).encode("utf-8")

        req = urllib.request.Request(
            OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8"))

        raw = body.get("response", "")

        # Extract JSON from the response
        parsed = _extract_json(raw)
        if parsed and "queries" in parsed:
            # Always include the original query
            queries = parsed["queries"]
            if query not in queries:
                queries.insert(0, query)

            hints = parsed.get("hints", fallback["hints"])
            # Ensure all hint keys exist
            for key in ("people", "topics", "file_types", "projects"):
                if key not in hints:
                    hints[key] = []

            return {
                "queries": queries,
                "hints": hints,
                "used_llm": True,
            }

    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        pass  # Ollama not running or unreachable
    except Exception:
        pass  # Any other parsing error

    return fallback


def check_ollama_status():
    """
    Check if Ollama is running and return available models.

    Returns:
        dict with keys:
            - running: bool
            - models: list of model name strings
    """
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            models = [m["name"] for m in body.get("models", [])]
            return {"running": True, "models": models}
    except Exception:
        return {"running": False, "models": []}


def _extract_json(text):
    """Try to extract a JSON object from LLM response text."""
    # Try direct parse first
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find JSON between braces
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

    return None
