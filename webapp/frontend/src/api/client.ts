import type {
  Criterion,
  CriterionInput,
  CriterionUpdate,
  Job,
  JobListResponse,
  JobUpdate,
  MatchDetail,
  Stats,
} from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(response.status, body?.detail ?? response.statusText);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

export interface JobListParams {
  status?: string;
  search?: string;
  min_score?: number;
  title?: string;
  company?: string;
  location?: string;
  posted?: string;
  job_id?: string;
  search_location?: string;
  notes?: string;
  salary?: string;
  employment_type?: string;
  seniority?: string;
  applicants?: string;
  sort_by?: string;
  sort_dir?: "ASC" | "DESC";
  limit?: number;
  offset?: number;
}

function toQueryString(params: object): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params) as [string, unknown][]) {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  }
  const queryString = query.toString();
  return queryString ? `?${queryString}` : "";
}

export const api = {
  listJobs: (params: JobListParams = {}) =>
    request<JobListResponse>(`/api/jobs${toQueryString(params)}`),

  getJob: (jobId: string) => request<Job>(`/api/jobs/${jobId}`),

  updateJob: (jobId: string, update: JobUpdate) =>
    request<Job>(`/api/jobs/${jobId}`, {
      method: "PATCH",
      body: JSON.stringify(update),
    }),

  deleteJob: (jobId: string) =>
    request<void>(`/api/jobs/${jobId}`, { method: "DELETE" }),

  getScoreBreakdown: (jobId: string) =>
    request<MatchDetail[]>(`/api/jobs/${jobId}/score-breakdown`),

  getStats: () => request<Stats>("/api/stats"),

  listCriteria: () => request<Criterion[]>("/api/criteria"),

  addCriterion: (criterion: CriterionInput) =>
    request<Criterion>("/api/criteria", {
      method: "POST",
      body: JSON.stringify(criterion),
    }),

  updateCriterion: (id: number, update: CriterionUpdate) =>
    request<Criterion>(`/api/criteria/${id}`, {
      method: "PATCH",
      body: JSON.stringify(update),
    }),

  deleteCriterion: (id: number) =>
    request<void>(`/api/criteria/${id}`, { method: "DELETE" }),

  recalculateScores: () =>
    request<{ updated: number }>("/api/scores/recalculate", { method: "POST" }),
};

export { ApiError };
