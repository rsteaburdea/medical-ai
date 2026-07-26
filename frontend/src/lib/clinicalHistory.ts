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

const KEY = "medtrain.clinical.history.v1";

export function loadHistory(): StationHistoryEntry[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as StationHistoryEntry[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveHistoryEntry(entry: StationHistoryEntry): StationHistoryEntry[] {
  const next = [entry, ...loadHistory()].slice(0, 40);
  localStorage.setItem(KEY, JSON.stringify(next));
  return next;
}

export function formatDuration(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
}
