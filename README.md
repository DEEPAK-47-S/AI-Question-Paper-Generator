# NIET AI Question Paper Generator

A private, full-stack academic document intelligence system for **Nehru Institute of Engineering and Technology (NIET), Coimbatore**. Authorized teachers upload an official syllabus and supporting material, select the exact examination portion, verify a marks/unit/difficulty blueprint, and generate source-traceable question papers for review and export.

This is not a random question generator. The pipeline gives priority to:

> syllabus accuracy → selected-portion accuracy → paper pattern → academic correctness → unit coverage → difficulty → novelty

## What is implemented

- Original responsive landing page, secure staff login, teacher dashboard, and admin control center
- Admin-managed teachers, departments, subjects, semesters, regulations, assignments, account deactivation, password reset, and activity logs
- JWT authentication with bcrypt password hashes, immediate logout invalidation, role checks, ownership checks, account lockout, and non-enumerating recovery requests
- Private multi-file library with PDF, DOCX, PPTX, XLSX, CSV, TXT, image, scanned-PDF, public URL, and public Google Drive ingestion
- Legacy DOC/PPT/XLS conversion when LibreOffice is installed (included in the Docker image)
- Native text extraction, tables, OCR fallback, cleaning, deduplication, unit/topic detection, meaningful chunking, classification, and database-backed indexing
- Strict teacher/subject/category-scoped lexical RAG with a replaceable retriever interface
- Editable AI-extracted unit/topic portion checklist plus manual permitted topics
- Section pattern builder with marks, question count, type, either/or choice, difficulty distribution, and blueprint preview
- Replaceable AI service (`LocalGroundedProvider` and `OpenAICompatibleProvider`)
- Transparent local grounded development engine—it transforms retrieved text and **does not pretend to be an external AI model**
- OpenAI-compatible generation using only retrieved excerpts, followed by an independent provider validation call
- Local portion, source-topic, grammar, marks, exact/near/semantic duplicate, and paper-pattern validation
- Question provenance: unit, topic, source document, page/sheet/slide, excerpt, confidence, Bloom level, difficulty, and rationale
- Teacher editor, source explanation, deletion, same-topic regeneration, alternatives, answer keys, version duplication, draft/history, and admin approval workflow
- Professional private PDF, editable DOCX, TXT, answer-key, print, and page-numbered export paths
- Dynamic analytics—no static dashboard counts or hard-coded generated papers
- SQLite development and PostgreSQL production support
- Structured request/audit logs, friendly API errors, CSP/security headers, SSRF controls, download limits, and secret-only environment configuration
- Automated authentication, authorization, extraction, syllabus, duplicate, generation, provenance, PDF, and DOCX tests

## Architecture

```text
Browser (HTML5 + CSS3 + Vanilla JavaScript)
        │ Bearer JWT / REST
        ▼
FastAPI routers
├── Authentication / RBAC
├── Academic master data / Admin
├── Private document library
└── Blueprint / generation / editor / exports
        │
        ├── Document pipeline
        │   Validate → Extract → OCR → Clean → Structure → Chunk → Classify → Index
        │
        ├── RAG layer
        │   Owner + subject + portion filtering → lexical retrieval
        │   (replaceable by FAISS or pgvector)
        │
        ├── AI service
        │   LocalGroundedProvider | OpenAICompatibleProvider | future providers
        │
        └── Validation
            portion → grounding → duplicates → marks → second AI pass → paper totals
        │
        ▼
SQLAlchemy → SQLite / PostgreSQL
```

### Main data model

The normalized schema includes `users`, `admins`, `teachers`, `departments`, `subjects`, `semesters`, `regulations`, `syllabus_documents`, `portion_topics`, `uploaded_documents`, `document_chunks`, `document_embeddings`, `previous_question_papers`, `question_patterns`, `question_blueprints`, `generated_question_papers`, `questions`, `question_sources`, `question_bank`, `answer_keys`, `generation_logs`, `audit_logs`, and `system_settings`.

Indexes cover private owner/subject queries, document status, paper status, audit dates, and question unit/topic lookups. The `users` table is the authentication identity; role-specific profile tables avoid duplicate credentials.

## Repository layout

```text
backend/app/
├── main.py, config.py, database.py, models.py, schemas.py
├── auth/                 # passwords, JWT, RBAC, ownership
├── routers/              # REST endpoints
├── document_processing/  # extractors, OCR, URL protection, pipeline
├── rag/                  # replaceable retrieval layer
├── ai/                   # provider interface and providers
├── validators/           # duplicate and question validation
├── exporters/            # PDF, DOCX, TXT
└── services/             # audit, blueprint, generation
frontend/
├── index.html, login.html, portal.html
├── css/styles.css
└── js/login.js, js/portal.js
sample_data/              # realistic C/Python/DS/Maths syllabus fixtures
tests/
```

## Local installation (Linux/macOS)

Prerequisites: Python 3.11+, pip/venv. Install Tesseract for image/scanned-PDF OCR and LibreOffice for legacy Office formats.

```bash
git clone <repository-url>
cd AI-Question-Paper-Generator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Ubuntu/Debian document tools:

```bash
sudo apt update
sudo apt install tesseract-ocr tesseract-ocr-eng libreoffice
```

Start the application (the frontend is served by FastAPI):

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open <http://localhost:8000>. API documentation is at <http://localhost:8000/api/docs> outside production mode.

## Windows installation

Install Python 3.11+ and select **Add Python to PATH**. In PowerShell:

```powershell
git clone <repository-url>
cd AI-Question-Paper-Generator
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

If activation is blocked for the current PowerShell session:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Install [Tesseract OCR for Windows](https://github.com/UB-Mannheim/tesseract/wiki) and ensure `tesseract.exe` is on `PATH`. Install LibreOffice and ensure its program directory is on `PATH` for DOC/PPT/XLS conversion. Modern DOCX/PPTX/XLSX works directly without LibreOffice.

## Environment configuration

Copy `.env.example` and change every deployment secret.

| Variable | Purpose |
|---|---|
| `APP_ENV` | `development`, `test`, or `production` |
| `DATABASE_URL` | SQLAlchemy SQLite or PostgreSQL URL |
| `SECRET_KEY` | Random JWT signing key (32+ characters) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime |
| `AI_PROVIDER` | `local`, `openai`, or `compatible` |
| `AI_API_KEY` | External provider key; never expose in browser code |
| `AI_MODEL` | Provider model name |
| `AI_BASE_URL` | OpenAI-compatible `/v1` base URL |
| `MAX_UPLOAD_SIZE` | Per-file upload bytes |
| `URL_FETCH_MAX_BYTES` | Public URL download ceiling |
| `UPLOAD_DIR` | Private source-file directory |
| `GENERATED_DIR` | Reserved private generated-file directory |
| `VECTOR_DB_URL` | Retriever configuration placeholder |
| `OCR_LANGUAGE` | Tesseract language, default `eng` |
| `ALLOWED_ORIGINS` | Comma-separated trusted browser origins |
| `BOOTSTRAP_*` | First-run admin/teacher accounts |

Generate a secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Production startup refuses the default application secret and default admin password.

## AI setup

### Local grounded mode

```env
AI_PROVIDER=local
```

This mode is useful for secure development and tests. It performs real extraction, chunking, retrieval, provenance, duplicate checks, blueprint allocation, and deterministic source-to-question transformation. It is clearly labelled in the UI. It does **not** claim an AI technical-correctness pass; teacher technical review remains required.

### OpenAI-compatible provider

```env
AI_PROVIDER=compatible
AI_API_KEY=replace-me
AI_MODEL=gpt-4o-mini
AI_BASE_URL=https://api.openai.com/v1
```

Only top retrieved excerpts are sent. The full source document is never blindly placed in a prompt. The provider must support Chat Completions and JSON response format. Generation and independent validation are separate calls. Provider failures create a user-safe failed operation; invalid questions are removed with the partial paper.

To add a local LLM later, implement the `AIProvider` interface in `backend/app/ai/providers.py`; the document, RAG, provenance, and validation layers remain unchanged.

## Database

SQLite is automatic for development:

```env
DATABASE_URL=sqlite:///./niet_qpg.db
```

PostgreSQL example:

```env
DATABASE_URL=postgresql+psycopg://niet_qpg:strong-password@localhost:5432/niet_qpg
```

Tables and idempotent academic bootstrap records are created at startup. Use managed PostgreSQL backups, encrypted disks, and private networking in production. The application stores unpredictable UUID filenames and never serves `uploads/` as a static path.

## Docker

Create a production-strength `.env` first, then:

```bash
docker compose up --build
```

This starts PostgreSQL and the application on port 8000 with persistent private volumes. The image includes English Tesseract OCR and LibreOffice conversion. For production, set at minimum:

```env
APP_ENV=production
POSTGRES_PASSWORD=<strong-random-value>
SECRET_KEY=<strong-random-value>
BOOTSTRAP_ADMIN_PASSWORD=<strong-random-value>
BOOTSTRAP_TEACHER_PASSWORD=<strong-random-value>
```

Place the service behind TLS (Nginx, Caddy, or a managed load balancer), restrict trusted origins, use a secrets manager, encrypt volumes/backups, and run multiple API workers plus a durable task queue for heavy institutional load.

## Initial development accounts

Unless changed in `.env`:

- Administrator: `admin@niet.edu` / `ChangeMe123!`
- Teacher: `teacher@niet.edu` / `Teacher123!`

The UI exposes these only as development guidance. Change them before any shared deployment. Admin-created teachers are forced to change their temporary password.

## Key REST endpoints

- `POST /api/auth/login`, `/logout`, `/forgot-password`, `/change-password`
- `GET/POST/PUT/DELETE /api/admin/teachers`
- `GET/POST/PUT/DELETE /api/departments`, `/api/subjects`
- `POST /api/documents/upload`, `/url`, `/{id}/analyze`
- `GET /api/documents/{id}/status`, `/subject/{id}/topics`
- `POST /api/question-paper/blueprint`, `/generate`, `/validate`
- `GET /api/question-paper/operations/{id}`
- `GET /api/question-papers`, `/{id}`
- `PUT/DELETE /api/questions/{id}`, `POST /api/questions/{id}/regenerate`
- `POST /api/question-papers/{id}/approval`
- `GET /api/question-papers/{id}/export/pdf|docx|txt`

Interactive OpenAPI documentation shows the complete contracts in non-production environments.

## Testing

```bash
pytest
# or
make test
```

The suite creates an isolated SQLite database under `/tmp` and exercises authentication, teacher management, RBAC, private ownership, PDF/DOCX/XLSX/PPTX/TXT extraction, syllabus structure, portion rejection, semantic duplicates, blueprint generation, source mapping, and PDF/DOCX export.

Sample development syllabi are in `sample_data/` for C Programming, Python, Data Structures, and Engineering Mathematics.

## Security notes

- Passwords use bcrypt and are never logged. JWTs include an account auth version; logout/password reset invalidates outstanding tokens immediately.
- Login attempts lock an account temporarily after repeated failures. A distributed deployment should additionally apply gateway/Redis IP rate limiting.
- Bearer headers are used rather than authentication cookies, so cookie CSRF is not applicable. The frontend keeps tokens in `sessionStorage`, clears them on logout, and uses a restrictive CSP.
- Teacher resource failures return non-enumerating 404 responses. Admin oversight is role-authorized and audit logged.
- Public URL ingestion resolves DNS and rejects private, loopback, reserved, link-local, credential-bearing, oversized, over-redirected, and authenticated resources. Every redirect is revalidated.
- Uploaded and generated files are never exposed through predictable static URLs. Downloads pass authentication and ownership checks and set `no-store`.
- Never log source text, passwords, API keys, or database credentials. Audit details contain metadata only.
- AI coverage/confidence values are review indicators—not guarantees. Teacher review is mandatory.

## Troubleshooting

**OCR says no usable text** — verify `tesseract --version`, install the language named by `OCR_LANGUAGE`, and upload a clear 200–300 DPI scan.

**Legacy DOC/PPT/XLS fails** — install LibreOffice or save the file as DOCX/PPTX/XLSX. The failure is explicit and does not silently ignore the document.

**Google Drive is private** — set “Anyone with the link: Viewer.” The system will not bypass private sharing controls.

**Blueprint rejected** — section `count × marks` subtotals must equal total marks; difficulty and optional unit/Bloom percentages must each total 100.

**Generation reports insufficient information** — the selected topic did not have a grounded source excerpt. Upload richer syllabus/reference material or correct the extracted topic selection; the engine will not invent content.

**AI provider failed** — check `AI_BASE_URL`, model JSON-mode support, key permissions, quotas, and outbound network access. Local mode remains available for extraction/RAG testing.

**Database is locked (SQLite)** — SQLite is for local use. Move concurrent deployments to PostgreSQL.

## Production extension path

The service boundaries support pgvector/FAISS retrieval, a durable Celery/RQ worker, encrypted object storage, multiple paper sets, CO/PO mapping, moderation, notifications, OneDrive/Drive OAuth, department templates, and Anna University regulation templates without replacing the document and authorization model.

---

Built as an original NIET academic interface inspired by a professional institutional identity; no reference-site code is copied.
