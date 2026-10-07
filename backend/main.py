"""AI Interview Coach — FastAPI backend.

Stateless: the frontend keeps the conversation (`history`) and sends it back on every call.
"""
import logging
import os
import re
from contextlib import asynccontextmanager
from typing import List

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator, model_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

from ai import (
    MODEL,
    AIError,
    Difficulty,
    InterviewerTurn,
    Message,
    Report,
    api_key_configured,
    generate_report,
    next_interviewer_turn,
)

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s - %(message)s")
log = logging.getLogger("api")

MAX_HISTORY = 40  # far more than a real interview (max 8 questions) needs

# Hosts like Render set PORT; locally it defaults to 8000.
PORT = int(os.getenv("PORT", "8000"))

# Local frontends on any port are always allowed. Deployed frontends are added via env:
#   ALLOWED_ORIGINS=https://ai-interview-coach.vercel.app,https://my-domain.com
LOCAL_ORIGIN_REGEX = r"http://(localhost|127\.0\.0\.1)(:\d+)?"
ALLOWED_ORIGINS = [o.strip().rstrip("/") for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
ORIGIN_REGEX = "^(" + "|".join([LOCAL_ORIGIN_REGEX] + [re.escape(o) for o in ALLOWED_ORIGINS]) + ")$"


# ---------- Startup banner ----------

@asynccontextmanager
async def lifespan(_: FastAPI):
    line = "=" * 60
    key_ok = api_key_configured()
    print(f"\n{line}\n  AI Interview Coach — backend is running")
    print(f"  Port:    {PORT}   (local: http://localhost:{PORT})")
    print("  Docs:    /docs     Health: /health")
    print(f"  Model:   {MODEL}")
    print(f"  API key: {'configured ✓' if key_ok else 'MISSING ✗'}")
    print(f"  Allowed frontends: localhost (any port){''.join(', ' + o for o in ALLOWED_ORIGINS)}")
    if not key_ok:
        print("\n  ⚠  Set GROQ_API_KEY (in backend/.env locally, or in your host's environment settings).")
        print("     Interviews will fail until you do.")
    print(f"{line}\n", flush=True)
    yield


app = FastAPI(title="AI Interview Coach API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=ORIGIN_REGEX,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ---------- Friendly errors (always {"detail": "<readable message>"}) ----------

FIELD_NAMES = {
    "topic": "Topic",
    "difficulty": "Difficulty",
    "answer": "Answer",
    "history": "Conversation",
}


def _friendly_validation_message(exc: RequestValidationError) -> str:
    err = exc.errors()[0] if exc.errors() else {}
    loc = [str(p) for p in err.get("loc", []) if p != "body"]
    kind = err.get("type", "")
    ctx = err.get("ctx") or {}

    if kind == "json_invalid":
        return "The request body isn't valid JSON."
    if not loc:
        return str(err.get("msg", "Invalid request.")).removeprefix("Value error, ")

    field = FIELD_NAMES.get(loc[0], loc[0])
    if loc[0] == "history" and len(loc) > 1:
        field = "A message in the conversation"

    if kind == "missing":
        return f"{field} is required."
    if kind == "literal_error" and loc[0] == "difficulty":
        return "Difficulty must be one of: easy, medium, hard."
    if kind == "literal_error":
        return f"{field} has an invalid role (must be 'interviewer' or 'candidate')."
    if kind in ("string_too_short", "too_short"):
        return f"{field} can't be empty."
    if kind == "string_too_long":
        return f"{field} is too long (max {ctx.get('max_length')} characters)."
    if kind == "too_long":
        return f"{field} is too long."
    if kind in ("string_type", "list_type", "dict_type", "model_type"):
        return f"{field} has the wrong format."
    if kind == "value_error":
        return str(err.get("msg", "")).replace("Value error, ", "")
    return f"{field}: {err.get('msg', 'invalid value')}"


@app.exception_handler(RequestValidationError)
async def on_validation_error(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": _friendly_validation_message(exc)})


@app.exception_handler(AIError)
async def on_ai_error(_: Request, exc: AIError):
    log.warning("AI error (%s): %s", exc.status_code, exc.message)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(StarletteHTTPException)
async def on_http_error(_: Request, exc: StarletteHTTPException):
    messages = {404: "That endpoint doesn't exist.", 405: "That method isn't allowed on this endpoint."}
    detail = exc.detail if isinstance(exc.detail, str) and exc.status_code not in messages else messages.get(exc.status_code, str(exc.detail))
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})


@app.exception_handler(Exception)
async def on_unexpected_error(_: Request, exc: Exception):
    log.exception("Unexpected error: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on the server. Please try again."})


ERROR_RESPONSES = {
    400: {"description": "Request doesn't make sense (e.g. wrong conversation order)"},
    422: {"description": "Invalid input"},
    500: {"description": "Server misconfigured (e.g. missing or invalid GROQ_API_KEY)"},
    502: {"description": "AI provider returned an error or unusable response"},
    503: {"description": "AI provider busy or unreachable"},
    504: {"description": "AI provider timed out"},
}


# ---------- Request / response shapes ----------

class StartRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    difficulty: Difficulty

    @field_validator("topic", mode="before")
    @classmethod
    def _strip_topic(cls, v):
        return v.strip() if isinstance(v, str) else v

    @field_validator("difficulty", mode="before")
    @classmethod
    def _normalise_difficulty(cls, v):
        return v.strip().lower() if isinstance(v, str) else v


def _check_history(history: List[Message]) -> List[Message]:
    if history[0].role != "interviewer":
        raise ValueError("The conversation must start with the interviewer.")
    for prev, cur in zip(history, history[1:]):
        if prev.role == cur.role:
            raise ValueError("The conversation must alternate between interviewer and candidate.")
    for m in history:
        if not m.content.strip():
            raise ValueError("The conversation contains an empty message.")
    return history


class AnswerRequest(StartRequest):
    history: List[Message] = Field(min_length=1, max_length=MAX_HISTORY)
    answer: str = Field(min_length=1, max_length=5000)

    @field_validator("answer", mode="before")
    @classmethod
    def _strip_answer(cls, v):
        return v.strip() if isinstance(v, str) else v

    @model_validator(mode="after")
    def _validate_history(self):
        _check_history(self.history)
        if self.history[-1].role != "interviewer":
            raise ValueError("You can only answer after the interviewer has asked a question.")
        return self


class ReportRequest(StartRequest):
    history: List[Message] = Field(min_length=1, max_length=MAX_HISTORY)

    @model_validator(mode="after")
    def _validate_history(self):
        _check_history(self.history)
        if not any(m.role == "candidate" for m in self.history):
            raise ValueError("There are no answers to evaluate yet.")
        return self


class TurnResponse(InterviewerTurn):
    history: List[Message]  # full updated conversation, to send back next time


def _turn(topic: str, difficulty: str, history: List[Message]) -> TurnResponse:
    turn = next_interviewer_turn(topic, difficulty, history)
    return TurnResponse(
        message=turn.message,
        interview_complete=turn.interview_complete,
        history=history + [Message(role="interviewer", content=turn.message)],
    )


# ---------- Routes ----------

@app.get("/")
def root():
    return {"message": "AI Interview Coach backend is running.", "health": "/health", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL, "groq_key_configured": api_key_configured()}


@app.post("/interview/start", response_model=TurnResponse, responses=ERROR_RESPONSES)
def start_interview(req: StartRequest):
    """Topic + difficulty in, greeting + first question out."""
    return _turn(req.topic, req.difficulty, [])


@app.post("/interview/answer", response_model=TurnResponse, responses=ERROR_RESPONSES)
def submit_answer(req: AnswerRequest):
    """Candidate's answer in, interviewer's next message + interview_complete out."""
    history = req.history + [Message(role="candidate", content=req.answer)]
    return _turn(req.topic, req.difficulty, history)


@app.post("/interview/report", response_model=Report, responses=ERROR_RESPONSES)
def interview_report(req: ReportRequest):
    """Full conversation in, structured scored report out."""
    return generate_report(req.topic, req.difficulty, req.history)
