# NEXO_INBOX (GitHub)

ChatGPT writes proposals here; only the Claude writer (`scripts/nexo_tower.py inbox`) applies them to the Tower.

- Create ONE new file per proposal in `inbox/`: `inbox/<utc>-<kind>-<slug>.json`
- Never edit or delete files. Never touch `main`.
- Root: `{"kind": ..., "source": "CHATGPT", "payload": {...}, "created_at": "<UTC ISO-8601>"}`
- kinds: MUTATION_PROPOSAL, HYPOTHESIS_PROPOSAL, LEARNING_SIGNAL, LESSON_PROPOSAL, OPERATOR_INTENT
- Every result carries `payload.semantic.result_meaning` (2–3 sentences, plain Portuguese).

Applied files are moved to `processed/` by the writer.
