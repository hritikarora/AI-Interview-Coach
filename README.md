# AI Interview Coach

Type a technical topic, pick Easy / Medium / Hard, and an AI interviewer asks you one question at a
time, decides when the interview is over, then gives you a scored report with Pass or Fail.

- `frontend/` — Next.js (TypeScript, Tailwind)
- `backend/` — FastAPI + Groq

## Run locally

```bash
# Backend (terminal 1)
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # then put your Groq key in .env
.venv/bin/uvicorn main:app --reload --port 8000

# Frontend (terminal 2)
cd frontend
npm install
cp .env.example .env.local
npm run dev                   # http://localhost:3000
```

## Environment variables

| Where | Variable | Example |
|---|---|---|
| Backend | `GROQ_API_KEY` (required) | `gsk_...` |
| Backend | `GROQ_MODEL` | `openai/gpt-oss-120b` |
| Backend | `ALLOWED_ORIGINS` | `https://your-app.vercel.app` |
| Frontend | `NEXT_PUBLIC_API_URL` | `https://your-backend.onrender.com` |
