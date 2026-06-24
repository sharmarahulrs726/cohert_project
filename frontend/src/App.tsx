import React from 'react';
import { useCaseProcessing } from './hooks/useCaseProcessing';
import { ErrorBoundary } from './components/ErrorBoundary';
import { FileUpload } from './components/FileUpload';
import { ProcessingScreen } from './components/ProcessingScreen';
import { ReportViewer } from './components/ReportViewer';
import { NoticeReview } from './components/NoticeReview';
import { NoticeViewer } from './components/NoticeViewer';

const App: React.FC = () => {
  const {
    sessionId,
    step,
    uploadedNames,
    uploadedFilenames,
    allUploaded,
    processing,
    progress,
    elapsed,
    processingMessages,
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
  } = useCaseProcessing();

  const handleStart = async () => {
    if (!sessionId) {
      await createSession();
    } else if (allUploaded) {
      await startProcess();
    }
  };

  const handleNewCase = () => {
    clearSession();
  };

  const handleNoticeYes = async () => {
    await handleNoticeDecision(true);
  };

  const handleNoticeNo = async () => {
    await handleNoticeDecision(false);
  };

  const handleProcessingComplete = () => {
    // Already handled in useCaseProcessing via step change
  };

  return (
    <ErrorBoundary>
      {step === 'upload' && (
        <FileUpload
          onStart={handleStart}
          onFileSelect={handleFileUpload}
          uploadedNames={uploadedNames}
          uploadedFilenames={uploadedFilenames}
          allUploaded={allUploaded}
          hasSession={!!sessionId}
          reportTemplateFound={reportTemplateFound}
          noticeTemplateFound={noticeTemplateFound}
          error={error}
        />
      )}

      {step === 'processing' && (
        <ProcessingScreen
          messages={processingMessages}
          progress={progress}
          elapsed={elapsed}
          onComplete={handleProcessingComplete}
          onError={(msg) => setError(msg)}
        />
      )}

      {step === 'report' && reportData && sessionId && (
        <ReportViewer
          data={reportData}
          sessionId={sessionId}
          onReviewNotice={goToNoticeReview}
          onNewCase={handleNewCase}
        />
      )}

      {step === 'notice_review' && sessionId && (
        <NoticeReview
          sessionId={sessionId}
          onYes={handleNoticeYes}
          onNo={handleNoticeNo}
          onNewCase={handleNewCase}
        />
      )}

      {step === 'notice_generated' && sessionId && (
        <NoticeViewer
          sessionId={sessionId}
          onNewCase={handleNewCase}
        />
      )}

      {step === 'complete' && (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100">
          <div className="bg-white rounded-xl shadow-lg p-8 max-w-md text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-green-100 rounded-full mb-4">
              <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h2 className="text-xl font-bold text-gray-800 mb-2">Case Complete</h2>
            <p className="text-gray-500 mb-6">
              The case has been processed and no notice was generated. This case will be forwarded for next person evaluation.
            </p>
            <button
              onClick={handleNewCase}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 shadow"
            >
              Start New Case
            </button>
          </div>
        </div>
      )}
    </ErrorBoundary>
  );
};

export default App;
