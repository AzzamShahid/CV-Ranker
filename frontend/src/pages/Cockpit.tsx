import {useEffect,useRef,useState} from 'react';
import type {MouseEvent} from 'react';
import {client} from '../api/client';
import type {JDRow,Job,JobUsage,RunSettings,WeightInput} from '../api/client';
import {
  createEditableRow,
  editableToCanonical,
  hasRowValidationErrors,
  moveRow,
  removeRow,
  rowsToEditable,
  updateRowField,
  updateRowYearText,
} from '../api/jdRows';
import type {EditableJDRow} from '../api/jdRows';
import {consumeSequence,isTerminalJob,newerSnapshot,nextReconnectMs} from '../api/observation';
import {submitOnce} from '../api/submissionIntent';
import {useWorkspace} from '../app';
import {ActionLink,Blank,Button,FormField,Message,Panel,Status} from '../components/ui';
import {CandidateDetailView,ProgressBar,useRankings} from './Results';
import {Feedback,useAction} from './Workflow';
import {workspacePath} from '../router';
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  ArrowUpIcon,
  ArrowDownIcon,
  ArrowRightIcon,
  PlusIcon,
  PlayIcon,
  RefreshIcon,
  DownloadIcon,
  ChartBarIcon,
  CloseIcon,
  SearchIcon,
  DocumentIcon,
} from '../components/icons';

function defaultRunSettings(provider:string):RunSettings{
  return {provider:provider==='openrouter'?'openrouter':'ollama',use_llm:true,unified:true,yake_top_k:40};
}

export function CockpitPage(){
  const {workspaceId,data,settings,refresh}=useWorkspace();
  const action=useAction();

  // Active Job resolution: running/queued assessment job first, else latest assessment job
  const runningJob = data.jobs.find(j => j.kind === 'assess' && (j.state === 'running' || j.state === 'queued'));
  const latestAssessJob = data.jobs.find(j => j.kind === 'assess');
  const defaultJobId = runningJob?.id ?? latestAssessJob?.id ?? null;
  const [selectedJobId, setSelectedJobId] = useState<string | null>(defaultJobId);
  const activeJobId = selectedJobId ?? defaultJobId;

  // Active Job State & Live Observation
  const [observedJob, setObservedJob] = useState<Job | null>(null);
  const [observationOnline, setObservationOnline] = useState(true);
  const [obsEpoch, setObsEpoch] = useState(0);

  // Leaderboard & Filter State
  const [candidateFilter, setCandidateFilter] = useState('');
  const [page, setPage] = useState(0);
  const rankings = useRankings(activeJobId ?? undefined, page * 50, candidateFilter);
  const rankingsRefreshRef = useRef(rankings.refresh);
  rankingsRefreshRef.current = rankings.refresh;

  // Candidate Inspection State
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const detailSectionRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (selectedCandidateId && detailSectionRef.current) {
      detailSectionRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [selectedCandidateId]);

  // Staged Documents State
  const jds = data.documents.filter(file => file.kind === 'jd');
  const cvs = data.documents.filter(d => d.kind === 'cv');
  const [selectedJDId, setSelectedJDId] = useState('');
  const activeJDId = selectedJDId || (jds.length ? jds[0].id : '');

  // Layout & Stepper toggles
  const [controlsOpen, setControlsOpen] = useState(() => !defaultJobId || !data.approved);
  const [activeSection, setActiveSection] = useState<'intake'|'jd'|'weights'|'run'>(() => {
    if (!data.approved && !data.draft) return 'intake';
    if (!data.approved) return 'jd';
    if (cvs.length === 0) return 'intake';
    return 'run';
  });

  // Modals / Overlays
  const [usage, setUsage] = useState<JobUsage | null>(null);
  const [showUsage, setShowUsage] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const [exportNotice, setExportNotice] = useState<string | null>(null);

  const [provider, setProvider] = useState<RunSettings['provider']>(settings.configured_provider === 'openrouter' ? 'openrouter' : 'ollama');
  const [llm, setLLM] = useState(true);
  const [yake, setYake] = useState(settings.yake_top_k_default);
  const [draftRows, setDraftRows] = useState<EditableJDRow[]>([]);
  const [editingDraftId, setEditingDraftId] = useState<string | null>(null);
  const [jdDirty, setJdDirty] = useState(false);
  const [expandedCriteria, setExpandedCriteria] = useState<Record<string, boolean>>({});

  // Weights State
  const currentWeights = data.weights;
  const [weightDraft, setWeightDraft] = useState<WeightInput | null>(null);

  // Initialize weights draft
  useEffect(() => {
    if (currentWeights) {
      setWeightDraft({
        experience: currentWeights.body.experience,
        education: currentWeights.body.education,
        jd: currentWeights.body.jd,
        split_jd: currentWeights.body.split_jd,
        jd_allocation: currentWeights.body.jd_allocation,
        jd_required_share: currentWeights.body.jd_required_share ?? 80,
        requirement_shares_percent_of_category: { ...currentWeights.body.requirement_shares_percent_of_category }
      });
    }
  }, [currentWeights]);

  // Keep activeJobId synced when new jobs arrive
  useEffect(() => {
    if (!selectedJobId && defaultJobId) {
      setSelectedJobId(defaultJobId);
    }
  }, [defaultJobId, selectedJobId]);

  // Load JD Draft rows with stable row identity
  useEffect(() => {
    const serverDraft = data.draft;
    if (!serverDraft) return;
    if (jdDirty && editingDraftId && editingDraftId !== serverDraft.id) return;
    let live = true;
    void client.getDraft(workspaceId, serverDraft.id).then(result => {
      if (!live) return;
      setDraftRows(rowsToEditable(result.rows ?? []));
      setEditingDraftId(serverDraft.id);
      setJdDirty(false);
    }).catch(() => { /* Draft read error fallback */ });
    return () => { live = false; };
  }, [workspaceId, data.draft, editingDraftId, jdDirty]);

  // Live Observation of Active Job via SSE & Polling
  useEffect(() => {
    if (!activeJobId) {
      setObservedJob(null);
      return;
    }
    let mounted = true;
    let stream: EventSource | null = null;
    let poller: number | null = null;
    let reconnect: number | null = null;
    let refreshTimer: number | null = null;
    let errors = 0;
    let healthy = false;
    let stopped = false;
    let lastSeq = 0;

    const endpoint = `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/jobs/${encodeURIComponent(activeJobId)}/events`;

    const clean = () => {
      if (stream) { stream.close(); stream = null; }
      if (poller !== null) { window.clearInterval(poller); poller = null; }
      if (reconnect !== null) { window.clearTimeout(reconnect); reconnect = null; }
      if (refreshTimer !== null) { window.clearTimeout(refreshTimer); refreshTimer = null; }
    };

    const fetchAuthoritative = async () => {
      if (!mounted || stopped) return;
      try {
        const j = await client.getJob(workspaceId, activeJobId);
        if (mounted) {
          setObservedJob(prev => newerSnapshot(prev, j));
          void rankingsRefreshRef.current();
        }
      } catch {
        /* Polling network blip handled by reconnection backoff */
      }
    };

    const scheduleRefresh = () => {
      if (refreshTimer !== null) return;
      refreshTimer = window.setTimeout(() => {
        refreshTimer = null;
        void fetchAuthoritative();
      }, 150);
    };

    const connect = () => {
      if (!mounted || stopped) return;
      if (stream) { stream.close(); stream = null; }
      stream = new EventSource(endpoint, { withCredentials: true });
      stream.onopen = () => {
        if (!mounted) return;
        healthy = true; errors = 0; setObservationOnline(true);
      };
      const update = (e: Event) => {
        if (!mounted || stopped) return;
        const msg = e as MessageEvent<string>;
        if (msg.type === 'snapshot') {
          try {
            const rec = JSON.parse(msg.data) as { id?: string; sequence?: number; state?: string };
            if (rec && rec.id === activeJobId && typeof rec.sequence === 'number' && rec.sequence >= lastSeq) {
              lastSeq = rec.sequence;
              scheduleRefresh();
              if (typeof rec.state === 'string' && isTerminalJob(rec.state)) {
                stopped = true; void fetchAuthoritative(); clean();
              }
            }
          } catch { scheduleRefresh(); }
          return;
        }
        if (msg.type === 'replay_expired') { scheduleRefresh(); return; }
        const seq = Number(msg.lastEventId);
        const newer = consumeSequence(lastSeq, seq);
        if (newer === null) return;
        lastSeq = newer;
        scheduleRefresh();
        if (['completed', 'completed_with_errors', 'failed', 'cancelled'].includes(msg.type)) {
          void fetchAuthoritative(); stopped = true; clean();
        }
      };

      for (const name of ['snapshot', 'queued', 'running', 'progress', 'candidate_committed',
        'paused', 'completed', 'completed_with_errors', 'failed', 'cancelled']) {
        stream.addEventListener(name, update);
      }
      stream.onerror = () => {
        if (!mounted || stopped) return;
        healthy = false; setObservationOnline(false); errors++;
        if (stream) { stream.close(); stream = null; }
        if (reconnect !== null) window.clearTimeout(reconnect);
        reconnect = window.setTimeout(() => { reconnect = null; connect(); }, nextReconnectMs(errors));
      };
    };

    void fetchAuthoritative();
    connect();

    poller = window.setInterval(() => {
      if (mounted && !healthy && !stopped) void fetchAuthoritative();
    }, 10000);

    return () => { mounted = false; stopped = true; clean(); };
  }, [workspaceId, activeJobId, obsEpoch]);

  // Keyboard shortcut: Escape closes candidate drawer
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setSelectedCandidateId(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // Document Upload handlers
  const handleFileUpload = async (kind: 'cv' | 'jd', files: FileList | null) => {
    if (!files?.length) return;
    await action.run(async () => {
      let count = 0;
      for (const f of Array.from(files)) {
        await client.upload(workspaceId, kind, f);
        count++;
      }
      await refresh();
      action.setNotice(`${count} ${kind.toUpperCase()} document(s) uploaded successfully.`);
    });
  };

  // JD Actions
  const modifyJDField = (key: string, field: keyof JDRow, val: string) => {
    setJdDirty(true);
    setDraftRows(r => updateRowField(r, key, field, val));
  };
  const modifyJDYears = (key: string, text: string) => {
    setJdDirty(true);
    setDraftRows(r => updateRowYearText(r, key, text));
  };
  const removeJDCriterion = (key: string) => {
    setJdDirty(true);
    setDraftRows(r => removeRow(r, key));
  };
  const moveJDCriterion = (from: number, to: number) => {
    setJdDirty(true);
    setDraftRows(r => moveRow(r, from, to));
  };
  const addJDCriterion = () => {
    setJdDirty(true);
    const newRow = createEditableRow({
      ID: '',
      Requirement: '',
      Priority: 'required',
      Type: 'skill',
      'JD source': ''
    });
    setDraftRows(r => [...r, newRow]);
    setExpandedCriteria(prev => ({ ...prev, [newRow._clientKey]: true }));
  };

  const handleExtractJD = () => void action.run(async () => {
    if (!activeJDId) throw new Error('Select a JD document first.');
    const req = { document_id: activeJDId, provider, use_llm: llm, unified: false, yake_top_k: yake };
    const job = await submitOnce(workspaceId, 'jd_extract', req,
      k => client.getSubmission(workspaceId, k),
      k => client.startJD(workspaceId, activeJDId, req, k)
    );
    setSelectedJobId(job.id);
    setObsEpoch(v => v + 1);
    await refresh();
    setActiveSection('jd');
    action.setNotice('JD extraction job started in worker. Criteria review view opened.');
  });

  const handleSaveJD = (approve: boolean) => void action.run(async () => {
    if (!data.draft || !editingDraftId) throw new Error('Extract a JD first.');
    if (hasRowValidationErrors(draftRows)) {
      throw new Error('Please resolve highlighted experience year validation errors before saving.');
    }
    const rows = editableToCanonical(draftRows);
    if (approve) {
      if (jdDirty && data.approved?.draft_id === data.draft.id) {
        throw new Error('This JD is already approved. Save a new draft revision before re-approving.');
      }
      await client.approveJD(workspaceId, editingDraftId, data.draft.revision, rows);
      setJdDirty(false);
      await refresh();
      setActiveSection('weights');
      action.setNotice(`JD revision ${data.draft.revision} approved & frozen. Advancing to weight allocation.`);
    } else {
      await client.reviseJD(workspaceId, editingDraftId, data.draft.revision, rows);
      setJdDirty(false);
      await refresh();
      action.setNotice('New JD draft revision saved.');
    }
  });

  // Weights Actions
  const totalWeight = weightDraft ? weightDraft.experience + weightDraft.education + weightDraft.jd : 100;
  const handleSaveWeights = () => void action.run(async () => {
    if (!currentWeights || !weightDraft) return;
    if (totalWeight !== 100) throw new Error('Total category weight must equal 100%.');
    await client.saveWeights(workspaceId, currentWeights.revision, weightDraft);
    await refresh();
    void rankings.refresh(true);
    setActiveSection('run');
    action.setNotice('Weights revision updated. Advancing to launch assessment.');
  });

  const handleEvenWeights = () => void action.run(async () => {
    const shares = await client.rebalance(workspaceId);
    if (weightDraft) {
      setWeightDraft(w => w ? ({ ...w, requirement_shares_percent_of_category: shares }) : null);
    }
  });

  // Assessment Dispatcher
  const [assessmentConfig, setAssessmentConfig] = useState<RunSettings>(() => defaultRunSettings(settings.configured_provider));
  const handleStartAssessment = () => void action.run(async () => {
    if (!data.approved) throw new Error('Approve the JD before starting an assessment.');
    if (!cvs.length) throw new Error('Upload at least one candidate CV.');
    const candIds = cvs.map(c => c.id);
    const req = { candidate_ids: candIds, approved_revision_id: data.approved.id, ...assessmentConfig };
    const job = await submitOnce(workspaceId, 'assess', req,
      k => client.getSubmission(workspaceId, k),
      k => client.startAssessment(workspaceId, candIds, data.approved!.id, assessmentConfig, k)
    );
    setSelectedJobId(job.id);
    setObsEpoch(v => v + 1);
    await refresh();
    action.setNotice(`Candidate assessment job #${job.id.slice(0, 8)} submitted to Python worker.`);
  });

  // Export Revision ZIP
  const handleExport = async () => {
    if (!observedJob || !data.weights || exportBusy) return;
    setExportBusy(true);
    setExportNotice(null);
    try {
      const latest = await client.getJob(workspaceId, observedJob.id);
      if (latest.result_revision !== rankings.resultRevision || data.weights.revision !== rankings.weightRevision) {
        throw new Error('Result or weight revision changed. Refresh rankings before export.');
      }
      const exp = await client.export(workspaceId, observedJob.id, latest.result_revision, data.weights.revision);
      const a = document.createElement('a');
      a.href = `/api/v1/workspaces/${workspaceId}/exports/${exp.id}/download`;
      a.download = 'Reliance_Weaving_Mills_Assessment.zip';
      document.body.append(a); a.click(); a.remove();
      setExportNotice('Export archive generated and downloaded.');
    } catch (e: unknown) {
      action.run(async () => { throw e instanceof Error ? e : new Error('Export failed'); });
    } finally {
      setExportBusy(false);
    }
  };

  // Usage & Shadow Loaders
  const loadUsage = async () => {
    if (!activeJobId) return;
    try {
      const u = await client.getJobUsage(workspaceId, activeJobId);
      setUsage(u);
      setShowUsage(true);
    } catch (e: unknown) {
      action.run(async () => { throw e instanceof Error ? e : new Error('Usage metrics unavailable'); });
    }
  };

  // Job Controls: Cancel / Resume
  const handleCancelJob = () => void action.run(async () => {
    if (!activeJobId) return;
    await client.controlJob(workspaceId, activeJobId, 'cancel');
    setObsEpoch(v => v + 1);
    action.setNotice('Cancellation requested for active worker job.');
  });
  const handleResumeJob = () => void action.run(async () => {
    if (!activeJobId) return;
    await client.controlJob(workspaceId, activeJobId, 'resume');
    setObsEpoch(v => v + 1);
    action.setNotice('Job resumed with saved checkpoints preserved.');
  });

  const activeJob = observedJob ?? data.jobs.find(j => j.id === activeJobId) ?? null;
  const canResume = activeJob && (activeJob.state === 'paused' || activeJob.state === 'failed' || activeJob.state === 'cancelled');

  return (
    <div className="cockpit-root">
      {/* 1. TOP STATUS & PROGRESS BANNER */}
      {activeJob ? (
        <div className="cockpit-progress-ribbon" role="region" aria-label="Active assessment run">
          <div className="ribbon-content">
            <div className="ribbon-info">
              <span className="ribbon-title">
                <strong>{activeJob.kind === 'assess' ? 'Candidate Assessment' : 'JD Extraction'}</strong>
                <span className="mono small text-muted"> #{activeJob.id.slice(0, 10)}</span>
              </span>
              <Status value={activeJob.state} />
              <span className="small text-muted">{activeJob.progress} of {activeJob.total} candidates committed</span>
              {!observationOnline ? <span className="badge warning">Reconnecting stream...</span> : null}
            </div>

            <div className="ribbon-progress-track">
              <ProgressBar completed={activeJob.progress} total={activeJob.total} />
            </div>

            <div className="ribbon-actions">
              {['queued', 'running'].includes(activeJob.state) ? (
                <Button size="small" kind="danger" disabled={action.busy} onClick={handleCancelJob}>
                  Cancel Run
                </Button>
              ) : null}
              {canResume ? (
                <Button size="small" kind="primary" disabled={action.busy} onClick={handleResumeJob}>
                  Resume Work
                </Button>
              ) : null}
              {data.jobs.length > 1 ? (
                <select
                  aria-label="Select active job"
                  className="job-select small"
                  value={activeJob.id}
                  onChange={e => { setSelectedJobId(e.target.value); setObsEpoch(v => v + 1); }}
                >
                  {data.jobs.map(j => (
                    <option key={j.id} value={j.id}>
                      {j.kind === 'assess' ? 'Assessment' : 'JD'} #{j.id.slice(0, 8)} ({j.state} - {j.progress}/{j.total})
                    </option>
                  ))}
                </select>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

      {/* Global Action Feedback */}
      <Feedback error={action.error} notice={action.notice} />
      {exportNotice ? <Message kind="success">{exportNotice}</Message> : null}

      {/* 2. TOP GUIDED 4-STEP CONFIGURATION PIPELINE */}
      <div className="pipeline-stepper-panel" role="region" aria-label="Assessment Pipeline Configuration">
        <div className="pipeline-header">
          <div className="pipeline-header-info">
            <h2 className="pipeline-header-title">Assessment Configuration Pipeline</h2>
            <div className="pipeline-header-status">
              <span className={`status-pill ${jds.length ? 'done' : 'pending'}`}>
                {jds.length ? `✓ ${jds.length} JD Uploaded` : '1. Intake Needed'}
              </span>
              <span className={`status-pill ${data.approved ? 'done' : 'pending'}`}>
                {data.approved ? `✓ Criteria Approved (Rev ${data.approved.revision})` : '2. Criteria Pending'}
              </span>
              <span className={`status-pill ${totalWeight === 100 ? 'done' : 'warning'}`}>
                {totalWeight === 100 ? `✓ Weights Set (${totalWeight}%)` : `Weights ${totalWeight}%`}
              </span>
              <span className={`status-pill ${cvs.length ? 'done' : 'pending'}`}>
                {cvs.length ? `✓ ${cvs.length} CVs Staged` : 'No CVs'}
              </span>
            </div>
          </div>
          <div className="pipeline-header-actions">
            <Button
              size="small"
              kind="subtle"
              onClick={() => setControlsOpen(v => !v)}
              aria-expanded={controlsOpen}
            >
              {controlsOpen ? (
                <><ChevronUpIcon size={14} style={{ marginRight: 6 }} />Collapse Pipeline</>
              ) : (
                <><ChevronDownIcon size={14} style={{ marginRight: 6 }} />Configure Pipeline</>
              )}
            </Button>
          </div>
        </div>

        {controlsOpen ? (
          <div className="pipeline-body">
            {/* STEPPER NAVIGATION TABS */}
            <div className="pipeline-steps-nav">
              <button
                type="button"
                className={`pipeline-step-tab ${activeSection === 'intake' ? 'active' : ''}`}
                onClick={() => setActiveSection('intake')}
              >
                <span className="step-badge">1</span>
                <span className="step-title">Intake & Extraction</span>
                <span className="step-sub">{jds.length} JD · {cvs.length} CVs</span>
              </button>
              <button
                type="button"
                className={`pipeline-step-tab ${activeSection === 'jd' ? 'active' : ''}`}
                onClick={() => setActiveSection('jd')}
              >
                <span className="step-badge">2</span>
                <span className="step-title">JD Criteria Review</span>
                <span className="step-sub">{data.approved ? 'Approved & Frozen' : data.draft ? 'Draft Ready' : 'Pending Intake'}</span>
              </button>
              <button
                type="button"
                className={`pipeline-step-tab ${activeSection === 'weights' ? 'active' : ''}`}
                onClick={() => setActiveSection('weights')}
              >
                <span className="step-badge">3</span>
                <span className="step-title">Scoring Weights</span>
                <span className="step-sub">Sum: {totalWeight}%</span>
              </button>
              <button
                type="button"
                className={`pipeline-step-tab ${activeSection === 'run' ? 'active' : ''}`}
                onClick={() => setActiveSection('run')}
              >
                <span className="step-badge">4</span>
                <span className="step-title">Launch Assessment</span>
                <span className="step-sub">{data.approved && cvs.length ? 'Ready to Run' : 'Needs Setup'}</span>
              </button>
            </div>

            {/* STEP 1: INTAKE & EXTRACTION */}
            {activeSection === 'intake' ? (
              <div className="pipeline-step-view">
                <div className="grid cols2">
                  <Panel>
                    <div className="card-header">
                      <h3>Job Description</h3>
                      <Status value={jds.length ? `${jds.length} Uploaded` : 'Missing'} />
                    </div>
                    {jds.length ? (
                      <FormField id="dock-jd-select" label="Active Job Description">
                        <select
                          id="dock-jd-select"
                          value={activeJDId}
                          onChange={e => setSelectedJDId(e.target.value)}
                        >
                          {jds.map(d => <option key={d.id} value={d.id}>{d.filename}</option>)}
                        </select>
                      </FormField>
                    ) : (
                      <p className="small text-muted">Upload an employer job description to extract evaluation criteria.</p>
                    )}
                    <div className="row wrap" style={{ marginTop: 12, gap: 10 }}>
                      <label className="file-upload-btn btn small">
                        <PlusIcon size={14} style={{ marginRight: 6 }} />Upload New JD (.docx, .pdf, .txt)
                        <input
                          type="file"
                          accept=".docx,.pdf,.txt,.md"
                          style={{ display: 'none' }}
                          onChange={e => { void handleFileUpload('jd', e.target.files); e.target.value = ''; }}
                        />
                      </label>
                      <Button
                        size="small"
                        kind="primary"
                        disabled={!activeJDId || action.busy}
                        onClick={handleExtractJD}
                      >
                        <PlayIcon size={13} style={{ marginRight: 6 }} />Extract Criteria with Worker
                      </Button>
                    </div>
                  </Panel>

                  <Panel>
                    <div className="card-header">
                      <h3>Candidate CVs</h3>
                      <Status value={`${cvs.length} Staged`} />
                    </div>
                    <p className="small text-muted">
                      {cvs.length ? `${cvs.length} candidate CV file(s) uploaded and ready for evaluation.` : 'Upload applicant CVs (.docx, .pdf, .txt) to evaluate.'}
                    </p>
                    <label className="file-upload-btn btn small primary" style={{ marginTop: 12 }}>
                      <PlusIcon size={14} style={{ marginRight: 6 }} />Upload Candidate CVs (Batch)
                      <input
                        type="file"
                        multiple
                        accept=".docx,.pdf,.txt,.md"
                        style={{ display: 'none' }}
                        onChange={e => { void handleFileUpload('cv', e.target.files); e.target.value = ''; }}
                      />
                    </label>
                    <div style={{ marginTop: 12 }}>
                      <ActionLink to={workspacePath(workspaceId, 'uploads')}>
                        Manage & download raw files <ArrowRightIcon size={13} style={{ marginLeft: 4, display: 'inline-block', verticalAlign: 'middle' }} />
                      </ActionLink>
                    </div>
                  </Panel>
                </div>
              </div>
            ) : null}

            {/* STEP 2: JD CRITERIA & ROW-IDENTITY EDITOR */}
            {activeSection === 'jd' ? (
              <div className="pipeline-step-view">
                <div className="card-header">
                  <div>
                    <strong>Extracted Criteria</strong>
                    <span className="small text-muted block">
                      {data.approved ? `Approved Rev ${data.approved.revision} · Frozen` : data.draft ? `Draft Rev ${data.draft.revision}` : 'No JD Extracted'}
                    </span>
                  </div>
                  {data.draft ? (
                    <div className="row" style={{ gap: 6 }}>
                      <Button size="small" disabled={action.busy || draftRows.length === 0} onClick={() => handleSaveJD(false)}>
                        Save Draft
                      </Button>
                      <Button size="small" kind="primary" disabled={action.busy || draftRows.length === 0} onClick={() => handleSaveJD(true)}>
                        Approve JD & Next
                      </Button>
                    </div>
                  ) : null}
                </div>

                {!data.draft ? (
                  <Panel>
                    <Blank title="JD Not Extracted" description="Select an uploaded JD in Step 1 and extract criteria in worker." />
                    <div className="grid cols2" style={{ marginTop: 12 }}>
                      <FormField id="dock-extract-prov" label="Extraction Provider">
                        <select
                          id="dock-extract-prov"
                          value={provider}
                          onChange={e => setProvider(e.target.value as RunSettings['provider'])}
                        >
                          <option value="ollama">Ollama (Local)</option>
                          <option value="openrouter">OpenRouter (Cloud)</option>
                        </select>
                      </FormField>
                      <FormField id="dock-extract-yake" label="YAKE Keyword Threshold">
                        <input
                          id="dock-extract-yake"
                          type="number"
                          min={1}
                          max={150}
                          value={yake}
                          onChange={e => setYake(Number(e.target.value))}
                        />
                      </FormField>
                    </div>
                    <label className="row" style={{ marginTop: 8 }}>
                      <input
                        type="checkbox"
                        checked={llm}
                        onChange={e => setLLM(e.target.checked)}
                      />
                      <span>Enable AI-guided extraction</span>
                    </label>
                    <Button kind="primary" style={{ marginTop: 12, width: '100%' }} disabled={!activeJDId || action.busy} onClick={handleExtractJD}>
                      Extract JD with Worker
                    </Button>
                  </Panel>
                ) : (
                  <div className="criteria-list">
                    {draftRows.map((row, idx) => {
                      const isExpanded = expandedCriteria[row._clientKey] ?? false;
                      return (
                        <div className="criteria-item-card" key={row._clientKey}>
                          <div
                            className="criteria-item-header"
                            onClick={() => setExpandedCriteria(prev => ({ ...prev, [row._clientKey]: !isExpanded }))}
                            role="button"
                            tabIndex={0}
                            onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') setExpandedCriteria(prev => ({ ...prev, [row._clientKey]: !isExpanded })); }}
                          >
                            <div className="criteria-meta">
                              <span className="mono small font-bold">{row.ID || `REQ-${idx + 1}`}</span>
                              <Status value={row.Priority} />
                              <span className="badge small">{row.Type}</span>
                            </div>
                            <span className="criteria-toggle-glyph">
                              {isExpanded ? <ChevronUpIcon size={12} /> : <ChevronDownIcon size={12} />}
                            </span>
                          </div>

                          <p className="criteria-preview-text">
                            {row.Requirement || 'Empty requirement text...'}
                          </p>

                          {isExpanded ? (
                            <div className="criteria-expand-body">
                              <FormField id={`crit-req-${row._clientKey}`} label="Requirement Description">
                                <textarea
                                  id={`crit-req-${row._clientKey}`}
                                  rows={2}
                                  value={row.Requirement}
                                  onChange={e => modifyJDField(row._clientKey, 'Requirement', e.target.value)}
                                />
                              </FormField>

                              <div className="grid cols2" style={{ marginTop: 8 }}>
                                <FormField id={`crit-prio-${row._clientKey}`} label="Priority">
                                  <select
                                    id={`crit-prio-${row._clientKey}`}
                                    value={row.Priority}
                                    onChange={e => modifyJDField(row._clientKey, 'Priority', e.target.value)}
                                  >
                                    <option value="required">Required</option>
                                    <option value="preferred">Preferred</option>
                                    <option value="unknown">Unknown</option>
                                  </select>
                                </FormField>

                                <FormField id={`crit-type-${row._clientKey}`} label="Criterion Type">
                                  <select
                                    id={`crit-type-${row._clientKey}`}
                                    value={row.Type}
                                    onChange={e => modifyJDField(row._clientKey, 'Type', e.target.value)}
                                  >
                                    {['skill', 'experience', 'education', 'certification', 'license', 'responsibility', 'eligibility', 'other'].map(t => (
                                      <option key={t} value={t}>{t}</option>
                                    ))}
                                  </select>
                                </FormField>
                              </div>

                              <FormField id={`crit-years-${row._clientKey}`} label="Minimum Experience (Years; blank = engine derived)">
                                <input
                                  id={`crit-years-${row._clientKey}`}
                                  inputMode="decimal"
                                  value={row.yearText}
                                  onChange={e => modifyJDYears(row._clientKey, e.target.value)}
                                />
                              </FormField>
                              {row.yearError ? (
                                <p className="small text-danger" style={{ color: 'var(--danger)', marginTop: 2 }}>{row.yearError}</p>
                              ) : null}

                              <FormField id={`crit-src-${row._clientKey}`} label="Exact Employer JD Quotation">
                                <textarea
                                  id={`crit-src-${row._clientKey}`}
                                  rows={2}
                                  value={row['JD source']}
                                  onChange={e => modifyJDField(row._clientKey, 'JD source', e.target.value)}
                                />
                              </FormField>

                              <div className="toolbar" style={{ marginTop: 8 }}>
                                <Button size="small" disabled={idx === 0} onClick={() => moveJDCriterion(idx, idx - 1)}>
                                  <ArrowUpIcon size={13} style={{ marginRight: 4 }} />Up
                                </Button>
                                <Button size="small" disabled={idx === draftRows.length - 1} onClick={() => moveJDCriterion(idx, idx + 1)}>
                                  <ArrowDownIcon size={13} style={{ marginRight: 4 }} />Down
                                </Button>
                                <Button size="small" kind="danger" disabled={draftRows.length <= 1} onClick={() => removeJDCriterion(row._clientKey)}>
                                  Delete
                                </Button>
                              </div>
                            </div>
                          ) : null}
                        </div>
                      );
                    })}

                    <Button size="small" style={{ marginTop: 10, width: '100%' }} onClick={addJDCriterion}>
                      <PlusIcon size={14} style={{ marginRight: 6 }} />Add Source-Backed Criterion
                    </Button>
                  </div>
                )}
              </div>
            ) : null}

            {/* STEP 3: WEIGHT ALLOCATION (ZERO-CALL RECALCULATION) */}
            {activeSection === 'weights' ? (
              <div className="pipeline-step-view">
                <div className="card-header">
                  <strong>Weight Allocation</strong>
                  <Status value={`Total: ${totalWeight}%`} />
                </div>
                <p className="small text-muted">
                  Modifying weights recalculates leaderboards instantly with zero model calls.
                </p>

                {weightDraft ? (
                  <Panel style={{ marginTop: 10 }}>
                    <FormField id="weight-exp" label={`Experience Weight: ${weightDraft.experience}%`}>
                      <input
                        id="weight-exp"
                        type="range"
                        min={0}
                        max={100}
                        value={weightDraft.experience}
                        onChange={e => setWeightDraft(w => w ? ({ ...w, experience: Number(e.target.value) }) : null)}
                      />
                    </FormField>

                    <FormField id="weight-edu" label={`Education Weight: ${weightDraft.education}%`}>
                      <input
                        id="weight-edu"
                        type="range"
                        min={0}
                        max={100}
                        value={weightDraft.education}
                        onChange={e => setWeightDraft(w => w ? ({ ...w, education: Number(e.target.value) }) : null)}
                      />
                    </FormField>

                    <FormField id="weight-jd" label={`Other JD Criteria Weight: ${weightDraft.jd}%`}>
                      <input
                        id="weight-jd"
                        type="range"
                        min={0}
                        max={100}
                        value={weightDraft.jd}
                        onChange={e => setWeightDraft(w => w ? ({ ...w, jd: Number(e.target.value) }) : null)}
                      />
                    </FormField>

                    <div className="toolbar" style={{ marginTop: 12 }}>
                      <Button size="small" onClick={handleEvenWeights}>
                        Reset Equal Shares
                      </Button>
                      <Button
                        size="small"
                        kind="primary"
                        disabled={action.busy || totalWeight !== 100}
                        onClick={handleSaveWeights}
                      >
                        Save & Recalculate
                      </Button>
                    </div>
                    {totalWeight !== 100 ? (
                      <p className="small text-danger" style={{ color: 'var(--danger)', marginTop: 6 }}>
                        Category weights must sum to 100% (currently {totalWeight}%).
                      </p>
                    ) : null}
                  </Panel>
                ) : (
                  <Blank title="Weights Unavailable" description="Approve a JD first in Step 2 to configure scoring weights." />
                )}
              </div>
            ) : null}

            {/* STEP 4: LAUNCH ASSESSMENT */}
            {activeSection === 'run' ? (
              <div className="pipeline-step-view">
                <Panel>
                  <div className="card-header">
                    <strong>Launch Candidate Assessment</strong>
                    <Status value={data.approved ? 'Ready' : 'JD Unapproved'} />
                  </div>
                  <div className="grid cols2" style={{ marginTop: 12 }}>
                    <FormField id="dock-run-provider" label="Execution Provider">
                      <select
                        id="dock-run-provider"
                        value={assessmentConfig.provider}
                        onChange={e => setAssessmentConfig(v => ({ ...v, provider: e.target.value as RunSettings['provider'] }))}
                      >
                        <option value="ollama">Local Ollama ({settings.ollama_model})</option>
                        <option value="openrouter">Cloud OpenRouter ({settings.openrouter_model})</option>
                      </select>
                    </FormField>

                    <div>
                      <label className="field-label" style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
                        Assessment Mode
                      </label>
                      <div style={{ display: 'flex', alignItems: 'center', height: 42 }}>
                        <span className="badge small primary">
                          AI Unified Assessment (Protocol 58)
                        </span>
                      </div>
                    </div>
                  </div>

                  <div style={{ marginTop: 16 }}>
                    <Button
                      kind="primary"
                      style={{ width: '100%' }}
                      disabled={!data.approved || cvs.length === 0 || action.busy}
                      onClick={handleStartAssessment}
                    >
                      <PlayIcon size={14} style={{ marginRight: 6 }} />Start Assessment ({cvs.length} Staged CVs)
                    </Button>
                  </div>
                </Panel>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      {/* 3. CENTER CANVAS: CANDIDATE RANKINGS & LEADERBOARD */}
      <main className="cockpit-main-canvas" id="cockpit-leaderboard-anchor" aria-label="Candidate Rankings Canvas">
        {/* STATS SUMMARY BAR (3 EQUAL CARDS) */}
        <div className="cockpit-stats-bar">
          <div className="cockpit-stat-item">
            <span className="stat-label">Processed run total</span>
            <span className="stat-number">{rankings.total}</span>
            <span className="stat-sub">{candidateFilter ? 'Matching search query' : 'All evaluated in run'}</span>
          </div>
          <div className="cockpit-stat-item">
            <span className="stat-label">Official scores</span>
            <span className="stat-number">{rankings.officialCount}</span>
            <span className="stat-sub">Completed evaluations</span>
          </div>
          <div className="cockpit-stat-item">
            <span className="stat-label">Unfinished</span>
            <span className="stat-number">{rankings.unfinishedCount}</span>
            <span className="stat-sub">In-flight or pending</span>
          </div>
        </div>

        {/* SEARCH & CONTROLS TOOLBAR */}
        <div className="cockpit-table-toolbar">
          <div className="search-field-container" style={{ position: 'relative' }}>
            <SearchIcon size={15} style={{ position: 'absolute', left: 12, top: 13, color: 'var(--text-muted)', pointerEvents: 'none' }} />
            <input
              id="cockpit-candidate-search"
              type="text"
              placeholder="Search candidate filename or name..."
              value={candidateFilter}
              onChange={e => { setCandidateFilter(e.target.value); setPage(0); }}
              className="search-input"
              style={{ paddingLeft: 36 }}
            />
          </div>

          <div className="toolbar-actions">
            <Button size="small" onClick={() => { setPage(0); rankings.resetPin(); void rankings.refresh(true); }}>
              <RefreshIcon size={14} style={{ marginRight: 6 }} />Refresh Rankings
            </Button>
            <Button size="small" kind="primary" disabled={exportBusy || rankings.total === 0} onClick={() => void handleExport()}>
              <DownloadIcon size={14} style={{ marginRight: 6 }} />Export Archive (ZIP)
            </Button>
            <Button size="small" onClick={() => void loadUsage()}>
              <ChartBarIcon size={14} style={{ marginRight: 6 }} />Usage & Costs
            </Button>
          </div>
        </div>

        {/* REVISION CONFLICT BANNER */}
        {rankings.error ? (
          <Panel className="error-panel" style={{ marginBottom: 12 }}>
            <Message kind="warn"><strong>Revision notice:</strong> {rankings.error.message}</Message>
            <Button size="small" kind="primary" style={{ marginTop: 8 }} onClick={() => { setPage(0); rankings.resetPin(); void rankings.refresh(true); }}>
              Reload Latest Revision
            </Button>
          </Panel>
        ) : null}

        {/* RANKINGS LEADERBOARD TABLE */}
        <Panel className="table-panel">

          {rankings.rows.length ? (
            <div className="table-scroller">
              <table className="cockpit-table">
                <thead>
                  <tr>
                    <th scope="col" style={{ width: 64 }}>Rank</th>
                    <th scope="col">Candidate Name</th>
                    <th scope="col" style={{ width: 140 }}>Score</th>
                    <th scope="col" style={{ width: 90 }}>Required</th>
                    <th scope="col" style={{ width: 90 }}>Preferred</th>
                    <th scope="col" style={{ width: 110 }}>State</th>
                    <th scope="col" style={{ width: 150 }}>Evidence & Scorecard</th>
                  </tr>
                </thead>
                <tbody>
                  {rankings.rows.map(row => {
                    const isSelected = selectedCandidateId === row.candidate_id;
                    const scoreVal = row.weighted_score !== null ? row.weighted_score : null;
                    return (
                      <tr
                        key={row.candidate_id}
                        className={`cockpit-table-row ${isSelected ? 'row-selected' : ''}`}
                        onClick={() => setSelectedCandidateId(row.candidate_id)}
                      >
                        <td className="mono font-bold">
                          {row.rank !== null ? `#${row.rank}` : '—'}
                        </td>
                        <td>
                          <strong>{row.candidate}</strong>
                          <span className="mono small text-muted block">{row.candidate_id.slice(0, 10)}</span>
                        </td>
                        <td>
                          {scoreVal !== null ? (
                            <div className="score-meter-wrap">
                              <span className="score-text mono font-bold">{scoreVal.toFixed(1)}%</span>
                              <div className="mini-progress-bar">
                                <div className="mini-progress-fill" style={{ width: `${Math.min(100, Math.max(0, scoreVal))}%` }} />
                              </div>
                            </div>
                          ) : (
                            <span className="badge warning">Not ready</span>
                          )}
                        </td>
                        <td className="mono">{row.required}</td>
                        <td className="mono">{row.preferred}</td>
                        <td><Status value={row.score_status} /></td>
                        <td>
                          <Button
                            size="small"
                            kind={isSelected ? 'primary' : 'subtle'}
                            onClick={(e: MouseEvent<HTMLButtonElement>) => {
                              e.stopPropagation();
                              setSelectedCandidateId(row.candidate_id);
                            }}
                            title={`Inspect evidence for ${row.candidate}`}
                          >
                            <DocumentIcon size={13} style={{ marginRight: 5 }} />
                            Inspect Evidence
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <Blank
              title="No Candidate Rankings"
              description={candidateFilter ? 'No candidates match your search filter.' : 'Launch an assessment run to view candidate rankings.'}
            />
          )}

          {/* PAGINATION */}
          <div className="cockpit-pagination">
            <span className="small text-muted">
              Showing {rankings.rows.length ? page * 50 + 1 : 0}–{Math.min((page + 1) * 50, rankings.total)} of {rankings.total} matching candidates
            </span>
            <div className="pagination-buttons">
              <Button size="small" disabled={page === 0} onClick={() => setPage(v => Math.max(0, v - 1))}>
                <ChevronLeftIcon size={13} style={{ marginRight: 4 }} />Previous
              </Button>
              <Button size="small" disabled={(page + 1) * 50 >= rankings.total} onClick={() => setPage(v => v + 1)}>
                Next<ChevronRightIcon size={13} style={{ marginLeft: 4 }} />
              </Button>
            </div>
          </div>
        </Panel>

        {/* 3.5 WHY CANDIDATES RANKED THIS WAY (Image 3) */}
        {rankings.rows.length > 0 ? (
          <Panel className="ranking-explanations-panel" style={{ marginTop: 20 }}>
            <div className="section-eyebrow">RANKING EXPLAINED</div>
            <h2 className="section-title" style={{ margin: '4px 0 4px 0' }}>Why candidates ranked this way</h2>
            <p className="section-subtitle" style={{ margin: '0 0 16px 0', color: 'var(--text-muted)' }}>
              One clear explanation per candidate. Detailed evidence is available below.
            </p>

            <div className="ranking-explanations-list">
              {rankings.rows.map(row => {
                const isSelected = selectedCandidateId === row.candidate_id;
                const scoreStr = row.weighted_score !== null ? `${row.weighted_score.toFixed(2)}%` : 'Provisional';
                return (
                  <div
                    key={row.candidate_id}
                    className={`ranking-explanation-card ${isSelected ? 'selected' : ''}`}
                    onClick={() => setSelectedCandidateId(row.candidate_id)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        setSelectedCandidateId(row.candidate_id);
                      }
                    }}
                  >
                    <div className="explanation-rank-badge mono">
                      #{row.rank !== null ? row.rank : '—'}
                    </div>
                    <div className="explanation-card-content">
                      <div className="explanation-card-header">
                        <span className="explanation-candidate-name">{row.candidate}</span>
                        <span className="explanation-candidate-score mono">{scoreStr}</span>
                      </div>
                      <p className="explanation-card-body">
                        {row.placement_reason ||
                          (row.rank === 1
                            ? `Top-ranked at ${scoreStr} because the current JD weights favor the candidate's verified matches. This is the highest verified weighted total.`
                            : `Rank #${row.rank ?? '—'} at ${scoreStr}. The position reflects verified evidence contributions.`)}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </Panel>
        ) : null}

        {/* 4. CANDIDATE FULL DETAIL & WHY SECTION (MOUNTED BELOW THE TABLE) */}
        {selectedCandidateId && activeJobId ? (
          <section
            className="candidate-detail-mount-section"
            ref={detailSectionRef}
            id="candidate-detail-section"
            aria-label="Candidate Scorecard and Evidence"
          >
            <CandidateDetailView
              workspaceId={workspaceId}
              jobId={activeJobId}
              candidateId={selectedCandidateId}
              onClose={() => setSelectedCandidateId(null)}
              onBackToLeaderboard={() => {
                const el = document.getElementById('cockpit-leaderboard-anchor');
                if (el) el.scrollIntoView({ behavior: 'smooth' });
              }}
              onFocusedReviewComplete={() => void rankings.refresh()}
            />
          </section>
        ) : null}
      </main>

      {/* MODAL 1: PROVIDER USAGE & COSTS */}
      {showUsage && usage ? (
        <div className="modal-backdrop" onClick={() => setShowUsage(false)}>
          <div className="modal-dialog" onClick={e => e.stopPropagation()}>
            <Panel>
              <div className="card-header">
                <h2>Provider Usage & Cost Metrics</h2>
                <Button size="small" onClick={() => setShowUsage(false)}>
                  <CloseIcon size={14} style={{ marginRight: 4 }} />Close
                </Button>
              </div>
              <p className="small">Job: <span className="mono">{usage.job_id}</span> · Provider: <strong>{usage.provider}</strong> · Model: <strong>{usage.model}</strong></p>
              <div className="grid cols3" style={{ marginTop: 14, marginBottom: 14 }}>
                <div><small>Logical Model Calls</small><p className="font-bold">{usage.logical_model_calls}</p></div>
                <div><small>Actual HTTP Attempts</small><p className="font-bold">{usage.actual_model_request_attempts}</p></div>
                <div><small>Prompt Reuses</small><p className="font-bold">{usage.reused_prompt_calls}</p></div>
              </div>
              <p><strong>Token Usage:</strong> {usage.token_usage.total_tokens !== null && usage.token_usage.total_tokens !== undefined ? `Prompt: ${usage.token_usage.prompt_tokens} · Completion: ${usage.token_usage.completion_tokens} · Total: ${usage.token_usage.total_tokens}` : 'Preserved as unknown'}</p>
              <p><strong>Cost Label:</strong> {usage.cost_label}</p>
            </Panel>
          </div>
        </div>
      ) : null}
    </div>
  );
}
