"""Simulates full interviews against the running backend (strong and struggling candidates)."""
import json
import sys
import time

import httpx

from ai import MODEL, get_client

API = "http://localhost:8000"
O = {"Origin": "http://localhost:3000"}


def strong_answer(topic, difficulty, question):
    r = get_client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": f"You are an expert candidate in a {difficulty} {topic} interview. Answer correctly and concisely in 2-4 sentences, plain text."},
            {"role": "user", "content": question},
        ],
        temperature=0.3,
    )
    return r.choices[0].message.content.strip()


def run(topic, difficulty, mode):
    print(f"\n===== {mode.upper()} | {topic} | {difficulty} =====")
    c = httpx.Client(timeout=120, headers=O)
    t = time.time()
    r = c.post(f"{API}/interview/start", json={"topic": topic, "difficulty": difficulty}).json()
    print(f"[{time.time()-t:.1f}s] AI: {r['message']}")
    turns = 0
    while not r["interview_complete"] and turns < 14:
        a = strong_answer(topic, difficulty, r["message"]) if mode == "strong" else "I'm not really sure, sorry."
        print(f"  ME: {a[:160]}")
        t = time.time()
        r = c.post(f"{API}/interview/answer", json={"topic": topic, "difficulty": difficulty, "history": r["history"], "answer": a}).json()
        turns += 1
        print(f"[{time.time()-t:.1f}s] AI ({'END' if r['interview_complete'] else 'cont'}): {r['message']}")
    q = sum(1 for m in r["history"] if m["role"] == "interviewer")
    print(f"--> ended={r['interview_complete']} after {turns} answers, {q} interviewer msgs")
    t = time.time()
    rep = c.post(f"{API}/interview/report", json={"topic": topic, "difficulty": difficulty, "history": r["history"]}).json()
    print(f"[{time.time()-t:.1f}s] REPORT:", json.dumps(rep, indent=1)[:1500])


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2], sys.argv[3])
