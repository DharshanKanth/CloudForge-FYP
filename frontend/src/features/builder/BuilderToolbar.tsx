import { useCallback, useState } from 'react';
import {
  Search, X, ZoomIn, ZoomOut, Maximize2, LayoutDashboard,
  ChevronsUpDown, ChevronsDownUp, Save, Loader2,
} from 'lucide-react';

interface BuilderToolbarProps {
  rfInstance: { zoomIn: () => void; zoomOut: () => void; fitView: (o?: any) => void } | null;
  saving: boolean;
  resourceCount: number;
  edgeCount: number;
  onSave: () => void;
  onAutoLayout: () => void;
  onExpandAll: () => void;
  onCollapseAll: () => void;
  onSearch: (query: string) => void;
  onClearSearch: () => void;
  searchQuery: string;
}

export function BuilderToolbar({
  rfInstance, saving, resourceCount, edgeCount,
  onSave, onAutoLayout, onExpandAll, onCollapseAll,
  onSearch, onClearSearch, searchQuery,
}: BuilderToolbarProps) {
  const [localQuery, setLocalQuery] = useState(searchQuery || '');

  const handleSearchChange = useCallback(
    (value: string) => {
      setLocalQuery(value);
      onSearch(value);
    },
    [onSearch]
  );

  const handleClear = useCallback(() => {
    setLocalQuery('');
    onClearSearch();
  }, [onClearSearch]);

  const handleZoomIn = useCallback(() => rfInstance?.zoomIn(), [rfInstance]);
  const handleZoomOut = useCallback(() => rfInstance?.zoomOut(), [rfInstance]);
  const handleFitView = useCallback(
    () => rfInstance?.fitView({ padding: 0.2, duration: 300 }),
    [rfInstance]
  );

  return (
    <div className="flex items-center gap-2 px-4 py-2 bg-dark-900 border-b border-dark-800 flex-shrink-0">
      {/* Search */}
      <div className="relative flex-shrink-0">
        <Search className="w-3.5 h-3.5 text-dark-600 absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
        <input
          type="text"
          value={localQuery}
          onChange={(e) => handleSearchChange(e.target.value)}
          placeholder="Search resources..."
          className="w-48 bg-dark-800 border border-dark-700 rounded-lg pl-8 pr-7 py-1.5 text-xs text-dark-200 placeholder-dark-600 focus:outline-none focus:border-primary-500 transition-colors"
        />
        {localQuery && (
          <button
            onClick={handleClear}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-dark-600 hover:text-dark-300"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      <div className="w-px h-5 bg-dark-700 mx-1" />

      {/* Zoom controls */}
      <ToolButton icon={ZoomIn} onClick={handleZoomIn} title="Zoom in" />
      <ToolButton icon={ZoomOut} onClick={handleZoomOut} title="Zoom out" />
      <ToolButton icon={Maximize2} onClick={handleFitView} title="Fit to screen" />

      <div className="w-px h-5 bg-dark-700 mx-1" />

      {/* Layout + group controls */}
      <ToolButton icon={LayoutDashboard} onClick={onAutoLayout} title="Auto layout" label="Layout" />
      <ToolButton icon={ChevronsUpDown} onClick={onExpandAll} title="Expand all groups" />
      <ToolButton icon={ChevronsDownUp} onClick={onCollapseAll} title="Collapse all groups" />

      <div className="flex-1" />

      {/* Stats */}
      <span className="text-[10px] text-dark-600 hidden lg:block mr-2">
        {resourceCount} resource{resourceCount !== 1 ? 's' : ''} ·{' '}
        {edgeCount} connection{edgeCount !== 1 ? 's' : ''}
      </span>

      {/* Save */}
      <button
        onClick={onSave}
        disabled={saving}
        className="btn-secondary text-xs flex items-center gap-1.5"
      >
        {saving ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
        ) : (
          <Save className="w-3.5 h-3.5" />
        )}
        {saving ? 'Saving...' : 'Save'}
      </button>
    </div>
  );
}

function ToolButton({
  icon: Icon,
  onClick,
  title,
  label,
}: {
  icon: React.ComponentType<{ className?: string }>;
  onClick: () => void;
  title: string;
  label?: string;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="flex items-center gap-1 px-2 py-1.5 rounded-md text-dark-400 hover:text-white hover:bg-dark-800 transition-colors text-xs"
    >
      <Icon className="w-3.5 h-3.5" />
      {label && <span>{label}</span>}
    </button>
  );
}
