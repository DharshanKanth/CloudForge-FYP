import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Plus, FolderOpen, Clock, Layers, Trash2, ExternalLink, Cloud, Server, Workflow, ShieldCheck, ArrowRight, RefreshCw, ChevronDown, ChevronUp, Globe, Loader2 } from 'lucide-react';
import { Layout } from '../components/Layout';
import { projectsApi, infrastructureApi, terraformApi } from '../services/api';
import InfraResourceGrid, { categoryMeta } from '../components/InfraResourceGrid';
import type { Project, InfraStackSummary } from '../types';
import { useAuth } from '../hooks/useAuth';
import toast from 'react-hot-toast';

const providerColors: Record<string, string> = { aws: 'badge-aws', azure: 'badge-azure', gcp: 'badge-gcp' };
const providerLabels: Record<string, string> = { aws: '☁ AWS', azure: '⬡ Azure', gcp: '● GCP' };

function timeAgo(dateStr: string): string {
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [liveStacks, setLiveStacks] = useState<InfraStackSummary[]>([]);
  const [destroyingStack, setDestroyingStack] = useState<string | null>(null);
  const [expandedStacks, setExpandedStacks] = useState<Record<string, boolean>>({});
  const { user } = useAuth();
  const navigate = useNavigate();

  const fetchProjects = async () => {
    try {
      const res = await projectsApi.list();
      setProjects(res.data);
    } catch {
      toast.error('Failed to load projects');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchProjects(); }, []);

  // Live-infrastructure tracking: poll the bulk summary so the dashboard
  // always reflects what is actually running in the cloud right now.
  const fetchLive = async () => {
    try {
      const res = await infrastructureApi.summary();
      setLiveStacks(res.data);
    } catch {
      // Nothing deployed or endpoint unavailable — section stays hidden
    }
  };

  useEffect(() => {
    fetchLive();
    const timer = setInterval(fetchLive, 20000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleDestroyStack = async (stack: InfraStackSummary) => {
    if (!stack.project_id) return;
    const label = stack.name || 'this project';
    if (!confirm(`Destroy ALL infrastructure for "${label}" (${stack.resource_count} resources in ${stack.region})? This cannot be undone.`)) return;
    setDestroyingStack(stack.project_id);
    const detail = (err: any) => {
      const d = (err?.response?.data?.detail as any) || err?.response?.data?.detail?.message || null;
      return typeof d === 'string' ? d.split('\n').slice(0, 6).join(' · ') : null;
    };
    try {
      // Same reviewed two-step teardown the Terraform page uses.
      const planRes = await terraformApi.planDestroy(stack.project_id);
      if (planRes.data.status !== 'destroy_planned') {
        const out = planRes.data.output || 'Destroy plan failed';
        toast.error(`Destroy plan failed: ${out.slice(0, 300)}`);
        return;
      }
      const res = await terraformApi.destroy(stack.project_id);
      if (res.data.status === 'destroyed') {
        toast.success(`Infrastructure for "${label}" destroyed`);
        fetchLive();
        fetchProjects();
      } else {
        toast.error(`Destroy failed: ${(res.data.output || 'see project').slice(0, 300)}`);
      }
    } catch (err: any) {
      toast.error(detail(err) || 'Destroy failed');
    } finally {
      setDestroyingStack(null);
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Delete project "${name}"? This cannot be undone.`)) return;
    setDeleting(id);
    try {
      await projectsApi.delete(id);
      setProjects((prev) => prev.filter((p) => p.id !== id));
      toast.success('Project deleted');
    } catch {
      toast.error('Failed to delete project');
    } finally {
      setDeleting(null);
    }
  };

  const awsCount = projects.filter((p) => p.provider === 'aws').length;
  const recentCount = projects.filter((p) => Date.now() - new Date(p.updated_at).getTime() < 7 * 24 * 60 * 60 * 1000).length;

  return (
    <Layout title="Dashboard">
      <div className="p-6 space-y-6 max-w-7xl mx-auto">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-white">Welcome back, <span className="text-gradient">{user?.username}</span></h2>
            <p className="text-dark-400 text-sm mt-1">Manage and deploy your cloud infrastructure</p>
          </div>
          <Link to="/projects/new"><button className="btn-primary"><Plus className="w-4 h-4" />New Project</button></Link>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'Total Projects', value: projects.length, icon: FolderOpen, color: 'text-primary-400', bg: 'bg-primary-900/20' },
            { label: 'AWS Projects', value: awsCount, icon: Cloud, color: 'text-orange-400', bg: 'bg-orange-900/20' },
            { label: 'Live Stacks', value: liveStacks.length, icon: Globe, color: 'text-emerald-400', bg: 'bg-emerald-900/20' },
            { label: 'Modified This Week', value: recentCount, icon: Clock, color: 'text-accent-400', bg: 'bg-accent-900/20' },
          ].map((stat) => {
            const Icon = stat.icon;
            return (
              <div key={stat.label} className="card flex items-center gap-4">
                <div className={`w-11 h-11 rounded-xl ${stat.bg} flex items-center justify-center`}><Icon className={`w-5 h-5 ${stat.color}`} /></div>
                <div><div className="text-2xl font-bold text-white">{stat.value}</div><div className="text-xs text-dark-500">{stat.label}</div></div>
              </div>
            );
          })}
        </div>
        {liveStacks.length > 0 && (
          <section>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-semibold text-dark-300 uppercase tracking-wider">Running Infrastructure</h3>
                <p className="text-xs text-dark-500 mt-1">Live resources tracked by Terraform — destroy them here when you're done</p>
              </div>
              <button onClick={fetchLive} className="btn-ghost text-xs"><RefreshCw className="w-3.5 h-3.5" />Refresh</button>
            </div>
            <div className="space-y-4">
              {liveStacks.map((stack) => (
                <div key={stack.project_id} className="card p-4">
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-900/40 text-emerald-400 text-xs font-semibold">
                      <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                      LIVE — {stack.resource_count} resource{stack.resource_count !== 1 ? 's' : ''}
                    </span>
                    <div className="text-sm font-semibold text-white truncate">{stack.name || 'Project'}</div>
                    <span className="text-xs text-dark-400">Region: <span className="font-mono text-dark-200">{stack.region}</span></span>
                    <div className="flex items-center gap-1 flex-wrap">
                      {Object.entries(stack.categories).filter(([, n]) => n > 0).map(([cat, n]) => (
                        <span key={cat} className="px-1.5 py-0.5 rounded bg-dark-800 text-dark-300 text-[10px] font-mono">
                          {categoryMeta[cat]?.icon} {cat}: {n}
                        </span>
                      ))}
                    </div>
                    {stack.state_updated_at && (
                      <span className="text-[10px] text-dark-600">updated {new Date(stack.state_updated_at * 1000).toLocaleString()}</span>
                    )}
                    <div className="ml-auto flex items-center gap-2">
                      <button
                        onClick={() => setExpandedStacks((prev) => ({ ...prev, [stack.project_id]: !prev[stack.project_id] }))}
                        className="btn-secondary text-xs"
                      >
                        {expandedStacks[stack.project_id] ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                        {expandedStacks[stack.project_id] ? 'Hide' : 'View'} Resources
                      </button>
                      <button onClick={() => navigate(`/projects/${stack.project_id}/terraform`)} className="btn-secondary text-xs" title="Open Terraform view"><ExternalLink className="w-3.5 h-3.5" /></button>
                      <button
                        onClick={() => handleDestroyStack(stack)}
                        disabled={destroyingStack === stack.project_id}
                        className="btn-danger text-xs"
                        title="Destroy all deployed resources for this project"
                      >
                        {destroyingStack === stack.project_id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                        {destroyingStack === stack.project_id ? 'Destroying...' : 'Destroy'}
                      </button>
                    </div>
                  </div>
                  {Object.keys(stack.outputs).length > 0 && (
                    <div className="flex flex-wrap gap-2 mt-3">
                      {Object.entries(stack.outputs).map(([k, v]) => {
                        const text = String(v);
                        if (k.includes('public_ip')) {
                          return (
                            <a key={k} href={`http://${text}`} target="_blank" rel="noreferrer" className="px-2 py-1 rounded-lg bg-primary-900/40 text-primary-300 text-[10px] font-mono hover:bg-primary-900/70">
                              {k}: {text} ↗
                            </a>
                          );
                        }
                        return (
                          <span key={k} className="px-2 py-1 rounded-lg bg-dark-800 text-dark-300 text-[10px] font-mono">
                            {k}: {text.length > 46 ? `${text.slice(0, 46)}…` : text}
                          </span>
                        );
                      })}
                    </div>
                  )}
                  {stack.recent_events && stack.recent_events.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1.5 mt-3 text-[10px]">
                      <span className="uppercase tracking-wider text-dark-600 mr-1">Activity</span>
                      {stack.recent_events.map((ev) => (
                        <span key={ev.id} className={`px-1.5 py-0.5 rounded font-mono ${ev.status === 'succeeded' ? 'bg-emerald-900/40 text-emerald-400' : ev.status === 'blocked' ? 'bg-yellow-900/40 text-yellow-400' : 'bg-red-900/40 text-red-400'}`}>
                          {ev.event_type.replace('_', ' ')}{' '}
                          {ev.status === 'succeeded' ? '✓' : ev.status === 'blocked' ? '⊘' : '✗'}
                          {ev.resource_count != null ? ` · ${ev.resource_count}` : ''}
                        </span>
                      ))}
                    </div>
                  )}
                  {expandedStacks[stack.project_id] && (
                    <div className="mt-4 pt-4 border-t border-dark-800">
                      <InfraResourceGrid resources={stack.resources} />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}
        <section>
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-dark-300 uppercase tracking-wider">Core Features</h3>
              <p className="text-xs text-dark-500 mt-1">Two complete workflows to demonstrate CloudForge</p>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Link to={projects.length > 0 ? `/projects/${projects[0].id}/builder` : '/projects/new'} className="card-hover group flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-primary-900/30 flex items-center justify-center flex-shrink-0">
                <Workflow className="w-6 h-6 text-primary-400" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h4 className="text-sm font-semibold text-dark-100 group-hover:text-white">Visual Infrastructure Builder</h4>
                  <ArrowRight className="w-3.5 h-3.5 text-dark-600 group-hover:text-primary-400 transition-colors" />
                </div>
                <p className="text-xs text-dark-500 mt-1">Design AWS architectures with draggable resources and connections.</p>
              </div>
            </Link>
            <Link to={projects.length > 0 ? `/projects/${projects[0].id}/terraform` : '/projects/new'} className="card-hover group flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-emerald-900/30 flex items-center justify-center flex-shrink-0">
                <ShieldCheck className="w-6 h-6 text-emerald-400" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h4 className="text-sm font-semibold text-dark-100 group-hover:text-white">Validate and Generate Terraform</h4>
                  <ArrowRight className="w-3.5 h-3.5 text-dark-600 group-hover:text-emerald-400 transition-colors" />
                </div>
                <p className="text-xs text-dark-500 mt-1">Check architecture relationships, then export reviewable Terraform files.</p>
              </div>
            </Link>
          </div>
        </section>
        <div>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-dark-300 uppercase tracking-wider">Recent Projects</h3>
            {projects.length > 0 && <span className="text-xs text-dark-500">{projects.length} total</span>}
          </div>
          {loading ? (
            <div className="grid grid-cols-3 gap-4">
              {[1,2,3].map((i) => <div key={i} className="card animate-pulse"><div className="h-4 bg-dark-700 rounded w-2/3 mb-3" /><div className="h-3 bg-dark-800 rounded w-full mb-2" /><div className="h-3 bg-dark-800 rounded w-1/2" /></div>)}
            </div>
          ) : projects.length === 0 ? (
            <div className="card flex flex-col items-center justify-center py-16 text-center">
              <div className="w-16 h-16 rounded-2xl bg-dark-800 flex items-center justify-center mb-4"><Layers className="w-7 h-7 text-dark-500" /></div>
              <h3 className="text-base font-semibold text-dark-300 mb-2">No projects yet</h3>
              <p className="text-dark-500 text-sm mb-5 max-w-sm">Create your first cloud infrastructure project and start designing visually.</p>
              <Link to="/projects/new"><button className="btn-primary"><Plus className="w-4 h-4" />Create First Project</button></Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {projects.map((project) => (
                <div key={project.id} className="card-hover group cursor-pointer" onClick={() => navigate(`/projects/${project.id}/builder`)}>
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span className={providerColors[project.provider]}>{providerLabels[project.provider]}</span>
                      <span className={
                        project.status === 'deployed'
                          ? 'badge bg-emerald-900/40 text-emerald-400'
                          : project.status === 'deploying' || project.status === 'destroying'
                            ? 'badge bg-blue-900/40 text-blue-400'
                            : project.status === 'ready'
                              ? 'badge bg-yellow-900/40 text-yellow-400'
                              : project.status === 'failed'
                                ? 'badge bg-red-900/40 text-red-400'
                                : project.status === 'destroyed'
                                  ? 'badge bg-dark-700 text-dark-400'
                                  : 'badge-success'
                      }>
                        {project.status === 'deployed' ? '● live' : project.status}
                      </span>
                    </div>
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button className="btn-ghost p-1.5" onClick={(e) => { e.stopPropagation(); navigate(`/projects/${project.id}/terraform`); }} title="View Terraform"><ExternalLink className="w-3.5 h-3.5" /></button>
                      <button className="btn-danger p-1.5 text-xs" onClick={(e) => { e.stopPropagation(); handleDelete(project.id, project.name); }} title="Delete project">
                        {deleting === project.id ? <div className="w-3.5 h-3.5 border border-red-400 border-t-transparent rounded-full animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                  </div>
                  <h3 className="font-semibold text-dark-100 mb-1 group-hover:text-white transition-colors truncate">{project.name}</h3>
                  {project.description && <p className="text-dark-500 text-xs mb-3 line-clamp-2">{project.description}</p>}
                  <div className="flex items-center justify-between text-xs text-dark-500 mt-3 pt-3 border-t border-dark-800">
                    <div className="flex items-center gap-1"><Server className="w-3 h-3" />{project.resource_count} resource{project.resource_count !== 1 ? 's' : ''}</div>
                    <div className="flex items-center gap-1"><Clock className="w-3 h-3" />{timeAgo(project.updated_at)}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
