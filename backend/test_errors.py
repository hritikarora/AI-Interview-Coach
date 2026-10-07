"""Checks validation, friendly errors and AI-failure handling without calling Groq."""
import types

import groq
import httpx
from fastapi.testclient import TestClient

import ai
import main

Q = {"role": "interviewer", "content": "What is a list?"}
A = {"role": "candidate", "content": "An ordered sequence."}
BASE = {"topic": "Python", "difficulty": "easy"}

failures = 0


def check(name, resp, status, contains=""):
    global failures
    body = resp.json()
    ok = resp.status_code == status and isinstance(body.get("detail", ""), str) and contains.lower() in str(body).lower()
    failures += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {name:<42} {resp.status_code}  {body.get('detail', '')}")


def fake_create(behaviour):
    def create(**_):
        if isinstance(behaviour, Exception):
            raise behaviour
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=behaviour))])
    return create


def status_err(cls, code):
    req = httpx.Request("POST", "https://api.groq.com")
    return cls("x", response=httpx.Response(code, request=req), body=None)


fake_client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace()))
ai._client = fake_client

with TestClient(main.app, raise_server_exceptions=False) as c:
    print("\n--- Input validation ---")
    check("empty topic", c.post("/interview/start", json={"topic": "   ", "difficulty": "easy"}), 422, "can't be empty")
    check("missing difficulty", c.post("/interview/start", json={"topic": "x"}), 422, "required")
    check("bad difficulty", c.post("/interview/start", json={"topic": "x", "difficulty": "insane"}), 422, "easy, medium, hard")
    check("topic too long", c.post("/interview/start", json={"topic": "x" * 201, "difficulty": "easy"}), 422, "too long")
    check("invalid JSON body", c.post("/interview/start", content=b"{oops", headers={"Content-Type": "application/json"}), 422, "valid JSON")
    check("empty answer", c.post("/interview/answer", json={**BASE, "history": [Q], "answer": "  "}), 422, "can't be empty")
    check("answer with empty history", c.post("/interview/answer", json={**BASE, "history": [], "answer": "hi"}), 422, "empty")
    check("history starts with candidate", c.post("/interview/answer", json={**BASE, "history": [A, Q], "answer": "hi"}), 422, "start with the interviewer")
    check("history not alternating", c.post("/interview/answer", json={**BASE, "history": [Q, Q], "answer": "hi"}), 422, "alternate")
    check("answer when it's not my turn", c.post("/interview/answer", json={**BASE, "history": [Q, A], "answer": "hi"}), 422, "only answer after")
    check("bad role in history", c.post("/interview/answer", json={**BASE, "history": [{"role": "bot", "content": "x"}], "answer": "hi"}), 422, "role")
    check("report with no answers", c.post("/interview/report", json={**BASE, "history": [Q]}), 422, "no answers")
    check("history too long", c.post("/interview/report", json={**BASE, "history": [Q, A] * 30}), 422, "too long")
    check("unknown route", c.get("/nope"), 404, "doesn't exist")
    check("wrong method", c.get("/interview/start"), 405, "isn't allowed")

    print("\n--- Groq failures -> friendly messages ---")
    cases = [
        ("bad API key", status_err(groq.AuthenticationError, 401), 500, "key was rejected"),
        ("model not found", status_err(groq.NotFoundError, 404), 500, "isn't available"),
        ("rate limited", status_err(groq.RateLimitError, 429), 503, "busy"),
        ("Groq 500", status_err(groq.InternalServerError, 500), 502, "had a problem"),
        ("timeout", groq.APITimeoutError(request=httpx.Request("POST", "https://x")), 504, "too long"),
        ("no internet", groq.APIConnectionError(request=httpx.Request("POST", "https://x")), 503, "couldn't reach"),
        ("garbage (non-JSON) reply", "not json at all", 502, "unreadable"),
        ("empty interviewer message", '{"message": "", "interview_complete": false}', 502, "didn't respond"),
    ]
    for name, behaviour, status, text in cases:
        fake_client.chat.completions.create = fake_create(behaviour)
        check(name, c.post("/interview/start", json=BASE), status, text)

    fake_client.chat.completions.create = fake_create('{"score": "not a number"}')
    check("report with no valid score", c.post("/interview/report", json={**BASE, "history": [Q, A]}), 502, "valid score")

    fake_client.chat.completions.create = fake_create(lambda: 1 / 0)  # not an exception instance -> returns weird object
    original = ai._call_groq
    ai._call_groq = lambda *a, **k: (_ for _ in ()).throw(ZeroDivisionError("boom"))
    check("unexpected server bug", c.post("/interview/start", json=BASE), 500, "something went wrong")
    ai._call_groq = original

    print("\n--- Messy but usable AI output is cleaned up ---")
    fake_client.chat.completions.create = fake_create('{"message": "  Hi! What is a list?  ", "interview_complete": "false"}')
    r = c.post("/interview/start", json={"topic": "  Python  ", "difficulty": " EASY "})
    check("string 'false' + whitespace + caps difficulty", r, 200)
    print("      ->", r.json()["message"], "| complete:", r.json()["interview_complete"])

    fake_client.chat.completions.create = fake_create('{"score": 87.6, "strengths": "Knew lists", "weaknesses": null, "topics_to_revise": ["", "Slicing"], "verdict": ""}')
    r = c.post("/interview/report", json={**BASE, "history": [Q, A]})
    check("float score, string list, null, blanks", r, 200)
    print("      ->", r.json())

print(f"\n{'ALL CHECKS PASSED' if not failures else f'{failures} CHECK(S) FAILED'}")
