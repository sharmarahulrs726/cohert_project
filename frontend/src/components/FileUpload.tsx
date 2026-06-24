import React, { useCallback, useRef, useState } from 'react';

interface FileUploadProps {
  onStart: () => Promise<unknown>;
  onFileSelect: (file: File) => Promise<unknown>;
  uploadedNames: string[];
  uploadedFilenames: Record<string, string>;
  allUploaded: boolean;
  hasSession: boolean;
  reportTemplateFound: boolean;
  noticeTemplateFound: boolean;
  error: string | null;
}

const FILE_TYPES = [
  { key: 'form16', label: 'Form 16', accept: '.xlsx,.xls,.docx,.doc', color: 'blue' },
  { key: 'ais', label: 'AIS', accept: '.xlsx,.xls,.docx,.doc', color: 'green' },
  { key: 'itr', label: 'ITR Extract', accept: '.xlsx,.xls,.docx,.doc', color: 'purple' },
] as const;

const COLOR_MAP: Record<string, { bg: string; border: string; text: string; hover: string }> = {
  blue: {
    bg: 'bg-blue-50',
    border: 'border-blue-300',
    text: 'text-blue-700',
    hover: 'hover:bg-blue-100',
  },
  green: {
    bg: 'bg-green-50',
    border: 'border-green-300',
    text: 'text-green-700',
    hover: 'hover:bg-green-100',
  },
  purple: {
    bg: 'bg-purple-50',
    border: 'border-purple-300',
    text: 'text-purple-700',
    hover: 'hover:bg-purple-100',
  },
};

export const FileUpload: React.FC<FileUploadProps> = ({
  onStart,
  onFileSelect,
  uploadedNames,
  uploadedFilenames,
  allUploaded,
  hasSession,
  reportTemplateFound,
  noticeTemplateFound,
  error,
}) => {
  const [dragging, setDragging] = useState<string | null>(null);
  const [uploading, setUploading] = useState<string | null>(null);
  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  const handleDrop = useCallback(async (key: string, file: File) => {
    if (!hasSession) return;
    setUploading(key);
    try {
      await onFileSelect(file);
    } finally {
      setUploading(null);
    }
  }, [onFileSelect, hasSession]);

  const handleFileChange = useCallback(async (key: string, e: React.ChangeEvent<HTMLInputElement>) => {
    if (!hasSession) return;
    const file = e.target.files?.[0];
    if (file) {
      setUploading(key);
      try {
        await onFileSelect(file);
      } finally {
        setUploading(null);
      }
    }
  }, [onFileSelect, hasSession]);

  const isUploaded = (key: string) => uploadedNames.includes(key);

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 py-12 px-4">
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-10">
          <h1 className="text-3xl font-bold text-gray-800 mb-2">Tax Investigation System</h1>
          <p className="text-gray-500">Upload the three required documents to begin analysis</p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-100 border border-red-400 text-red-700 rounded-lg">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {FILE_TYPES.map(({ key, label, accept, color }) => {
            const c = COLOR_MAP[color];
            const uploaded = isUploaded(key);
            const isDragging = dragging === key;
            const isUploading = uploading === key;

            return (
              <div
                key={key}
                className={`relative border-2 border-dashed rounded-xl p-6 text-center transition-all
                  ${uploaded ? 'bg-green-50 border-green-400' : ''}
                  ${!hasSession && !uploaded ? 'bg-gray-100 border-gray-300 opacity-60' : ''}
                  ${hasSession && !uploaded && isDragging ? `${c.bg} border-blue-500 scale-105` : ''}
                  ${hasSession && !uploaded && !isDragging ? `${c.bg} ${c.border} ${c.hover}` : ''}
                  ${hasSession && !uploaded ? 'cursor-pointer' : 'cursor-default'}
                `}
                onDragOver={hasSession ? (e) => { e.preventDefault(); setDragging(key); } : undefined}
                onDragLeave={hasSession ? () => setDragging(null) : undefined}
                onDrop={hasSession ? (e) => {
                  e.preventDefault();
                  setDragging(null);
                  const file = e.dataTransfer.files[0];
                  if (file) handleDrop(key, file);
                } : undefined}
                onClick={hasSession ? () => fileInputRefs.current[key]?.click() : undefined}
              >
                <input
                  ref={(el) => { fileInputRefs.current[key] = el; }}
                  type="file"
                  accept={accept}
                  className="hidden"
                  onChange={(e) => handleFileChange(key, e)}
                  disabled={uploaded}
                />

                {uploaded ? (
                  <div className="text-green-600">
                    <svg className="w-12 h-12 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    <p className="font-semibold text-lg">{label}</p>
                    <p className="text-xs text-green-600 mt-1 truncate max-w-full px-2">{uploadedFilenames[key] || 'Uploaded'}</p>
                    <p className="text-xs text-green-500 mt-0.5">Click to re-upload</p>
                  </div>
                ) : !hasSession ? (
                  <div>
                    <svg className="w-12 h-12 mx-auto mb-3 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                    </svg>
                    <p className={`font-semibold ${c.text}`}>{label}</p>
                    <p className="text-xs text-gray-400 mt-2">Start New Case to upload</p>
                  </div>
                ) : isUploading ? (
                  <div className="text-gray-500">
                    <svg className="w-12 h-12 mx-auto mb-3 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    <p className="font-semibold">{label}</p>
                    <p className="text-sm mt-1">Uploading...</p>
                  </div>
                ) : (
                  <div>
                    <svg className={`w-12 h-12 mx-auto mb-3 ${c.text}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                    </svg>
                    <p className={`font-semibold ${c.text}`}>{label}</p>
                    <p className="text-sm text-gray-400 mt-1">Click or drag to upload</p>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {(!reportTemplateFound || !noticeTemplateFound) && (
          <div className="mb-6 p-4 bg-yellow-50 border border-yellow-300 rounded-lg">
            <p className="text-yellow-800 font-medium mb-2">Templates not found in sample/ folder</p>
            <p className="text-yellow-600 text-sm mb-3">Please upload the required templates:</p>
            <div className="flex gap-4">
              {!reportTemplateFound && (
                <TemplateUploadButton type="report" sessionId="" onUpload={() => {}} />
              )}
              {!noticeTemplateFound && (
                <TemplateUploadButton type="notice" sessionId="" onUpload={() => {}} />
              )}
            </div>
          </div>
        )}

        {!hasSession && (
          <div className="text-center">
            <button
              onClick={onStart}
              className="px-8 py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 transition shadow-lg"
            >
              Start New Case
            </button>
          </div>
        )}

        {hasSession && (
          <div className="text-center">
            <button
              onClick={onStart}
              disabled={!allUploaded}
              className={`px-8 py-3 font-semibold rounded-lg transition shadow-lg ${
                allUploaded
                  ? 'bg-blue-600 text-white hover:bg-blue-700 cursor-pointer'
                  : 'bg-gray-300 text-gray-500 cursor-not-allowed'
              }`}
            >
              {allUploaded ? 'Process Case →' : 'Upload all 3 files to proceed'}
            </button>
            {allUploaded && (
              <p className="text-green-600 text-sm mt-2">All files uploaded! Click to process.</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

const TemplateUploadButton: React.FC<{
  type: string;
  sessionId: string;
  onUpload: () => void;
}> = ({ type, onUpload }) => (
  <label className="px-4 py-2 bg-yellow-200 text-yellow-800 rounded cursor-pointer hover:bg-yellow-300 text-sm">
    Upload {type === 'report' ? 'Report' : 'Notice'} Template
    <input type="file" accept=".docx" className="hidden" onChange={onUpload} />
  </label>
);
