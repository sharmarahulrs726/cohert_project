export interface SessionInit {
  session_id: string;
  required_files: string[];
  report_template_found: boolean;
  notice_template_found: boolean;
  message: string;
}

export interface FileUploadResponse {
  session_id: string;
  uploaded_files: string[];
  all_uploaded: boolean;
  message: string;
}

export interface SessionStatus {
  session_id: string;
  step: string;
  uploaded_files: string[];
  all_uploaded: boolean;
  report_template_found: boolean;
  notice_template_found: boolean;
  report_template_uploaded: boolean;
  notice_template_uploaded: boolean;
  all_templates_ready: boolean;
  error: string | null;
}

export interface CaseSummaryCard {
  risk_level: string;
  findings_count: number;
  notice_candidate: boolean;
  material_discrepancy_count: number;
}

export interface ReportData {
  case_summary: Record<string, unknown>;
  canonical_case: Record<string, unknown>;
  discrepancies: Record<string, unknown>[];
  llm_review: Record<string, unknown>;
  decision_type: string;
  is_notice_required: boolean;
  summary_cards: CaseSummaryCard;
  generated_files: Record<string, string>;
}

export interface NoticeData {
  case_id: string;
  assessee_name: string | null;
  pan: string | null;
  assessment_year: string | null;
  discrepancies: Record<string, unknown>[];
  llm_review: Record<string, unknown>;
  decision: Record<string, unknown>;
  notice_files: Record<string, string>;
  preview_available: boolean;
}

export interface NoticeDecisionResponse {
  session_id: string;
  notice_generated: boolean;
  notice_files: Record<string, string>;
  message: string;
}

export interface ProcessResult {
  case_id: string;
  decision_type: string;
  is_notice_required: boolean;
  output_dir: string;
  generated_files: Record<string, string>;
  canonical_case: Record<string, unknown>;
  discrepancies: Record<string, unknown>[];
  llm_review: Record<string, unknown>;
  validation: Record<string, unknown>;
  decision: Record<string, unknown>;
  context: Record<string, unknown>;
  logs?: string[];
}

export type AppStep = 'upload' | 'processing' | 'report' | 'notice_review' | 'notice_generated' | 'complete';

export interface ProgressData {
  step: string;
  progress: number;
  message: string;
  timestamp?: string;
  error?: string | null;
  result_ready?: boolean;
  logs?: string[];
  log_offset?: number;
}
