# SMULitHack · Aithena

React + Vite + TypeScript + Tailwind frontend for Track 1. Everything remains local until you choose to commit and push.

## Run locally

Install Node.js 22.12+ (Node 24 LTS recommended) and pnpm. Then from the repository root:

```sh
cd frontend
pnpm install --frozen-lockfile
pnpm run dev
```

Open the URL printed in your terminal. The frontend starts in clearly labelled sample mode with four synthetic contracts. Navigation, contract search/filter, evidence views, the 90-day calendar, potential conflicts, and review-brief downloads work. File selection and drag-and-drop work locally; real uploads require the backend.

The project uses esbuild's platform binary from its optional dependencies; its extra install script is disabled in `pnpm-workspace.yaml`.

## Team handoff

- Frontend: `frontend/src/App.tsx` (screens), `styles.css` (appearance), `data.ts` (API adapter and validation).
- Shared response types: `shared/types.ts`.
- Working example JSON: `shared/sample-portfolio.json`.
- OCR/extraction/conflict interfaces and ownership: [Integration guide](docs/INTEGRATION.md).
- Synthetic source transcriptions: `sample-contracts/`.

Agree who owns obligation extraction and the FastAPI assembly routes. OCR supplies text; extraction identifies obligations; conflict detection compares those obligations. Neither OCR nor the frontend implements the extraction step.

## Connect the backend

Create `frontend/.env.local` with:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Restart Vite. The backend must serve `GET /portfolio` and `POST /documents` as described in the integration guide. No backend, OCR, AI extraction, or conflict detection engine is implemented here. Source evidence currently displays text pages; a PDF renderer with coordinate highlights can be connected later.

## Check changes

```sh
cd frontend
pnpm test
pnpm run build
```

The frontend validates response schemas, IDs, page references, literal quote matching, and date formats. This does not validate legal correctness or confidence calibration. Demo confidence is illustrative. The sample scan is a simulated poor OCR transcription, not a real scanned PDF.

An optional read-only `read_contract_portfolio` WebMCP tool is feature-detected for supporting browsers. Unsupported browsers use the ordinary interface. This tool's browser registration has not been verified in a WebMCP-capable browser.
