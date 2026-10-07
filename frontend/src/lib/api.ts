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
// Tolerates common paste mistakes: missing https://, trailing slash, or a pasted /health or /docs path.
function normaliseApiUrl(raw: string | undefined): string {
  let url = (raw || "").trim();
  if (!url) return "http://localhost:8000";
  if (!/^https?:\/\//i.test(url)) {
    url = (/^(localhost|127\.0\.0\.1)(:|$)/.test(url) ? "http://" : "https://") + url;
  }
  try {
    return new URL(url).origin; // keeps only scheme://host[:port]
  } catch {
    return url.replace(/\/$/, "");
  }
}

const API_URL = normaliseApiUrl(process.env.NEXT_PUBLIC_API_URL);

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
    let detail = `Server error (${res.status}) from ${API_URL}${path}.`;
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
