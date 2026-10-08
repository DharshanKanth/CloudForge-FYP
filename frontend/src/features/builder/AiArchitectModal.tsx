import { useState } from 'react';
import { Sparkles, X, Loader2, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { aiApi } from '../../services/api';
import toast from 'react-hot-toast';

interface AiArchitectModalProps {
  onApply: (nodes: any[], edges: any[]) => void;
  onClose: () => void;
}

/**
 * Advisory AI assistant: it proposes an architecture, the deterministic
 * validator scores it, and the user must click Apply. Nothing is deployed.
 */
export function AiArchitectModal({ onApply, onClose }: AiArchitectModalProps) {
  const [prompt, setPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [notConfigured, setNotConfigured] = useState<string | null>(null);

  const submit = async () => {
    if (!prompt.trim()) return;
    setLoading(true);
    setResult(null);
    setNotConfigured(null);
    try {
      const res = await aiApi.architect(prompt.trim());
      if (!res.data.configured) {
        setNotConfigured(res.data.message || 'AI is not configured on the backend.');
        return;
      }
      setResult(res.data);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'AI request failed');
    } finally {
      setLoading(false);
    }
  };

  const apply = () => {
    if (!result) return;
    onApply(result.nodes || [], result.edges || []);
    toast.success('AI suggestion applied — review, then Validate');
    onClose();
  };

  const issues = result?.validation?.issues || [];
  const errors = issues.filter((i: any) => i.level === 'error');
  const warnings = issues.filter((i: any) => i.level === 'warning');

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={onClose}>
      <div className="card w-full max-w-lg p-5" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 mb-3">
          <Sparkles className="w-4 h-4 text-primary-400" />
          <h3 className="text-sm font-semibold text-dark-100">AI Architecture Assistant</h3>
          <button onClick={onClose} className="ml-auto text-dark-500 hover:text-dark-200">
            <X className="w-4 h-4" />
          </button>
        </div>
        <p className="text-xs text-dark-500 mb-3">
          Describe what you want. The AI proposes a design; CloudForge validates it and nothing is
          deployed until you approve.
        </p>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={3}
          className="input w-full"
          placeholder="e.g. a web app with a load balancer, two app servers behind it, and an RDS database"
        />
        <div className="flex gap-2 mt-3">
          <button onClick={submit} disabled={loading || !prompt.trim()} className="btn-primary text-xs">
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
            {loading ? 'Thinking…' : 'Generate suggestion'}
          </button>
        </div>

        {notConfigured && (
          <div className="mt-4 flex items-start gap-2 p-3 rounded-lg bg-dark-800 text-dark-300 text-xs">
            <AlertTriangle className="w-4 h-4 text-yellow-400 flex-shrink-0 mt-0.5" />
            {notConfigured}
          </div>
        )}

        {result && (
          <div className="mt-4 space-y-3">
            {result.rationale && <p className="text-xs text-dark-300">{result.rationale}</p>}
            <div className="flex items-center gap-3 text-xs">
              <span className="text-dark-400">{result.nodes?.length || 0} resources</span>
              {errors.length === 0 ? (
                <span className="text-emerald-400 inline-flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  valid
                </span>
              ) : (
                <span className="text-red-400">{errors.length} error(s)</span>
              )}
              {warnings.length > 0 && <span className="text-yellow-400">{warnings.length} warning(s)</span>}
            </div>
            <button onClick={apply} className="btn-secondary text-xs">
              Apply to canvas
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
