import axios from 'axios';
import type {
  SessionInit,
  FileUploadResponse,
  SessionStatus,
  ProcessResult,
  ReportData,
  NoticeData,
  NoticeDecisionResponse,
  ProgressData,
} from '../types';

const API_BASE = import.meta.env.VITE_API_URL || 'https://rahulsharma713096-hf-cohort.hf.space/api';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 300000,
});


export async function initSession(): Promise<SessionInit> {
  const { data } = await api.post('/session/init');
  return data;
}

export async function uploadFile(
  sessionId: string,
  file: File
): Promise<FileUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await api.post(`/session/${sessionId}/upload`, formData);
  return data;
}

export async function uploadTemplate(
  sessionId: string,
  templateType: 'report' | 'notice',
  file: File
): Promise<void> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('template_type', templateType);
  await api.post(`/session/${sessionId}/upload-template`, formData);
}

export async function getSessionStatus(sessionId: string): Promise<SessionStatus> {
  const { data } = await api.get(`/session/${sessionId}/status`);
  return data;
}

export async function startProcessing(sessionId: string): Promise<ProcessResult> {
  const { data } = await api.post(`/session/${sessionId}/process`);
  return data;
}

export async function getReport(sessionId: string): Promise<ReportData> {
  const { data } = await api.get(`/session/${sessionId}/report`);
  return data;
}

export async function getNotice(sessionId: string): Promise<NoticeData> {
  const { data } = await api.get(`/session/${sessionId}/notice`);
  return data;
}

export async function submitNoticeDecision(
  sessionId: string,
  generateNotice: boolean
): Promise<NoticeDecisionResponse> {
  const { data } = await api.post(`/session/${sessionId}/notice-decision`, {
    session_id: sessionId,
    generate_notice: generateNotice,
  });
  return data;
}

export async function getLogs(sessionId: string, offset: number = 0): Promise<{logs: string[], total: number}> {
  const { data } = await api.get(`/session/${sessionId}/logs`, { params: { offset } });
  return data;
}

export async function getProgress(sessionId: string): Promise<ProgressData> {
  const { data } = await api.get(`/session/${sessionId}/progress`);
  return data;
}

export function getFileUrl(sessionId: string, filename: string): string {
  return `${API_BASE}/files/${sessionId}/${filename}`;
}
