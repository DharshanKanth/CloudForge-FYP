import { CheckCircle, AlertCircle, AlertTriangle, X, Info } from 'lucide-react';
import type { ValidationIssue, ValidationResult } from '../../types';

interface ValidationPanelProps {
  result: ValidationResult | null;
  onClose: () => void;
}

const levelConfig = {
  error: { icon: AlertCircle, color: 'text-red-400', bg: 'bg-red-900/10', border: 'border-red-800/30', label: 'Error' },
  warning: { icon: AlertTriangle, color: 'text-yellow-400', bg: 'bg-yellow-900/10', border: 'border-yellow-800/30', label: 'Warning' },
  info: { icon: Info, color: 'text-blue-400', bg: 'bg-blue-900/10', border: 'border-blue-800/30', label: 'Info' },
};

export function ValidationPanel({ result, onClose }: ValidationPanelProps) {
  if (!result) return null;
  const errors = result.issues.filter((i) => i.level === 'error');
  const warnings = result.issues.filter((i) => i.level === 'warning');

  return (
    <div className="border-t border-dark-800 bg-dark-950 flex-shrink-0" style={{ maxHeight: 220 }}>
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-dark-800">
        <div className="flex items-center gap-3">
          <span className="text-xs font-semibold text-dark-400 uppercase tracking-wider">Validation Results</span>
          {result.valid ? (
            <span className="flex items-center gap-1 text-xs text-emerald-400"><CheckCircle className="w-3.5 h-3.5" />All checks passed</span>
          ) : (
            <span className="flex items-center gap-1 text-xs text-red-400"><AlertCircle className="w-3.5 h-3.5" />{errors.length} error{errors.length !== 1 ? 's' : ''}</span>
          )}
          {warnings.length > 0 && <span className="text-xs text-yellow-400">{warnings.length} warning{warnings.length !== 1 ? 's' : ''}</span>}
        </div>
        <button onClick={onClose} className="text-dark-600 hover:text-dark-300 transition-colors"><X className="w-4 h-4" /></button>
      </div>
      <div className="overflow-y-auto px-4 py-2 space-y-1.5" style={{ maxHeight: 160 }}>
        {result.issues.length === 0 ? (
          <div className="flex items-center gap-2 text-sm text-emerald-400 py-2">
            <CheckCircle className="w-4 h-4" />Architecture is valid. No issues found.
          </div>
        ) : (
          result.issues.map((issue: ValidationIssue, i: number) => {
            const cfg = levelConfig[issue.level] || levelConfig.info;
            const Icon = cfg.icon;
            return (
              <div key={i} className={`flex items-start gap-2 px-3 py-2 rounded-lg text-xs ${cfg.bg} border ${cfg.border}`}>
                <Icon className={`w-3.5 h-3.5 ${cfg.color} flex-shrink-0 mt-0.5`} />
                <div className="flex-1">
                  <span className={`font-medium ${cfg.color}`}>{cfg.label}</span>
                  {issue.resource_type && <span className="text-dark-500 ml-1">[{issue.resource_type.toUpperCase()}]</span>}
                  <span className="text-dark-300 ml-1.5">{issue.message}</span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
