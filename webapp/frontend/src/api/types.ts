// Mirrors webapp/backend/schemas.py. Kept as plain types (not generated)
// since the API surface is small and stable -- see docs/roadmap.rst.

export type ApplicationStatus =
  | "not_applied"
  | "viewed"
  | "applied"
  | "interview"
  | "rejected"
  | "offer"
  | "ignored";

export const APPLICATION_STATUSES: ApplicationStatus[] = [
  "not_applied",
  "viewed",
  "applied",
  "interview",
  "rejected",
  "offer",
  "ignored",
];

export interface Job {
  job_id: string;
  job_url: string;
  title: string;
  company: string;
  company_url: string | null;
  location: string;
  location_entity: string;
  search_location: string;
  salary: string;
  posted: string;
  employment_type: string;
  seniority: string;
  workplace_type: string;
  applicants: string;
  description: string;
  skills: string[];
  scraped_at: string;
  application_status: ApplicationStatus;
  notes: string;
  match_score: number | null;
  interview_date: string;
  status_updated_at: string | null;
}

export interface JobListResponse {
  items: Job[];
  total: number;
}

export interface JobUpdate {
  status?: ApplicationStatus;
  notes?: string;
  interview_date?: string;
}

export interface Stats {
  total: number;
  by_status: Record<ApplicationStatus, number>;
}

export interface Criterion {
  id: number;
  term: string;
  weight: number;
  enabled: boolean;
}

export interface CriterionInput {
  term: string;
  weight?: number;
  enabled?: boolean;
}

export interface CriterionUpdate {
  term?: string;
  weight?: number;
  enabled?: boolean;
}

export interface MatchDetail {
  term: string;
  weight: number;
  matched: boolean;
  matched_in_title: boolean;
}
