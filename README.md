# Authentic AI

Authentic AI is a conversational AI workspace with governed, source-aware generation of professional PDF, DOCX, and PPTX artifacts.

## Current artifact capabilities

- Natural-language artifact commands in chat.
- Source resolution from an explicit prompt, the previous Serenya response, recent conversation context, or an uploaded file analysis.
- Asynchronous generation with progress, cancellation, and private capability tokens.
- Durable logical artifacts with versions, rename, revise, export, duplicate, restore, audit, and delete operations.
- Professional Publishing V9 with editorial covers, embedded typography, numbered figures/tables, improved mathematical notation, publication-style charts, and navigable PDF outlines.
- Large-document generation up to 4,000,000 source characters, a validated single-PDF budget of 320 estimated pages, and automatic numbered PDF ZIP bundles for larger sources.
- Structured document intermediate representation for paragraphs, lists, tables, charts, quotes, callouts, equations, diagrams, code, and page breaks.
- PDF, DOCX, and PPTX renderers with post-render quality validation.
- Idempotent creation and mutation operations.
- Correlation IDs, request limits, rate limits, expiry, cleanup, integrity checks, and safe filenames.

## Repository structure

```text
backend/   FastAPI API, model routing, artifact lifecycle, storage, tests
frontend/  React + Vite chat workspace and artifact experience
docs/      Architecture, API, and operations documentation
```

## Local development

### Backend

Use Python 3.12 or 3.13.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
cd backend
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
npm ci
printf 'VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1\n' > .env.local
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173`.

## Validation

```bash
cd backend
pytest -q

cd ../frontend
npm test
npm run build
```

The backend suite covers artifact storage, repository integrity, async jobs, API authorization, idempotency, revision/export/version lifecycle, structured IR, and PDF/DOCX/PPTX reopening. The frontend suite covers command routing, source selection, and artifact reference resolution.

## Artifact behavior

Examples:

```text
Create a professional PDF about the Serenya logo analysis.
Create a PDF from the previous answer.
Rename this PDF to Serenya-Logo-Review.pdf.
Make it shorter and add a comparison table.
Convert this document to DOCX.
Show version history.
Restore version 1.
```

A generic request such as `create a PDF` uses the latest meaningful conversation source. If no reliable source exists, Serenya asks what the document should be about rather than generating unrelated company content.

## Security notes

- Do not commit `.env` files or API keys.
- Artifact and job access tokens are capabilities and must be treated as secrets.
- The local filesystem implementation is suitable for development and single-node deployment. Production deployments should use durable database and object-storage adapters behind the documented contracts.

See:

- `docs/ARTIFACT_SYSTEM_ARCHITECTURE.md`
- `docs/ARTIFACT_API.md`
- `docs/ARTIFACT_OPERATIONS_RUNBOOK.md`
- `docs/LARGE_ARTIFACTS_V3_RELEASE_NOTES.md`
- `docs/PROFESSIONAL_PUBLISHING_V9_RELEASE_NOTES.md`
