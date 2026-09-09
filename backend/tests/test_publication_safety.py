import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check_publication_safety.py"
SPEC = importlib.util.spec_from_file_location("publication_safety_script", SCRIPT_PATH)
assert SPEC and SPEC.loader
publication_safety = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = publication_safety
SPEC.loader.exec_module(publication_safety)

build_book_fingerprints = publication_safety.build_book_fingerprints
path_violation = publication_safety.path_violation
text_overlap_source = publication_safety.text_overlap_source


def test_private_book_artifacts_are_blocked_but_registry_is_allowed() -> None:
    assert path_violation("data/books/README.md") is None
    assert path_violation("data/books/owned.pdf") is not None
    assert path_violation("data/book_knowledge.db") is not None
    assert path_violation("docs/source.epub") is not None
    assert path_violation("backend/chess_coach/service.py") is None


def test_long_verbatim_book_overlap_is_detected_without_storing_plaintext() -> None:
    source = " ".join(f"sourceword{index}" for index in range(30))
    fingerprints = build_book_fingerprints([("book_test:p1:c0001", source)], width=24)

    assert text_overlap_source(f"prefix {source} suffix", fingerprints, width=24) == (
        "book_test:p1:c0001"
    )
    assert text_overlap_source(" ".join(source.split()[:23]), fingerprints, width=24) is None
