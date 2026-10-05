import { ChevronRight, Home } from 'lucide-react';
import type { Node } from '@xyflow/react';

interface BreadcrumbProps {
  /** The chain from root to the currently focused group. */
  focusPath: Node[];
  onNavigate: (nodeId: string | null) => void;
}

export function Breadcrumb({ focusPath, onNavigate }: BreadcrumbProps) {
  if (focusPath.length === 0) return null;

  return (
    <div className="flex items-center gap-1 px-4 py-1.5 bg-dark-900 border-b border-dark-800 text-xs select-none">
      <button
        onClick={() => onNavigate(null)}
        className="flex items-center gap-1 text-dark-400 hover:text-white transition-colors"
        title="Show all"
      >
        <Home className="w-3 h-3" />
        <span>All</span>
      </button>
      {focusPath.map((node) => {
        const rt = (node.data?.resourceType as string) || node.type || 'group';
        const name = (node.data?.properties as Record<string, any>)?.name || node.id;
        return (
          <span key={node.id} className="flex items-center gap-1">
            <ChevronRight className="w-3 h-3 text-dark-600" />
            <button
              onClick={() => onNavigate(node.id)}
              className="text-dark-400 hover:text-white transition-colors"
              title={`Focus on ${name}`}
            >
              <span className="text-dark-500 mr-0.5">
                {rt.replace('_', ' ').toUpperCase()}:
              </span>
              {name}
            </button>
          </span>
        );
      })}
    </div>
  );
}
