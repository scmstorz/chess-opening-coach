"use client";

import { type CSSProperties, useEffect, useMemo, useRef, useState } from "react";

type Piece = {
  color: "white" | "black";
  kind: "king" | "queen" | "rook" | "bishop" | "knight" | "pawn";
};

type PlayerColor = "white" | "black" | "random";
type TrainingMode = "free" | "guided";

type EngineInfo = {
  available: boolean;
  evaluation_played: number | null;
  mate_played: number | null;
  loss_pawns: number | null;
  classification: string;
};

type BookReference = {
  kind: "book";
  book_id: string;
  title: string;
  author: string | null;
  year: number | null;
  pdf_page_start: number;
  pdf_page_end: number;
  source_ref: string;
  status: "source_only" | "legality_checked" | "engine_checked";
  warnings: string[];
  match_kind: string;
};

type GroupedBookReference = Omit<
  BookReference,
  "pdf_page_start" | "pdf_page_end" | "source_ref" | "warnings" | "match_kind"
> & {
  page_ranges: { start: number; end: number }[];
  reference_count: number;
};

type KnowledgeInfo = {
  status: "grounded" | "no_evidence" | "insufficient_evidence" | "model_unavailable" | "rejected";
  reason: string | null;
  evidence_count: number;
  perspective_filtered_count?: number;
  used_evidence_ids: string[];
};

type ExplanationRating = "helpful" | "unclear" | "wrong";

type ExplanationFeedback = {
  rating: ExplanationRating;
  note: string;
  updated_at: string;
};

type FeedbackReviewRecord = ExplanationFeedback & {
  id: number;
  message_id: string;
  position_fen: string;
  opening_eco: string | null;
  opening_name: string | null;
  message_kind: string | null;
  actor: "learner" | "coach";
  question: string | null;
  move_uci: string | null;
  move_san: string | null;
  summary_snapshot: string;
  details_snapshot: string;
  explanation_sections: { title: string; text: string }[] | null;
  source: string;
  llm_model: string | null;
  engine: EngineInfo | null;
};

type CoachMessage = {
  message_id?: string;
  kind?: "move" | "question" | "clarification" | "phase" | "summary" | "prompt";
  actor: "learner" | "coach";
  question?: string;
  move: string | null;
  summary: string;
  details: string;
  explanation_sections?: { title: string; text: string }[];
  source: string;
  model: string | null;
  attempt: number | null;
  engine: EngineInfo | null;
  move_uci?: string;
  fen_after?: string;
  analysis_mode?: "standard" | "deep";
  references?: BookReference[];
  knowledge?: KnowledgeInfo;
  feedback?: ExplanationFeedback | null;
};

type ProgressKind = "move" | "suggestion" | "question" | "deep";

type BusyProgress = {
  kind: ProgressKind;
  startedAt: number;
  estimateSeconds: number;
};

type OpeningEndSignal = {
  id: string;
  label: string;
  met: boolean;
};

type OpeningEnd = {
  likely: boolean;
  headline: string;
  explanation: string;
  signals: OpeningEndSignal[];
  can_continue: boolean;
};

type OpeningSummary = {
  opening: { eco: string; name: string } | null;
  learner_color: "white" | "black";
  moves_played: number;
  learner_moves: number;
  concepts: string[];
  strengths: string[];
  review_points: string[];
  takeaway: string;
  recommendation: { title: string; reason: string; fen: string } | null;
  source: string;
  created_at: string;
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
  message_history: CoachMessage[];
  can_undo: boolean;
  correction: {
    active: boolean;
    attempt: number;
    remaining: number;
    solution_revealed: boolean;
    recommended_move: string | null;
  } | null;
  game_over: boolean;
  phase: "opening" | "transition" | "middlegame" | "complete";
  opening_end: OpeningEnd | null;
  opening_summary: OpeningSummary | null;
  training_mode: TrainingMode;
  lesson: {
    lesson_id: string;
    title: string;
    opening_name: string;
    eco: string;
    goal: string;
    total_learner_moves: number;
  } | null;
  training_progress: {
    current: number;
    completed: number;
    total: number;
    question: string;
    goal: string;
  } | null;
};

type MoveSuggestion = {
  move_uci: string;
  move_san: string;
  basis: "theory" | "engine" | "repertoire";
  opening: { eco: string; name: string } | null;
  summary: string;
  details: string;
  engine: EngineInfo;
};

type QuestionResponse = {
  message: CoachMessage;
  message_history: CoachMessage[];
};

type Health = {
  status: string;
  openings: { source: string; entries: number };
  stockfish: { available: boolean; name: string | null };
  ollama: { available: boolean; model: string | null; reason: string | null };
  books?: { available: boolean; book_count: number; chunk_count: number; reason: string | null };
};

function groupBookReferences(references: BookReference[]): GroupedBookReference[] {
  const groups = new Map<string, BookReference[]>();
  for (const reference of references) {
    const current = groups.get(reference.book_id) ?? [];
    current.push(reference);
    groups.set(reference.book_id, current);
  }
  const statusOrder: Record<BookReference["status"], number> = {
    source_only: 0,
    legality_checked: 1,
    engine_checked: 2,
  };
  return [...groups.values()].map((bookReferences) => {
    const first = bookReferences[0];
    const pageRanges = bookReferences
      .map((reference) => ({
        start: reference.pdf_page_start,
        end: reference.pdf_page_end,
      }))
      .sort((left, right) => left.start - right.start || left.end - right.end)
      .reduce<{ start: number; end: number }[]>((merged, range) => {
        const previous = merged.at(-1);
        if (previous && range.start <= previous.end + 1) {
          previous.end = Math.max(previous.end, range.end);
        } else {
          merged.push({ ...range });
        }
        return merged;
      }, []);
    const conservativeStatus = bookReferences.reduce<BookReference["status"]>(
      (current, reference) => (
        statusOrder[reference.status] < statusOrder[current] ? reference.status : current
      ),
      "engine_checked",
    );
    return {
      kind: "book",
      book_id: first.book_id,
      title: first.title,
      author: first.author,
      year: first.year,
      status: conservativeStatus,
      page_ranges: pageRanges,
      reference_count: bookReferences.length,
    };
  });
}

function pdfPageRangesLabel(reference: GroupedBookReference): string {
  const ranges = reference.page_ranges.map((range) => (
    range.start === range.end ? `${range.start}` : `${range.start}–${range.end}`
  ));
  const singular = ranges.length === 1 && reference.page_ranges[0].start === reference.page_ranges[0].end;
  return `PDF-${singular ? "Seite" : "Seiten"} ${ranges.join(", ")}`;
}

function groupedReferenceStatus(reference: GroupedBookReference): string {
  const count = `${reference.reference_count} ${reference.reference_count === 1 ? "Buchstelle" : "Buchstellen"}`;
  if (reference.status === "engine_checked") return `${count} · mit Stockfish geprüft`;
  if (reference.status === "legality_checked") return `${count} · Buchzüge auf Legalität geprüft`;
  return `${count} · Buchaussagen nicht unabhängig verifiziert`;
}

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

const defaultProgressEstimates: Record<ProgressKind, number> = {
  move: 18,
  suggestion: 3,
  question: 12,
  deep: 22,
};

const progressLabels: Record<ProgressKind, string> = {
  move: "Coach prüft den Zug",
  suggestion: "Stockfish sucht einen stabilen Zug",
  question: "Coach ordnet die geprüften Fakten",
  deep: "Stockfish vergleicht mehrere Zukunftspläne",
};

function currentTimeMs(): number {
  return Date.now();
}

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

const feedbackOptions: { rating: ExplanationRating; label: string; icon: string }[] = [
  { rating: "helpful", label: "Hilfreich", icon: "✓" },
  { rating: "unclear", label: "Unklar", icon: "?" },
  { rating: "wrong", label: "Falsch", icon: "!" },
];

function ExplanationFeedbackControl({
  sessionId,
  message,
  onSaved,
}: {
  sessionId: string;
  message: CoachMessage;
  onSaved: (feedback: ExplanationFeedback) => void;
}) {
  const [note, setNote] = useState(message.feedback?.note ?? "");
  const [editingNote, setEditingNote] = useState(false);
  const [saving, setSaving] = useState(false);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);

  if (!message.message_id) return null;

  async function persist(rating: ExplanationRating, nextNote: string): Promise<boolean> {
    if (!message.message_id) return false;
    setSaving(true);
    setFeedbackError(null);
    try {
      const saved = await api<ExplanationFeedback>(
        `/api/sessions/${sessionId}/messages/${message.message_id}/feedback`,
        {
          method: "PUT",
          body: JSON.stringify({ rating, note: nextNote }),
        },
      );
      setNote(saved.note);
      onSaved(saved);
      return true;
    } catch (caught) {
      setFeedbackError(
        caught instanceof Error ? caught.message : "Das Feedback konnte nicht gespeichert werden.",
      );
      return false;
    } finally {
      setSaving(false);
    }
  }

  function selectRating(rating: ExplanationRating) {
    if (rating !== "helpful" || message.feedback?.note) setEditingNote(true);
    void persist(rating, note);
  }

  return (
    <section className="explanation-feedback" aria-label="Erklärung bewerten">
      <span>Hilft dir diese Erklärung?</span>
      <div className="feedback-actions">
        {feedbackOptions.map((option) => (
          <button
            aria-pressed={message.feedback?.rating === option.rating}
            className={message.feedback?.rating === option.rating ? `selected ${option.rating}` : ""}
            disabled={saving}
            key={option.rating}
            onClick={() => selectRating(option.rating)}
            type="button"
          >
            <b aria-hidden="true">{option.icon}</b>{option.label}
          </button>
        ))}
      </div>
      {message.feedback && !editingNote && (
        <div className="feedback-saved" role="status">
          <span>Gespeichert</span>
          <button onClick={() => setEditingNote(true)} type="button">
            {message.feedback.note ? "Notiz bearbeiten" : "Notiz ergänzen"}
          </button>
        </div>
      )}
      {message.feedback && editingNote && (
        <form
          className="feedback-note"
          onSubmit={(event) => {
            event.preventDefault();
            void persist(message.feedback!.rating, note).then((saved) => {
              if (saved) setEditingNote(false);
            });
          }}
        >
          <label htmlFor={`feedback-note-${message.message_id}`}>Optional: Was fehlt oder stimmt nicht?</label>
          <textarea
            id={`feedback-note-${message.message_id}`}
            maxLength={1000}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Zum Beispiel: Der langfristige Plan bleibt unklar."
            rows={3}
            value={note}
          />
          <div>
            <button disabled={saving} type="submit">{saving ? "Speichert …" : "Notiz speichern"}</button>
            <button
              disabled={saving}
              onClick={() => {
                setNote(message.feedback?.note ?? "");
                setEditingNote(false);
              }}
              type="button"
            >
              Schließen
            </button>
          </div>
        </form>
      )}
      {feedbackError && <small className="feedback-error" role="alert">{feedbackError}</small>}
    </section>
  );
}

export default function Home() {
  const [requestedColor, setRequestedColor] = useState<PlayerColor>("white");
  const [requestedMode, setRequestedMode] = useState<TrainingMode>("guided");
  const [session, setSession] = useState<SessionState | null>(null);
  const [messages, setMessages] = useState<CoachMessage[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [selectedSquare, setSelectedSquare] = useState<string | null>(null);
  const [draggedFrom, setDraggedFrom] = useState<string | null>(null);
  const [displayFen, setDisplayFen] = useState(initialFen);
  const [moveAnimation, setMoveAnimation] = useState<MoveAnimation | null>(null);
  const [suggestion, setSuggestion] = useState<MoveSuggestion | null>(null);
  const [questionText, setQuestionText] = useState("");
  const [askingQuestion, setAskingQuestion] = useState(false);
  const [animatingSequence, setAnimatingSequence] = useState(false);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState<BusyProgress | null>(null);
  const [progressClock, setProgressClock] = useState(0);
  const [durationEstimates, setDurationEstimates] = useState(defaultProgressEstimates);
  const [error, setError] = useState<string | null>(null);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewItems, setReviewItems] = useState<FeedbackReviewRecord[]>([]);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const coachFeedRef = useRef<HTMLDivElement | null>(null);
  const initialSessionRequestedRef = useRef(false);
  const interactionLocked = loading || askingQuestion;
  const phaseDecisionPending = session?.phase === "transition";
  const sessionComplete = session?.phase === "complete";
  const boardInteractionLocked = interactionLocked || phaseDecisionPending || sessionComplete;

  useEffect(() => {
    api<Health>("/api/health").then(setHealth).catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    if (initialSessionRequestedRef.current) return;
    initialSessionRequestedRef.current = true;
    api<SessionState>("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ color: "white", training_mode: "guided" }),
    }).then((next) => {
      setSession(next);
      setMessages(next.message_history);
      setDisplayFen(next.fen);
    }).catch((caught) => {
      setError(caught instanceof Error ? caught.message : "Der lokale Coach ist nicht erreichbar.");
    });
  }, []);

  useEffect(() => {
    const feed = coachFeedRef.current;
    if (!feed || messages.length === 0) return;
    window.requestAnimationFrame(() => {
      feed.scrollTo({ top: feed.scrollHeight, behavior: "smooth" });
    });
  }, [messages.length]);

  useEffect(() => {
    if (!progress) return;
    const timer = window.setInterval(() => setProgressClock(currentTimeMs()), 250);
    return () => window.clearInterval(timer);
  }, [progress]);

  useEffect(() => {
    if (!reviewOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setReviewOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [reviewOpen]);

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

  const suggestedFrom = suggestion?.move_uci.slice(0, 2);
  const suggestedTo = suggestion?.move_uci.slice(2, 4);

  const latestEngine = [...messages].reverse().find((message) => message.engine?.available)?.engine;
  const evaluation = latestEngine?.evaluation_played ?? 0;
  const evaluationWidth = Math.max(6, Math.min(94, 50 + evaluation * 8));
  const elapsedSeconds = progress ? Math.max(0, (progressClock - progress.startedAt) / 1000) : 0;
  const remainingSeconds = progress
    ? Math.max(0, Math.ceil(progress.estimateSeconds - elapsedSeconds))
    : 0;
  const progressPercent = progress
    ? Math.min(96, Math.max(4, (elapsedSeconds / progress.estimateSeconds) * 100))
    : 0;
  const activeProgressLabel = progress?.kind === "deep" && elapsedSeconds >= 10
    ? "Tutor formuliert die geprüften Pläne"
    : progress
    ? progressLabels[progress.kind]
    : "Coach denkt nach";

  function beginProgress(kind: ProgressKind): number {
    const startedAt = currentTimeMs();
    const stored = Number(window.localStorage.getItem(`coach-duration-${kind}`));
    const estimateSeconds = Number.isFinite(stored) && stored > 0
      ? Math.max(1, Math.round(stored))
      : durationEstimates[kind];
    setDurationEstimates((current) => ({ ...current, [kind]: estimateSeconds }));
    setProgressClock(startedAt);
    setProgress({ kind, startedAt, estimateSeconds });
    return startedAt;
  }

  function finishProgress(kind: ProgressKind, startedAt: number) {
    const measured = Math.max(0.5, (currentTimeMs() - startedAt) / 1000);
    const previous = Number(window.localStorage.getItem(`coach-duration-${kind}`));
    const smoothed = Number.isFinite(previous) && previous > 0
      ? previous * 0.65 + measured * 0.35
      : measured;
    window.localStorage.setItem(`coach-duration-${kind}`, smoothed.toFixed(1));
    setDurationEstimates((current) => ({ ...current, [kind]: Math.round(smoothed) }));
    setProgress(null);
  }

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

  async function startSession(
    color: PlayerColor = requestedColor,
    trainingMode: TrainingMode = requestedMode,
  ) {
    setRequestedColor(color);
    setRequestedMode(trainingMode);
    setLoading(true);
    setError(null);
    setSuggestion(null);
    setQuestionText("");
    setDisplayFen(initialFen);
    setMoveAnimation(null);
    try {
      const next = await api<SessionState>("/api/sessions", {
        method: "POST",
        body: JSON.stringify({ color, training_mode: trainingMode }),
      });
      setSession(next);
      setMessages(next.message_history);
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
    if (!session || boardInteractionLocked || session.turn !== session.learner_color) return;
    setSuggestion(null);
    const fenBefore = displayFen;
    const matchingMove = session.legal_moves.find((move) => move.startsWith(`${from}${to}`));
    const optimisticFen = matchingMove ? visualFenAfterMove(fenBefore, matchingMove) : fenBefore;
    if (matchingMove) setDisplayFen(optimisticFen);
    setLoading(true);
    const progressStartedAt = beginProgress("move");
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
      setMessages(next.message_history);
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
      finishProgress("move", progressStartedAt);
    }
  }

  async function undoLastTurn() {
    if (!session?.can_undo || interactionLocked) return;
    setLoading(true);
    setError(null);
    setSuggestion(null);
    setMoveAnimation(null);
    try {
      const next = await api<SessionState>(`/api/sessions/${session.session_id}/undo`, {
        method: "POST",
      });
      setSession(next);
      setMessages(next.message_history);
      setDisplayFen(next.fen);
      setSelectedSquare(null);
      setDraggedFrom(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Der Zug konnte nicht zurückgenommen werden.");
    } finally {
      setLoading(false);
    }
  }

  async function requestSuggestion() {
    if (!session || boardInteractionLocked || session.turn !== session.learner_color) return;
    setLoading(true);
    const progressStartedAt = beginProgress("suggestion");
    setError(null);
    setSuggestion(null);
    setSelectedSquare(null);
    try {
      const next = await api<MoveSuggestion>(
        `/api/sessions/${session.session_id}/suggestion`,
        { method: "POST" },
      );
      setSuggestion(next);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Es konnte kein Zug vorgeschlagen werden.");
    } finally {
      setLoading(false);
      finishProgress("suggestion", progressStartedAt);
    }
  }

  async function askQuestion(deep = false, suggestedQuestion?: string) {
    const question = questionText.trim() || suggestedQuestion?.trim() || "";
    if (!session || boardInteractionLocked || question.length < 2) return;
    setAskingQuestion(true);
    const progressKind: ProgressKind = deep ? "deep" : "question";
    const progressStartedAt = beginProgress(progressKind);
    setError(null);
    try {
      const response = await api<QuestionResponse>(
        `/api/sessions/${session.session_id}/questions`,
        {
          method: "POST",
          body: JSON.stringify({
            question,
            focus_move_uci: suggestion?.move_uci,
            deep,
          }),
        },
      );
      setMessages(response.message_history);
      setQuestionText("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Die Frage konnte nicht beantwortet werden.");
    } finally {
      setAskingQuestion(false);
      finishProgress(progressKind, progressStartedAt);
    }
  }

  async function resolveOpeningEnd(action: "continue" | "summary") {
    if (!session || interactionLocked || session.phase !== "transition") return;
    setLoading(true);
    setError(null);
    setSuggestion(null);
    try {
      const next = await api<SessionState>(
        `/api/sessions/${session.session_id}/opening/${action}`,
        { method: "POST" },
      );
      setSession(next);
      setMessages(next.message_history);
      setDisplayFen(next.fen);
      setSelectedSquare(null);
      setDraggedFrom(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Die Auswahl konnte nicht gespeichert werden.");
    } finally {
      setLoading(false);
    }
  }

  function selectOrMove(square: string) {
    if (!session || boardInteractionLocked) return;
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

  function updateMessageFeedback(messageId: string, feedback: ExplanationFeedback) {
    setMessages((current) => current.map((message) => (
      message.message_id === messageId ? { ...message, feedback } : message
    )));
    if (reviewOpen) void loadFeedbackReview();
  }

  async function loadFeedbackReview() {
    setReviewLoading(true);
    setReviewError(null);
    try {
      const records = await api<FeedbackReviewRecord[]>("/api/feedback?limit=100");
      setReviewItems(records.filter((record) => record.rating !== "helpful"));
    } catch (caught) {
      setReviewError(
        caught instanceof Error ? caught.message : "Die Feedback-Liste konnte nicht geladen werden.",
      );
    } finally {
      setReviewLoading(false);
    }
  }

  function openFeedbackReview() {
    setReviewOpen(true);
    void loadFeedbackReview();
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="Chess Opening Coach Startseite">
          <span className="brand-mark" aria-hidden="true">♞</span>
          <span><strong>Chess Opening Coach</strong><small>Verstehen statt auswendig lernen</small></span>
        </a>
        <div className="topbar-actions">
          <button className="review-list-action" onClick={openFeedbackReview} type="button">
            Feedback prüfen
          </button>
          <div className={health ? "local-status" : "local-status offline"}>
            <span className="status-dot" aria-hidden="true" />
            {health ? "Lokal verbunden" : "Coach nicht verbunden"}
          </div>
        </div>
      </header>

      <section className="workspace" id="top">
        <div className="board-column">
          <div className="session-toolbar">
            <div>
              <p className="eyebrow">
                {requestedMode === "guided" ? "Geführtes Repertoiretraining" : "Freies Eröffnungsspiel"}
              </p>
              <h1>Eröffnungen</h1>
            </div>
            <div className="session-options">
              <div className="mode-picker" aria-label="Trainingsmodus wählen">
                <button
                  aria-pressed={requestedMode === "guided"}
                  className={requestedMode === "guided" ? "mode-option active" : "mode-option"}
                  disabled={interactionLocked || phaseDecisionPending}
                  onClick={() => void startSession("white", "guided")}
                  type="button"
                >
                  Italienisch üben
                </button>
                <button
                  aria-pressed={requestedMode === "free"}
                  className={requestedMode === "free" ? "mode-option active" : "mode-option"}
                  disabled={interactionLocked || phaseDecisionPending}
                  onClick={() => void startSession(requestedColor, "free")}
                  type="button"
                >
                  Freies Spiel
                </button>
              </div>
              {requestedMode === "free" && (
                <div className="color-picker" aria-label="Farbe wählen">
                  {(["white", "black", "random"] as PlayerColor[]).map((color) => (
                    <button
                      className={requestedColor === color ? "color-option active" : "color-option"}
                      disabled={interactionLocked || phaseDecisionPending}
                      key={color}
                      onClick={() => void startSession(color, "free")}
                      aria-pressed={requestedColor === color}
                      type="button"
                    >
                      {color === "white" ? "Weiß" : color === "black" ? "Schwarz" : "Zufällig"}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="board-stage">
            <div className="evaluation" aria-label={`Stockfish-Bewertung: ${scoreLabel()}`}>
              <div className="evaluation-labels"><span>Schwarz</span><strong>{scoreLabel()}</strong><span>Weiß</span></div>
              <div className="evaluation-track"><span style={{ width: `${evaluationWidth}%` }} /></div>
              <p className="evaluation-help">+ bedeutet Vorteil für Weiß · − bedeutet Vorteil für Schwarz</p>
            </div>

            {session?.training_progress && (
              <section className="lesson-prompt" aria-live="polite">
                <div>
                  <span>Zug {session.training_progress.current} von {session.training_progress.total}</span>
                  <strong>{session.training_progress.question}</strong>
                </div>
                <small>{session.training_progress.goal}</small>
              </section>
            )}

            <div className={`board-frame${interactionLocked && !animatingSequence ? " thinking" : ""}`}>
              <div className="chessboard" aria-disabled={!session || boardInteractionLocked} aria-label="Interaktives Schachbrett">
                {orientedSquares.map((square, index) => {
                  const piece = position[square];
                  const file = square[0];
                  const rank = square[1];
                  const isLight = (files.indexOf(file) + Number(rank)) % 2 === 1;
                  const canDrag = Boolean(
                    session && !boardInteractionLocked && piece?.color === session.learner_color && session.turn === session.learner_color,
                  );
                  return (
                    <button
                      aria-label={`${square}${piece ? `, ${piece.color} ${piece.kind}` : ""}`}
                      className={`square ${isLight ? "light" : "dark"} ${selectedSquare === square ? "selected" : ""} ${legalTargets.has(square) ? "legal-target" : ""} ${suggestedFrom === square ? "suggested-from" : ""} ${suggestedTo === square ? "suggested-to" : ""}`}
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
              {interactionLocked && !animatingSequence && (
                <div className="board-loader" role="status">
                  <div className="thinking-card">
                    <strong>{activeProgressLabel}</strong>
                    <span>{remainingSeconds > 0 ? `noch etwa ${remainingSeconds} s` : "noch einen Moment …"}</span>
                    <i aria-hidden="true"><b style={{ width: `${progressPercent}%` }} /></i>
                  </div>
                </div>
              )}
            </div>

            <div className="board-footer">
              <div className="opening-chip">
                <span className="opening-icon" aria-hidden="true">◎</span>
                <span>
                  <small>{session?.lesson ? `Trainingslinie · ${session.lesson.eco}` : session?.opening?.eco ? `Eröffnung · ${session.opening.eco}` : "Eröffnung"}</small>
                  <strong>{session?.lesson?.title ?? session?.opening?.name ?? "Noch nicht erkannt"}</strong>
                </span>
              </div>
              <div className="board-actions">
                {session && (
                  <button
                    className="secondary-action"
                    disabled={interactionLocked || sessionComplete || !session.can_undo}
                    onClick={() => void undoLastTurn()}
                    title="Nimmt deinen letzten Zug und die Coach-Antwort zurück"
                    type="button"
                  >
                    <span aria-hidden="true">↶</span>Zug zurück
                  </button>
                )}
                <button
                  className="secondary-action suggestion-action"
                  disabled={!session || boardInteractionLocked || session.turn !== session.learner_color || session.game_over}
                  onClick={() => void requestSuggestion()}
                  title="Markiert einen guten Zug aus Eröffnungstheorie oder Stockfish-Analyse"
                  type="button"
                >
                  <span aria-hidden="true">✦</span>Zug vorschlagen
                </button>
                <button className="primary-action" onClick={() => void startSession()} disabled={interactionLocked || phaseDecisionPending} type="button">
                  Neue Partie<span aria-hidden="true">→</span>
                </button>
              </div>
            </div>

            {suggestion && (
              <div className="suggestion-banner" role="status">
                <span aria-hidden="true">✦</span>
                <div>
                  <strong>{suggestion.basis === "engine" ? "Engine-Vorschlag" : suggestion.basis === "repertoire" ? "Zug der Trainingslinie" : "Eröffnungsvorschlag"} · {suggestion.move_san}</strong>
                  <p>{suggestion.summary}</p>
                  <details><summary>Warum dieser Zug?</summary><p>{suggestion.details}</p></details>
                  <button
                    className="deep-explain-action"
                    disabled={boardInteractionLocked}
                    onClick={() => void askQuestion(true, `Warum ist ${suggestion.move_san} mittel- und langfristig gut?`)}
                    type="button"
                  >
                    Tief erklären <span>· ca. {durationEstimates.deep} s</span>
                  </button>
                </div>
              </div>
            )}

            {session?.opening_end && (
              <section className="opening-end-banner" aria-labelledby="opening-end-title" role="status">
                <div className="opening-end-icon" aria-hidden="true">◎</div>
                <div className="opening-end-content">
                  <p className="eyebrow">Phasenwechsel</p>
                  <h3 id="opening-end-title">{session.opening_end.headline}</h3>
                  <p>{session.opening_end.explanation}</p>
                  <details>
                    <summary>Woran erkennt der Coach das?</summary>
                    <ul className="phase-signals">
                      {session.opening_end.signals.map((signal) => (
                        <li className={signal.met ? "met" : ""} key={signal.id}>
                          <span aria-hidden="true">{signal.met ? "✓" : "·"}</span>{signal.label}
                        </li>
                      ))}
                    </ul>
                  </details>
                  <div className="opening-end-actions">
                    {session.opening_end.can_continue && (
                      <button className="secondary-action" disabled={interactionLocked} onClick={() => void resolveOpeningEnd("continue")} type="button">
                        Partie weiterspielen
                      </button>
                    )}
                    <button className="primary-action" disabled={interactionLocked} onClick={() => void resolveOpeningEnd("summary")} type="button">
                      Eröffnung auswerten<span aria-hidden="true">→</span>
                    </button>
                  </div>
                </div>
              </section>
            )}

            {session?.opening_summary && (
              <section className="opening-summary" aria-labelledby="opening-summary-title">
                <header>
                  <div>
                    <p className="eyebrow">Deine Auswertung</p>
                    <h3 id="opening-summary-title">{session.opening_summary.opening?.name ?? "Freies Eröffnungsspiel"}</h3>
                  </div>
                  <span>{session.opening_summary.learner_moves} eigene Züge</span>
                </header>

                <div className="summary-section summary-concepts">
                  <h4>Was in der Stellung wichtig war</h4>
                  <ul>{session.opening_summary.concepts.map((item) => <li key={item}>{item}</li>)}</ul>
                </div>

                <div className="summary-columns">
                  <div className="summary-section">
                    <h4>Das lief gut</h4>
                    <ul>{session.opening_summary.strengths.map((item) => <li key={item}>{item}</li>)}</ul>
                  </div>
                  <div className="summary-section">
                    <h4>Noch einmal anschauen</h4>
                    {session.opening_summary.review_points.length ? (
                      <ul>{session.opening_summary.review_points.map((item) => <li key={item}>{item}</li>)}</ul>
                    ) : <p>Kein konkreter Korrekturpunkt in dieser Eröffnungsphase.</p>}
                  </div>
                </div>

                <blockquote className="summary-takeaway">{session.opening_summary.takeaway}</blockquote>

                {session.opening_summary.recommendation && (
                  <div className="review-recommendation">
                    <span aria-hidden="true">↻</span>
                    <div><strong>{session.opening_summary.recommendation.title}</strong><p>{session.opening_summary.recommendation.reason}</p></div>
                  </div>
                )}
              </section>
            )}

            {session?.correction && (
              <div className="correction-banner" role="status">
                <strong>Versuch {session.correction.attempt} von 3</strong>
                <span>{session.training_mode === "guided" ? "Der Zug wurde nicht ausgeführt. Nutze den Hinweis und versuche den Zug dieser Trainingslinie noch einmal." : "Die Stellung wurde zurückgesetzt. Probiere einen besseren Zug."}</span>
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
            <div>
              <p className="eyebrow">Dein Coach</p>
              <h2>{sessionComplete ? "Eröffnung ausgewertet" : phaseDecisionPending ? "Zeit für eine Entscheidung" : session?.training_mode === "guided" ? "Italienisch mit Weiß" : session?.phase === "middlegame" ? "Wir sind im Mittelspiel" : session ? "Wir sind in der Partie" : "Bereit für den ersten Zug"}</h2>
            </div>
          </div>

          <div className="coach-feed" aria-live="polite" ref={coachFeedRef}>
            {messages.length === 0 ? (
              <article className="coach-message">
                <span className="message-index">01</span>
                <div>
                  <p>Du spielst zunächst Weiß und kannst sofort ziehen. Ich ordne jeden Zug ein und erkläre dir auch meine Antworten.</p>
                  <details><summary>So funktioniert das Training</summary><p>Gute ungewöhnliche Züge bleiben auf dem Brett. Bei einem echten Fehler bekommst du bis zu zwei Hinweise, bevor ich die Lösung zeige.</p></details>
                </div>
              </article>
            ) : (
              messages.map((message, index) => (
                <article className={`coach-message ${message.actor}${message.kind === "question" || message.kind === "clarification" ? " question-answer" : ""}`} key={`${index}-${message.move}-${message.question ?? message.summary}`}>
                  <span className="message-index">{String(index + 1).padStart(2, "0")}</span>
                  <div>
                    <small className="message-author">{message.kind === "prompt" ? "Trainingsfrage" : message.kind === "clarification" ? "Rückfrage zum Zug" : message.kind === "question" ? "Antwort zur Frage" : message.kind === "phase" ? "Phasenwechsel" : message.kind === "summary" ? "Lernbilanz" : message.actor === "learner" ? "Dein Zug" : "Coach-Zug"}{message.move ? ` · ${message.move}` : ""}</small>
                    {message.question && <blockquote className="question-quote">„{message.question}“</blockquote>}
                    <p>{message.summary}</p>
                    <details>
                      <summary>{message.explanation_sections?.length ? "Erklärung und Vergleich aufklappen" : "Erklärung aufklappen"}</summary>
                      {message.explanation_sections?.length ? (
                        <div className="explanation-sections">
                          {message.explanation_sections.map((section) => (
                            <section key={section.title}>
                              <h4>{section.title}</h4>
                              <p>{section.text}</p>
                            </section>
                          ))}
                        </div>
                      ) : <p>{message.details}</p>}
                      {message.references && message.references.length > 0 && (
                        <div className="book-references" aria-label="Verwendete Buchquellen">
                          <h4>Buchquelle</h4>
                          {groupBookReferences(message.references).map((reference) => (
                            <div className="book-reference" key={reference.book_id}>
                              <strong>{reference.title}</strong>
                              <span>
                                {[reference.author, reference.year, pdfPageRangesLabel(reference)]
                                  .filter(Boolean)
                                  .join(" · ")}
                              </span>
                              <small>{groupedReferenceStatus(reference)}</small>
                            </div>
                          ))}
                        </div>
                      )}
                    </details>
                    {session && message.message_id && message.kind !== "clarification" && message.kind !== "prompt" && (
                      <ExplanationFeedbackControl
                        key={message.message_id}
                        message={message}
                        onSaved={(feedback) => updateMessageFeedback(message.message_id!, feedback)}
                        sessionId={session.session_id}
                      />
                    )}
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
            <form onSubmit={(event) => { event.preventDefault(); void askQuestion(false); }}>
              <input
                id="coach-question"
                onChange={(event) => setQuestionText(event.target.value)}
                placeholder={suggestion ? `Warum ist ${suggestion.move_san} hier gut?` : "Warum ist e4 hier sinnvoll?"}
                value={questionText}
                disabled={!session || boardInteractionLocked}
                maxLength={600}
              />
              <button type="submit" disabled={!session || boardInteractionLocked || questionText.trim().length < 2} aria-label="Frage senden">
                {askingQuestion ? "…" : "↑"}
              </button>
            </form>
            <button
              className="deep-question-action"
              disabled={!session || boardInteractionLocked || questionText.trim().length < 2}
              onClick={() => void askQuestion(true)}
              type="button"
            >
              Tief erklären <span>mehrere Varianten · ca. {durationEstimates.deep} s</span>
            </button>
            <small>{sessionComplete ? "Die Eröffnungslektion ist abgeschlossen. Starte eine neue Partie, wenn du weiterüben möchtest." : phaseDecisionPending ? "Entscheide zuerst, ob du weiterspielen oder auswerten möchtest." : askingQuestion && progress ? `${activeProgressLabel} · ${remainingSeconds > 0 ? `noch etwa ${remainingSeconds} Sekunden` : "noch einen Moment"}` : `Geerdet mit Stellung, Eröffnungstheorie und Stockfish${health?.ollama.model ? ` · ${health.ollama.model}` : ""}`}</small>
          </div>
        </aside>
      </section>

      {reviewOpen && (
        <div className="review-overlay" role="presentation" onMouseDown={(event) => {
          if (event.target === event.currentTarget) setReviewOpen(false);
        }}>
          <section aria-labelledby="review-title" aria-modal="true" className="review-dialog" role="dialog">
            <header>
              <div>
                <p className="eyebrow">Lokale Qualitätsprüfung</p>
                <h2 id="review-title">Unklare und falsche Erklärungen</h2>
              </div>
              <button aria-label="Feedback-Liste schließen" onClick={() => setReviewOpen(false)} type="button">×</button>
            </header>
            <p className="review-intro">Diese Einträge sind Prüfkandidaten, noch keine bestätigten Schachfehler.</p>
            <div className="review-list">
              {reviewLoading && <p role="status">Feedback wird geladen …</p>}
              {reviewError && <p className="review-error" role="alert">{reviewError}</p>}
              {!reviewLoading && !reviewError && reviewItems.length === 0 && (
                <div className="review-empty"><span aria-hidden="true">✓</span><p>Noch keine unklaren oder falschen Erklärungen markiert.</p></div>
              )}
              {!reviewLoading && reviewItems.map((record) => (
                <article className="review-item" key={record.id}>
                  <div className="review-item-heading">
                    <span className={`review-rating ${record.rating}`}>{record.rating === "wrong" ? "Falsch" : "Unklar"}</span>
                    <strong>{record.move_san ? `${record.move_san} · ` : ""}{record.opening_name ?? "Unbenannte Stellung"}</strong>
                  </div>
                  {record.question && <blockquote>„{record.question}“</blockquote>}
                  <p>{record.summary_snapshot}</p>
                  {record.note && <div className="review-note"><small>Deine Notiz</small>{record.note}</div>}
                  <details>
                    <summary>Gespeicherten Kontext ansehen</summary>
                    <p>{record.details_snapshot}</p>
                    <dl>
                      <div><dt>Stellung</dt><dd>{record.position_fen}</dd></div>
                      <div><dt>Quelle</dt><dd>{record.source}</dd></div>
                      <div><dt>Modell</dt><dd>{record.llm_model ?? "kein LLM"}</dd></div>
                    </dl>
                  </details>
                </article>
              ))}
            </div>
          </section>
        </div>
      )}
    </main>
  );
}
