from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TutorText:
    summary: str
    details: str
    source: str
    model: str | None


class OllamaTutor:
    def __init__(self, base_url: str, model: str | None = None, timeout: float = 35) -> None:
        self.base_url = base_url.rstrip("/")
        self.configured_model = model
        self.timeout = timeout
        self._detected_model: str | None = None
        self.last_error: str | None = None

    @property
    def model(self) -> str | None:
        return self.configured_model or self._detected_model

    def status(self) -> dict[str, Any]:
        try:
            models = self._models()
        except RuntimeError as exc:
            return {"available": False, "model": None, "reason": str(exc)}
        if self.configured_model:
            available = self.configured_model in models
            return {
                "available": available,
                "model": self.configured_model,
                "reason": None if available else "Das konfigurierte Modell ist nicht installiert.",
                "last_error": self.last_error,
            }
        preferred_models = (
            "qwen3.8:27b-mlx",
            "gemma4:31b-mlx",
            "qwen3:4b",
            "llama3.2:3b",
        )
        self._detected_model = next(
            (candidate for candidate in preferred_models if candidate in models),
            models[0] if models else None,
        )
        return {
            "available": bool(self._detected_model),
            "model": self._detected_model,
            "reason": None
            if self._detected_model
            else "In Ollama ist noch kein Modell installiert.",
            "last_error": self.last_error,
        }

    def explain(self, facts: dict[str, Any], fallback: TutorText) -> TutorText:
        if not self.model:
            self.status()
        if not self.model:
            return fallback
        grounded_facts = {
            **facts,
            "verified_feedback": {
                "summary": fallback.summary,
                "details": fallback.details,
            },
        }
        payload = {
            "model": self.model,
            "stream": False,
            "format": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "details": {"type": "string"},
                },
                "required": ["summary", "details"],
            },
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Du redigierst einen bereits verifizierten deutschen Schachkommentar für "
                        "einen Spieler mit etwa 700 Elo. Paraphrasiere nur verified_feedback. "
                        "Füge keinerlei Eröffnungsnamen, Varianten, Häufigkeiten, Züge, Zahlen, "
                        "Bewertungen oder taktische Behauptungen hinzu. Nenne überhaupt keinen "
                        "Eröffnungsnamen. Antworte als JSON mit summary und details; beide sind "
                        "Strings. "
                        "summary hat maximal 3 kurze Sätze, details maximal 5 Sätze."
                    ),
                },
                {"role": "user", "content": json.dumps(grounded_facts, ensure_ascii=False)},
            ],
            "think": False,
            "options": {"temperature": 0.2, "num_predict": 240},
        }
        try:
            body = self._request("/api/chat", payload)
            content = _parse_model_json(body["message"]["content"])
            details = content["details"]
            if isinstance(details, list):
                details = " ".join(str(item) for item in details)
            result = TutorText(
                summary=str(content["summary"]).strip(),
                details=str(details).strip(),
                source="ollama",
                model=self.model,
            )
            if not _is_grounded_rewrite(result, fallback):
                raise ValueError("Ollama added facts outside the verified draft")
            self.last_error = None
            return result
        except (RuntimeError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            return fallback

    def _models(self) -> list[str]:
        body = self._request("/api/tags")
        return [str(model["name"]) for model in body.get("models", []) if model.get("name")]

    def _request(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers={"Content-Type": "application/json"} if data else {},
            method="POST" if data else "GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.load(response)
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Ollama ist nicht erreichbar: {exc}") from exc


def _parse_model_json(raw_content: str) -> dict[str, Any]:
    content = raw_content.strip()
    start = content.find("{")
    end = content.rfind("}")
    if start < 0 or end <= start:
        raise json.JSONDecodeError("No JSON object found", content, 0)
    parsed = json.loads(content[start : end + 1])
    if not isinstance(parsed, dict):
        raise json.JSONDecodeError("Expected a JSON object", content, start)
    return parsed


def _is_grounded_rewrite(candidate: TutorText, fallback: TutorText) -> bool:
    candidate_text = f"{candidate.summary} {candidate.details}"
    fallback_text = f"{fallback.summary} {fallback.details}"
    forbidden_opening_language = re.compile(
        r"\b(gambit|verteidigung|defen[cs]e|sizilian\w*|sicilian|spanisch\w*|"
        r"italienisch\w*|caro-?kann|französisch\w*|french|najdorf|london|"
        r"königsindisch\w*|king'?s indian|eröffnung|opening|variante|variation)\b",
        re.IGNORECASE,
    )
    if forbidden_opening_language.search(candidate_text):
        return False

    number_pattern = re.compile(r"[+#−-]?\d+(?:[,.]\d+)?")
    allowed_numbers = {number.replace(".", ",") for number in number_pattern.findall(fallback_text)}
    candidate_numbers = {
        number.replace(".", ",") for number in number_pattern.findall(candidate_text)
    }
    return candidate_numbers <= allowed_numbers
