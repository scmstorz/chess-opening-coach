from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_public_readme_contains_complete_local_quickstart() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    required_instructions = (
        "git clone https://github.com/scmstorz/chess-opening-coach.git",
        "uv sync --extra dev",
        "npm ci",
        "npm run coach",
        "http://localhost:53687/",
    )

    assert all(instruction in readme for instruction in required_instructions)


def test_public_readme_documents_platform_and_degraded_modes() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    required_topics = (
        "### macOS with Apple Silicon",
        "### Linux",
        "### Windows",
        "WSL 2",
        "qwen3:4b",
        "## Optional components",
        "Private chess books",
        "Ollama and Stockfish",
        "## Startup checks and troubleshooting",
    )

    assert all(topic in readme for topic in required_topics)
