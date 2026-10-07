export type Difficulty = "easy" | "medium" | "hard";

export type Message = {
  role: "interviewer" | "candidate";
  content: string;
};

export type TurnResponse = {
  message: string;
  interview_complete: boolean;
  history: Message[];
};

export type Report = {
  score: number;
  band: "Excellent" | "Good" | "Adequate" | "Weak";
  result: "Pass" | "Fail";
  strengths: string[];
  weaknesses: string[];
  topics_to_revise: string[];
  verdict: string;
};

// Set NEXT_PUBLIC_API_URL to the backend's URL (e.g. on Vercel). It's baked in at build time.
const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

async function post<T>(path: string, body: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error("Can't reach the server. Make sure the backend is running on " + API_URL + ".");
  }

  if (!res.ok) {
    let detail = `Server error (${res.status}).`;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") detail = data.detail;
      else if (Array.isArray(data.detail)) detail = "Invalid input: " + data.detail.map((d: { msg: string }) => d.msg).join("; ");
    } catch {
      /* keep default message */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export function startInterview(topic: string, difficulty: Difficulty) {
  return post<TurnResponse>("/interview/start", { topic, difficulty });
}

export function submitAnswer(topic: string, difficulty: Difficulty, history: Message[], answer: string) {
  return post<TurnResponse>("/interview/answer", { topic, difficulty, history, answer });
}

export function generateReport(topic: string, difficulty: Difficulty, history: Message[]) {
  return post<Report>("/interview/report", { topic, difficulty, history });
}
