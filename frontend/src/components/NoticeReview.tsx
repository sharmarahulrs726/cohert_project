import React, { useEffect, useState } from 'react';
import type { NoticeData } from '../types';
import * as apiService from '../services/api';

interface NoticeReviewProps {
  sessionId: string;
  onYes: () => void;
  onNo: () => void;
  onNewCase: () => void;
}

export const NoticeReview: React.FC<NoticeReviewProps> = ({
  sessionId,
  onYes,
  onNo,
  onNewCase,
}) => {
  const [noticeData, setNoticeData] = useState<NoticeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchNotice = async () => {
      try {
        const data = await apiService.getNotice(sessionId);
        setNoticeData(data);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Failed to load notice data');
      } finally {
        setLoading(false);
      }
    };
    fetchNotice();
  }, [sessionId]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-4 border-blue-500 border-t-transparent" />
      </div>
    );
  }

  if (error || !noticeData) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="bg-red-50 p-6 rounded-lg border border-red-300 max-w-md">
          <h3 className="text-red-700 font-semibold mb-2">Error loading notice</h3>
          <p className="text-red-600 text-sm">{error || 'No notice data available'}</p>
          <button onClick={onNewCase} className="mt-4 px-4 py-2 bg-gray-600 text-white rounded">New Case</button>
        </div>
      </div>
    );
  }

  const llm_cs = noticeData.llm_review?.case_summary as Record<string, unknown> || {};
  const findings = (noticeData.llm_review?.findings as Record<string, unknown>[]) || [];
  const highSeverityFindings = findings.filter(
    (f: Record<string, unknown>) => f.materiality === 'high' || f.status === 'confirmed'
  );

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 py-8 px-4">
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-red-100 rounded-full mb-4">
            <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-800">Review Notice Recommendation</h1>
          <p className="text-gray-500 mt-1">The system recommends issuing a notice based on the analysis</p>
        </div>

        {/* Preview cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="bg-white rounded-lg border p-4 text-center">
            <p className="text-sm text-gray-500">Risk Level</p>
            <p className="text-xl font-bold text-red-600">{String(llm_cs.overall_risk || 'N/A').toUpperCase()}</p>
          </div>
          <div className="bg-white rounded-lg border p-4 text-center">
            <p className="text-sm text-gray-500">Discrepancies</p>
            <p className="text-xl font-bold text-gray-700">{noticeData.discrepancies.length}</p>
          </div>
          <div className="bg-white rounded-lg border p-4 text-center">
            <p className="text-sm text-gray-500">High Severity Findings</p>
            <p className="text-xl font-bold text-red-600">{highSeverityFindings.length}</p>
          </div>
        </div>

        {/* Case Info */}
        <div className="bg-white rounded-lg border p-6 mb-6">
          <h3 className="font-semibold text-gray-700 mb-3">Case Details</h3>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-gray-500">Case ID</p>
              <p className="font-medium">{noticeData.case_id}</p>
            </div>
            <div>
              <p className="text-gray-500">PAN</p>
              <p className="font-medium">{noticeData.pan || 'N/A'}</p>
            </div>
            <div>
              <p className="text-gray-500">Name</p>
              <p className="font-medium">{noticeData.assessee_name || 'N/A'}</p>
            </div>
            <div>
              <p className="text-gray-500">Assessment Year</p>
              <p className="font-medium">{noticeData.assessment_year || 'N/A'}</p>
            </div>
          </div>
        </div>

        {/* Findings summary */}
        {highSeverityFindings.length > 0 && (
          <div className="bg-white rounded-lg border p-6 mb-6">
            <h3 className="font-semibold text-gray-700 mb-3">Key Findings Triggering Notice</h3>
            <div className="space-y-3">
              {highSeverityFindings.slice(0, 5).map((f: Record<string, unknown>, i: number) => (
                <div key={i} className="border-l-4 border-red-400 bg-red-50 p-3 rounded-r-lg">
                  <p className="text-sm font-medium">{String(f.finding_id || '')} - {String(f.category || '')}</p>
                  <p className="text-xs text-gray-600 mt-1">{String(f.difference_summary || '')}</p>
                  <p className="text-xs text-gray-400 mt-1">{String(f.reasoning || '')}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Notice Preview */}
        <div className="bg-white rounded-lg border p-6 mb-8">
          <h3 className="font-semibold text-gray-700 mb-3">Notice Preview</h3>
          <div className="bg-gray-50 rounded-lg p-4 border text-sm space-y-2">
            <p><strong>To:</strong> {noticeData.assessee_name || 'Taxpayer'}</p>
            <p><strong>PAN:</strong> {noticeData.pan || 'N/A'}</p>
            <p><strong>Assessment Year:</strong> {noticeData.assessment_year || 'N/A'}</p>
            <p><strong>Under:</strong> Section 133(6) of the Income Tax Act, 1961</p>
            <p className="text-gray-500 mt-2">
              Notice calling for books of accounts and supporting documents related to discrepancies identified during investigation.
            </p>
            <p className="text-xs text-gray-400 mt-2">
              A detailed notice will be generated upon confirmation.
            </p>
          </div>
        </div>

        {/* Decision */}
        <div className="text-center">
          <p className="text-lg font-medium text-gray-700 mb-6">
            Do you want to generate the Notice under Section 133(6)?
          </p>
          <div className="flex justify-center gap-4">
            <button
              onClick={onYes}
              className="px-8 py-3 bg-red-600 text-white font-semibold rounded-lg hover:bg-red-700 transition shadow-lg"
            >
              Yes, Generate Notice
            </button>
            <button
              onClick={onNo}
              className="px-8 py-3 bg-gray-200 text-gray-700 font-semibold rounded-lg hover:bg-gray-300 transition shadow"
            >
              No, Skip Notice
            </button>
          </div>
          <p className="text-xs text-gray-400 mt-4">
            If skipped, the case will be marked for next person evaluation
          </p>
        </div>
      </div>
    </div>
  );
};
