import { useRef, useState } from 'react';
import { X, Loader2, AlertTriangle, CheckCircle2, Upload } from 'lucide-react';
import { diagramApi } from '../../services/api';
import toast from 'react-hot-toast';

interface DiagramImportModalProps {
  onApply: (nodes: any[], edges: any[]) => void;
  onClose: () => void;
}

const ACCEPT = '.drawio,.xml,.mmd,.mermaid,.json,.txt';
const MAX_BYTES = 5_000_000;

/**
 * Deterministic diagram import: a draw.io / Mermaid / JSON file is parsed into
 * a canvas proposal (no AI, no deployment). The user must click Apply, then
 * review and validate as usual.
 */
export function DiagramImportModal({ onApply, onClose }: DiagramImportModalProps) {
  const [filename, setFilename] = useState('');
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const readFile = (file: File) => {
    setError(null);
    setResult(null);
    if (file.size > MAX_BYTES) {
      setError('File is too large (maximum 5 MB).');
      return;
    }
    setFilename(file.name);
    const reader = new FileReader();
    reader.onload = () => setContent(String(reader.result ?? ''));
    reader.onerror = () => setError('Could not read the file.');
    reader.readAsText(file);
  };

  const runImport = async () => {
    if (!content) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await diagramApi.import(filename || 'diagram', content);
      setResult(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Could not read the diagram.');
    } finally {
      setLoading(false);
    }
  };

  const apply = () => {
    if (!result) return;
    onApply(result.nodes || [], result.edges || []);
    toast.success('Diagram imported — review the canvas, then Validate');
    onClose();
  };

  const issues = result?.validation?.issues || [];
  const errors = issues.filter((i: any) => i.level === 'error');
  const warnings = issues.filter((i: any) => i.level === 'warning');

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="card w-full max-w-lg p-5 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 mb-3">
          <Upload className="w-4 h-4 text-primary-400" />
          <h3 className="text-sm font-semibold text-dark-100">Import architecture diagram</h3>
          <button onClick={onClose} className="ml-auto text-dark-500 hover:text-dark-200">
            <X className="w-4 h-4" />
          </button>
        </div>
        <p className="text-xs text-dark-500 mb-3">
          Upload a <span className="font-mono">draw.io</span> file, a{' '}
          <span className="font-mono">Mermaid</span> flowchart, or CloudForge{' '}
          <span className="font-mono">JSON</span>. CloudForge maps icons and labels to
          infrastructure deterministically, then you review and validate. Nothing is deployed.
        </p>

        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            const file = e.dataTransfer.files?.[0];
            if (file) readFile(file);
          }}
          onClick={() => inputRef.current?.click()}
          className={`cursor-pointer rounded-xl border-2 border-dashed p-6 text-center transition-colors ${
            dragging ? 'border-primary-500 bg-dark-800' : 'border-dark-700 hover:border-dark-600'
          }`}
        >
          <Upload className="w-6 h-6 mx-auto text-dark-500 mb-2" />
          <p className="text-xs text-dark-300">
            {filename ? (
              <>
                Selected: <span className="font-mono text-primary-300">{filename}</span>
              </>
            ) : (
              'Drop a file here, or click to browse'
            )}
          </p>
          <p className="text-[10px] text-dark-600 mt-1">draw.io · Mermaid · JSON · max 5 MB</p>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) readFile(file);
              e.target.value = '';
            }}
          />
        </div>

        <div className="flex gap-2 mt-3">
          <button
            onClick={runImport}
            disabled={loading || !content}
            className="btn-primary text-xs"
          >
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
            {loading ? 'Reading…' : 'Read diagram'}
          </button>
        </div>

        {error && (
          <div className="mt-4 flex items-start gap-2 p-3 rounded-lg bg-dark-800 text-dark-300 text-xs">
            <AlertTriangle className="w-4 h-4 text-yellow-400 flex-shrink-0 mt-0.5" />
            {error}
          </div>
        )}

        {result && (
          <div className="mt-4 space-y-3">
            {result.summary && <p className="text-xs text-dark-300">{result.summary}</p>}
            {result.recognized === 0 ? (
              <div className="flex items-start gap-2 p-3 rounded-lg bg-dark-800 text-dark-300 text-xs">
                <AlertTriangle className="w-4 h-4 text-yellow-400 flex-shrink-0 mt-0.5" />
                No supported AWS resources were recognised. Check that the diagram uses AWS
                service icons or recognisable labels.
              </div>
            ) : (
              <>
                <div className="flex flex-wrap items-center gap-3 text-xs">
                  <span className="text-dark-400">{result.recognized} resource(s)</span>
                  <span className="text-dark-400">{result.edges?.length || 0} connection(s)</span>
                  {errors.length === 0 ? (
                    <span className="text-emerald-400 inline-flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      valid
                    </span>
                  ) : (
                    <span className="text-red-400">{errors.length} error(s)</span>
                  )}
                  {warnings.length > 0 && (
                    <span className="text-yellow-400">{warnings.length} warning(s)</span>
                  )}
                </div>
                {errors.length > 0 && (
                  <ul className="text-[10px] text-red-300 list-disc pl-4 space-y-0.5">
                    {errors.slice(0, 4).map((e: any, i: number) => (
                      <li key={i}>{e.message}</li>
                    ))}
                  </ul>
                )}
                <button onClick={apply} className="btn-secondary text-xs">
                  Apply to canvas
                </button>
              </>
            )}

            {(result.unrecognized?.length || 0) > 0 && (
              <div className="text-[10px] text-dark-400">
                <p className="text-yellow-400 mb-1">
                  {result.unrecognized.length} element(s) not recognised (skipped):
                </p>
                <ul className="list-disc pl-4 space-y-0.5">
                  {result.unrecognized.slice(0, 6).map((u: any, i: number) => (
                    <li key={i}>
                      <span className="font-mono">{u.label}</span>
                    </li>
                  ))}
                  {result.unrecognized.length > 6 && <li>…and more</li>}
                </ul>
              </div>
            )}

            {(result.warnings?.length || 0) > 0 && (
              <ul className="text-[10px] text-dark-500 list-disc pl-4 space-y-0.5">
                {result.warnings.map((w: string, i: number) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
