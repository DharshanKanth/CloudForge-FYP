import { useState } from 'react';
import { Play, Rocket, Trash2, Undo2, XCircle, History, Loader2, ChevronDown, ChevronUp } from 'lucide-react';
import type { DeploymentEvent } from '../types';
import type { LucideIcon } from 'lucide-react';

const eventMeta: Record<string, { label: string; icon: LucideIcon; color: string; bg: string }> = {
  plan:         { label: 'Plan',         icon: Play,    color: 'text-blue-400',      bg: 'bg-blue-900/30' },
  apply:        { label: 'Apply',        icon: Rocket,  color: 'text-emerald-400',   bg: 'bg-emerald-900/30' },
  plan_destroy: { label: 'Destroy Plan', icon: Undo2,   color: 'text-yellow-400',    bg: 'bg-yellow-900/30' },
  destroy:      { label: 'Destroy',      icon: Trash2,  color: 'text-red-400',       bg: 'bg-red-900/30' },
  clear:        { label: 'Clear',        icon: XCircle, color: 'text-dark-400',      bg: 'bg-dark-800' },
};

function formatTime(iso: string | null): string {
  if (!iso) return '';
  return new Date(iso).toLocaleString();
}

function EventDetail({ detail }: { detail: string }) {
  const [expanded, setExpanded] = useState(false);
  const truncated = detail.length > 600;
  const preview = expanded ? detail : detail.slice(0, 600);
  return (
    <div className="mt-2">
      <pre className="text-[10px] text-dark-400 font-mono whitespace-pre-wrap max-h-40 overflow-auto">{preview}</pre>
      {truncated && (
        <button onClick={() => setExpanded((v) => !v)} className="mt-1 flex items-center gap-1 text-[10px] text-primary-400 hover:text-primary-300 transition-colors">
          {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          {expanded ? 'Show less' : `Show full output (${detail.length} chars)`}
        </button>
      )}
    </div>
  );
}

/**
 * Timeline of a project's deployment actions — every plan/apply/destroy/clear
 * recorded by the backend audit log. Shared by the Terraform page's History
 * tab and the Dashboard activity line.
 */
export default function DeploymentHistory({ events, loading, onRefresh }: {
  events: DeploymentEvent[];
  loading: boolean;
  onRefresh?: () => void;
}) {
  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center h-full">
        <Loader2 className="w-6 h-6 animate-spin text-dark-500" />
      </div>
    );
  }
  if (events.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center h-full">
        <div className="text-center max-w-sm">
          <div className="w-20 h-20 rounded-2xl bg-dark-800 flex items-center justify-center mx-auto mb-5"><History className="w-9 h-9 text-dark-500" /></div>
          <h3 className="text-base font-semibold text-dark-300 mb-2">No deployment history yet</h3>
          <p className="text-dark-500 text-sm mb-5">Run a Plan, Deploy, or Destroy — every action gets recorded here.</p>
        </div>
      </div>
    );
  }
  return (
    <div className="max-w-3xl mx-auto pb-6 pt-2">
      <ol className="relative space-y-4 border-l border-dark-700 ml-2 pl-6">
        {events.map((e) => {
          const meta = eventMeta[e.event_type] || eventMeta.clear;
          const Icon = meta.icon;
          const ok = e.status === 'succeeded';
          return (
            <li key={e.id} className="relative">
              <span className={`absolute -left-[26px] top-0 w-5 h-5 rounded-full flex items-center justify-center ${meta.bg}`}>
                <Icon className={`w-3 h-3 ${meta.color}`} />
              </span>
              <div className="card p-3">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs font-semibold text-white">{meta.label}</span>
                  {ok ? (
                    <span className="px-1.5 py-0.5 rounded bg-emerald-900/40 text-emerald-400 text-[10px] font-semibold">SUCCEEDED</span>
                  ) : (
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${e.status === 'blocked' ? 'bg-yellow-900/40 text-yellow-400' : 'bg-red-900/40 text-red-400'}`}>
                      {e.status.toUpperCase()}
                    </span>
                  )}
                  {e.resource_count != null && (
                    <span className="px-1.5 py-0.5 rounded bg-dark-800 text-dark-300 text-[10px] font-mono">
                      {e.resource_count} resource{e.resource_count !== 1 ? 's' : ''}
                    </span>
                  )}
                  {e.created_at && <span className="ml-auto text-[10px] text-dark-500">{formatTime(e.created_at)}</span>}
                </div>
                {e.detail && <EventDetail detail={e.detail} />}
              </div>
            </li>
          );
        })}
      </ol>
      {onRefresh && (
        <button onClick={onRefresh} className="btn-secondary text-xs mt-4"><History className="w-3.5 h-3.5" />Refresh History</button>
      )}
    </div>
  );
}