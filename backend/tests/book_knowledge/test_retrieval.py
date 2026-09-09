from pathlib import Path

import chess
from chess_coach.book_knowledge.compiler import _insert_seeds
from chess_coach.book_knowledge.retrieval import BookKnowledgeBase, NullBookKnowledgeBase
from chess_coach.book_knowledge.schema import connect_writable, initialize
from chess_coach.openings import OpeningIdentity, position_key


def _knowledge_database(path: Path) -> None:
    connection = connect_writable(path)
    initialize(connection)
    _insert_seeds(connection)
    final_board = chess.Board()
    final_board.push_san("e4")
    final_board.push_san("e5")
    connection.execute(
        """
        INSERT INTO books(
            id, sha256, title, author, publication_year, source_path,
            file_size, page_count, extraction_version, imported_at
        ) VALUES('book_test', 'hash', 'Test Book', 'Test Author', 2026,
                 '/private/library/test.pdf', 1, 20, 'test', 'now')
        """
    )
    cursor = connection.execute(
        """
        INSERT INTO chunks(
            book_id, ordinal, title, section_path, page_start, page_end,
            text, text_sha256, char_count, token_estimate, source_ref
        ) VALUES(
            'book_test', 1, 'Ruy Lopez', 'Openings > Ruy Lopez', 18, 20,
            'The main plan is pressure on the center.', 'text-hash', 40, 10,
            'book_test:p18-p20:c0001'
        )
        """
    )
    chunk_id = int(cursor.lastrowid)
    connection.execute(
        "INSERT INTO chunks_fts(chunk_id, title, section_path, text) VALUES(?, ?, ?, ?)",
        (chunk_id, "Ruy Lopez", "Openings > Ruy Lopez", "The main plan is pressure on the center."),
    )
    broad_chunk = connection.execute(
        """
        INSERT INTO chunks(
            book_id, ordinal, title, section_path, page_start, page_end,
            text, text_sha256, char_count, token_estimate, source_ref
        ) VALUES(
            'book_test', 2, 'Ruy Lopez', 'Openings > Ruy Lopez', 30, 31,
            'Bb5. A broad and unrelated plan.', 'broad-hash', 32, 8,
            'book_test:p30-p31:c0002'
        )
        """
    )
    connection.execute(
        "INSERT INTO chunks_fts(chunk_id, title, section_path, text) VALUES(?, ?, ?, ?)",
        (
            broad_chunk.lastrowid,
            "Ruy Lopez",
            "Openings > Ruy Lopez",
            "Bb5. A broad and unrelated plan.",
        ),
    )
    connection.execute(
        """
        INSERT INTO claims(
            book_id, chunk_id, page_number, claim_type, text,
            confidence, extraction_method, validation_status
        ) VALUES('book_test', ?, 30, 'plan', 'A broad and unrelated plan.',
                 0.9, 'fixture', 'source_only')
        """,
        (broad_chunk.lastrowid,),
    )
    connection.execute(
        """
        INSERT INTO claims(
            book_id, chunk_id, page_number, claim_type, text,
            confidence, extraction_method, validation_status
        ) VALUES('book_test', ?, 30, 'recommendation',
                 'Play a risky unrelated gambit.', 0.9, 'fixture', 'source_only')
        """,
        (broad_chunk.lastrowid,),
    )
    connection.execute(
        """
        INSERT INTO claims(
            book_id, chunk_id, page_number, claim_type, text,
            confidence, extraction_method, validation_status
        ) VALUES('book_test', ?, 20, 'plan', 'The plan is pressure on the center.',
                 0.9, 'fixture', 'source_only')
        """,
        (chunk_id,),
    )
    connection.execute(
        """
        INSERT INTO claims(
            book_id, chunk_id, page_number, claim_type, text,
            confidence, extraction_method, validation_status
        ) VALUES('book_test', ?, 20, 'statistic', 'This wins 75 percent.',
                 0.9, 'fixture', 'unverified')
        """,
        (chunk_id,),
    )
    line = connection.execute(
        """
        INSERT INTO book_lines(
            book_id, chunk_id, page_number, raw_text, ply_count, validation_status
        ) VALUES('book_test', ?, 20, '1. e4 e5', 2, 'valid')
        """,
        (chunk_id,),
    )
    connection.execute(
        """
        INSERT INTO book_position_evidence(
            position_key, line_id, book_id, chunk_id, page_number, ply
        ) VALUES(?, ?, 'book_test', ?, 20, 2)
        """,
        (position_key(final_board), line.lastrowid, chunk_id),
    )
    connection.commit()
    connection.close()


def test_german_alias_and_exact_position_retrieve_safe_fact(tmp_path: Path) -> None:
    database = tmp_path / "knowledge.db"
    _knowledge_database(database)
    knowledge = BookKnowledgeBase(database)
    final_board = chess.Board()
    final_board.push_san("e4")
    final_board.push_san("e5")

    evidence = knowledge.retrieve(
        question="Warum spielt man in der Spanischen Partie Bb5?",
        board=final_board,
        opening=OpeningIdentity("C60", "Ruy Lopez"),
        focus_move=chess.Move.from_uci("g1f3"),
    )

    assert evidence.facts
    assert len(evidence.facts) == 1
    assert evidence.facts[0].match_kind == "position"
    assert "75" not in evidence.facts[0].text
    reference = evidence.public_references()[0]
    assert reference["pdf_page_start"] == 18
    assert "source_path" not in reference
    assert "/private/" not in str(reference)


def test_focused_move_can_match_the_exact_resulting_position(tmp_path: Path) -> None:
    database = tmp_path / "knowledge.db"
    _knowledge_database(database)
    knowledge = BookKnowledgeBase(database)
    board = chess.Board()
    board.push_san("e4")

    evidence = knowledge.retrieve(
        question="Warum ist e5 sinnvoll?",
        board=board,
        opening=OpeningIdentity("C20", "Ruy Lopez"),
        focus_move=chess.Move.from_uci("e7e5"),
    )

    assert len(evidence.facts) == 1
    assert evidence.facts[0].match_kind == "position_after_move"


def test_missing_database_uses_an_empty_degraded_provider(tmp_path: Path) -> None:
    knowledge = BookKnowledgeBase(tmp_path / "missing.db")

    assert knowledge.status()["available"] is False
    evidence = knowledge.retrieve(
        question="Warum?",
        board=chess.Board(),
        opening=None,
        focus_move=None,
    )
    assert evidence.facts == ()
    assert evidence.reason

    null = NullBookKnowledgeBase()
    assert null.status()["available"] is False


def test_unidentified_position_does_not_use_ambiguous_san_only_book_matches(
    tmp_path: Path,
) -> None:
    database = tmp_path / "knowledge.db"
    _knowledge_database(database)
    knowledge = BookKnowledgeBase(database)

    evidence = knowledge.retrieve(
        question="Warum ist e4 gut?",
        board=chess.Board(),
        opening=None,
        focus_move=chess.Move.from_uci("e2e4"),
    )

    assert evidence.facts == ()


def test_broad_move_match_does_not_admit_variation_specific_recommendation(
    tmp_path: Path,
) -> None:
    database = tmp_path / "knowledge.db"
    _knowledge_database(database)
    knowledge = BookKnowledgeBase(database)
    board = chess.Board()
    for san in ("e4", "e5", "Nf3", "Nc6"):
        board.push_san(san)

    evidence = knowledge.retrieve(
        question="Warum ist Bb5 gut?",
        board=board,
        opening=OpeningIdentity("C60", "Ruy Lopez"),
        focus_move=board.parse_san("Bb5"),
    )

    assert evidence.facts
    assert {fact.claim_type for fact in evidence.facts} == {"plan"}
    assert all("risky unrelated gambit" not in fact.text for fact in evidence.facts)
