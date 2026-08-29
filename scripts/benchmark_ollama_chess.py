from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any

from chess_coach.tutor import OllamaTutor, TutorText, _parse_model_json


@dataclass(frozen=True, slots=True)
class OpeningCase:
    case_id: str
    moves: str
    accepted_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ConceptCase:
    case_id: str
    question: str
    choices: tuple[str, str, str]
    correct_choice: str


CASES = (
    OpeningCase("modern", "1. e4 g6", ("modern defense", "moderne verteidigung")),
    OpeningCase(
        "ruy_lopez",
        "1. e4 e5 2. Nf3 Nc6 3. Bb5",
        ("ruy lopez", "spanish game", "spanische partie"),
    ),
    OpeningCase(
        "queens_gambit",
        "1. d4 d5 2. c4",
        ("queen's gambit", "damengambit", "damen-gambit"),
    ),
    OpeningCase(
        "najdorf",
        "1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6",
        ("najdorf",),
    ),
    OpeningCase(
        "kings_indian",
        "1. d4 Nf6 2. c4 g6 3. Nc3 Bg7 4. e4 d6",
        ("king's indian", "königsindisch"),
    ),
    OpeningCase(
        "french_advance",
        "1. e4 e6 2. d4 d5 3. e5 c5",
        ("french defense", "french advance", "französisch", "vorstoßvariante"),
    ),
)

CONCEPT_CASES = (
    ConceptCase(
        "modern_g6",
        "Was ist nach 1. e4 g6 die zentrale Idee von ...g6?",
        (
            "A: ...Bg7 vorbereiten und das Zentrum zunächst aus der Distanz bekämpfen",
            "B: den Bauern e4 sofort angreifen",
            "C: die Dame früh nach g5 entwickeln",
        ),
        "A",
    ),
    ConceptCase(
        "ruy_bishop",
        "Was bewirkt 3. Bb5 in 1. e4 e5 2. Nf3 Nc6 3. Bb5 am genauesten?",
        (
            "A: Der Springer c6 ist absolut an den König gefesselt",
            "B: Der Läufer setzt den Verteidiger des Bauern e5 unter Druck",
            "C: Weiß gewinnt den Springer c6 erzwungen",
        ),
        "B",
    ),
    ConceptCase(
        "queens_gambit_c4",
        "Was ist der Hauptzweck von 2. c4 nach 1. d4 d5?",
        (
            "A: die Dame über die c-Linie entwickeln",
            "B: den schwarzen Zentralbauern d5 herausfordern",
            "C: sofort am Königsflügel angreifen",
        ),
        "B",
    ),
    ConceptCase(
        "najdorf_a6",
        "Was leistet ...a6 in der Najdorf-Variante typischerweise?",
        (
            "A: Es kontrolliert c4 und bereitet ...a5 vor",
            "B: Es kontrolliert b5 und bereitet häufig ...b5 vor",
            "C: Es greift den weißen Bauern e4 direkt an",
        ),
        "B",
    ),
    ConceptCase(
        "kings_indian_breaks",
        "Welche zentralen Bauernhebel sind für Schwarz im Königsinder typisch?",
        ("A: ...e5 oder ...c5", "B: ...e4 oder ...c4", "C: ...a5 oder ...h5"),
        "A",
    ),
    ConceptCase(
        "french_c5",
        "Welchen weißen Zentralbauern greift ...c5 in der Französischen Vorstoßvariante an?",
        ("A: d4", "B: e5", "C: c2"),
        "A",
    ),
    ConceptCase(
        "false_premise",
        "Ein Schüler nennt 1. e4 g6 ein Königsgambit. Wie reagierst du?",
        (
            "A: Das stimmt; ...g6 ist eine seltene Königsgambit-Variante",
            "B: Das stimmt nicht; die Zugfolge beginnt die Moderne Verteidigung",
            "C: Das stimmt nicht; diese Stellung ist zwingend die Pirc-Verteidigung",
        ),
        "B",
    ),
)


def request(base_url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    raw = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/chat",
        data=raw,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def normalize_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", without_marks).strip()


def benchmark_knowledge(base_url: str, model: str, timeout: float) -> dict[str, Any]:
    positions = [{"id": case.case_id, "moves": case.moves} for case in CASES]
    payload = {
        "model": model,
        "stream": False,
        "think": False,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Du beantwortest einen reproduzierbaren Schachwissenstest. "
                    "Identifiziere jede Eröffnung so präzise wie durch die Zugfolge möglich. "
                    "Nenne außerdem eine zentrale strategische Idee in genau einem kurzen "
                    "deutschen Satz. Erfinde keine Statistik und keine Engine-Bewertung. "
                    "Antworte ausschließlich als JSON-Objekt in der Form "
                    '{"answers":[{"id":"...","opening":"...","key_idea":"..."}]}. '
                    "Liefere für jede Eingabe genau ein Objekt und behalte ihre id bei."
                ),
            },
            {"role": "user", "content": json.dumps(positions, ensure_ascii=False)},
        ],
        "options": {"temperature": 0, "num_predict": 1800},
        "keep_alive": "10m",
    }
    started = time.perf_counter()
    body = request(base_url, payload, timeout)
    wall_seconds = time.perf_counter() - started
    raw_content = body["message"]["content"]
    parse_error = None
    try:
        parsed = _parse_model_json(raw_content)
        answers = parsed["answers"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        parse_error = f"{type(exc).__name__}: {exc}"
        answers = []
    by_id = {answer["id"]: answer for answer in answers}
    scored: list[dict[str, Any]] = []
    for case in CASES:
        answer = by_id.get(case.case_id, {})
        opening = str(answer.get("opening", ""))
        normalized = normalize_name(opening)
        correct = any(normalize_name(name) in normalized for name in case.accepted_names)
        scored.append(
            {
                "id": case.case_id,
                "correct": correct,
                "opening": opening,
                "key_idea": answer.get("key_idea", ""),
            }
        )
    return {
        "correct": sum(item["correct"] for item in scored),
        "total": len(CASES),
        "wall_seconds": round(wall_seconds, 2),
        "load_seconds": round(body.get("load_duration", 0) / 1_000_000_000, 2),
        "prompt_tokens": body.get("prompt_eval_count"),
        "output_tokens": body.get("eval_count"),
        "json_valid": parse_error is None,
        "parse_error": parse_error,
        "answers": scored,
    }


def benchmark_concepts(base_url: str, model: str, timeout: float) -> dict[str, Any]:
    questions = [
        {"id": case.case_id, "question": case.question, "choices": case.choices}
        for case in CONCEPT_CASES
    ]
    payload = {
        "model": model,
        "stream": False,
        "think": False,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Du beantwortest einen reproduzierbaren Multiple-Choice-Test zu "
                    "Schacheröffnungen. Wähle für jede Frage genau A, B oder C und begründe "
                    "die Wahl in einem kurzen deutschen Satz. Antworte ausschließlich als "
                    "JSON-Objekt in der Form "
                    '{"answers":[{"id":"...","choice":"A","reason":"..."}]}. '
                    "Liefere für jede Eingabe genau ein Objekt und behalte ihre id bei."
                ),
            },
            {"role": "user", "content": json.dumps(questions, ensure_ascii=False)},
        ],
        "options": {"temperature": 0, "num_predict": 2200},
        "keep_alive": "10m",
    }
    started = time.perf_counter()
    body = request(base_url, payload, timeout)
    wall_seconds = time.perf_counter() - started
    raw_content = body["message"]["content"]
    parse_error = None
    try:
        parsed = _parse_model_json(raw_content)
        answers = parsed["answers"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        parse_error = f"{type(exc).__name__}: {exc}"
        answers = [
            {"id": case_id, "choice": choice, "reason": ""}
            for case_id, choice in re.findall(
                r'"id"\s*:\s*"([^"]+)".*?"choice"\s*:\s*"([ABC])"',
                raw_content,
                re.DOTALL,
            )
        ]
    by_id = {answer["id"]: answer for answer in answers}
    scored: list[dict[str, Any]] = []
    for case in CONCEPT_CASES:
        answer = by_id.get(case.case_id, {})
        choice = str(answer.get("choice", "")).strip().upper()
        scored.append(
            {
                "id": case.case_id,
                "correct": choice == case.correct_choice,
                "choice": choice,
                "reason": answer.get("reason", ""),
            }
        )
    return {
        "correct": sum(item["correct"] for item in scored),
        "total": len(CONCEPT_CASES),
        "wall_seconds": round(wall_seconds, 2),
        "load_seconds": round(body.get("load_duration", 0) / 1_000_000_000, 2),
        "prompt_tokens": body.get("prompt_eval_count"),
        "output_tokens": body.get("eval_count"),
        "json_valid": parse_error is None,
        "parse_error": parse_error,
        "answers": scored,
    }


def benchmark_grounding(base_url: str, model: str, timeout: float) -> dict[str, Any]:
    tutor = OllamaTutor(base_url, model, timeout=timeout)
    fallback = TutorText(
        summary="Ich spiele g6. Der Zug führt Modern Defense solide weiter.",
        details=(
            "Der Bauernzug bereitet die Entwicklung des Läufers auf der langen Diagonale vor. "
            "Stockfish bewertet die entstehende Stellung mit +0,17. "
            "Der beste Engine-Zug ist e5."
        ),
        source="deterministic",
        model=None,
    )
    facts = {
        "task": "Erkläre den gerade gespielten Eröffnungszug.",
        "fen": "rnbqkbnr/pppppp1p/6p1/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
        "move": "g6",
        "actor": "coach",
        "opening": {"eco": "B06", "name": "Modern Defense"},
        "theory_match": True,
        "engine": {"best_move_san": "e5", "loss_pawns": 0.17},
    }
    started = time.perf_counter()
    result = tutor.explain(facts, fallback)
    return {
        "accepted": result.source == "ollama",
        "wall_seconds": round(time.perf_counter() - started, 2),
        "last_error": tutor.last_error,
        "result": asdict(result),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare local Ollama models for the coach.")
    parser.add_argument("models", nargs="+", help="Installed Ollama model names")
    parser.add_argument("--url", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()

    results: list[dict[str, Any]] = []
    for model in args.models:
        print(f"Benchmarking {model}...", flush=True)
        result: dict[str, Any] = {"model": model}
        for name, benchmark in (
            ("knowledge", benchmark_knowledge),
            ("concepts", benchmark_concepts),
            ("grounded_rewrite", benchmark_grounding),
        ):
            try:
                result[name] = benchmark(args.url, model, args.timeout)
            except Exception as exc:  # noqa: BLE001 - preserve per-stage failures
                result[name] = {"error": f"{type(exc).__name__}: {exc}"}
        results.append(result)
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)

    print("\nCOMBINED_RESULT")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
