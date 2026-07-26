import type { ChatMessage, ScoreResult } from "../api/client";

export interface StationHistoryEntry {
  id: string;
  at: string;
  modelId: string;
  caseId: string;
  caseTitle: string;
  overallScore: number;
  durationSeconds: number;
  passLikely: boolean;
  messages: ChatMessage[];
  score: ScoreResult;
}

/** Lightweight score log for the progression chart (independent of chat history). */
export interface ScoreProgressEntry {
  id: string;
  at: string;
  overallScore: number;
  caseTitle?: string;
  caseId?: string;
}

const HISTORY_KEY = "medtrain.clinical.history.v1";
const SCORES_KEY = "medtrain.clinical.scores.v1";

export function loadHistory(): StationHistoryEntry[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as StationHistoryEntry[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function loadScoreProgress(): ScoreProgressEntry[] {
  try {
    const raw = localStorage.getItem(SCORES_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as ScoreProgressEntry[];
      if (Array.isArray(parsed)) return parsed;
    }
  } catch {
    /* fall through to seed */
  }
  // One-time seed from existing chat history so the chart isn't empty after upgrade
  const seeded = loadHistory().map((h) => ({
    id: `score-${h.id}`,
    at: h.at,
    overallScore: h.overallScore,
    caseTitle: h.caseTitle,
    caseId: h.caseId,
  }));
  if (seeded.length > 0) {
    localStorage.setItem(SCORES_KEY, JSON.stringify(seeded));
  }
  return seeded;
}

export function saveHistoryEntry(entry: StationHistoryEntry): StationHistoryEntry[] {
  const next = [entry, ...loadHistory()].slice(0, 40);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
  appendScoreProgress({
    id: `score-${entry.id}`,
    at: entry.at,
    overallScore: entry.overallScore,
    caseTitle: entry.caseTitle,
    caseId: entry.caseId,
  });
  return next;
}

function appendScoreProgress(entry: ScoreProgressEntry): ScoreProgressEntry[] {
  // Prefer explicit scores store; avoid re-seeding from history after clear
  let existing: ScoreProgressEntry[] = [];
  try {
    const raw = localStorage.getItem(SCORES_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as ScoreProgressEntry[];
      if (Array.isArray(parsed)) existing = parsed;
    } else if (localStorage.getItem(SCORES_KEY) === null) {
      // Distinguish "never set" vs "cleared to []" — use a marker via empty array write on clear
      existing = [];
    }
  } catch {
    existing = [];
  }
  const next = [entry, ...existing].slice(0, 200);
  localStorage.setItem(SCORES_KEY, JSON.stringify(next));
  return next;
}

/** Clear chart / averages only — keeps past station chats. */
export function clearScoreProgression(): void {
  localStorage.setItem(SCORES_KEY, JSON.stringify([]));
}

/** Clear past station chats only — keeps score progression. */
export function clearStationChats(): void {
  localStorage.setItem(HISTORY_KEY, JSON.stringify([]));
}

export function formatDuration(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
}

/** Local calendar day key YYYY-MM-DD */
export function dayKey(iso: string, now = new Date()): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) {
    const fallback = now;
    return `${fallback.getFullYear()}-${String(fallback.getMonth() + 1).padStart(2, "0")}-${String(fallback.getDate()).padStart(2, "0")}`;
  }
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function formatDayLabel(key: string): string {
  const [y, m, d] = key.split("-").map(Number);
  if (!y || !m || !d) return key;
  const date = new Date(y, m - 1, d);
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

export interface DailyScorePoint {
  dateKey: string;
  label: string;
  score: number;
  count: number;
  detail: string;
}

/** One point per calendar day = arithmetic mean of that day's scores (oldest → newest). */
export function dailyAveragePoints(scores: ScoreProgressEntry[]): DailyScorePoint[] {
  const byDay = new Map<string, number[]>();
  for (const h of scores) {
    const key = dayKey(h.at);
    const list = byDay.get(key) ?? [];
    list.push(h.overallScore);
    byDay.set(key, list);
  }
  return [...byDay.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([dateKey, dayScores]) => {
      const avg = dayScores.reduce((s, n) => s + n, 0) / dayScores.length;
      const rounded = Math.round(avg * 10) / 10;
      return {
        dateKey,
        label: formatDayLabel(dateKey),
        score: rounded,
        count: dayScores.length,
        detail: `${rounded}/100 avg · ${dayScores.length} station${dayScores.length === 1 ? "" : "s"} · ${formatDayLabel(dateKey)}`,
      };
    });
}

function mean(scores: number[]): number | null {
  if (scores.length === 0) return null;
  return Math.round((scores.reduce((s, n) => s + n, 0) / scores.length) * 10) / 10;
}

export function todayAverage(scores: ScoreProgressEntry[], now = new Date()): number | null {
  const localToday = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  return mean(scores.filter((h) => dayKey(h.at) === localToday).map((h) => h.overallScore));
}

export function lastWeekAverage(scores: ScoreProgressEntry[], now = new Date()): number | null {
  const end = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59, 999);
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 6, 0, 0, 0, 0);
  const values = scores
    .filter((h) => {
      const t = new Date(h.at).getTime();
      return !Number.isNaN(t) && t >= start.getTime() && t <= end.getTime();
    })
    .map((h) => h.overallScore);
  return mean(values);
}
