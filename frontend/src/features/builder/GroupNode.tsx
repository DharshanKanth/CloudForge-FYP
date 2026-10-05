import { memo, useCallback } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { ChevronDown, ChevronRight } from 'lucide-react';

/** Only these resource types render as visual containers. */
export const CONTAINER_TYPES = new Set(['vpc', 'subnet']);

const containerStyles: Record<string, { border: string; header: string; bg: string }> = {
  vpc: { border: 'border-blue-500/60', header: 'bg-blue-900/40', bg: 'bg-blue-950/20' },
  subnet: { border: 'border-cyan-500/60', header: 'bg-cyan-900/40', bg: 'bg-cyan-950/20' },
};
const defaultContainerStyle = { border: 'border-dark-600', header: 'bg-dark-800', bg: 'bg-dark-900/30' };

const containerIcons: Record<string, string> = { vpc: '☁', subnet: '⬡' };

export interface GroupNodeData {
  label: string;
  resourceType: string;
  properties: Record<string, any>;
  collapsed?: boolean;
  childCount?: number;
}

export const GroupNodeComponent = memo(
  ({ data, selected, id }: NodeProps) => {
    const d = data as unknown as GroupNodeData;
    const rt = d.resourceType || 'vpc';
    const style = containerStyles[rt] || defaultContainerStyle;
    const props = d.properties || {};
    const displayName = props.name || d.label || id;
    const collapsed = !!d.collapsed;
    const childCount = d.childCount ?? 0;
    const icon = containerIcons[rt] || '📦';

    const subtitle =
      rt === 'vpc' ? (props.cidr || '10.0.0.0/16') :
      rt === 'subnet' ? (props.cidr || '10.0.1.0/24') : '';

    const handleToggle = useCallback(
      (e: React.MouseEvent) => {
        e.stopPropagation();
        window.dispatchEvent(
          new CustomEvent('group:toggle', { detail: { nodeId: id } })
        );
      },
      [id]
    );

    return (
      <div
        className={`rounded-xl border-2 ${style.border} ${
          selected ? 'ring-2 ring-primary-500/50 ring-offset-1 ring-offset-dark-900' : ''
        }`}
        style={{
          minWidth: collapsed ? 220 : 320,
          minHeight: collapsed ? 52 : 180,
          background: 'transparent',
        }}
      >
        <Handle type="target" position={Position.Top} id="top" style={{ top: -5 }} />
        <Handle type="target" position={Position.Left} id="left" style={{ left: -5 }} />

        {/* Header bar — a plain click selects the node (opening the config
            panel); only the chevron toggles collapse/expand. Stopping
            propagation on the whole header would swallow React Flow's
            onNodeClick and make the resource unconfigurable. */}
        <div
          className={`${style.header} px-3 py-2 rounded-t-xl flex items-center gap-2 select-none`}
        >
          <button
            type="button"
            className="text-dark-400 hover:text-white transition-colors"
            onClick={handleToggle}
            title={collapsed ? 'Expand' : 'Collapse'}
          >
            {collapsed
              ? <ChevronRight className="w-4 h-4" />
              : <ChevronDown className="w-4 h-4" />}
          </button>
          <span className="text-base leading-none">{icon}</span>
          <div className="flex-1 min-w-0">
            <div className="text-xs font-bold text-white truncate">
              {rt.replace('_', ' ').toUpperCase()}: {displayName}
            </div>
            {subtitle && (
              <div className="text-[10px] text-dark-400 truncate">{subtitle}</div>
            )}
          </div>
          {collapsed && childCount > 0 && (
            <span className="text-[10px] text-dark-400 bg-dark-800 px-2 py-0.5 rounded-full">
              {childCount} resource{childCount !== 1 ? 's' : ''}
            </span>
          )}
        </div>

        {/* Children area — React Flow renders children inside this div */}
        {!collapsed && (
          <div
            className={`${style.bg} p-3 rounded-b-xl`}
            style={{ minHeight: 120 }}
          />
        )}

        <Handle type="source" position={Position.Bottom} id="bottom" style={{ bottom: -5 }} />
        <Handle type="source" position={Position.Right} id="right" style={{ right: -5 }} />
      </div>
    );
  }
);

GroupNodeComponent.displayName = 'GroupNode';
