import { useEffect, useState } from 'react';
import { X, Loader2, Sparkles, DollarSign, Shield, AlertCircle, AlertTriangle, Info } from 'lucide-react';
import { architectureApi, aiApi } from '../../services/api';
import toast from 'react-hot-toast';

interface InsightsModalProps {
  projectId: string;
  onClose: () => void;
}

const severityIcon: Record<string, any> = {
  high: { icon: AlertCircle, color: 'text-red-400' },
  medium: { icon: AlertTriangle, color: 'text-orange-400' },
  low: { icon: AlertTriangle, color: 'text-yellow-400' },
  info: { icon: Info, color: 'text-blue-400' },
};

export function InsightsModal({ projectId, onClose }: InsightsModalProps) {
  const [cost, setCost] = useState<any>(null);
  const [security, setSecurity] = useState<any>(null);
  const [tab, setTab] = useState<'cost' | 'security'>('cost');
  const [aiText, setAiText] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);

  useEffect(() => {
    architectureApi.cost(projectId).then((r) => setCost(r.data)).catch(() => {});
    architectureApi.security(projectId).then((r) => setSecurity(r.data)).catch(() => {});
  }, [projectId]);

  useEffect(() => setAiText(null), [tab]);

  const runAi = async (which: 'cost' | 'security') => {
    setAiLoading(true);
    setAiText(null);
    try {
      const res = which === 'cost' ? await aiApi.cost(projectId) : await aiApi.security(projectId);
      if (!res.data.configured) {
        toast.error(res.data.message || 'AI is not configured');
        return;
      }
      setAiText(res.data.text || '');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'AI request failed');
    } finally {
      setAiLoading(false);
    }
  };

  const findings = security?.findings || [];

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={onClose}>
      <div className="card w-full max-w-2xl max-h-[85vh] flex flex-col p-5" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 mb-3">
          <h3 className="text-sm font-semibold text-dark-100">Cost &amp; Security Insights</h3>
          <button onClick={onClose} className="ml-auto text-dark-500 hover:text-dark-200"><X className="w-4 h-4" /></button>
        </div>

        <div className="flex rounded-lg bg-dark-800 p-1 mb-4">
          <button onClick={() => setTab('cost')} className={`flex-1 py-1.5 text-xs font-medium rounded-md inline-flex items-center justify-center gap-1.5 ${tab === 'cost' ? 'bg-dark-900 text-dark-100 shadow' : 'text-dark-500'}`}>
            <DollarSign className="w-3.5 h-3.5" />Cost
          </button>
          <button onClick={() => setTab('security')} className={`flex-1 py-1.5 text-xs font-medium rounded-md inline-flex items-center justify-center gap-1.5 ${tab === 'security' ? 'bg-dark-900 text-dark-100 shadow' : 'text-dark-500'}`}>
            <Shield className="w-3.5 h-3.5" />Security
          </button>
        </div>

        <div className="flex-1 overflow-y-auto space-y-3">
          {tab === 'cost' ? (
            !cost ? <p className="text-xs text-dark-500">Loading…</p> : (
              <>
                <div className="text-xs text-dark-400">Estimated <span className="text-emerald-400 font-semibold">${cost.monthly_total}/mo</span> <span className="text-dark-600">({cost.currency})</span></div>
                <div className="divide-y divide-dark-800">
                  {(cost.items || []).filter((i: any) => i.monthly_cost > 0).map((i: any) => (
                    <div key={i.resource_id} className="flex items-center gap-2 py-1.5 text-xs">
                      <span className="text-dark-200">{i.label}</span>
                      <span className="text-[10px] uppercase text-dark-600">{i.resource_type}</span>
                      {i.note && <span className="text-[10px] text-dark-600">· {i.note}</span>}
                      <span className="ml-auto font-mono text-dark-300">${i.monthly_cost}</span>
                    </div>
                  ))}
                </div>
                <p className="text-[10px] text-dark-600">{cost.disclaimer}</p>
              </>
            )
          ) : (
            !security ? <p className="text-xs text-dark-500">Loading…</p> : (
              findings.length === 0 ? <p className="text-xs text-emerald-400">No security findings.</p> : (
                <div className="space-y-1.5">
                  {findings.map((f: any, idx: number) => {
                    const cfg = severityIcon[f.severity] || severityIcon.info;
                    const Icon = cfg.icon;
                    return (
                      <div key={idx} className="flex items-start gap-2 text-xs">
                        <Icon className={`w-3.5 h-3.5 ${cfg.color} mt-0.5 flex-shrink-0`} />
                        <div>
                          <div className="text-dark-200">{f.title}</div>
                          <div className="text-[10px] text-dark-500">{f.recommendation}</div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )
            )
          )}

          <div className="border-t border-dark-800 pt-3">
            {aiLoading && <p className="text-xs text-dark-500 inline-flex items-center gap-1"><Loader2 className="w-3.5 h-3.5 animate-spin" />Asking the AI…</p>}
            {!aiLoading && aiText && <div className="whitespace-pre-wrap text-xs text-dark-300 leading-relaxed">{aiText}</div>}
          </div>
        </div>

        <div className="pt-3 border-t border-dark-800 flex items-center gap-2">
          <button onClick={() => runAi(tab)} disabled={aiLoading} className="btn-secondary text-xs inline-flex items-center gap-1.5">
            {aiLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
            {tab === 'cost' ? 'AI cost optimization' : 'AI security review'}
          </button>
          <span className="text-[10px] text-dark-600">Advisory — deterministic figures first, AI adds suggestions.</span>
        </div>
      </div>
    </div>
  );
}
