"use client";

import { type CSSProperties, useEffect, useMemo, useState } from "react";

type Piece = {
  color: "white" | "black";
  kind: "king" | "queen" | "rook" | "bishop" | "knight" | "pawn";
};

type PlayerColor = "white" | "black" | "random";

type EngineInfo = {
  available: boolean;
  evaluation_played: number | null;
  mate_played: number | null;
  loss_pawns: number | null;
  classification: string;
};

type CoachMessage = {
  actor: "learner" | "coach";
  move: string | null;
  summary: string;
  details: string;
  source: string;
  model: string | null;
  attempt: number | null;
  engine: EngineInfo | null;
  move_uci?: string;
  fen_after?: string;
};

type MoveAnimation = {
  from: string;
  to: string;
  piece: Piece;
};

type SessionState = {
  session_id: string;
  fen: string;
  learner_color: "white" | "black";
  turn: "white" | "black";
  opening: { eco: string; name: string } | null;
  legal_moves: string[];
  move_history: { actor: "learner" | "coach"; san: string }[];
  messages: CoachMessage[];
  correction: {
    active: boolean;
    attempt: number;
    remaining: number;
    solution_revealed: boolean;
    recommended_move: string | null;
  } | null;
  game_over: boolean;
};

type Health = {
  status: string;
  openings: { source: string; entries: number };
  stockfish: { available: boolean; name: string | null };
  ollama: { available: boolean; model: string | null; reason: string | null };
};

const files = ["a", "b", "c", "d", "e", "f", "g", "h"];
const initialFen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const symbols: Record<Piece["color"], Record<Piece["kind"], string>> = {
  white: { king: "♚", queen: "♛", rook: "♜", bishop: "♝", knight: "♞", pawn: "♟" },
  black: { king: "♚", queen: "♛", rook: "♜", bishop: "♝", knight: "♞", pawn: "♟" },
};
const pieceKinds: Record<string, Piece["kind"]> = {
  k: "king",
  q: "queen",
  r: "rook",
  b: "bishop",
  n: "knight",
  p: "pawn",
};
const fenPieces: Record<Piece["kind"], string> = {
  king: "k",
  queen: "q",
  rook: "r",
  bishop: "b",
  knight: "n",
  pawn: "p",
};

function parseFen(fen: string): Record<string, Piece> {
  const result: Record<string, Piece> = {};
  fen.split(" ")[0].split("/").forEach((rankData, rankIndex) => {
    let fileIndex = 0;
    for (const character of rankData) {
      if (/\d/.test(character)) {
        fileIndex += Number(character);
        continue;
      }
      const color = character === character.toUpperCase() ? "white" : "black";
      result[`${files[fileIndex]}${8 - rankIndex}`] = {
        color,
        kind: pieceKinds[character.toLowerCase()],
      };
      fileIndex += 1;
    }
  });
  return result;
}

function visualFenAfterMove(fen: string, moveUci: string): string {
  const position = { ...parseFen(fen) };
  const from = moveUci.slice(0, 2);
  const to = moveUci.slice(2, 4);
  const promotion = moveUci[4];
  const piece = position[from];
  if (!piece) return fen;

  delete position[from];
  if (piece.kind === "pawn" && from[0] !== to[0] && !position[to]) {
    delete position[`${to[0]}${from[1]}`];
  }
  if (piece.kind === "king" && Math.abs(files.indexOf(from[0]) - files.indexOf(to[0])) === 2) {
    const kingside = to[0] === "g";
    const rookFrom = `${kingside ? "h" : "a"}${from[1]}`;
    const rookTo = `${kingside ? "f" : "d"}${from[1]}`;
    if (position[rookFrom]) {
      position[rookTo] = position[rookFrom];
      delete position[rookFrom];
    }
  }
  position[to] = {
    ...piece,
    kind: promotion ? pieceKinds[promotion] : piece.kind,
  };

  const ranks = Array.from({ length: 8 }, (_, index) => 8 - index);
  const boardFen = ranks.map((rank) => {
    let empty = 0;
    let row = "";
    for (const file of files) {
      const occupant = position[`${file}${rank}`];
      if (!occupant) {
        empty += 1;
        continue;
      }
      if (empty) row += String(empty);
      const symbol = fenPieces[occupant.kind];
      row += occupant.color === "white" ? symbol.toUpperCase() : symbol;
      empty = 0;
    }
    if (empty) row += String(empty);
    return row;
  }).join("/");
  const fields = fen.split(" ");
  fields[0] = boardFen;
  fields[1] = fields[1] === "w" ? "b" : "w";
  return fields.join(" ");
}

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: "Unbekannter Fehler" }));
    throw new Error(body.detail || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

function wait(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

export default function Home() {
  const [requestedColor, setRequestedColor] = useState<PlayerColor>("white");
  const [session, setSession] = useState<SessionState | null>(null);
  const [messages, setMessages] = useState<CoachMessage[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [selectedSquare, setSelectedSquare] = useState<string | null>(null);
  const [draggedFrom, setDraggedFrom] = useState<string | null>(null);
  const [displayFen, setDisplayFen] = useState(initialFen);
  const [moveAnimation, setMoveAnimation] = useState<MoveAnimation | null>(null);
  const [animatingSequence, setAnimatingSequence] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Health>("/api/health").then(setHealth).catch(() => setHealth(null));
  }, []);

  const orientation = session?.learner_color ?? (requestedColor === "black" ? "black" : "white");
  const position = parseFen(displayFen);
  const orientedSquares = useMemo(() => {
    const ranks = orientation === "black" ? [1, 2, 3, 4, 5, 6, 7, 8] : [8, 7, 6, 5, 4, 3, 2, 1];
    const orientedFiles = orientation === "black" ? [...files].reverse() : files;
    return ranks.flatMap((rank) => orientedFiles.map((file) => `${file}${rank}`));
  }, [orientation]);

  const moveAnimationStyle = useMemo(() => {
    if (!moveAnimation) return undefined;
    const fromIndex = orientedSquares.indexOf(moveAnimation.from);
    const toIndex = orientedSquares.indexOf(moveAnimation.to);
    if (fromIndex < 0 || toIndex < 0) return undefined;
    const fromColumn = fromIndex % 8;
    const fromRow = Math.floor(fromIndex / 8);
    const toColumn = toIndex % 8;
    const toRow = Math.floor(toIndex / 8);
    return {
      "--move-x": `${(toColumn - fromColumn) * 100}%`,
      "--move-y": `${(toRow - fromRow) * 100}%`,
      height: "12.5%",
      left: `${fromColumn * 12.5}%`,
      top: `${fromRow * 12.5}%`,
      width: "12.5%",
    } as CSSProperties;
  }, [moveAnimation, orientedSquares]);

  const legalTargets = useMemo(() => {
    if (!selectedSquare || !session) return new Set<string>();
    return new Set(
      session.legal_moves
        .filter((move) => move.startsWith(selectedSquare))
        .map((move) => move.slice(2, 4)),
    );
  }, [selectedSquare, session]);

  const latestEngine = [...messages].reverse().find((message) => message.engine?.available)?.engine;
  const evaluation = latestEngine?.evaluation_played ?? 0;
  const evaluationWidth = Math.max(6, Math.min(94, 50 + evaluation * 8));

  async function animateMoves(
    startFen: string,
    nextMessages: CoachMessage[],
    finalFen: string,
    learnerMoveToSkip?: string,
  ) {
    const transitions = nextMessages.filter(
      (message): message is CoachMessage & { move_uci: string; fen_after: string } =>
        Boolean(
          message.move_uci
          && message.fen_after
          && !(message.actor === "learner" && message.move_uci === learnerMoveToSkip),
        ),
    );
    if (transitions.length === 0) {
      setDisplayFen(finalFen);
      return;
    }

    setAnimatingSequence(true);
    let currentFen = startFen;
    setDisplayFen(currentFen);
    for (const transition of transitions) {
      const from = transition.move_uci.slice(0, 2);
      const to = transition.move_uci.slice(2, 4);
      const piece = parseFen(currentFen)[from];
      if (piece) {
        setMoveAnimation({ from, to, piece });
        await wait(520);
      }
      currentFen = transition.fen_after;
      setDisplayFen(currentFen);
      setMoveAnimation(null);
      await wait(120);
    }
    setDisplayFen(finalFen);
    setAnimatingSequence(false);
  }

  async function startSession() {
    setLoading(true);
    setError(null);
    setDisplayFen(initialFen);
    setMoveAnimation(null);
    try {
      const next = await api<SessionState>("/api/sessions", {
        method: "POST",
        body: JSON.stringify({ color: requestedColor }),
      });
      setSession(next);
      setMessages(next.messages);
      setSelectedSquare(null);
      await animateMoves(initialFen, next.messages, next.fen);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Der lokale Coach ist nicht erreichbar.");
      setAnimatingSequence(false);
    } finally {
      setLoading(false);
    }
  }

  async function submitMove(from: string, to: string) {
    if (!session || loading || session.turn !== session.learner_color) return;
    const fenBefore = displayFen;
    const matchingMove = session.legal_moves.find((move) => move.startsWith(`${from}${to}`));
    const optimisticFen = matchingMove ? visualFenAfterMove(fenBefore, matchingMove) : fenBefore;
    if (matchingMove) setDisplayFen(optimisticFen);
    setLoading(true);
    setError(null);
    try {
      const next = await api<SessionState>(`/api/sessions/${session.session_id}/moves`, {
        method: "POST",
        body: JSON.stringify({
          from_square: from,
          to_square: to,
          promotion: matchingMove?.length === 5 ? matchingMove[4] : undefined,
        }),
      });
      setSession(next);
      setMessages((current) => [...current, ...next.messages]);
      const learnerMoveWasAccepted = next.messages.some(
        (message) => message.actor === "learner" && message.move_uci === matchingMove,
      );
      await animateMoves(
        learnerMoveWasAccepted ? optimisticFen : fenBefore,
        next.messages,
        next.fen,
        learnerMoveWasAccepted ? matchingMove : undefined,
      );
    } catch (caught) {
      setDisplayFen(fenBefore);
      setError(caught instanceof Error ? caught.message : "Der Zug konnte nicht geprüft werden.");
      setAnimatingSequence(false);
    } finally {
      setSelectedSquare(null);
      setDraggedFrom(null);
      setLoading(false);
    }
  }

  function selectOrMove(square: string) {
    if (!session || loading) return;
    const piece = position[square];
    if (selectedSquare && legalTargets.has(square)) {
      void submitMove(selectedSquare, square);
      return;
    }
    if (piece?.color === session.learner_color && session.turn === session.learner_color) {
      setSelectedSquare(square === selectedSquare ? null : square);
    } else {
      setSelectedSquare(null);
    }
  }

  function scoreLabel() {
    if (latestEngine?.mate_played) {
      return `#${Math.abs(latestEngine.mate_played)}`;
    }
    return `${evaluation >= 0 ? "+" : ""}${evaluation.toFixed(2)}`.replace(".", ",");
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="Chess Opening Coach Startseite">
          <span className="brand-mark" aria-hidden="true">♞</span>
          <span><strong>Chess Opening Coach</strong><small>Verstehen statt auswendig lernen</small></span>
        </a>
        <div className={health ? "local-status" : "local-status offline"}>
          <span className="status-dot" aria-hidden="true" />
          {health ? "Lokal verbunden" : "Coach nicht verbunden"}
        </div>
      </header>

      <section className="workspace" id="top">
        <div className="board-column">
          <div className="session-toolbar">
            <div>
              <p className="eyebrow">Freies Eröffnungsspiel</p>
              <h1>Deine ersten Züge. Mit Plan.</h1>
            </div>
            <div className="color-picker" aria-label="Farbe wählen">
              {(["white", "black", "random"] as PlayerColor[]).map((color) => (
                <button
                  className={requestedColor === color ? "color-option active" : "color-option"}
                  key={color}
                  onClick={() => setRequestedColor(color)}
                  type="button"
                >
                  {color === "white" ? "Weiß" : color === "black" ? "Schwarz" : "Zufällig"}
                </button>
              ))}
            </div>
          </div>

          <div className="board-stage">
            <div className="evaluation" aria-label={`Stockfish-Bewertung: ${scoreLabel()}`}>
              <div className="evaluation-labels"><span>Schwarz</span><strong>{scoreLabel()}</strong><span>Weiß</span></div>
              <div className="evaluation-track"><span style={{ width: `${evaluationWidth}%` }} /></div>
              <p className="evaluation-help">+ bedeutet Vorteil für Weiß · − bedeutet Vorteil für Schwarz</p>
            </div>

            <div className={`board-frame${loading && !animatingSequence ? " thinking" : ""}${session ? "" : " inactive"}`}>
              <div className="chessboard" aria-disabled={!session} aria-label="Interaktives Schachbrett">
                {orientedSquares.map((square, index) => {
                  const piece = position[square];
                  const file = square[0];
                  const rank = square[1];
                  const isLight = (files.indexOf(file) + Number(rank)) % 2 === 1;
                  const canDrag = Boolean(
                    session && piece?.color === session.learner_color && session.turn === session.learner_color,
                  );
                  return (
                    <button
                      aria-label={`${square}${piece ? `, ${piece.color} ${piece.kind}` : ""}`}
                      className={`square ${isLight ? "light" : "dark"} ${selectedSquare === square ? "selected" : ""} ${legalTargets.has(square) ? "legal-target" : ""}`}
                      key={square}
                      onClick={() => selectOrMove(square)}
                      onDragOver={(event) => event.preventDefault()}
                      onDrop={() => draggedFrom && void submitMove(draggedFrom, square)}
                      type="button"
                    >
                      {index % 8 === 0 && <span className="rank-label">{rank}</span>}
                      {index >= 56 && <span className="file-label">{file}</span>}
                      {piece && moveAnimation?.from !== square && (
                        <span
                          className={`piece ${piece.color}`}
                          draggable={canDrag}
                          onDragStart={() => canDrag && setDraggedFrom(square)}
                          role="img"
                          aria-label={`${piece.color} ${piece.kind}`}
                        >
                          {symbols[piece.color][piece.kind]}
                        </span>
                      )}
                    </button>
                  );
                })}
                {moveAnimation && moveAnimationStyle && (
                  <span aria-hidden="true" className="moving-piece" style={moveAnimationStyle}>
                    <span className={`piece ${moveAnimation.piece.color}`}>
                      {symbols[moveAnimation.piece.color][moveAnimation.piece.kind]}
                    </span>
                  </span>
                )}
              </div>
              {!session && !loading && (
                <div className="board-start-overlay">
                  <strong>Das Brett ist noch nicht aktiv</strong>
                  <span>Wähle deine Farbe und starte dann das Training.</span>
                  <button onClick={() => void startSession()} type="button">Training starten</button>
                </div>
              )}
              {loading && !animatingSequence && <div className="board-loader">Coach denkt nach …</div>}
            </div>

            <div className="board-footer">
              <div className="opening-chip">
                <span className="opening-icon" aria-hidden="true">◎</span>
                <span>
                  <small>{session?.opening?.eco ? `Eröffnung · ${session.opening.eco}` : "Eröffnung"}</small>
                  <strong>{session?.opening?.name ?? "Noch nicht erkannt"}</strong>
                </span>
              </div>
              <button className="primary-action" onClick={() => void startSession()} disabled={loading} type="button">
                {session ? "Neue Partie" : "Training starten"}<span aria-hidden="true">→</span>
              </button>
            </div>

            {session?.correction && (
              <div className="correction-banner" role="status">
                <strong>Versuch {session.correction.attempt} von 3</strong>
                <span>Die Stellung wurde zurückgesetzt. Probiere einen besseren Zug.</span>
              </div>
            )}
            {error && <div className="error-banner" role="alert">{error}</div>}
          </div>

          {session && session.move_history.length > 0 && (
            <div className="move-strip" aria-label="Zugliste">
              <span>Zugliste</span>
              {session.move_history.map((move, index) => (
                <strong key={`${index}-${move.san}`}>{index % 2 === 0 ? `${Math.floor(index / 2) + 1}. ` : ""}{move.san}</strong>
              ))}
            </div>
          )}
        </div>

        <aside className="coach-panel">
          <div className="coach-heading">
            <div className="coach-avatar" aria-hidden="true">♟</div>
            <div><p className="eyebrow">Dein Coach</p><h2>{session ? "Wir sind in der Partie" : "Bereit für den ersten Zug"}</h2></div>
          </div>

          <div className="coach-feed" aria-live="polite">
            {messages.length === 0 ? (
              <article className="coach-message">
                <span className="message-index">01</span>
                <div>
                  <p>Wähle deine Farbe und eröffne die Partie. Ich ordne jeden Zug ein und erkläre dir auch meine Antworten.</p>
                  <details><summary>So funktioniert das Training</summary><p>Gute ungewöhnliche Züge bleiben auf dem Brett. Bei einem echten Fehler bekommst du bis zu zwei Hinweise, bevor ich die Lösung zeige.</p></details>
                </div>
              </article>
            ) : (
              messages.map((message, index) => (
                <article className={`coach-message ${message.actor}`} key={`${index}-${message.move}-${message.summary}`}>
                  <span className="message-index">{String(index + 1).padStart(2, "0")}</span>
                  <div>
                    <small className="message-author">{message.actor === "learner" ? "Dein Zug" : "Coach-Zug"}{message.move ? ` · ${message.move}` : ""}</small>
                    <p>{message.summary}</p>
                    <details><summary>Erklärung aufklappen</summary><p>{message.details}</p></details>
                  </div>
                </article>
              ))
            )}
          </div>

          <div className="truth-grid">
            <div><span className="truth-icon valid">✓</span><small>Legalität</small><strong>python-chess</strong></div>
            <div><span className="truth-icon theory">◇</span><small>Theorie</small><strong>{health ? `${health.openings.entries} Linien` : "lokale Daten"}</strong></div>
            <div><span className="truth-icon engine">±</span><small>Qualität</small><strong>{health?.stockfish.available ? "Stockfish aktiv" : "Stockfish fehlt"}</strong></div>
          </div>

          <div className="question-box">
            <label htmlFor="coach-question">Frage zur Stellung</label>
            <div><input id="coach-question" placeholder="Warum ist e4 hier sinnvoll?" disabled /><button type="button" disabled aria-label="Frage senden">↑</button></div>
            <small>Freie Rückfragen folgen im nächsten Ausbau</small>
          </div>
        </aside>
      </section>
    </main>
  );
}
