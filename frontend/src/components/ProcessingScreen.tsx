import React, { useEffect, useRef } from 'react';
import type { ProgressData } from '../types';

interface ProcessingScreenProps {
  messages: string[];
  progress: ProgressData | null;
  elapsed: number;
  onComplete: () => void;
  onError: (error: string) => void;
}

const STEP_LABELS: Record<string, string> = {
  queued: 'Queued',
  initializing: 'Initializing',
  extracting: 'Extracting Documents',
  mapping: 'Building Case Data',
  validating: 'Validating Data',
  discrepancies: 'Discrepancy Analysis',
  llm_review: 'LLM Forensic Review',
  decision: 'Composing Decision',
  report_gen: 'Generating Report',
  notice_gen: 'Generating Notice',
  packaging: 'Packaging Output',
  complete: 'Complete',
  error: 'Error',
};

export const ProcessingScreen: React.FC<ProcessingScreenProps> = ({
  messages,
  progress,
  elapsed,
  onComplete,
  onError,
}) => {
  const logEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll logs
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Detect completion
  useEffect(() => {
    if (progress?.step === 'complete' || progress?.result_ready) {
      const timer = setTimeout(onComplete, 1500);
      return () => clearTimeout(timer);
    }
    if (progress?.error) {
      onError(progress.error);
    }
  }, [progress, onComplete, onError]);

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  const pct = progress?.progress ?? 0;
  const currentStep = progress?.step ?? 'queued';
  const currentMsg = progress?.message ?? 'Starting pipeline...';
  const stepLabel = STEP_LABELS[currentStep] || currentStep;

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-lg p-8 max-w-2xl w-full">
        <div className="text-center mb-6">
          {pct < 100 ? (
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent mb-4" />
          ) : (
            <div className="inline-flex items-center justify-center w-12 h-12 bg-green-100 rounded-full mb-4">
              <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
          )}
          <h2 className="text-xl font-semibold text-gray-700">
            {pct < 100 ? 'Running Forensic Analysis' : 'Analysis Complete'}
          </h2>
          <p className="text-gray-400 text-sm mt-1">
            Elapsed: {formatTime(elapsed)}
            {pct > 0 && pct < 100 && ` | ${pct}%`}
          </p>
        </div>

        {/* Progress Bar */}
        <div className="w-full bg-gray-200 rounded-full h-3 mb-6 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ease-out ${
              pct >= 100 ? 'bg-green-500' : pct > 50 ? 'bg-blue-500' : 'bg-blue-400'
            }`}
            style={{ width: `${Math.max(pct, 2)}%` }}
          />
        </div>

        {/* Current Step Indicator */}
        <div className="flex items-center justify-center mb-4">
          {pct < 100 ? (
            <span className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm font-medium">
              {stepLabel}
            </span>
          ) : (
            <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm font-medium">
              Complete
            </span>
          )}
        </div>

        <p className="text-center text-gray-500 text-sm mb-4">{currentMsg}</p>

        {/* Log Messages */}
        <div className="bg-gray-900 rounded-lg p-4 max-h-64 overflow-y-auto font-mono text-sm">
          {messages.length === 0 ? (
            <p className="text-gray-500 animate-pulse">Starting pipeline...</p>
          ) : (
            messages.map((msg, i) => (
              <p
                key={i}
                className={`${
                  msg.startsWith('ERROR') ? 'text-red-400' :
                  msg.startsWith('WARNING') ? 'text-yellow-400' :
                  'text-green-400'
                } ${i === messages.length - 1 ? 'animate-pulse' : ''}`}
              >
                &gt; {msg}
              </p>
            ))
          )}
          <div ref={logEndRef} />
        </div>

        {pct >= 100 && (
          <div className="text-center mt-6">
            <button
              onClick={onComplete}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-semibold shadow"
            >
              View Report
            </button>
          </div>
        )}

        {messages.length > 0 && (
          <p className="text-center text-xs text-gray-400 mt-4">
            {messages.length} log message(s)
          </p>
        )}
      </div>
    </div>
  );
};
