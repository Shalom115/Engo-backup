# Gelliceaux Engineering Agent

Local engineering assistant for SY Gelliceaux (Southern Wind 108).

## Architecture principle

Every external service (LLM, embeddings, vector store) sits behind an abstract
interface in `providers/`. The rest of the codebase never imports a vendor SDK
directly. Swapping providers = one env var change.

## Smoke test

```bash
source .venv/bin/activate
python tests/test_connection.py
```

If it prints "ALL SYSTEMS GO", the foundation is wired correctly.

## Folder layout

```
gelliceaux/
├── providers/        Vendor abstractions (LLM, embeddings, vector store)
├── pipeline/         Document ingestion + retrieval (next session)
├── tests/            Smoke tests
├── data/             Documents, vector store, walker state (not committed)
├── config.py         Loads .env and resolves project paths
└── .env              API keys (NEVER commit)
```

## Status

- [x] Model-agnostic provider abstractions
- [x] Smoke test (Anthropic + Voyage)
- [ ] Document ingestion pipeline
- [ ] Retrieval + HyDE
- [ ] System prompt + agent loop
- [ ] Exocet sensor pre-processor
- [ ] Communication layer (WhatsApp/Twilio)
