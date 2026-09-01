import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Plus, FolderOpen, Clock, Layers, Trash2, ExternalLink, Cloud, Server } from 'lucide-react';
import { Layout } from '../components/Layout';
import { projectsApi } from '../services/api';
import type { Project } from '../types';
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
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: 'Total Projects', value: projects.length, icon: FolderOpen, color: 'text-primary-400', bg: 'bg-primary-900/20' },
            { label: 'AWS Projects', value: awsCount, icon: Cloud, color: 'text-orange-400', bg: 'bg-orange-900/20' },
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
                      <span className={project.status === 'saved' ? 'badge-success' : 'badge bg-dark-700 text-dark-400'}>{project.status}</span>
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
