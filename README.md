# 🏥 MedRAG — Doctor RAG System
### Production-ready Clinical Intelligence with Zero-Hallucination Architecture

---

## 🗂 Project Structure

```
doctor-rag/
├── backend/                          # Django REST API
│   ├── core/
│   │   ├── settings.py               # Full config (MySQL, Qdrant, JWT, Redis)
│   │   ├── urls.py                   # Root URL router
│   │   └── celery.py                 # Async task queue
│   ├── apps/
│   │   ├── accounts/                 # Doctor auth (JWT + custom user model)
│   │   │   ├── models.py             # Doctor + QueryHistory models
│   │   │   ├── views.py              # Login, Register, Logout, Profile, History
│   │   │   └── serializers.py
│   │   ├── rag/
│   │   │   ├── rag_engine.py         # ⭐ Core RAG orchestrator (LangChain + OpenAI)
│   │   │   ├── vector_store.py       # ⭐ Qdrant CRUD (upsert, search, delete)
│   │   │   ├── hallucination_guard.py# ⭐ Anti-hallucination engine (3 layers)
│   │   │   ├── tasks.py              # Celery: async document ingestion
│   │   │   └── views.py              # /query/ + /voice/query/ endpoints
│   │   └── documents/
│   │       ├── models.py             # MedicalDocument model
│   │       └── views.py              # Upload, list, delete, reindex
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── index.html                    # Login / Register page
│   ├── dashboard.html                # Main clinical workspace
│   ├── css/styles.css                # Design system (dark clinical)
│   └── js/
│       ├── api.js                    # HTTP client + JWT auto-refresh
│       ├── auth.js                   # Login/register/logout/session guard
│       ├── voice.js                  # MediaRecorder → Whisper → TTS
│       └── chat.js                   # Full dashboard controller
├── docker-compose.yml                # Full stack (MySQL + Qdrant + Redis + Django + Nginx)
└── nginx.conf                        # Reverse proxy config
```

---

## ⚡ Quick Start

### Option A — Docker (recommended)

```bash
git clone <repo>
cd doctor-rag

# Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env with your OpenAI API key, MySQL password, etc.

# Start full stack
docker-compose up --build

# Access:
# Frontend  → http://localhost
# API       → http://localhost/api/v1/
# Qdrant UI → http://localhost:6333/dashboard
```

### Option B — Local development

```bash
# 1. Start services
docker-compose up db qdrant redis -d

# 2. Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your values

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver

# 3. Celery worker (new terminal)
celery -A core.celery worker --loglevel=info

# 4. Frontend (any static server)
cd ../frontend
python -m http.server 5500
# → http://localhost:5500
```

---

## 🛡 Anti-Hallucination Architecture

The hallucination guard (`apps/rag/hallucination_guard.py`) is the most critical component.

### 3-Layer Verification

| Layer | Method | Weight | Description |
|-------|--------|--------|-------------|
| 1 | **Token Overlap** | 35% | Are key medical terms from the answer present in retrieved chunks? |
| 2 | **Semantic Similarity** | 65% | Sentence-level cosine similarity against chunk corpus |
| 3 | **LLM Self-Check** | Optional | LLM verifies its own claims against sources |

### Confidence Scoring

```
confidence_score = 0.35 × token_overlap + 0.65 × semantic_similarity

≥ 0.85  → HIGH       ✅ Safe to use
≥ 0.65  → MEDIUM     ⚠ Use with caution
≥ 0.45  → LOW        ⚠ Verify before use
< 0.45  → CRITICAL   🚨 BLOCKED — Hallucination risk
```

### Strict Prompt Enforcer

The system prompt **explicitly forbids** the LLM from using parametric knowledge:
```
"You MUST answer ONLY using the information in <context> blocks.
You are STRICTLY FORBIDDEN from adding facts not in the context.
If context is insufficient, you MUST say so."
```

---

## 🔌 API Reference

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register/` | Register new doctor |
| POST | `/api/v1/auth/login/` | Login → JWT tokens |
| POST | `/api/v1/auth/logout/` | Blacklist refresh token |
| POST | `/api/v1/auth/token/refresh/` | Refresh access token |
| GET/PUT | `/api/v1/auth/profile/` | Doctor profile |
| GET | `/api/v1/auth/history/` | Query history |
| GET | `/api/v1/auth/stats/` | Dashboard analytics |

### RAG
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/rag/query/` | Text RAG query |
| POST | `/api/v1/rag/voice/query/` | Voice → Whisper → RAG → TTS |
| GET | `/api/v1/rag/collection/stats/` | Qdrant vector count |

### Documents
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/v1/documents/` | List / Upload PDF/DOCX/TXT |
| GET/DELETE | `/api/v1/documents/<id>/` | Get / Delete document |
| POST | `/api/v1/documents/<id>/reindex/` | Re-trigger Qdrant indexing |

### Query Request/Response

**POST `/api/v1/rag/query/`**
```json
// Request
{
  "question": "What is the first-line treatment for hypertension?",
  "specialty_filter": "cardiology",
  "top_k": 5
}

// Response
{
  "answer": "## First-Line Hypertension Treatment\n...",
  "confidence_score": 0.87,
  "confidence_label": "high",
  "is_hallucination_risk": false,
  "warning_message": "",
  "sources": [
    {
      "doc_id": "uuid",
      "source": "WHO_HTN_Guidelines_2023.pdf",
      "title": "WHO Hypertension Guidelines",
      "speciality": "cardiology",
      "date": "2023",
      "score": 0.94
    }
  ],
  "retrieved_chunks": [...],
  "sentence_grounding": [
    { "sentence": "...", "max_similarity": 0.91, "grounded": true, "best_source": "..." }
  ],
  "chunks_retrieved": 5,
  "response_time_ms": 1243
}
```

---

## 📦 Qdrant Chunk Schema

```json
{
  "chunk_text": "Patients with stage 1 hypertension (BP ≥ 130/80) should...",
  "doc_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "speciality": "cardiology",
  "date": "2023",
  "source": "WHO_HTN_Guidelines_2023.pdf",
  "title": "WHO Hypertension Guidelines 2023",
  "chunk_index": 4,
  "total_chunks": 47
}
```

---

## 🗄 Database Models (MySQL)

| Table | Key Fields |
|-------|-----------|
| `doctors` | id (UUID), email, specialty, license_number, is_verified |
| `query_history` | doctor FK, query, answer, confidence_score, is_hallucination_risk, sources (JSON) |
| `medical_documents` | title, file_type, specialty, status, chunk_count, qdrant_ids (JSON) |

---

## 🔐 Security

- JWT with refresh token rotation and blacklisting
- Rate limiting: 20 req/min anon, 100 req/min authenticated
- File type validation (PDF/DOCX/TXT only)
- CORS configured
- Strict SQL via `STRICT_TRANS_TABLES`
- Passwords validated by Django's built-in validators

---

## 🎙 Voice AI Flow

```
Doctor speaks → MediaRecorder (WebM/Opus)
                     ↓
              POST /rag/voice/query/
                     ↓
              Whisper STT (local model)
                     ↓
              RAG Engine (same as text)
                     ↓
              gTTS Text-to-Speech
                     ↓
              Return: transcript + rag_result + audio_url
```

---

## 🌱 Environment Variables

See `backend/.env.example` for full list. Key variables:

```env
OPENAI_API_KEY=sk-...
OPENAI_CHAT_MODEL=gpt-4o
MIN_CONFIDENCE_THRESHOLD=0.45   # answers below this trigger hallucination warning
SIMILARITY_TOP_K=5              # chunks retrieved per query
WHISPER_MODEL_SIZE=base         # tiny|base|small|medium|large
```
#   R A G - D o c t o r - 3  
 