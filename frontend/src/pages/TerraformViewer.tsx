import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Editor from '@monaco-editor/react';
import { ArrowLeft, Download, Copy, RefreshCw, FileText, Check, Loader2, Cloud, AlertCircle } from 'lucide-react';
import { terraformApi, projectsApi } from '../services/api';
import type { TerraformFile, Project } from '../types';
import toast from 'react-hot-toast';

const fileIcons: Record<string, string> = {
  'main.tf': '📄', 'variables.tf': '📋', 'outputs.tf': '📤', 'providers.tf': '🔧',
  'network.tf': '🌐', 'compute.tf': '🖥', 'storage.tf': '🪣', 'database.tf': '🗄',
};

export default function TerraformViewer() {
  const { id: projectId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [project, setProject] = useState<Project | null>(null);
  const [files, setFiles] = useState<TerraformFile[]>([]);
  const [activeFile, setActiveFile] = useState<string>('');
  const [generating, setGenerating] = useState(false);
  const [copied, setCopied] = useState(false);
  const [validationInfo, setValidationInfo] = useState<any>(null);

  useEffect(() => {
    if (!projectId) return;
    projectsApi.get(projectId).then((res) => setProject(res.data)).catch(() => {});
    loadTerraform();
  }, [projectId]);

  const loadTerraform = async () => {
    if (!projectId) return;
    try {
      const res = await terraformApi.get(projectId);
      setFiles(res.data.files);
      if (res.data.files.length > 0) setActiveFile(res.data.files[0].filename);
    } catch {
      // Not generated yet - that's fine
    }
  };

  const handleGenerate = async () => {
    if (!projectId) return;
    setGenerating(true);
    try {
      const res = await terraformApi.generate(projectId);
      setFiles(res.data.files);
      setValidationInfo(res.data.validation);
      if (res.data.files.length > 0) setActiveFile(res.data.files[0].filename);
      toast.success(`Generated ${res.data.files.length} Terraform files!`);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to generate Terraform');
    } finally {
      setGenerating(false);
    }
  };

  const handleCopy = async () => {
    if (!activeContent) return;
    await navigator.clipboard.writeText(activeContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    toast.success('Copied to clipboard!');
  };

  const handleDownload = async () => {
    if (!projectId) return;
    const token = localStorage.getItem('cloudforge_token');
    const url = terraformApi.downloadUrl(projectId);
    try {
      const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) throw new Error('Download failed');
      const blob = await res.blob();
      const downloadUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `cloudforge-${project?.name || projectId}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(downloadUrl);
      toast.success('Downloading ZIP...');
    } catch {
      toast.error('Failed to download ZIP');
    }
  };

  const activeContent = files.find((f) => f.filename === activeFile)?.content || '';

  return (
    <div className="flex flex-col h-screen bg-dark-950 overflow-hidden">
      <header className="flex items-center gap-3 px-4 py-2.5 bg-dark-900 border-b border-dark-800 flex-shrink-0">
        <button onClick={() => navigate(`/projects/${projectId}/builder`)} className="btn-ghost p-2 -ml-1" title="Back to Builder"><ArrowLeft className="w-4 h-4" /></button>
        <div className="flex items-center gap-2 mr-4">
          <div className="w-6 h-6 bg-gradient-to-br from-primary-500 to-accent-600 rounded-md flex items-center justify-center"><Cloud className="w-3 h-3 text-white" /></div>
          <div>
            <div className="text-sm font-semibold text-white leading-none">{project?.name || 'Project'}</div>
            <div className="text-[10px] text-dark-500 capitalize">{project?.provider} · Terraform</div>
          </div>
        </div>
        <div className="flex-1" />
        <div className="flex items-center gap-2">
          <button onClick={handleGenerate} disabled={generating} className="btn-primary text-xs">
            {generating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
            {generating ? 'Generating...' : 'Generate Terraform'}
          </button>
          {files.length > 0 && <>
            <button onClick={handleCopy} className="btn-secondary text-xs">{copied ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}{copied ? 'Copied!' : 'Copy'}</button>
            <button onClick={handleDownload} className="btn-secondary text-xs"><Download className="w-3.5 h-3.5" /></button>
          </>}
        </div>
      </header>
      {validationInfo && !validationInfo.valid && (
        <div className="flex items-center gap-3 px-4 py-2 bg-yellow-900/20 border-b border-yellow-800/30">
          <AlertCircle className="w-4 h-4 text-yellow-400 flex-shrink-0" />
          <div className="text-xs text-yellow-400">Architecture has issues. Terraform was generated but may need fixes.</div>
          <button onClick={() => navigate(`/projects/${projectId}/builder`)} className="ml-auto text-xs text-yellow-400 underline hover:no-underline">Fix in Builder</button>
        </div>
      )}
      <div className="flex flex-1 overflow-hidden">
        <aside className="w-48 bg-dark-900 border-r border-dark-800 flex flex-col flex-shrink-0">
          <div className="px-4 py-3 border-b border-dark-800">
            <div className="text-xs font-bold text-dark-400 uppercase tracking-wider">Files</div>
            <div className="text-[10px] text-dark-600 mt-0.5">{files.length} generated</div>
          </div>
          <div className="flex-1 py-2 overflow-y-auto">
            {files.length === 0 ? (
              <div className="px-4 py-6 text-center"><FileText className="w-8 h-8 text-dark-700 mx-auto mb-2" /><p className="text-xs text-dark-500">No Terraform generated yet.<br />Click Generate Terraform.</p></div>
            ) : (
              files.map((file) => (
                <button key={file.filename} onClick={() => setActiveFile(file.filename)} className={`w-full flex items-center gap-2.5 px-4 py-2.5 text-left transition-all duration-150 ${activeFile === file.filename ? 'bg-primary-900/20 text-primary-300 border-r-2 border-primary-500' : 'text-dark-400 hover:bg-dark-800 hover:text-dark-200'}`}>
                  <span className="text-sm">{fileIcons[file.filename] || '📄'}</span>
                  <span className="text-xs font-mono font-medium truncate">{file.filename}</span>
                </button>
              ))
            )}
          </div>
        </aside>
        <div className="flex-1 flex flex-col overflow-hidden">
          {files.length === 0 ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center max-w-sm">
                <div className="w-20 h-20 rounded-2xl bg-dark-800 flex items-center justify-center mx-auto mb-5"><FileText className="w-9 h-9 text-dark-500" /></div>
                <h3 className="text-base font-semibold text-dark-300 mb-2">No Terraform Generated</h3>
                <p className="text-dark-500 text-sm mb-5">Design your infrastructure in the visual builder, then generate Terraform.</p>
                <div className="flex gap-2 justify-center">
                  <button onClick={() => navigate(`/projects/${projectId}/builder`)} className="btn-secondary text-xs"><ArrowLeft className="w-3.5 h-3.5" />Back to Builder</button>
                  <button onClick={handleGenerate} disabled={generating} className="btn-primary text-xs">{generating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}Generate Terraform</button>
                </div>
              </div>
            </div>
          ) : (
            <>
              {activeFile && (
                <div className="flex items-center gap-2 px-4 py-2 bg-dark-900 border-b border-dark-800">
                  <span className="text-sm">{fileIcons[activeFile] || '📄'}</span>
                  <span className="text-xs font-mono text-dark-300 font-medium">{activeFile}</span>
                  <span className="ml-auto text-[10px] text-dark-600">{activeContent.split('\n').length} lines · HCL (Terraform)</span>
                </div>
              )}
              <div className="flex-1">
                <Editor value={activeContent} language="hcl" theme="vs-dark" options={{ readOnly: true, minimap: { enabled: true }, fontSize: 13, fontFamily: 'JetBrains Mono, Fira Code, monospace', lineNumbers: 'on', scrollBeyondLastLine: false, wordWrap: 'on', automaticLayout: true, padding: { top: 16 } }} />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
