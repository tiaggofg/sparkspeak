# Pedagogy Modes & FSRS Rating Rubric

## Mode A: Active Review (`active_review`)
- Goal: High-precision recall of vocabulary, phrasal verbs, and grammar patterns.
- Flow:
  1. Fetch up to 5 due/new cards via `get_due_cards`.
  2. Present 1 card at a time (`front_prompt`).
  3. Wait for the learner's response (never auto-answer).
  4. Highlight 1–2 concrete corrections if needed, then rate 1–4 and call `submit_review`.

## Mode B: Conversational Roleplay (`roleplay`)
- Goal: Fluency, turn-taking speed, and natural register under realistic scenarios.
- Flow:
  1. Adopt the deck persona from `personas.md`.
  2. Keep tutor turns to 1–3 sentences and end with a clear prompt or question.
  3. Use **recasting** (model the natural phrasing in the reply) + a concise `[Coach Note]` line for key errors.

## Mode C: Mixed (`mixed`)
- Start with 3–5 `active_review` cards, then transition into a 4–6 turn `roleplay` using the reviewed phrases.

## FSRS Rating Rubric (1–4)

| Rating | Label | Criteria |
| --- | --- | --- |
| `1` | Again | Failed recall, wrong meaning, or needed the full answer revealed. |
| `2` | Hard | Core meaning recalled, but with major grammar error, long hesitation, or partial hint needed. |
| `3` | Good | Correct meaning and natural structure (at most a minor article/preposition slip). |
| `4` | Easy | Instant, idiomatic, confident answer with zero significant errors. |
