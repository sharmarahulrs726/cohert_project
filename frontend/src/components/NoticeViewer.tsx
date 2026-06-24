import React, { useEffect, useState } from 'react';
import type { NoticeData } from '../types';
import * as apiService from '../services/api';

interface NoticeViewerProps {
  sessionId: string;
  onNewCase: () => void;
}

type FileTab = 'docx' | 'pdf' | 'data';

export const NoticeViewer: React.FC<NoticeViewerProps> = ({ sessionId, onNewCase }) => {
  const [noticeData, setNoticeData] = useState<NoticeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pdfError, setPdfError] = useState(false);
  const [activeTab, setActiveTab] = useState<FileTab>('docx');

  useEffect(() => {
    const fetchNotice = async () => {
      try {
        const data = await apiService.getNotice(sessionId);
        setNoticeData(data);
        if (data.notice_files?.['Notice.docx']) {
          setActiveTab('docx');
        } else if (data.notice_files?.['Notice.pdf']) {
          setActiveTab('pdf');
        } else {
          setActiveTab('data');
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Failed to load notice');
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

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="bg-red-50 p-6 rounded-lg border border-red-300">
          <h3 className="text-red-700 font-semibold">Error</h3>
          <p className="text-red-600 text-sm mt-1">{error}</p>
          <button onClick={onNewCase} className="mt-4 px-4 py-2 bg-gray-600 text-white rounded">New Case</button>
        </div>
      </div>
    );
  }

  const hasDocx = noticeData?.notice_files?.['Notice.docx'] != null;
  const hasPdf = noticeData?.notice_files?.['Notice.pdf'] != null;
  const hasFallback = noticeData?.notice_files?.['Notice_Fallback.json'] != null;
  const hasNoFiles = !hasDocx && !hasPdf && !hasFallback;

  const tabs: { key: FileTab; label: string; enabled: boolean }[] = [
    { key: 'docx', label: 'DOCX (Editable)', enabled: hasDocx },
    { key: 'pdf', label: 'PDF (Preview)', enabled: hasPdf },
    { key: 'data', label: 'Notice Data', enabled: true },
  ];

  const active = tabs.find(t => t.key === activeTab) || tabs[0];
  if (!active.enabled) {
    const firstEnabled = tabs.find(t => t.enabled);
    if (firstEnabled && activeTab !== firstEnabled.key) {
      setActiveTab(firstEnabled.key);
    }
  }

  const calcTabClass = (tab: typeof tabs[0]) =>
    `px-4 py-2 text-sm font-medium rounded-t-lg transition ${
      activeTab === tab.key
        ? 'bg-white text-blue-700 border-l border-t border-r border-blue-300 -mb-px z-10'
        : tab.enabled
          ? 'bg-gray-100 text-gray-500 hover:bg-gray-200 cursor-pointer'
          : 'bg-gray-50 text-gray-300 cursor-not-allowed'
    }`;

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 py-8 px-4">
      <div className="max-w-6xl mx-auto">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-800">Notice Generated</h1>
            <p className="text-green-600 flex items-center mt-1">
              <svg className="w-5 h-5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              Notice under Section 133(6) has been generated successfully
            </p>
          </div>
          <button onClick={onNewCase} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 shadow">
            + New Case
          </button>
        </div>

        {noticeData && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
            <div className="bg-white rounded-lg border p-4 text-center">
              <p className="text-sm text-gray-500">Assessee</p>
              <p className="font-semibold">{noticeData.assessee_name || 'N/A'}</p>
            </div>
            <div className="bg-white rounded-lg border p-4 text-center">
              <p className="text-sm text-gray-500">PAN</p>
              <p className="font-semibold">{noticeData.pan || 'N/A'}</p>
            </div>
            <div className="bg-white rounded-lg border p-4 text-center">
              <p className="text-sm text-gray-500">Assessment Year</p>
              <p className="font-semibold">{noticeData.assessment_year || 'N/A'}</p>
            </div>
          </div>
        )}

        {/* Tab bar */}
        <div className="flex gap-1 border-b border-gray-300 mb-0">
          {tabs.map(tab => (
            <button
              key={tab.key}
              onClick={() => tab.enabled && setActiveTab(tab.key)}
              className={calcTabClass(tab)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="bg-white rounded-b-lg rounded-tr-lg shadow-lg border border-t-0 p-4">
          {/* DOCX Tab */}
          {activeTab === 'docx' && hasDocx && (
            <div className="text-center py-8">
              <svg className="w-20 h-20 mx-auto mb-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <p className="text-gray-700 mb-2 font-medium">Notice.docx (Editable)</p>
              <p className="text-gray-500 text-sm mb-6">
                Open in Word to review and edit before finalizing.
              </p>
              <a
                href={`/api/files/${sessionId}/Notice.docx`}
                download
                className="inline-flex items-center px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 shadow font-semibold"
              >
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                Download Notice.docx
              </a>
            </div>
          )}

          {/* PDF Tab */}
          {activeTab === 'pdf' && hasPdf && !pdfError && (
            <div>
              <div className="flex justify-end items-center mb-2">
                <a
                  href={`/api/files/${sessionId}/Notice.pdf`}
                  download
                  className="text-sm text-blue-600 hover:underline"
                >
                  Download
                </a>
              </div>
              <div className="h-[700px] border rounded-lg overflow-hidden bg-gray-100">
                <object
                  data={`/api/files/${sessionId}/Notice.pdf`}
                  type="application/pdf"
                  className="w-full h-full"
                  onError={() => setPdfError(true)}
                >
                  <div className="flex items-center justify-center h-full">
                    <div className="text-center p-8">
                      <svg className="w-16 h-16 mx-auto mb-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                      </svg>
                      <p className="text-gray-500 mb-4">PDF preview not available in your browser.</p>
                      <a
                        href={`/api/files/${sessionId}/Notice.pdf`}
                        download
                        className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                      >
                        Download Notice.pdf
                      </a>
                    </div>
                  </div>
                </object>
              </div>
            </div>
          )}

          {activeTab === 'pdf' && pdfError && (
            <div className="text-center py-12">
              <svg className="w-20 h-20 mx-auto mb-4 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <p className="text-yellow-700 mb-2 font-medium">PDF Preview Unavailable</p>
              <p className="text-gray-500 text-sm mb-6">
                Your browser cannot display this PDF inline. Download it instead.
              </p>
              <a
                href={`/api/files/${sessionId}/Notice.pdf`}
                download
                className="inline-flex items-center px-6 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 shadow font-semibold"
              >
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                Download Notice.pdf
              </a>
            </div>
          )}

          {/* Data Tab */}
          {activeTab === 'data' && (
            <div className="py-4">
              {hasFallback && (
                <div className="bg-yellow-50 border border-yellow-300 rounded-lg p-4 mb-4">
                  <p className="text-yellow-800 text-sm font-medium">
                    Notice template not available — showing fallback data.
                  </p>
                </div>
              )}
              {hasNoFiles && (
                <div className="bg-yellow-50 border border-yellow-300 rounded-lg p-4 mb-4">
                  <p className="text-yellow-800 text-sm font-medium">
                    No notice files were generated. Review the case data below.
                  </p>
                </div>
              )}
              <div className="bg-gray-50 rounded-lg p-4 border text-sm space-y-3">
                <p><strong>Case ID:</strong> {noticeData?.case_id || 'N/A'}</p>
                <p><strong>Assessee:</strong> {noticeData?.assessee_name || 'N/A'}</p>
                <p><strong>PAN:</strong> {noticeData?.pan || 'N/A'}</p>
                <p><strong>Assessment Year:</strong> {noticeData?.assessment_year || 'N/A'}</p>
                <p><strong>Under:</strong> Section 133(6) of the Income Tax Act, 1961</p>

                {noticeData?.discrepancies && noticeData.discrepancies.length > 0 && (
                  <>
                    <hr className="my-2" />
                    <p className="font-semibold">Discrepancies ({noticeData.discrepancies.length})</p>
                    {noticeData.discrepancies.slice(0, 10).map((d: Record<string, unknown>, i: number) => (
                      <div key={i} className="ml-2 border-l-2 border-red-300 pl-3 mt-1">
                        <p className="text-red-700 text-xs font-medium">{String(d.field || d.category || d.field_name || 'N/A')}</p>
                        <p className="text-gray-600 text-xs">{String(d.description || d.difference_summary || d.narrative || '')}</p>
                      </div>
                    ))}
                  </>
                )}

                {noticeData?.llm_review && (
                  <>
                    <hr className="my-2" />
                    <p className="font-semibold">LLM Review</p>
                    <pre className="bg-gray-800 text-green-300 p-3 rounded text-xs overflow-x-auto max-h-64">
                      {JSON.stringify(noticeData.llm_review, null, 2)}
                    </pre>
                  </>
                )}
              </div>
            </div>
          )}

          {activeTab === 'pdf' && !hasPdf && (
            <div className="text-center py-12">
              <p className="text-gray-500">PDF file not available.</p>
            </div>
          )}
          {activeTab === 'docx' && !hasDocx && (
            <div className="text-center py-12">
              <p className="text-gray-500">DOCX file not available.</p>
            </div>
          )}
        </div>

        {/* Download buttons always visible */}
        <div className="flex justify-center gap-4 mt-6 flex-wrap">
          {hasDocx && (
            <a
              href={`/api/files/${sessionId}/Notice.docx`}
              download
              className="flex items-center px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 shadow font-semibold"
            >
              <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Download Notice.docx
            </a>
          )}
          {hasPdf && (
            <a
              href={`/api/files/${sessionId}/Notice.pdf`}
              download
              className="flex items-center px-6 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 shadow font-semibold"
            >
              <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Download Notice.pdf
            </a>
          )}
          {!hasDocx && !hasPdf && (
            <p className="text-gray-500 text-sm">No notice files available for download.</p>
          )}
        </div>

        <div className="text-center mt-6">
          <p className="text-gray-500 text-sm">
            The case has been processed. Files are saved to the output directory.
          </p>
        </div>
      </div>
    </div>
  );
};
