#!/usr/bin/env python3
"""Compare cloud tutors on verified Stockfish evidence without storing credentials."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict
from pathlib import Path
from typing import Any

import chess
from chess_coach.engine import StockfishService

CASES = (
    {
        "id": "a4_flexible_prophylaxis",
        "fen": "r1bqk2r/pp2bppp/2np1n2/2p1p3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w kq - 2 7",
        "focus_uci": "a2a4",
        "question": "Warum ist a4 mittel- und langfristig nützlich?",
    },
    {
        "id": "nd5_central_exchange",
        "fen": "r1bqk2r/pp2bpp1/2np1n1p/2p1p3/P1B1P3/2NP1N2/1PP2PPP/R1BQ1RK1 w kq - 0 8",
        "focus_uci": "c3d5",
        "question": "Was nützt Nd5 mittel- und langfristig?",
    },
    {
        "id": "ra6_premise_check",
        "fen": "r2q1r2/1p4pk/3p1b1p/p3p3/Pn2P3/1Q1P1N2/5PPP/R1B2RK1 b - - 2 16",
        "focus_uci": "a8a6",
        "question": "Warum soll Ra6 hier der beste Zug sein?",
    },
)

PROVIDERS = {
    "kimi": {
        "key": "KIMI_API_KEY",
        "models_url": "https://api.moonshot.ai/v1/models",
        "chat_url": "https://api.moonshot.ai/v1/chat/completions",
        "preferred": ("kimi-k3", "kimi-k2.6", "kimi-k2.7-code-highspeed"),
        "temperature": 0.6,
        "thinking": {"type": "disabled"},
    },
    "deepseek": {
        "key": "DEEPSEEK_API_KEY",
        "models_url": "https://api.deepseek.com/models",
        "chat_url": "https://api.deepseek.com/chat/completions",
        "preferred": ("deepseek-v4-pro", "deepseek-v4-flash"),
        "temperature": 0.1,
        "thinking": {"type": "disabled"},
    },
}


def load_env(path: Path) -> None:
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def request_json(
    url: str, api_key: str, payload: dict[str, Any] | None = None, timeout: float = 90
) -> dict[str, Any]:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST" if data else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        raise RuntimeError(f"HTTP {exc.code} from {url}: {detail}") from exc


def choose_model(provider: dict[str, Any], api_key: str) -> tuple[str, list[str]]:
    result = request_json(provider["models_url"], api_key, timeout=30)
    models = [str(item["id"]) for item in result.get("data", []) if item.get("id")]
    for preferred in provider["preferred"]:
        if preferred in models:
            return preferred, models
    usable = [
        model
        for model in models
        if not any(term in model.lower() for term in ("embed", "rerank"))
    ]
    if not usable:
        raise RuntimeError("Provider returned no usable chat model")
    return usable[0], models


def build_evidence(engine: StockfishService, case: dict[str, str]) -> dict[str, Any]:
    board = chess.Board(case["fen"])
    focus = chess.Move.from_uci(case["focus_uci"])
    comparison = engine.compare_moves(board, count=4, focus_move=focus, deep=True)
    if not comparison.available:
        raise RuntimeError(comparison.reason or "Stockfish comparison failed")
    return {
        **case,
        "focus_san": board.san(focus),
        "side_to_move": "white" if board.turn == chess.WHITE else "black",
        "score_convention": "positive values favor White; negative values favor Black",
        "engine_comparison": asdict(comparison),
    }


def prompt_for(evidence: dict[str, Any]) -> list[dict[str, str]]:
    system = (
        "Du bist ein geduldiger deutscher Schachtrainer für einen Spieler mit etwa 700 Elo. "
        "Erkläre den mittel- und langfristigen Nutzen des focus_move, nicht bloß seine legalen "
        "Angriffsfelder. Nutze ausschließlich die FEN-Stellung und die gelieferten Stockfish-"
        "Varianten als Belege. Stockfish liefert Varianten und Bewertungen, aber keine Gründe: "
        "Kennzeichne strategische Deutungen deshalb als aus den Varianten abgeleitete Erklärung. "
        "Wenn der Zug nicht stabil der beste Kandidat ist, korrigiere die Prämisse ausdrücklich. "
        "Nenne keine triviale Bauernregel. Gib zuerst 3 bis 5 verständliche Sätze, danach einen "
        "kurzen Merksatz. Vermeide lange Variantenlisten und erfundene Gewissheit."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(evidence, ensure_ascii=False)},
    ]


def benchmark_provider(
    name: str, provider: dict[str, Any], evidence_cases: list[dict[str, Any]]
) -> dict[str, Any]:
    api_key = os.environ.get(provider["key"], "").strip()
    if not api_key:
        return {"provider": name, "error": f"{provider['key']} is not configured"}
    model, models = choose_model(provider, api_key)
    results = []
    for evidence in evidence_cases:
        started = time.monotonic()
        body = request_json(
            provider["chat_url"],
            api_key,
            {
                "model": model,
                "messages": prompt_for(evidence),
                "temperature": provider["temperature"],
                "thinking": provider["thinking"],
                "max_tokens": 800,
            },
        )
        results.append(
            {
                "case": evidence["id"],
                "seconds": round(time.monotonic() - started, 2),
                "answer": body["choices"][0]["message"]["content"],
                "usage": body.get("usage"),
            }
        )
    return {
        "provider": name,
        "model": model,
        "available_models": models,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--provider", choices=tuple(PROVIDERS), action="append")
    args = parser.parse_args()
    load_env(args.env_file)

    engine = StockfishService(explanation_time_seconds=0.8, deep_time_seconds=5.0)
    try:
        evidence_cases = [build_evidence(engine, case) for case in CASES]
    finally:
        engine.close()

    selected = args.provider or list(PROVIDERS)
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "stockfish_deep_seconds": 5.0,
        "cases": evidence_cases,
        "providers": [
            benchmark_provider(name, PROVIDERS[name], evidence_cases) for name in selected
        ],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
