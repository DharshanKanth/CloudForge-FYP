import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { ResourceType } from '../../types';

const ResourceIcon = ({ type }: { type: ResourceType }) => {
  const icons: Record<string, string> = {
    vpc: '☁',
    subnet: '⬡',
    ec2: '🖥',
    s3: '🪣',
    rds: '🗄',
    security_group: '🛡',
    load_balancer: '⚖',
  };
  return <span className="text-xl leading-none">{icons[type] || '📦'}</span>;
};

const typeColors: Record<string, { border: string; header: string; badge: string }> = {
  vpc: { border: 'border-blue-500/50', header: 'bg-blue-900/30', badge: 'bg-blue-900/50 text-blue-300' },
  subnet: { border: 'border-cyan-500/50', header: 'bg-cyan-900/30', badge: 'bg-cyan-900/50 text-cyan-300' },
  ec2: { border: 'border-orange-500/50', header: 'bg-orange-900/30', badge: 'bg-orange-900/50 text-orange-300' },
  s3: { border: 'border-green-500/50', header: 'bg-green-900/30', badge: 'bg-green-900/50 text-green-300' },
  rds: { border: 'border-purple-500/50', header: 'bg-purple-900/30', badge: 'bg-purple-900/50 text-purple-300' },
  security_group: { border: 'border-red-500/50', header: 'bg-red-900/30', badge: 'bg-red-900/50 text-red-300' },
  load_balancer: { border: 'border-yellow-500/50', header: 'bg-yellow-900/30', badge: 'bg-yellow-900/50 text-yellow-300' },
};

const defaultColors = { border: 'border-dark-600', header: 'bg-dark-800', badge: 'bg-dark-700 text-dark-400' };

function getSubtitle(resourceType: ResourceType, props: Record<string, any>): string {
  switch (resourceType) {
    case 'vpc': return props.cidr || '10.0.0.0/16';
    case 'subnet': return props.cidr || '10.0.1.0/24';
    case 'ec2': return props.instanceType || 't2.micro';
    case 's3': return props.bucketName || 'my-bucket';
    case 'rds': return `${props.engine || 'mysql'} · ${props.instanceClass || 'db.t3.micro'}`;
    case 'security_group': return props.description || 'Security Group';
    case 'load_balancer': return props.lbType || 'application';
    default: return '';
  }
}

export const ResourceNodeComponent = memo(({ data, selected }: NodeProps) => {
  const resourceType = data.resourceType as ResourceType;
  const colors = typeColors[resourceType] || defaultColors;
  const properties = (data.properties as Record<string, any>) || {};
  const displayName = properties.name || properties.bucketName || properties.identifier || data.label as string;
  const subtitle = getSubtitle(resourceType, properties);

  return (
    <div
      className={`resource-node border-2 ${colors.border} ${selected ? 'ring-2 ring-primary-500/50 ring-offset-1 ring-offset-dark-900' : ''}`}
      style={{ minWidth: 190 }}
    >
      <Handle type="target" position={Position.Top} id="top" style={{ top: -5 }} />
      <Handle type="target" position={Position.Left} id="left" style={{ left: -5 }} />
      <div className={`${colors.header} px-3 py-2 rounded-t-xl flex items-center gap-2.5`}>
        <ResourceIcon type={resourceType} />
        <div className="flex-1 min-w-0">
          <div className="text-xs font-bold text-white truncate">{displayName}</div>
          <div className="text-[10px] text-dark-400 truncate">{subtitle}</div>
        </div>
      </div>
      <div className="px-3 py-2">
        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium ${colors.badge}`}>
          {resourceType.replace('_', ' ').toUpperCase()}
        </span>
      </div>
      <Handle type="source" position={Position.Bottom} id="bottom" style={{ bottom: -5 }} />
      <Handle type="source" position={Position.Right} id="right" style={{ right: -5 }} />
    </div>
  );
});

ResourceNodeComponent.displayName = 'ResourceNode';
