import { useEffect, useState, type FormEvent } from 'react';
import { Layout } from '../components/Layout';
import { Cloud, Plus, Trash2, Loader2, ShieldCheck, Sparkles } from 'lucide-react';
import { cloudApi, aiApi } from '../services/api';
import type { CloudAccount } from '../types';
import toast from 'react-hot-toast';

const AWS_REGIONS = [
  { label: 'US East (N. Virginia)', value: 'us-east-1' },
  { label: 'US East (Ohio)', value: 'us-east-2' },
  { label: 'US West (Oregon)', value: 'us-west-2' },
  { label: 'Asia Pacific (Mumbai)', value: 'ap-south-1' },
  { label: 'Asia Pacific (Tokyo)', value: 'ap-northeast-1' },
  { label: 'Europe (Ireland)', value: 'eu-west-1' },
];

export default function Settings() {
  const [accounts, setAccounts] = useState<CloudAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState('My AWS Account');
  const [region, setRegion] = useState('us-east-1');
  const [accessKeyId, setAccessKeyId] = useState('');
  const [secretAccessKey, setSecretAccessKey] = useState('');
  const [ai, setAi] = useState<any>(null);

  const load = async () => {
    try {
      const res = await cloudApi.list();
      setAccounts(res.data);
    } catch {
      toast.error('Failed to load cloud accounts');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    aiApi
      .status()
      .then((r) => setAi(r.data))
      .catch(() => {});
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await cloudApi.create({
        provider: 'aws',
        name,
        region,
        access_key_id: accessKeyId,
        secret_access_key: secretAccessKey,
      });
      toast.success('Cloud account connected');
      setShowForm(false);
      setAccessKeyId('');
      setSecretAccessKey('');
      setName('My AWS Account');
      await load();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to connect account');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (
      !confirm(
        'Disconnect this cloud account? Deployments that used it will fall back to the server environment credentials.'
      )
    )
      return;
    try {
      await cloudApi.remove(id);
      setAccounts((a) => a.filter((x) => x.id !== id));
      toast.success('Cloud account disconnected');
    } catch {
      toast.error('Failed to disconnect account');
    }
  };

  return (
    <Layout title="Settings">
      <div className="p-6 max-w-3xl mx-auto space-y-6">
        <section className="card p-5">
          <div className="flex items-start gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-dark-800 flex items-center justify-center flex-shrink-0">
              <Cloud className="w-5 h-5 text-primary-400" />
            </div>
            <div className="flex-1">
              <h3 className="text-sm font-semibold text-dark-100">Cloud Accounts</h3>
              <p className="text-xs text-dark-500 mt-0.5">
                Connect an AWS account so CloudForge can run Terraform against it. Credentials are
                encrypted at rest and are only ever used by the backend.
              </p>
            </div>
            <button onClick={() => setShowForm((v) => !v)} className="btn-primary text-xs flex-shrink-0">
              <Plus className="w-3.5 h-3.5" /> Connect AWS
            </button>
          </div>

          {showForm && (
            <form onSubmit={handleSubmit} className="space-y-3 border-t border-dark-800 pt-4 mb-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="label">Account Name</label>
                  <input className="input" value={name} onChange={(e) => setName(e.target.value)} required />
                </div>
                <div>
                  <label className="label">Default Region</label>
                  <select className="input" value={region} onChange={(e) => setRegion(e.target.value)}>
                    {AWS_REGIONS.map((r) => (
                      <option key={r.value} value={r.value} style={{ background: '#1f2937' }}>
                        {r.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label className="label">Access Key ID</label>
                <input
                  className="input font-mono"
                  value={accessKeyId}
                  onChange={(e) => setAccessKeyId(e.target.value)}
                  placeholder="AKIA..."
                  autoComplete="off"
                  required
                />
              </div>
              <div>
                <label className="label">Secret Access Key</label>
                <input
                  className="input font-mono"
                  type="password"
                  value={secretAccessKey}
                  onChange={(e) => setSecretAccessKey(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="new-password"
                  required
                />
              </div>
              <p className="text-[10px] text-dark-500 flex items-center gap-1">
                <ShieldCheck className="w-3 h-3" /> Stored encrypted; never returned by the API, never logged.
              </p>
              <div className="flex gap-2">
                <button type="submit" disabled={saving} className="btn-primary text-xs">
                  {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                  Save account
                </button>
                <button type="button" onClick={() => setShowForm(false)} className="btn-ghost text-xs">
                  Cancel
                </button>
              </div>
            </form>
          )}

          {loading ? (
            <p className="text-xs text-dark-500">Loading…</p>
          ) : accounts.length === 0 ? (
            <p className="text-xs text-dark-500">
              No accounts connected. Without one, deployments use the server's environment credentials
              (if configured).
            </p>
          ) : (
            <ul className="divide-y divide-dark-800">
              {accounts.map((a) => (
                <li key={a.id} className="flex items-center gap-3 py-3">
                  <span className="text-xs font-medium text-dark-200">{a.name}</span>
                  <span className="text-[10px] uppercase text-dark-500">{a.provider}</span>
                  <span className="text-[10px] font-mono text-dark-500">{a.region}</span>
                  <button
                    onClick={() => handleDelete(a.id)}
                    className="ml-auto text-dark-500 hover:text-red-400"
                    title="Disconnect"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card p-5">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-dark-800 flex items-center justify-center flex-shrink-0">
              <Sparkles className="w-5 h-5 text-primary-400" />
            </div>
            <div className="flex-1">
              <h3 className="text-sm font-semibold text-dark-100">AI Assistant</h3>
              <p className="text-xs text-dark-500 mt-0.5">
                Advisory only — the assistant proposes designs and explanations, but the validator
                gates everything and it never deploys infrastructure.
              </p>
              {ai &&
                (ai.configured ? (
                  <p className="text-xs text-emerald-400 mt-2">
                    Configured — provider: <span className="font-mono">{ai.provider}</span>, model:{' '}
                    <span className="font-mono">{ai.model}</span>
                  </p>
                ) : (
                  <p className="text-xs text-dark-500 mt-2">
                    Not configured. Set <span className="font-mono">AI_PROVIDER</span> and{' '}
                    <span className="font-mono">AI_API_KEY</span> (or{' '}
                    <span className="font-mono">AI_BASE_URL</span> for a local model such as Ollama)
                    on the backend to enable it.
                  </p>
                ))}
            </div>
          </div>
        </section>
      </div>
    </Layout>
  );
}
