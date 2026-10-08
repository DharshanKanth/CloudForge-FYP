import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Editor from '@monaco-editor/react';
import { ArrowLeft, Download, Copy, RefreshCw, FileText, Check, Loader2, Cloud, AlertCircle, Play, Rocket, Trash2, Undo2, Server, History, AlertTriangle, Info, ChevronDown, ChevronUp, Sparkles, Wrench, X } from 'lucide-react';
import { terraformApi, projectsApi, aiApi } from '../services/api';
import InfraResourceGrid, { categoryMeta } from '../components/InfraResourceGrid';
import DeploymentHistory from '../components/DeploymentHistory';
import type { TerraformFile, Project, Infrastructure, DeploymentEvent } from '../types';
import toast from 'react-hot-toast';

const fileIcons: Record<string, string> = {
  'main.tf': '📄', 'variables.tf': '📋', 'outputs.tf': '📤', 'providers.tf': '🔧',
  'network.tf': '🌐', 'compute.tf': '🖥', 'storage.tf': '🪣', 'database.tf': '🗄',
};

function InfraPanel({ infra, deploying, onRefresh, onDestroy, onBackToCode, onPower, busyAddress }: {
  infra: Infrastructure | null;
  deploying: boolean;
  onRefresh: () => void;
  onDestroy: () => void;
  onBackToCode: () => void;
  onPower: (address: string, action: 'start' | 'stop') => void;
  busyAddress: string | null;
}) {
  if (!infra || infra.status !== 'deployed') {
    return (
      <div className="flex-1 flex items-center justify-center h-full">
        <div className="text-center max-w-sm">
          <div className="w-20 h-20 rounded-2xl bg-dark-800 flex items-center justify-center mx-auto mb-5"><Server className="w-9 h-9 text-dark-500" /></div>
          <h3 className="text-base font-semibold text-dark-300 mb-2">Nothing is deployed</h3>
          <p className="text-dark-500 text-sm mb-5">Run Plan and Deploy from the Code view. Once live, every resource shows up here with automatic tracking.</p>
          <button onClick={onBackToCode} className="btn-secondary text-xs"><FileText className="w-3.5 h-3.5" />Open Code View</button>
        </div>
      </div>
    );
  }
  return (
    <div className="space-y-5 max-w-6xl mx-auto pb-6">
      <div className="card flex items-center gap-4 p-4 flex-wrap">
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-900/40 text-emerald-400 text-xs font-semibold">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          LIVE — {infra.resources.length} resource{infra.resources.length !== 1 ? 's' : ''}
        </span>
        <span className="text-xs text-dark-400">Region: <span className="font-mono text-dark-200">{infra.region}</span></span>
        {infra.state_updated_at && (
          <span className="text-xs text-dark-500">State updated {new Date(infra.state_updated_at * 1000).toLocaleString()}</span>
        )}
        <div className="ml-auto flex items-center gap-2">
          <button onClick={onRefresh} className="btn-secondary text-xs"><RefreshCw className="w-3.5 h-3.5" />Refresh</button>
          <button onClick={onDestroy} disabled={deploying} className="btn-danger text-xs">
            {deploying ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
            Destroy Infrastructure
          </button>
        </div>
      </div>
      <InfraResourceGrid resources={infra.resources} onPower={onPower} busyAddress={busyAddress} />
      {Object.keys(infra.outputs).length > 0 && (
        <section>
          <h3 className="text-xs font-semibold text-dark-300 uppercase tracking-wider mb-2">📤 Outputs</h3>
          <div className="card p-3 grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-1.5">
            {Object.entries(infra.outputs).map(([k, v]) => (
              <div key={k} className="flex items-baseline gap-2 text-[11px]">
                <span className="font-mono text-dark-400 truncate">{k}</span>
                <span className="ml-auto font-mono text-primary-300 truncate text-right" title={String(v)}>{String(v)}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

export default function TerraformViewer() {
  const { id: projectId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [project, setProject] = useState<Project | null>(null);
  const [files, setFiles] = useState<TerraformFile[]>([]);
  const [activeFile, setActiveFile] = useState<string>('');
  const [generating, setGenerating] = useState(false);
  const [copied, setCopied] = useState(false);
  const [validationInfo, setValidationInfo] = useState<any>(null);
  const [deploymentStatus, setDeploymentStatus] = useState<string>('');
  const [deploymentOutput, setDeploymentOutput] = useState('');
  const [deploying, setDeploying] = useState(false);
  const [view, setView] = useState<'code' | 'infra' | 'history' | 'runs'>('code');
  const [infra, setInfra] = useState<Infrastructure | null>(null);
  const [events, setEvents] = useState<DeploymentEvent[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [showValidation, setShowValidation] = useState(true);
  const [destroyPlanLocal, setDestroyPlanLocal] = useState(false);
  const [busyAddress, setBusyAddress] = useState<string | null>(null);
  const [deployments, setDeployments] = useState<any[]>([]);
  const [selectedDeployment, setSelectedDeployment] = useState<any>(null);
  const [runLogs, setRunLogs] = useState<any[]>([]);
  const [runsLoading, setRunsLoading] = useState(false);
  const [aiText, setAiText] = useState<{ title: string; body: string } | null>(null);

  useEffect(() => {
    if (!projectId) return;
    projectsApi
      .get(projectId)
      .then((res) => {
        setProject(res.data);
        // Restore the deployment lifecycle from the server so the Deploy /
        // Destroy buttons are enabled correctly after a page reload.
        if (
          ['validated', 'generated', 'ready', 'deploying', 'deployed', 'destroying', 'destroyed', 'failed'].includes(
            res.data.status
          )
        ) {
          setDeploymentStatus(res.data.status);
        }
      })
      .catch(() => {});
    loadTerraform();
  }, [projectId]);

  const loadTerraform = async () => {
    if (!projectId) return;
    try {
      const res = await terraformApi.get(projectId);
      setFiles(res.data.files);
      if (res.data.files.length > 0) setActiveFile(res.data.files[0].filename);
    } catch {
      // Not generated yet - that's fine
    }
  };

  // Live-infrastructure tracking: reads the Terraform state via the backend,
  // so the UI always shows what is actually deployed right now.
  const loadInfra = async () => {
    if (!projectId) return;
    try {
      const res = await terraformApi.infrastructure(projectId);
      setInfra(res.data);
    } catch {
      // No workspace yet — that's fine
    }
  };

  useEffect(() => {
    loadInfra();
    if (view === 'infra') {
      const timer = setInterval(loadInfra, 15000); // keep the live view fresh
      return () => clearInterval(timer);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, projectId]);

  // Auto-refresh history every 10s while the History tab is open
  useEffect(() => {
    if (view !== 'history') return;
    const timer = setInterval(loadEvents, 10000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, projectId]);

  // Load the deployment-run list when the Runs tab is opened.
  useEffect(() => {
    if (view === 'runs') loadDeployments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, projectId]);

  const loadEvents = async () => {
    if (!projectId) return;
    setHistoryLoading(true);
    try {
      const res = await terraformApi.events(projectId);
      setEvents(res.data);
    } catch {
      // History may be empty — that's fine
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    if (view === 'history') loadEvents();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, projectId]);

  const handleGenerate = async () => {
    if (!projectId) return;
    setGenerating(true);
    try {
      const res = await terraformApi.generate(projectId);
      setFiles(res.data.files);
      setValidationInfo(res.data.validation);
      if (res.data.files.length > 0) setActiveFile(res.data.files[0].filename);
      toast.success(`Generated ${res.data.files.length} Terraform files!`);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to generate Terraform');
    } finally {
      setGenerating(false);
    }
  };

  const handleCopy = async () => {
    if (!activeContent) return;
    await navigator.clipboard.writeText(activeContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    toast.success('Copied to clipboard!');
  };

  const handleDownload = async () => {
    if (!projectId) return;
    const url = terraformApi.downloadUrl(projectId);
    try {
      const res = await fetch(url, { credentials: 'include' });
      if (!res.ok) throw new Error('Download failed');
      const blob = await res.blob();
      const downloadUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `cloudforge-${project?.name || projectId}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(downloadUrl);
      toast.success('Downloading ZIP...');
    } catch {
      toast.error('Failed to download ZIP');
    }
  };

  const refreshProject = async () => {
    if (!projectId) return;
    try {
      const r = await projectsApi.get(projectId);
      setProject(r.data);
      setDeploymentStatus(r.data.status);
    } catch {
      // ignore
    }
  };

  // Poll a queued deployment's streamed logs until it reaches a terminal state.
  const pollDeployment = async (deploymentId: string): Promise<'succeeded' | 'failed'> => {
    if (!projectId) return 'failed';
    let after = -1;
    let buffer = '';
    for (;;) {
      let res;
      try {
        res = await terraformApi.deploymentLogs(projectId, deploymentId, after);
      } catch {
        await new Promise((r) => setTimeout(r, 1500));
        continue;
      }
      for (const l of res.data.logs) {
        buffer += `${l.message}\n`;
        after = l.seq;
      }
      setDeploymentOutput(buffer.slice(-10000));
      const status = res.data.deployment.status;
      if (status === 'succeeded' || status === 'failed') return status;
      await new Promise((r) => setTimeout(r, 1000));
    }
  };

  // Enqueue an operation for the isolated worker, then stream its logs.
  const runOperation = async (
    op: 'plan' | 'apply' | 'plan_destroy' | 'destroy',
    confirmMsg?: string
  ) => {
    if (!projectId) return;
    if (confirmMsg && !confirm(confirmMsg)) return;
    setDeploying(true);
    setDeploymentOutput('Queued…\n');
    try {
      const res =
        op === 'plan' ? await terraformApi.plan(projectId)
        : op === 'apply' ? await terraformApi.apply(projectId)
        : op === 'plan_destroy' ? await terraformApi.planDestroy(projectId)
        : await terraformApi.destroy(projectId);
      const final = await pollDeployment(res.data.id);
      await refreshProject();
      await loadInfra();
      loadEvents();
      if (final === 'succeeded') {
        if (op === 'plan') toast.success('Terraform plan created');
        else if (op === 'apply') toast.success('Infrastructure deployed');
        else if (op === 'plan_destroy') {
          setDestroyPlanLocal(true);
          toast.success('Destroy plan created — review it, then Destroy');
        } else {
          setDestroyPlanLocal(false);
          toast.success('Infrastructure destroyed');
        }
      } else {
        toast.error(`${op.replace('_', ' ')} failed — see output below`);
      }
    } catch (err: any) {
      setDeploymentStatus('failed');
      setDeploymentOutput(
        err.response?.data?.detail?.message || err.response?.data?.detail || 'Operation failed'
      );
      toast.error('Operation failed');
    } finally {
      setDeploying(false);
    }
  };

  const handlePlan = () => runOperation('plan');
  const handleApply = () => runOperation('apply', 'Deploy these resources to AWS? Review the plan first.');
  const handlePlanDestroy = () => runOperation('plan_destroy');
  const handleDestroy = () => runOperation('destroy', 'Destroy the deployed AWS infrastructure? This cannot be undone.');

  // One-click teardown from the Live Infrastructure view: plan-destroy → destroy.
  const handleInfraDestroy = async () => {
    if (!projectId || !confirm(`Destroy ALL deployed infrastructure in ${infra?.region || 'your region'}? This cannot be undone.`)) return;
    await runOperation('plan_destroy');
    await runOperation('destroy');
  };

  // Start/stop a deployed compute resource in place (provider API, not destroy).
  const handlePower = async (address: string, action: 'start' | 'stop') => {
    if (!projectId) return;
    setBusyAddress(address);
    try {
      const res = await terraformApi.power(projectId, address, action);
      if (res.data.state === 'started' || res.data.state === 'stopped') {
        toast.success(`${action === 'start' ? 'Started' : 'Stopped'} ${address}`);
        await loadInfra();
        loadEvents();
      } else {
        toast.error(res.data.message || 'Operation failed');
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Operation failed');
    } finally {
      setBusyAddress(null);
    }
  };

  // ── Deployment runs (jobs) + their streamed logs ────────────────────
  const loadDeployments = async () => {
    if (!projectId) return;
    setRunsLoading(true);
    try {
      const res = await terraformApi.deployments(projectId);
      setDeployments(res.data);
    } catch {
      // ignore
    } finally {
      setRunsLoading(false);
    }
  };

  const openDeployment = async (dep: any) => {
    if (!projectId) return;
    setSelectedDeployment(dep);
    try {
      const res = await terraformApi.deploymentLogs(projectId, dep.id, -1);
      setRunLogs(res.data.logs || []);
    } catch {
      setRunLogs([]);
    }
  };

  const runStatusClass = (status: string) =>
    status === 'succeeded'
      ? 'text-emerald-400'
      : status === 'failed'
        ? 'text-red-400'
        : status === 'running'
          ? 'text-blue-400'
          : 'text-dark-500';

  // ── Advisory AI actions ─────────────────────────────────────────────
  const runAi = async (kind: 'explain' | 'troubleshoot') => {
    if (!projectId) return;
    const toastId = toast.loading('Asking the AI…');
    try {
      const res =
        kind === 'explain'
          ? await aiApi.explain(projectId)
          : await aiApi.troubleshoot(projectId, deploymentOutput || 'Unknown error');
      toast.dismiss(toastId);
      if (!res.data.configured) {
        toast.error(res.data.message || 'AI is not configured');
        return;
      }
      setAiText({
        title: kind === 'explain' ? 'Terraform explained (AI)' : 'Troubleshooting (AI)',
        body: res.data.text || '',
      });
    } catch (err: any) {
      toast.dismiss(toastId);
      toast.error(err.response?.data?.detail || 'AI request failed');
    }
  };

  const handleClear = async (force = false) => {
    if (!projectId) return;
    if (!force && !confirm('Clear the local Terraform workspace? This removes the local state file and any cached plans.')) return;
    if (force && !confirm('Force-clear anyway? Deployed resources keep running in AWS, but CloudForge will lose track of them.')) return;
    try {
      await terraformApi.clear(projectId, force);
      setDeploymentStatus('');
      setDeploymentOutput('');
      setView('code');
      loadInfra();
      loadEvents();
      toast.success('Workspace cleared — run Plan to start fresh');
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (err.response?.status === 409 && detail?.live_resources) {
        // Guard: live infrastructure exists. Offer destroy (recommended) or force.
        if (confirm(`${detail.message}`)) await handleClear(true);
      } else {
        toast.error(detail?.message || 'Failed to clear workspace');
      }
    }
  };

  const activeContent = files.find((f) => f.filename === activeFile)?.content || '';
  const destroyPlanReady = Boolean(infra?.destroy_plan_ready) || destroyPlanLocal;

  return (
    <div className="flex flex-col h-screen bg-dark-950 overflow-hidden">
      <header className="flex items-center gap-3 px-4 py-2.5 bg-dark-900 border-b border-dark-800 flex-shrink-0">
        <button onClick={() => navigate(`/projects/${projectId}/builder`)} className="btn-ghost p-2 -ml-1" title="Back to Builder"><ArrowLeft className="w-4 h-4" /></button>
        <div className="flex items-center gap-2 mr-4">
          <div className="w-6 h-6 bg-gradient-to-br from-primary-500 to-accent-600 rounded-md flex items-center justify-center"><Cloud className="w-3 h-3 text-white" /></div>
          <div>
            <div className="text-sm font-semibold text-white leading-none">{project?.name || 'Project'}</div>
            <div className="text-[10px] text-dark-500 capitalize">{project?.provider} · Terraform</div>
          </div>
        </div>
        <div className="flex-1" />
        <div className="flex items-center gap-2">
          <button onClick={handleGenerate} disabled={generating} className="btn-primary text-xs">
            {generating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
            {generating ? 'Generating...' : 'Generate Terraform'}
          </button>
          {files.length > 0 && <>
            <button onClick={handleCopy} className="btn-secondary text-xs">{copied ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}{copied ? 'Copied!' : 'Copy'}</button>
            <button onClick={handleDownload} className="btn-secondary text-xs"><Download className="w-3.5 h-3.5" /></button>
            <button onClick={handlePlan} disabled={deploying} className="btn-secondary text-xs"><Play className="w-3.5 h-3.5" />{deploying ? 'Working...' : 'Plan'}</button>
            <button onClick={handleApply} disabled={deploying || deploymentStatus !== 'ready'} className="btn-primary text-xs"><Rocket className="w-3.5 h-3.5" />Deploy</button>
            {deploymentStatus === 'deployed' && (
              <button onClick={handlePlanDestroy} disabled={deploying} className="btn-secondary text-xs" title="Create a reviewable destroy plan"><Undo2 className="w-3.5 h-3.5" />{deploying ? 'Working...' : 'Plan Destroy'}</button>
            )}
            {deploymentStatus === 'deployed' && destroyPlanReady && (
              <span className="text-[10px] text-yellow-400">Destroy plan ready — click Destroy to tear down</span>
            )}
            {deploymentStatus === 'failed' && (
              <button onClick={() => handleClear()} disabled={deploying} className="btn-danger text-xs" title="Clear stale Terraform state"><Trash2 className="w-3.5 h-3.5" />Clear</button>
            )}
            <button onClick={handleDestroy} disabled={deploying || deploymentStatus !== 'deployed' || !destroyPlanReady} className="btn-danger text-xs" title="Destroy deployed infrastructure"><Trash2 className="w-3.5 h-3.5" /></button>
          </>}
        </div>
      </header>
      {validationInfo && (() => {
        const issues = validationInfo.issues || [];
        const errors = issues.filter((i: any) => i.level === 'error');
        const warnings = issues.filter((i: any) => i.level === 'warning');
        const infos = issues.filter((i: any) => i.level === 'info');
        return (
          <div className="border-b border-dark-800">
            <div className="flex items-center gap-3 px-4 py-2">
              <button onClick={() => setShowValidation((v) => !v)} className="flex items-center gap-3 flex-1 text-left min-w-0">
                {validationInfo.valid ? <Check className="w-4 h-4 text-emerald-400 flex-shrink-0" /> : <AlertCircle className="w-4 h-4 text-yellow-400 flex-shrink-0" />}
                <span className={`text-xs flex-shrink-0 ${validationInfo.valid ? 'text-emerald-400' : 'text-yellow-400'}`}>
                  Validation{validationInfo.valid ? ' — looks good' : ' — issues found'}
                </span>
                <span className="text-[10px] text-dark-500 truncate">
                  {errors.length > 0 && <span className="text-red-400">{errors.length} error{errors.length !== 1 ? 's' : ''}</span>}
                  {errors.length > 0 && warnings.length > 0 && <span> · </span>}
                  {warnings.length > 0 && <span className="text-yellow-400">{warnings.length} warning{warnings.length !== 1 ? 's' : ''}</span>}
                  {infos.length > 0 && <span className="text-dark-400">{warnings.length > 0 || errors.length > 0 ? ' · ' : ''}{infos.length} info</span>}
                </span>
                {showValidation ? <ChevronUp className="w-4 h-4 text-dark-500 flex-shrink-0" /> : <ChevronDown className="w-4 h-4 text-dark-500 flex-shrink-0" />}
              </button>
              {!validationInfo.valid && (
                <button onClick={() => navigate(`/projects/${projectId}/builder`)} className="ml-auto text-xs text-yellow-400 underline hover:no-underline flex-shrink-0">Fix in Builder</button>
              )}
            </div>
            {showValidation && issues.length > 0 && (
              <div className="px-4 pb-3 space-y-1 max-h-52 overflow-y-auto">
                {issues.map((issue: any, idx: number) => (
                  <div key={idx} className="flex items-start gap-2 text-[11px]">
                    {issue.level === 'error'
                      ? <AlertCircle className="w-3.5 h-3.5 text-red-400 mt-0.5 flex-shrink-0" />
                      : issue.level === 'warning'
                        ? <AlertTriangle className="w-3.5 h-3.5 text-yellow-400 mt-0.5 flex-shrink-0" />
                        : <Info className="w-3.5 h-3.5 text-blue-400 mt-0.5 flex-shrink-0" />}
                    <span className={issue.level === 'error' ? 'text-red-300' : issue.level === 'warning' ? 'text-yellow-300' : 'text-dark-300'}>{issue.message}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })()}
      {deploymentStatus && (
        <div className={`px-4 py-2 border-b ${deploymentStatus === 'failed' ? 'bg-red-900/20 border-red-800/30' : 'bg-emerald-900/20 border-emerald-800/30'}`}>
          <div className="flex items-center gap-2 text-xs">
            {deploymentStatus === 'failed' ? <AlertCircle className="w-4 h-4 text-red-400" /> : <Check className="w-4 h-4 text-emerald-400" />}
            <span className={deploymentStatus === 'failed' ? 'text-red-400' : 'text-emerald-400'}>Deployment: {deploymentStatus}</span>
          </div>
          {deploymentOutput && <pre className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap text-[10px] text-dark-300 font-mono">{deploymentOutput}</pre>}
          {deploymentStatus === 'failed' && (
            <div className="mt-1 flex items-center gap-2 text-[10px] text-red-300">
              <span>
                If this error is from stale state (e.g. "couldn't find resource"), click{' '}
                <span className="underline font-medium">Clear</span> above to reset the workspace, then re-run Plan.
              </span>
              <button onClick={() => runAi('troubleshoot')} className="ml-auto btn-secondary text-[10px] flex-shrink-0" title="Explain this error with AI">
                <Wrench className="w-3 h-3" />Troubleshoot with AI
              </button>
            </div>
          )}
        </div>
      )}
      <div className="flex flex-1 overflow-hidden">
        <aside className="w-52 bg-dark-900 border-r border-dark-800 flex flex-col flex-shrink-0">
          <div className="grid grid-cols-4 border-b border-dark-800 flex-shrink-0">
            <button onClick={() => setView('code')} className={`py-2.5 text-[11px] font-semibold transition-colors ${view === 'code' ? 'text-primary-300 bg-dark-800/60 border-b-2 border-primary-500' : 'text-dark-500 hover:text-dark-300'}`}><FileText className="w-3 h-3 inline mr-1 -mt-0.5" />Code</button>
            <button onClick={() => { setView('infra'); loadInfra(); }} className={`py-2.5 text-[11px] font-semibold transition-colors ${view === 'infra' ? 'text-primary-300 bg-dark-800/60 border-b-2 border-primary-500' : 'text-dark-500 hover:text-dark-300'}`}>
              Infra{infra?.status === 'deployed' && <span className="ml-1 text-emerald-400">●{infra.resources.length}</span>}
            </button>
            <button onClick={() => setView('runs')} className={`py-2.5 text-[11px] font-semibold transition-colors ${view === 'runs' ? 'text-primary-300 bg-dark-800/60 border-b-2 border-primary-500' : 'text-dark-500 hover:text-dark-300'}`}><Rocket className="w-3 h-3 inline mr-1 -mt-0.5" />Runs</button>
            <button onClick={() => setView('history')} className={`py-2.5 text-[11px] font-semibold transition-colors ${view === 'history' ? 'text-primary-300 bg-dark-800/60 border-b-2 border-primary-500' : 'text-dark-500 hover:text-dark-300'}`}><History className="w-3 h-3 inline mr-1 -mt-0.5" />History</button>
          </div>
          {view === 'code' ? (
            <>
              <div className="px-4 py-2 border-b border-dark-800">
                <div className="text-[10px] text-dark-600">{files.length} file{files.length !== 1 ? 's' : ''} generated</div>
              </div>
              <div className="flex-1 py-2 overflow-y-auto">
                {files.length === 0 ? (
                  <div className="px-4 py-6 text-center"><FileText className="w-8 h-8 text-dark-700 mx-auto mb-2" /><p className="text-xs text-dark-500">No Terraform generated yet.<br />Click Generate Terraform.</p></div>
                ) : (
                  files.map((file) => (
                    <button key={file.filename} onClick={() => setActiveFile(file.filename)} className={`w-full flex items-center gap-2.5 px-4 py-2.5 text-left transition-all duration-150 ${activeFile === file.filename ? 'bg-primary-900/20 text-primary-300 border-r-2 border-primary-500' : 'text-dark-400 hover:bg-dark-800 hover:text-dark-200'}`}>
                      <span className="text-sm">{fileIcons[file.filename] || '📄'}</span>
                      <span className="text-xs font-mono font-medium truncate">{file.filename}</span>
                    </button>
                  ))
                )}
              </div>
            </>
          ) : view === 'infra' ? (
            <div className="flex-1 py-2 overflow-y-auto">
              {infra?.status === 'deployed' ? (
                ['compute', 'network', 'data'].map((cat) => {
                  const items = infra.resources.filter((r) => r.category === cat);
                  if (items.length === 0) return null;
                  const meta = categoryMeta[cat];
                  return (
                    <div key={cat} className="px-3 py-2">
                      <div className="text-[10px] uppercase tracking-wider text-dark-500 mb-1">{meta.icon} {meta.label} ({items.length})</div>
                      {items.map((r) => (
                        <div key={r.address} className="px-2 py-1.5 rounded hover:bg-dark-800 transition-colors">
                          <div className="text-[10px] font-medium text-dark-200 truncate">{r.label}</div>
                          <div className="text-[9px] font-mono text-dark-600 truncate">{r.type.replace('aws_', '')}</div>
                        </div>
                      ))}
                    </div>
                  );
                })
              ) : (
                <div className="px-4 py-6 text-center"><Server className="w-7 h-7 text-dark-700 mx-auto mb-2" /><p className="text-[10px] text-dark-500">Nothing deployed yet</p></div>
              )}
            </div>
          ) : null}
        </aside>
        <div className="flex-1 flex flex-col overflow-hidden">
          {view === 'runs' ? (
            <div className="flex-1 overflow-hidden flex">
              <div className="w-72 border-r border-dark-800 overflow-y-auto flex-shrink-0">
                {runsLoading && <p className="p-4 text-xs text-dark-500">Loading…</p>}
                {!runsLoading && deployments.length === 0 && (
                  <p className="p-4 text-xs text-dark-500">No deployments yet. Run Plan or Deploy.</p>
                )}
                {deployments.map((d) => (
                  <button
                    key={d.id}
                    onClick={() => openDeployment(d)}
                    className={`w-full text-left px-4 py-2.5 border-b border-dark-800 transition-colors ${selectedDeployment?.id === d.id ? 'bg-dark-800' : 'hover:bg-dark-800/50'}`}
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-dark-200 capitalize">{d.operation.replace('_', ' ')}</span>
                      <span className={`ml-auto text-[10px] font-semibold ${runStatusClass(d.status)}`}>{d.status}</span>
                    </div>
                    <div className="text-[10px] text-dark-500 mt-0.5 truncate">
                      {d.created_at ? new Date(d.created_at).toLocaleString() : ''}
                      {d.resource_count != null ? ` · ${d.resource_count} resources` : ''}
                    </div>
                  </button>
                ))}
              </div>
              <div className="flex-1 overflow-y-auto p-4">
                {selectedDeployment ? (
                  <>
                    <div className="flex items-center gap-3 mb-3">
                      <span className="text-sm font-semibold text-dark-100 capitalize">{selectedDeployment.operation.replace('_', ' ')}</span>
                      <span className={`text-[10px] font-semibold ${runStatusClass(selectedDeployment.status)}`}>{selectedDeployment.status}</span>
                      <button onClick={() => openDeployment(selectedDeployment)} className="ml-auto btn-secondary text-xs"><RefreshCw className="w-3.5 h-3.5" />Reload logs</button>
                    </div>
                    <pre className="text-[11px] font-mono text-dark-300 bg-dark-900 border border-dark-800 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap">{runLogs.length ? runLogs.map((l) => l.message).join('\n') : '(no logs)'}</pre>
                  </>
                ) : (
                  <div className="h-full flex items-center justify-center text-xs text-dark-500">Select a deployment to view its logs.</div>
                )}
              </div>
            </div>
          ) : view === 'history' ? (
            <div className="flex-1 overflow-y-auto p-4">
              <DeploymentHistory events={events} loading={historyLoading} onRefresh={loadEvents} />
            </div>
          ) : view === 'infra' ? (
            <div className="flex-1 overflow-y-auto p-4">
              <InfraPanel
                infra={infra}
                deploying={deploying}
                onRefresh={loadInfra}
                onDestroy={handleInfraDestroy}
                onBackToCode={() => setView('code')}
                onPower={handlePower}
                busyAddress={busyAddress}
              />
            </div>
          ) : files.length === 0 ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center max-w-sm">
                <div className="w-20 h-20 rounded-2xl bg-dark-800 flex items-center justify-center mx-auto mb-5"><FileText className="w-9 h-9 text-dark-500" /></div>
                <h3 className="text-base font-semibold text-dark-300 mb-2">No Terraform Generated</h3>
                <p className="text-dark-500 text-sm mb-5">Design your infrastructure in the visual builder, then generate Terraform.</p>
                <div className="flex gap-2 justify-center">
                  <button onClick={() => navigate(`/projects/${projectId}/builder`)} className="btn-secondary text-xs"><ArrowLeft className="w-3.5 h-3.5" />Back to Builder</button>
                  <button onClick={handleGenerate} disabled={generating} className="btn-primary text-xs">{generating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}Generate Terraform</button>
                </div>
              </div>
            </div>
          ) : (
            <>
              {activeFile && (
                <div className="flex items-center gap-2 px-4 py-2 bg-dark-900 border-b border-dark-800">
                  <span className="text-sm">{fileIcons[activeFile] || '📄'}</span>
                  <span className="text-xs font-mono text-dark-300 font-medium">{activeFile}</span>
                  <button onClick={() => runAi('explain')} className="ml-auto btn-ghost text-[11px]" title="Explain this Terraform with AI"><Sparkles className="w-3.5 h-3.5" />Explain</button>
                  <span className="text-[10px] text-dark-600">{activeContent.split('\n').length} lines · HCL (Terraform)</span>
                </div>
              )}
              <div className="flex-1">
                <Editor value={activeContent} language="hcl" theme="vs-dark" options={{ readOnly: true, minimap: { enabled: true }, fontSize: 13, fontFamily: 'JetBrains Mono, Fira Code, monospace', lineNumbers: 'on', scrollBeyondLastLine: false, wordWrap: 'on', automaticLayout: true, padding: { top: 16 } }} />
              </div>
            </>
          )}
        </div>
      </div>

      {aiText && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={() => setAiText(null)}>
          <div className="card w-full max-w-2xl max-h-[80vh] flex flex-col p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center gap-2 mb-3">
              <Sparkles className="w-4 h-4 text-primary-400" />
              <h3 className="text-sm font-semibold text-dark-100">{aiText.title}</h3>
              <button onClick={() => setAiText(null)} className="ml-auto text-dark-500 hover:text-dark-200"><X className="w-4 h-4" /></button>
            </div>
            <div className="flex-1 overflow-y-auto whitespace-pre-wrap text-xs text-dark-300 leading-relaxed">{aiText.body}</div>
          </div>
        </div>
      )}
    </div>
  );
}
