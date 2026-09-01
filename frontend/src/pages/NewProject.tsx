import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle, ChevronRight, Lock } from 'lucide-react';
import { Layout } from '../components/Layout';
import { LoadingButton } from '../components/LoadingButton';
import { projectsApi } from '../services/api';
import toast from 'react-hot-toast';

const providers = [
  { id: 'aws', name: 'Amazon Web Services', icon: '☁', available: true, description: 'EC2, VPC, S3, RDS, and more' },
  { id: 'azure', name: 'Microsoft Azure', icon: '⬡', available: false, description: 'Coming soon' },
  { id: 'gcp', name: 'Google Cloud Platform', icon: '●', available: false, description: 'Coming soon' },
];

export default function NewProject() {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [provider, setProvider] = useState('aws');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) { setError('Project name is required'); return; }
    setError('');
    setLoading(true);
    try {
      const res = await projectsApi.create({ name: name.trim(), description, provider });
      toast.success('Project created!');
      navigate(`/projects/${res.data.id}/builder`);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(Array.isArray(detail) ? detail[0]?.msg : detail || 'Failed to create project');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout title="Create New Project">
      <div className="p-6 max-w-2xl mx-auto">
        <div className="mb-6"><p className="text-dark-400 text-sm">Set up a new cloud infrastructure project. You'll be taken to the visual builder after creation.</p></div>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="card space-y-4">
            <h3 className="text-sm font-semibold text-dark-200 pb-2 border-b border-dark-800">Project Details</h3>
            <div><label className="label">Project Name *</label><input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="My AWS Infrastructure" className="input" required maxLength={100} /></div>
            <div>
              <label className="label">Description</label>
              <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Describe what this infrastructure will support..." className="input resize-none" rows={3} maxLength={500} />
              <div className="text-right text-xs text-dark-600 mt-1">{description.length}/500</div>
            </div>
          </div>
          <div className="card space-y-4">
            <h3 className="text-sm font-semibold text-dark-200 pb-2 border-b border-dark-800">Cloud Provider</h3>
            <div className="space-y-3">
              {providers.map((p) => (
                <div key={p.id} onClick={() => p.available && setProvider(p.id)} className={`flex items-center gap-4 p-4 rounded-xl border-2 transition-all duration-150 ${!p.available ? 'opacity-50 cursor-not-allowed border-dark-800' : 'cursor-pointer'} ${provider === p.id && p.available ? 'border-primary-500 bg-primary-900/10' : p.available ? 'border-dark-700 hover:border-dark-600' : 'border-dark-800'}`}>
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-xl ${p.id === 'aws' ? 'bg-orange-900/30' : p.id === 'azure' ? 'bg-blue-900/30' : 'bg-green-900/30'}`}>{p.icon}</div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-dark-100 text-sm">{p.name}</span>
                      {!p.available && <span className="flex items-center gap-1 text-xs text-dark-500"><Lock className="w-3 h-3" />Coming Soon</span>}
                    </div>
                    <div className="text-xs text-dark-500">{p.description}</div>
                  </div>
                  {provider === p.id && p.available && <div className="w-5 h-5 rounded-full bg-primary-500 flex items-center justify-center"><div className="w-2 h-2 rounded-full bg-white" /></div>}
                </div>
              ))}
            </div>
          </div>
          {error && <div className="flex items-start gap-2 p-3 rounded-lg bg-red-900/20 border border-red-800/30 text-red-400 text-sm"><AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />{error}</div>}
          <div className="flex gap-3">
            <button type="button" onClick={() => navigate('/dashboard')} className="btn-secondary">Cancel</button>
            <LoadingButton type="submit" loading={loading} className="flex-1 justify-center">Create Project & Open Builder<ChevronRight className="w-4 h-4" /></LoadingButton>
          </div>
        </form>
      </div>
    </Layout>
  );
}
