import { useState, useCallback, useRef } from 'react';
import type { AppStep, ProcessResult, ReportData, ProgressData } from '../types';
import * as apiService from '../services/api';

const POLL_INTERVAL = 2000; // 2 seconds
const TIMEOUT_SECONDS = 600; // 10 minutes max

interface UploadedFiles {
  form16: File | null;
  ais: File | null;
  itr: File | null;
}

export function useCaseProcessing() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [step, setStep] = useState<AppStep>('upload');
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFiles>({
    form16: null,
    ais: null,
    itr: null,
  });
  const [uploadedNames, setUploadedNames] = useState<string[]>([]);
  const [uploadedFilenames, setUploadedFilenames] = useState<Record<string, string>>({});
  const [processing, setProcessing] = useState(false);
  const [processingMessages, setProcessingMessages] = useState<string[]>([]);
  const [progress, setProgress] = useState<ProgressData | null>(null);
  const [processResult, setProcessResult] = useState<ProcessResult | null>(null);
  const [reportData, setReportData] = useState<ReportData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [reportTemplateFound, setReportTemplateFound] = useState(true);
  const [noticeTemplateFound, setNoticeTemplateFound] = useState(true);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const processingRef = useRef(false);

  const _stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const _startPolling = useCallback((sid: string) => {
    _stopPolling();
    setElapsed(0);

    // Start elapsed timer
    timerRef.current = setInterval(() => {
      setElapsed(prev => prev + 1);
    }, 1000);

    // Start progress polling
    pollRef.current = setInterval(async () => {
      try {
        const pdata = await apiService.getProgress(sid);
        setProgress(pdata);

        // Append new logs
        if (pdata.logs && pdata.logs.length > 0) {
          setProcessingMessages(prev => [...prev, ...pdata.logs!]);
        }

        // Check for errors
        if (pdata.error) {
          _stopPolling();
          setError(pdata.error);
          setProcessing(false);
          setStep('upload');
          return;
        }

        // Check for completion
        if (pdata.result_ready || pdata.step === 'report') {
          _stopPolling();
          setProcessing(false);
          // Fetch the report
          try {
            const report = await apiService.getReport(sid);
            setReportData(report);
            setStep('report');
          } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : 'Failed to fetch report';
            setError(msg);
            setStep('upload');
          }
          return;
        }

        // Check for timeout
        if (elapsed > TIMEOUT_SECONDS) {
          _stopPolling();
          setError('Processing timed out. Please try again.');
          setProcessing(false);
          setStep('upload');
        }
      } catch {
        // Polling errors are expected, ignore
      }
    }, POLL_INTERVAL);
  }, [_stopPolling, elapsed]);

  const clearSession = useCallback(() => {
    _stopPolling();
    setSessionId(null);
    setStep('upload');
    setUploadedFiles({ form16: null, ais: null, itr: null });
    setUploadedNames([]);
    setUploadedFilenames({});
    setProcessing(false);
    setProcessingMessages([]);
    setProgress(null);
    setProcessResult(null);
    setReportData(null);
    setError(null);
    setElapsed(0);
    processingRef.current = false;
  }, [_stopPolling]);

  const createSession = useCallback(async () => {
    setError(null);
    try {
      const init = await apiService.initSession();
      setSessionId(init.session_id);
      setStep('upload');
      setReportTemplateFound(init.report_template_found);
      setNoticeTemplateFound(init.notice_template_found);
      setUploadedNames([]);
      setUploadedFiles({ form16: null, ais: null, itr: null });
      setUploadedFilenames({});
      return init;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create session';
      setError(msg);
      throw err;
    }
  }, []);

  const handleFileUpload = useCallback(async (file: File) => {
    if (!sessionId) return;
    setError(null);
    try {
      const resp = await apiService.uploadFile(sessionId, file);
      setUploadedNames(resp.uploaded_files);

      const norm = file.name.toLowerCase().replace(/[-_.]+/g, ' ');
      let ftype: string;
      if (/form\s*16/.test(norm)) {
        ftype = 'form16';
        setUploadedFiles(prev => ({ ...prev, form16: file }));
      } else if (norm.includes('ais')) {
        ftype = 'ais';
        setUploadedFiles(prev => ({ ...prev, ais: file }));
      } else if (norm.includes('itr')) {
        ftype = 'itr';
        setUploadedFiles(prev => ({ ...prev, itr: file }));
      } else {
        ftype = 'unknown';
      }
      setUploadedFilenames(prev => ({ ...prev, [ftype]: file.name }));

      return resp;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Upload failed';
      setError(msg);
      throw err;
    }
  }, [sessionId]);

  const startProcess = useCallback(async () => {
    if (!sessionId) return;
    setError(null);
    setProcessing(true);
    setProcessingMessages([]);
    setProgress(null);
    setElapsed(0);
    setStep('processing');
    processingRef.current = true;

    // Start polling BEFORE firing the process request
    _startPolling(sessionId);

    // Fire and forget the backend process
    try {
      await apiService.startProcessing(sessionId);
    } catch (err: unknown) {
      _stopPolling();
      const msg = err instanceof Error ? err.message : 'Failed to start processing';
      setError(msg);
      setProcessing(false);
      setStep('upload');
      processingRef.current = false;
    }
  }, [sessionId, _startPolling, _stopPolling]);

  const goToNoticeReview = useCallback(() => {
    setStep('notice_review');
  }, []);

  const handleNoticeDecision = useCallback(async (generateNotice: boolean) => {
    if (!sessionId) return;
    setError(null);
    try {
      const resp = await apiService.submitNoticeDecision(sessionId, generateNotice);
      if (generateNotice) {
        setStep('notice_generated');
      } else {
        setStep('complete');
      }
      return resp;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Notice decision failed';
      setError(msg);
      throw err;
    }
  }, [sessionId]);

  const getNoticeData = useCallback(async () => {
    if (!sessionId) return null;
    const data = await apiService.getNotice(sessionId);
    return data;
  }, [sessionId]);

  const allUploaded = uploadedNames.length >= 3;

  return {
    sessionId,
    step,
    uploadedFiles,
    uploadedNames,
    uploadedFilenames,
    allUploaded,
    processing,
    processingMessages,
    progress,
    elapsed,
    processResult,
    reportData,
    error,
    reportTemplateFound,
    noticeTemplateFound,
    createSession,
    handleFileUpload,
    startProcess,
    goToNoticeReview,
    handleNoticeDecision,
    getNoticeData,
    clearSession,
    setError,
  };
}
