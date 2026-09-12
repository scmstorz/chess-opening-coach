# ADR 0019: Use conservative workload-aware countdown estimates

- Status: accepted
- Date: 2026-09-12

## Context

During live play, the learner observed that the countdown shown while the coach
responded to a move was consistently too short. The browser already retained a
rolling duration per operation type, but every submitted move shared one
`move` bucket. This mixed two materially different workloads:

- an authored guided reply, which needs fast legality and engine checks; and
- an adaptive reply after the script ends, which may ask Ollama to explain both
  the learner move and the coach move.

The exponential mean also answered the wrong product question. An average is a
reasonable description of past work, but a countdown that expires on many normal
runs feels broken. The useful target is a conservative upper estimate.

## Options considered

1. Increase the single hard-coded default. Rejected because an existing stored
   average would override it and the two workloads would remain mixed.
2. Multiply the pooled average by a fixed safety factor. Rejected because fast
   scripted turns would continue dragging down free-play estimates.
3. Have the backend predict an exact duration from Stockfish and Ollama. Deferred
   because model loading, retries, cache state, and machine load are not known
   accurately enough in advance to justify an exact server promise.
4. Separate client-side workload profiles and estimate from the upper range of
   recent measurements.

## Decision

Choose option 4. Move submissions are classified as `move-guided` while a fixed
authored reply remains and as `move-adaptive` during free opening or middlegame
play. The final question in a realistic scenario is classified as adaptive
because the same request may finish the script and generate a free Black reply.

The first estimates are 4 seconds for scripted work and 45 seconds for adaptive
work. Each profile stores at most eight measurements on the current device. The
displayed estimate is the larger of its initial floor and:

`80th percentile of recent duration × 1.2 + 2 seconds`

Durations outside 0.5 to 300 seconds are ignored as corrupt or non-representative
storage values. A versioned `v2` browser-storage key intentionally does not
inherit the old pooled mean that triggered the defect.

## Consequences

Free coach turns begin with a deliberately cautious estimate and react strongly
to normal slow runs. Scripted lessons keep a short estimate instead of paying
for that caution. The estimate can still be wrong—especially on a model cold
start—but it should reach “noch einen Moment” substantially less often.

The history remains local browser telemetry and is neither sent to the backend
nor stored as learner performance. If later evidence shows distinct cold/warm
model populations, the backend can expose observable workload facts without
claiming an exact completion time.
