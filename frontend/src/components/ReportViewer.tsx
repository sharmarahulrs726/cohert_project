import React, { useState } from 'react';
import type { ReportData } from '../types';
import { getFileUrl } from '../services/api';

interface ReportViewerProps {
  data: ReportData;
  sessionId: string;
  onReviewNotice: () => void;
  onNewCase: () => void;
}

const RiskBadge: React.FC<{ level: string }> = ({ level }) => {
  const colors: Record<string, string> = {
    high: 'bg-red-100 text-red-800 border-red-300',
    medium: 'bg-yellow-100 text-yellow-800 border-yellow-300',
    low: 'bg-green-100 text-green-800 border-green-300',
    unknown: 'bg-gray-100 text-gray-800 border-gray-300',
  };
  return (
    <span className={`px-3 py-1 rounded-full text-sm font-semibold border ${colors[level] || colors.unknown}`}>
      {level.toUpperCase()}
    </span>
  );
};

export const ReportViewer: React.FC<ReportViewerProps> = ({
  data,
  sessionId,
  onReviewNotice,
  onNewCase,
}) => {
  const [expandedSection, setExpandedSection] = useState<string | null>('summary');
  const { summary_cards: cards, discrepancies, llm_review } = data;

  const toggleSection = (section: string) => {
    setExpandedSection(expandedSection === section ? null : section);
  };

  const findings = (llm_review?.findings as Record<string, unknown>[]) || [];
  const narrative = llm_review?.investigation_narrative as Record<string, unknown> || {};
  const validationSteps = llm_review?.validation_steps as Record<string, unknown>[] || [];
  const isLLMFallback = llm_review?._fallback_reason_detail === 'LLM connection failed';
  const fallbackReason = llm_review?._fallback_reason_detail as string || '';

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 py-8 px-4">
      <div className="max-w-6xl mx-auto">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold text-gray-800">Investigation Report</h1>
          <button onClick={onNewCase} className="px-4 py-2 text-sm text-gray-600 border rounded hover:bg-gray-100">
            + New Case
          </button>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <SummaryCard label="Overall Risk" value={cards.risk_level.toUpperCase()} color={cards.risk_level === 'high' ? 'red' : cards.risk_level === 'medium' ? 'yellow' : 'green'} />
          <SummaryCard label="Findings" value={String(cards.findings_count)} />
          <SummaryCard label="Material Discrepancies" value={String(cards.material_discrepancy_count)} />
          <SummaryCard label="Notice Candidate" value={cards.notice_candidate ? 'YES' : 'NO'} color={cards.notice_candidate ? 'red' : 'green'} />
        </div>

        {/* LLM Fallback Banner */}
        {isLLMFallback && (
          <div className="bg-yellow-50 border border-yellow-300 rounded-lg p-4 mb-6 flex items-start gap-3">
            <svg className="w-6 h-6 text-yellow-600 mt-0.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <div>
              <p className="font-semibold text-yellow-800">LLM Review Unavailable — Deterministic Fallback Used</p>
              <p className="text-sm text-yellow-700 mt-1">
                The AI review could not connect to the LLM provider. Analysis was completed using rule-based deterministic logic only.
                Findings shown below are generated without AI augmentation.
              </p>
              {fallbackReason && (
                <p className="text-xs text-yellow-600 mt-1 font-mono">Reason: {fallbackReason}</p>
              )}
            </div>
          </div>
        )}

        {/* Decision Banner */}
        <div className={`p-4 rounded-lg mb-6 border ${
          data.is_notice_required ? 'bg-red-50 border-red-300' : 'bg-green-50 border-green-300'
        }`}>
          <div className="flex items-center justify-between">
            <div>
              <span className="font-semibold text-lg">Decision: </span>
              <span className={`font-bold ${data.is_notice_required ? 'text-red-700' : 'text-green-700'}`}>
                {data.decision_type}
              </span>
              {data.is_notice_required && (
                <span className="ml-2 text-red-600">⚠ Notice Required</span>
              )}
            </div>
            {data.is_notice_required && (
              <button
                onClick={onReviewNotice}
                className="px-6 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 font-semibold shadow"
              >
                Review Notice
              </button>
            )}
          </div>
        </div>

        {/* Accordion Sections */}
        <div className="space-y-4">
          {/* Case Summary */}
          <AccordionSection
            title="Case Summary"
            isOpen={expandedSection === 'summary'}
            onToggle={() => toggleSection('summary')}
          >
            <div className="grid grid-cols-2 gap-4 p-4">
              <div>
                <p className="text-sm text-gray-500">Case ID</p>
                <p className="font-medium">{data.case_summary?.case_id as string || 'N/A'}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Decision</p>
                <p className="font-medium">{data.decision_type}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Summary</p>
                <p className="text-sm">{cards.risk_level} risk with {cards.findings_count} findings</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Notice Required</p>
                <p className="font-medium">{data.is_notice_required ? 'Yes' : 'No'}</p>
              </div>
            </div>
          </AccordionSection>

          {/* Discrepancies */}
          <AccordionSection
            title={`Discrepancies (${discrepancies.length})`}
            isOpen={expandedSection === 'discrepancies'}
            onToggle={() => toggleSection('discrepancies')}
          >
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-100">
                  <tr>
                    <th className="p-3 text-left">Category</th>
                    <th className="p-3 text-right">Source</th>
                    <th className="p-3 text-right">Declared</th>
                    <th className="p-3 text-right">Delta</th>
                    <th className="p-3 text-center">Materiality</th>
                    <th className="p-3 text-center">Notice</th>
                  </tr>
                </thead>
                <tbody>
                  {discrepancies.map((d: Record<string, unknown>, i: number) => (
                    <tr key={i} className="border-t hover:bg-gray-50">
                      <td className="p-3 font-medium capitalize">{String(d.category || '')}</td>
                      <td className="p-3 text-right">{String(d.source_reported_value || '')}</td>
                      <td className="p-3 text-right">{String(d.declared_value || '')}</td>
                      <td className="p-3 text-right">{String(d.delta || '')}</td>
                      <td className="p-3 text-center">
                        <MaterialityBadge level={String(d.materiality || '')} />
                      </td>
                      <td className="p-3 text-center">
                        {d.notice_candidate ? '⚠' : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </AccordionSection>

          {/* LLM Findings */}
          <AccordionSection
            title={
              <span className="flex items-center gap-2">
                LLM Findings ({findings.length})
                {isLLMFallback && (
                  <span className="px-2 py-0.5 bg-yellow-100 text-yellow-700 rounded text-xs font-medium">
                    Deterministic
                  </span>
                )}
              </span>
            }
            isOpen={expandedSection === 'findings'}
            onToggle={() => toggleSection('findings')}
          >
            <div className="space-y-3 p-4">
              {isLLMFallback && (
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-sm text-yellow-700">
                  <p className="font-medium mb-1">⚠ LLM Service Unavailable</p>
                  <p>AI-powered review could not connect to the LLM provider. The findings below were generated using
                  deterministic rule-based analysis as a fallback. Accuracy may be limited compared to AI-augmented review.</p>
                </div>
              )}
              {findings.map((f: Record<string, unknown>, i: number) => (
                <div key={i} className="border rounded-lg p-4 bg-gray-50">
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <span className="font-semibold">{String(f.finding_id || '')}</span>
                      <span className="ml-2 text-sm text-gray-500 capitalize">{String(f.category || '')}</span>
                      <span className={`ml-2 px-2 py-0.5 rounded text-xs ${
                        f.status === 'confirmed' ? 'bg-red-100 text-red-700' :
                        f.status === 'probable' ? 'bg-yellow-100 text-yellow-700' :
                        'bg-gray-100 text-gray-700'
                      }`}>{String(f.status || '')}</span>
                    </div>
                    <MaterialityBadge level={String(f.materiality || '')} />
                  </div>
                  <p className="text-sm text-gray-600 mb-1">{String(f.difference_summary || '')}</p>
                  <p className="text-xs text-gray-400">{String(f.reasoning || '')}</p>
                  {Boolean(f.manual_review_required) && (
                    <p className="text-xs text-red-500 mt-1">⚠ Manual review required</p>
                  )}
                </div>
              ))}
              {findings.length === 0 && (
                <p className="text-gray-400 text-center py-4">No findings from LLM</p>
              )}
            </div>
          </AccordionSection>

          {/* Investigation Narrative */}
          <AccordionSection
            title="Investigation Narrative"
            isOpen={expandedSection === 'narrative'}
            onToggle={() => toggleSection('narrative')}
          >
            <div className="p-4 space-y-4">
              <div>
                <h4 className="font-semibold text-sm text-gray-700 mb-2">Facts Established</h4>
                <ul className="list-disc list-inside space-y-1">
                  {(narrative.facts_established as string[] || []).map((f: string, i: number) => (
                    <li key={i} className="text-sm text-gray-600">{f}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h4 className="font-semibold text-sm text-gray-700 mb-2">Issues Observed</h4>
                <ul className="list-disc list-inside space-y-1">
                  {(narrative.issues_observed as string[] || []).map((f: string, i: number) => (
                    <li key={i} className="text-sm text-gray-600">{f}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h4 className="font-semibold text-sm text-gray-700 mb-2">Uncertainties</h4>
                <ul className="list-disc list-inside space-y-1">
                  {(narrative.uncertainties as string[] || []).map((f: string, i: number) => (
                    <li key={i} className="text-sm text-gray-600">{f}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h4 className="font-semibold text-sm text-gray-700 mb-2">Recommended Next Step</h4>
                <p className="text-sm font-medium">{String(narrative.recommended_next_step || '')}</p>
              </div>
            </div>
          </AccordionSection>

          {/* Validation Steps */}
          <AccordionSection
            title={`Validation Steps (${validationSteps.length})`}
            isOpen={expandedSection === 'validation'}
            onToggle={() => toggleSection('validation')}
          >
            <div className="space-y-3 p-4">
              {validationSteps.map((v: Record<string, unknown>, i: number) => (
                <div key={i} className="border-l-4 border-blue-400 bg-blue-50 p-4 rounded-r-lg">
                  <div className="flex justify-between">
                    <span className="font-semibold text-sm">{String(v.step_id || '')}</span>
                    <PriorityBadge priority={String(v.priority || '')} />
                  </div>
                  <p className="text-sm text-gray-700 mt-1">{String(v.description || '')}</p>
                  <div className="mt-2 text-xs text-gray-500">
                    <p><strong>Party:</strong> {String(v.responsible_party || '')}</p>
                    <p><strong>Document:</strong> {String(v.document_requested || '')}</p>
                    <p><strong>Legal Basis:</strong> {String(v.legal_basis || '')}</p>
                  </div>
                </div>
              ))}
              {validationSteps.length === 0 && (
                <p className="text-gray-400 text-center py-4">No validation steps</p>
              )}
            </div>
          </AccordionSection>

          {/* Generated Files */}
          <AccordionSection
            title="Generated Files"
            isOpen={expandedSection === 'files'}
            onToggle={() => toggleSection('files')}
          >
            <div className="p-4">
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {Object.entries(data.generated_files).map(([name, path]) => (
                  <a
                    key={name}
                    href={getFileUrl(sessionId, name)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center p-3 border rounded-lg hover:bg-blue-50 hover:border-blue-300 transition"
                  >
                    <svg className="w-5 h-5 mr-2 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <span className="text-sm truncate">{name}</span>
                  </a>
                ))}
              </div>
            </div>
          </AccordionSection>
        </div>
      </div>
    </div>
  );
};

const SummaryCard: React.FC<{ label: string; value: string; color?: string }> = ({ label, value, color = 'blue' }) => {
  const colors: Record<string, string> = {
    red: 'bg-red-50 border-red-200 text-red-700',
    green: 'bg-green-50 border-green-200 text-green-700',
    yellow: 'bg-yellow-50 border-yellow-200 text-yellow-700',
    blue: 'bg-blue-50 border-blue-200 text-blue-700',
  };
  return (
    <div className={`p-4 rounded-lg border ${colors[color]} text-center`}>
      <p className="text-xs uppercase tracking-wide opacity-75">{label}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
    </div>
  );
};

const AccordionSection: React.FC<{
  title: React.ReactNode;
  isOpen: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}> = ({ title, isOpen, onToggle, children }) => (
  <div className="bg-white rounded-lg shadow border">
    <button
      onClick={onToggle}
      className="w-full flex justify-between items-center p-4 hover:bg-gray-50 transition"
    >
      <span className="font-semibold text-gray-700">{title}</span>
      <svg className={`w-5 h-5 transition-transform ${isOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
      </svg>
    </button>
    {isOpen && <div className="border-t">{children}</div>}
  </div>
);

const MaterialityBadge: React.FC<{ level: string }> = ({ level }) => {
  const colors: Record<string, string> = {
    high: 'bg-red-100 text-red-700',
    medium: 'bg-yellow-100 text-yellow-700',
    low: 'bg-green-100 text-green-700',
    none: 'bg-gray-100 text-gray-500',
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[level] || colors.none}`}>
      {level}
    </span>
  );
};

const PriorityBadge: React.FC<{ priority: string }> = ({ priority }) => {
  const colors: Record<string, string> = {
    high: 'bg-red-100 text-red-700',
    medium: 'bg-yellow-100 text-yellow-700',
    low: 'bg-green-100 text-green-700',
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[priority] || colors.low}`}>
      {priority}
    </span>
  );
};
