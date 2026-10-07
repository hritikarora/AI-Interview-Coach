"""AI logic: the interviewer and the report generator (Groq)."""
import json
import logging
import os
from typing import Any, Dict, List, Literal

import groq
from dotenv import load_dotenv
from groq import Groq
from pydantic import BaseModel, Field

load_dotenv()

log = logging.getLogger("ai")

MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
TARGET_QUESTIONS = 6  # typical length for a candidate who is doing well
MAX_QUESTIONS = 8  # hard safety cap in case the model never ends the interview
PASS_THRESHOLD = 55  # "adequate" or better passes
REQUEST_TIMEOUT_S = 60

Difficulty = Literal["easy", "medium", "hard"]
Role = Literal["interviewer", "candidate"]

PLACEHOLDER_KEY = "your_groq_api_key_here"


class AIError(Exception):
    """A failure with a message that is safe and helpful to show the user."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def api_key_configured() -> bool:
    key = os.getenv("GROQ_API_KEY", "").strip()
    return bool(key) and key != PLACEHOLDER_KEY


_client = None


def get_client() -> Groq:
    global _client
    if _client is None:
        if not api_key_configured():
            raise AIError(
                "The server isn't set up yet: GROQ_API_KEY is missing in backend/.env.",
                status_code=500,
            )
        _client = Groq(api_key=os.getenv("GROQ_API_KEY").strip(), timeout=REQUEST_TIMEOUT_S, max_retries=2)
    return _client


# ---------- Models ----------

class Message(BaseModel):
    role: Role
    content: str = Field(min_length=1, max_length=8000)


class InterviewerTurn(BaseModel):
    message: str
    interview_complete: bool


class Report(BaseModel):
    score: int = Field(ge=0, le=100)
    band: Literal["Excellent", "Good", "Adequate", "Weak"]
    result: Literal["Pass", "Fail"]
    strengths: List[str]
    weaknesses: List[str]
    topics_to_revise: List[str]
    verdict: str


# ---------- Prompts ----------

DIFFICULTY_GUIDE = {
    "easy": "EASY: basic definitions, terminology and simple recall.",
    "medium": "MEDIUM: applied problems — how to use concepts in realistic scenarios, debugging, small design choices.",
    "hard": "HARD: trade-offs, system-level thinking, scalability, failure modes, comparing alternatives.",
}

INTERVIEWER_PROMPT = """You are a professional technical interviewer conducting a spoken-style interview.
Topic: {topic}
Difficulty: {difficulty_guide}

Rules:
- Ask exactly ONE question per turn, about ONE thing. Do not chain parts with "and" (e.g. NOT "explain X and when you'd use it and how it affects Y"). Keep questions to one or two sentences.
- If there is no conversation yet, greet the candidate in one short sentence and ask the first question.
- After each candidate answer, judge it:
  * Strong answer: acknowledge briefly (a few words) and move to a DIFFERENT aspect of the topic.
  * Partly right: ask ONE probing follow-up on the same point, without revealing the answer.
  * Wrong or "I don't know": note the gap in ONE neutral line (do not give the correct answer) and move on to a new aspect.
- NEVER teach, explain, correct in detail, or give hints. Never reveal correct answers.
- Stay professional, concise and encouraging.
- Pacing and ending the interview:
  * Plan to cover about {target_q} distinct key areas of the topic.
  * If the candidate is clearly struggling across several questions (e.g. 3 weak answers), end early and kindly.
  * If the candidate is doing well, end once about {target_q} key areas are covered. Do not keep going just because answers are good.
  * When ending, give a short, warm closing remark and DO NOT ask another question.
- Questions asked so far: {asked}. You MUST end the interview by question {max_q}.

Respond ONLY with JSON in this exact shape:
{{"message": "<what you say to the candidate>", "interview_complete": <true|false>}}
"""

REPORT_PROMPT = """You are an expert technical interview assessor.
Evaluate the candidate's performance in the interview transcript below.
Topic: {topic}
Difficulty: {difficulty}

Scoring bands: 85-100 excellent, 70-84 good, 55-69 adequate, below 55 weak.
Judge relative to the stated difficulty. Base everything ONLY on what the candidate actually said.
- strengths: specific points the candidate got right, referencing what they said (quote or paraphrase).
- weaknesses: specific gaps or mistakes, referencing what they said (or failed to say).
- topics_to_revise: concrete sub-topics to study.
- verdict: 2-3 sentence overall assessment.
If the candidate gave few or no answers, score low and say so.

Respond ONLY with JSON in this exact shape:
{{"score": <int 0-100>, "strengths": [<str>], "weaknesses": [<str>], "topics_to_revise": [<str>], "verdict": "<str>"}}
"""


# ---------- Helpers ----------

def _call_groq(messages: List[Dict[str, str]], temperature: float, reasoning: str) -> str:
    kwargs: Dict[str, Any] = {}
    if MODEL.startswith("openai/gpt-oss"):
        # gpt-oss "thinks" before answering; keep it short so the chat feels responsive.
        kwargs["reasoning_effort"] = reasoning
    try:
        resp = get_client().chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
            **kwargs,
        )
    except groq.AuthenticationError:
        raise AIError("The Groq API key was rejected. Check GROQ_API_KEY in backend/.env.", 500)
    except groq.PermissionDeniedError:
        raise AIError("This Groq API key isn't allowed to use the configured model.", 500)
    except groq.NotFoundError:
        raise AIError(f"The AI model '{MODEL}' isn't available. Check GROQ_MODEL in backend/.env.", 500)
    except groq.RateLimitError:
        raise AIError("The AI service is busy right now (rate limit reached). Please wait a moment and try again.", 503)
    except groq.APITimeoutError:
        raise AIError("The AI took too long to respond. Please try again.", 504)
    except groq.APIConnectionError:
        raise AIError("Couldn't reach the AI service. Check your internet connection and try again.", 503)
    except groq.BadRequestError as e:
        # Groq rejects replies that aren't valid JSON; treat it like an unreadable reply so we retry.
        if "json_validate_failed" in str(e):
            log.warning("Groq json_validate_failed; will retry")
            return ""
        log.warning("Groq returned 400: %s", e)
        raise AIError("The AI service had a problem. Please try again.", 502)
    except groq.APIStatusError as e:
        log.warning("Groq returned %s: %s", e.status_code, e)
        raise AIError("The AI service had a problem. Please try again.", 502)

    return (resp.choices[0].message.content or "") if resp.choices else ""


def _chat_json(messages: List[Dict[str, str]], temperature: float, reasoning: str = "low") -> dict:
    """Calls the model and returns its JSON reply. Retries once if the reply isn't valid JSON."""
    for attempt in (1, 2):
        raw = _call_groq(messages, temperature, reasoning)
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
        log.warning("Model returned invalid JSON (attempt %d): %.200s", attempt, raw)
    raise AIError("The AI gave an unreadable response. Please try again.", 502)


def _band(score: int) -> str:
    if score >= 85:
        return "Excellent"
    if score >= 70:
        return "Good"
    if score >= 55:
        return "Adequate"
    return "Weak"


def _transcript(history: List[Message]) -> str:
    return "\n".join(
        f"{'Interviewer' if m.role == 'interviewer' else 'Candidate'}: {m.content}" for m in history
    )


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("true", "yes", "1")
    return bool(value)


def _as_str_list(value: Any) -> List[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()]


def _as_score(value: Any) -> int:
    try:
        return max(0, min(100, round(float(value))))
    except (TypeError, ValueError):
        raise AIError("The AI returned a report without a valid score. Please try again.", 502)


# ---------- Public API ----------

def next_interviewer_turn(topic: str, difficulty: Difficulty, history: List[Message]) -> InterviewerTurn:
    asked = sum(1 for m in history if m.role == "interviewer")
    system = INTERVIEWER_PROMPT.format(
        topic=topic,
        difficulty_guide=DIFFICULTY_GUIDE[difficulty],
        asked=asked,
        max_q=MAX_QUESTIONS,
        target_q=TARGET_QUESTIONS,
    )
    messages = [{"role": "system", "content": system}]
    for m in history:
        # Interviewer turns are the assistant; candidate turns are the user.
        messages.append({"role": "assistant" if m.role == "interviewer" else "user", "content": m.content})
    if not history:
        messages.append({"role": "user", "content": "I'm ready to begin."})

    data = _chat_json(messages, temperature=0.6)
    message = str(data.get("message") or "").strip()
    if not message:
        raise AIError("The interviewer didn't respond. Please try again.", 502)
    turn = InterviewerTurn(message=message, interview_complete=_as_bool(data.get("interview_complete")))

    # Safety cap: force the end once the limit is reached.
    if asked >= MAX_QUESTIONS and not turn.interview_complete:
        turn = InterviewerTurn(
            message="That covers everything I wanted to ask. Thank you for your time — your report is ready.",
            interview_complete=True,
        )
    return turn


def generate_report(topic: str, difficulty: Difficulty, history: List[Message]) -> Report:
    messages = [
        {"role": "system", "content": REPORT_PROMPT.format(topic=topic, difficulty=difficulty)},
        {"role": "user", "content": "Transcript:\n" + _transcript(history)},
    ]
    data = _chat_json(messages, temperature=0.2, reasoning="medium")

    score = _as_score(data.get("score"))
    # Band and Pass/Fail are computed in code so they always match the score.
    return Report(
        score=score,
        band=_band(score),
        result="Pass" if score >= PASS_THRESHOLD else "Fail",
        strengths=_as_str_list(data.get("strengths")),
        weaknesses=_as_str_list(data.get("weaknesses")),
        topics_to_revise=_as_str_list(data.get("topics_to_revise")),
        verdict=str(data.get("verdict") or "").strip() or "No verdict was provided.",
    )
