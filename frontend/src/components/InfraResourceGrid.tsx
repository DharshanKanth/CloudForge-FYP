import type { InfraResource } from '../types';

export const categoryMeta: Record<string, { label: string; icon: string }> = {
  compute: { label: 'Compute', icon: '🖥' },
  network: { label: 'Network', icon: '🌐' },
  data: { label: 'Storage & Data', icon: '🪣' },
};

/**
 * Category-grouped card grid of live resources, shared between the
 * Terraform page's Infra tab and the Dashboard's Running Infrastructure.
 */
export default function InfraResourceGrid({ resources }: { resources: InfraResource[] }) {
  return (
    <div className="space-y-5">
      {['compute', 'network', 'data'].map((cat) => {
        const items = resources.filter((r) => r.category === cat);
        if (items.length === 0) return null;
        const meta = categoryMeta[cat];
        return (
          <section key={cat}>
            <h3 className="text-xs font-semibold text-dark-300 uppercase tracking-wider mb-2">{meta.icon} {meta.label} <span className="text-dark-600">({items.length})</span></h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {items.map((r) => (
                <div key={r.address} className="card p-3">
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="text-xs font-semibold text-white truncate">{r.label}</span>
                    <span className="ml-auto text-[9px] uppercase tracking-wider text-dark-500">{r.type.replace('aws_', '')}</span>
                  </div>
                  <div className="text-[10px] font-mono text-dark-500 truncate" title={r.address}>{r.address}</div>
                  <div className="text-[10px] font-mono text-primary-400 truncate mt-0.5">{r.id}</div>
                  <div className="flex flex-wrap gap-1 mt-2">
                    {Object.entries(r.attributes).filter(([k]) => k !== 'id').map(([k, v]) => {
                      const text = String(v);
                      if (k === 'public_ip') {
                        return (
                          <a key={k} href={`http://${text}`} target="_blank" rel="noreferrer" className="px-1.5 py-0.5 rounded bg-primary-900/40 text-primary-300 text-[10px] font-mono hover:bg-primary-900/70">
                            {k}: {text} ↗
                          </a>
                        );
                      }
                      return (
                        <span key={k} className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${k === 'instance_state' ? 'bg-emerald-900/40 text-emerald-400' : 'bg-dark-800 text-dark-300'}`}>
                          {k}: {text.length > 30 ? `${text.slice(0, 30)}…` : text}
                        </span>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}