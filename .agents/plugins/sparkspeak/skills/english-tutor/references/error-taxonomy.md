# Error Taxonomy & Card Extraction Criteria

## Canonical Error Categories (`error_logs.category`)

| Category | Definition | Example |
| --- | --- | --- |
| `grammar` | Tense, subject-verb agreement, prepositions, articles, or word order | `"I need put off"` -> `"I need to put off"` |
| `vocabulary` | Wrong word choice, false friend, or unnatural collocation | `"do a meeting"` -> `"hold / have a meeting"` |
| `phrasal_verb` | Missing particle, wrong particle, or literal verb where phrasal verb is expected | `"cancel the call off"` -> `"call off the meeting"` |
| `pronunciation_asr` | Raw ASR transcript reveals likely mispronunciation or dropped ending | `"work"` transcribed instead of `"worked"` |
| `register` | Too formal, too blunt, or mismatched for engineering/social context | `"Give me the doc"` -> `"Could you share the doc?"` |

## Card Extraction Rules
- Promote errors that are **reusable** across conversations (preposition collocations, irregular verbs, phrasal verbs, polite meeting phrasing).
- Skip one-off typos or proper-noun misspellings.
- Always pair `front_prompt` (clear cue or broken sentence to fix) with `back_reference` (natural target phrasing) and `context_example`.
