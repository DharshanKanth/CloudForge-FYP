import { useEffect, useState, type FormEvent } from 'react';
import { Layout } from '../components/Layout';
import { Cloud, Plus, Trash2, Loader2, ShieldCheck, Sparkles, CheckCircle2, XCircle } from 'lucide-react';
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
  const [showAiForm, setShowAiForm] = useState(false);
  const [aiProvider, setAiProvider] = useState('openai');
  const [aiBaseUrl, setAiBaseUrl] = useState('');
  const [aiModel, setAiModel] = useState('');
  const [aiKey, setAiKey] = useState('');
  const [aiTest, setAiTest] = useState<any>(null);
  const [aiSaving, setAiSaving] = useState(false);
  const [aiTesting, setAiTesting] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);
  const [verifyResults, setVerifyResults] = useState<Record<string, any>>({});

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

  const reloadAi = async () => {
    try {
      const r = await aiApi.status();
      setAi(r.data);
    } catch {
      /* ignore */
    }
  };

  const saveAi = async (e: FormEvent) => {
    e.preventDefault();
    setAiSaving(true);
    setAiTest(null);
    try {
      await aiApi.saveSettings({
        provider: aiProvider,
        base_url: aiBaseUrl || null,
        model: aiModel,
        api_key: aiKey || null,
      });
      toast.success('AI settings saved');
      setAiKey('');
      await reloadAi();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save AI settings');
    } finally {
      setAiSaving(false);
    }
  };

  const testAi = async () => {
    setAiTesting(true);
    setAiTest(null);
    try {
      const res = await aiApi.testSettings({
        provider: aiProvider,
        base_url: aiBaseUrl || null,
        model: aiModel,
        api_key: aiKey || null,
      });
      setAiTest(res.data);
      if (res.data.ok) toast.success('Connection successful');
      else toast.error('Connection failed');
    } catch (err: any) {
      setAiTest({ ok: false, message: err.response?.data?.detail || 'Test failed' });
    } finally {
      setAiTesting(false);
    }
  };

  const clearAi = async () => {
    try {
      await aiApi.deleteSettings();
      toast.success('AI settings cleared — using the server default');
      await reloadAi();
    } catch {
      toast.error('Failed to clear AI settings');
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await cloudApi.verifyCredentials({
        provider: 'aws',
        name,
        region,
        access_key_id: accessKeyId,
        secret_access_key: secretAccessKey,
      });
      setTestResult(res.data);
      if (res.data.valid) toast.success(`Credentials valid — account ${res.data.account}`);
      else toast.error('Credentials invalid — see the message below');
    } catch (err: any) {
      setTestResult({ valid: false, error: err.response?.data?.detail || 'Verification failed' });
      toast.error('Verification failed');
    } finally {
      setTesting(false);
    }
  };

  const handleVerify = async (id: string) => {
    try {
      const res = await cloudApi.verify(id);
      setVerifyResults((m) => ({ ...m, [id]: res.data }));
      if (res.data.valid) toast.success(`Account verified (${res.data.account})`);
      else toast.error('Account verification failed');
    } catch (err: any) {
      setVerifyResults((m) => ({
        ...m,
        [id]: { valid: false, error: err.response?.data?.detail || 'Verification failed' },
      }));
      toast.error('Verification failed');
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
                <button
                  type="button"
                  onClick={handleTest}
                  disabled={testing || !accessKeyId || !secretAccessKey}
                  className="btn-secondary text-xs"
                >
                  {testing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ShieldCheck className="w-3.5 h-3.5" />}
                  {testing ? 'Testing…' : 'Test connection'}
                </button>
                <button type="button" onClick={() => setShowForm(false)} className="btn-ghost text-xs">
                  Cancel
                </button>
              </div>
              {testResult && (
                <p className={`text-[11px] ${testResult.valid ? 'text-emerald-400' : 'text-red-400'}`}>
                  {testResult.valid
                    ? `✓ Valid — AWS account ${testResult.account}`
                    : `✗ ${testResult.error}`}
                </p>
              )}
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
                <li key={a.id} className="py-3">
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-medium text-dark-200">{a.name}</span>
                    <span className="text-[10px] uppercase text-dark-500">{a.provider}</span>
                    <span className="text-[10px] font-mono text-dark-500">{a.region}</span>
                    <button
                      onClick={() => handleVerify(a.id)}
                      className="ml-auto text-dark-500 hover:text-emerald-400 text-[11px] inline-flex items-center gap-1"
                      title="Verify credentials"
                    >
                      <ShieldCheck className="w-3.5 h-3.5" />Verify
                    </button>
                    <button
                      onClick={() => handleDelete(a.id)}
                      className="text-dark-500 hover:text-red-400"
                      title="Disconnect"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  {verifyResults[a.id] && (
                    <p
                      className={`text-[10px] mt-1 inline-flex items-center gap-1 ${
                        verifyResults[a.id].valid ? 'text-emerald-400' : 'text-red-400'
                      }`}
                    >
                      {verifyResults[a.id].valid ? (
                        <>
                          <CheckCircle2 className="w-3 h-3" /> AWS account {verifyResults[a.id].account}
                        </>
                      ) : (
                        <>
                          <XCircle className="w-3 h-3" /> {verifyResults[a.id].error}
                        </>
                      )}
                    </p>
                  )}
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
                gates everything and it never deploys infrastructure. Add your own provider key, or
                point it at a local model such as Ollama.
              </p>
              {ai &&
                (ai.configured ? (
                  <p className="text-xs text-emerald-400 mt-2">
                    Configured — provider: <span className="font-mono">{ai.provider}</span>, model:{' '}
                    <span className="font-mono">{ai.model}</span>{' '}
                    <span className="text-dark-500">
                      ({ai.source === 'user' ? 'your account' : 'server default'})
                    </span>
                    {ai.vision && <span className="text-primary-300"> · image import ✓</span>}
                  </p>
                ) : (
                  <p className="text-xs text-dark-500 mt-2">
                    Not configured — add a provider below to enable the assistant.
                  </p>
                ))}
            </div>
            <button
              type="button"
              className="btn-secondary text-xs flex-shrink-0"
              onClick={() => {
                if (!showAiForm && ai) {
                  setAiProvider(ai.provider === 'ollama' ? 'ollama' : 'openai');
                  setAiBaseUrl(ai.base_url || '');
                  setAiModel(ai.model || '');
                  setAiTest(null);
                }
                setShowAiForm((v) => !v);
              }}
            >
              {showAiForm ? 'Close' : 'Configure'}
            </button>
          </div>

          {showAiForm && (
            <form onSubmit={saveAi} className="space-y-3 border-t border-dark-800 pt-4 mt-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="label">Provider</label>
                  <select
                    className="input"
                    value={aiProvider}
                    onChange={(e) => setAiProvider(e.target.value)}
                  >
                    <option value="openai">OpenAI-compatible (hosted)</option>
                    <option value="ollama">Ollama (local)</option>
                  </select>
                </div>
                <div>
                  <label className="label">Model</label>
                  <input
                    className="input"
                    value={aiModel}
                    onChange={(e) => setAiModel(e.target.value)}
                    placeholder={aiProvider === 'ollama' ? 'llama3.1' : 'gpt-4o-mini'}
                  />
                </div>
              </div>
              <div>
                <label className="label">
                  Base URL {aiProvider === 'ollama' ? '(your local server)' : '(optional)'}
                </label>
                <input
                  className="input font-mono"
                  value={aiBaseUrl}
                  onChange={(e) => setAiBaseUrl(e.target.value)}
                  placeholder={
                    aiProvider === 'ollama'
                      ? 'http://host.docker.internal:11434/v1'
                      : 'https://api.openai.com/v1'
                  }
                />
              </div>
              <div>
                <label className="label">
                  API Key {aiProvider === 'ollama' ? '(not needed for local)' : ''}
                </label>
                <input
                  className="input font-mono"
                  type="password"
                  value={aiKey}
                  onChange={(e) => setAiKey(e.target.value)}
                  placeholder={ai.has_api_key ? '•••••• (leave blank to keep)' : 'sk-...'}
                  autoComplete="off"
                />
              </div>
              {aiTest && (
                <p className={`text-[11px] ${aiTest.ok ? 'text-emerald-400' : 'text-red-400'}`}>
                  {aiTest.ok ? '✓ ' : '✗ '}
                  {aiTest.message}
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                <button type="submit" disabled={aiSaving} className="btn-primary text-xs">
                  {aiSaving ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Sparkles className="w-3.5 h-3.5" />
                  )}
                  Save
                </button>
                <button
                  type="button"
                  onClick={testAi}
                  disabled={aiTesting}
                  className="btn-secondary text-xs"
                >
                  {aiTesting ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <ShieldCheck className="w-3.5 h-3.5" />
                  )}
                  Test connection
                </button>
                <button type="button" onClick={clearAi} className="btn-ghost text-xs">
                  <Trash2 className="w-3.5 h-3.5" />
                  Clear
                </button>
              </div>
              <p className="text-[10px] text-dark-600">
                The API key is encrypted at rest and never returned. Local model example: Base URL{' '}
                <span className="font-mono">http://host.docker.internal:11434/v1</span> when the app
                runs in Docker, or <span className="font-mono">http://localhost:11434/v1</span>{' '}
                otherwise.
              </p>
            </form>
          )}
        </section>
      </div>
    </Layout>
  );
}
