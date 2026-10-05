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
    internet_gateway: '🌐',
    route_table: '🛣',
    nat_gateway: '↗',
    lambda: 'λ',
    dynamodb: '▦',
    iam_role: '🔑',
    cloudfront: '⚡',
    api_gateway: '🔀',
    route53_zone: '🧭',
    route53_record: '📍',
    elastic_ip: '📌',
    ebs_volume: '💽',
    ecr_repository: '📦',
    ecs_cluster: '🐙',
    efs: '📂',
    elasticache: '🔥',
    aurora: '🌌',
    redshift: '📊',
    kinesis_stream: '🌊',
    sqs: '📨',
    sns: '📢',
    step_function: '🧩',
    secretsmanager: '🔐',
    cloudwatch_alarm: '⏰',
    cloudwatch_log_group: '📝',
    kms_key: '🗝',
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
  internet_gateway: { border: 'border-sky-500/50', header: 'bg-sky-900/30', badge: 'bg-sky-900/50 text-sky-300' },
  route_table: { border: 'border-indigo-500/50', header: 'bg-indigo-900/30', badge: 'bg-indigo-900/50 text-indigo-300' },
  nat_gateway: { border: 'border-amber-500/50', header: 'bg-amber-900/30', badge: 'bg-amber-900/50 text-amber-300' },
  lambda: { border: 'border-rose-500/50', header: 'bg-rose-900/30', badge: 'bg-rose-900/50 text-rose-300' },
  dynamodb: { border: 'border-teal-500/50', header: 'bg-teal-900/30', badge: 'bg-teal-900/50 text-teal-300' },
  iam_role: { border: 'border-lime-500/50', header: 'bg-lime-900/30', badge: 'bg-lime-900/50 text-lime-300' },
  cloudfront: { border: 'border-violet-500/50', header: 'bg-violet-900/30', badge: 'bg-violet-900/50 text-violet-300' },
  api_gateway: { border: 'border-fuchsia-500/50', header: 'bg-fuchsia-900/30', badge: 'bg-fuchsia-900/50 text-fuchsia-300' },
  route53_zone: { border: 'border-emerald-500/50', header: 'bg-emerald-900/30', badge: 'bg-emerald-900/50 text-emerald-300' },
  route53_record: { border: 'border-emerald-500/50', header: 'bg-emerald-900/30', badge: 'bg-emerald-900/50 text-emerald-300' },
  elastic_ip: { border: 'border-stone-500/50', header: 'bg-stone-900/30', badge: 'bg-stone-900/50 text-stone-300' },
  ebs_volume: { border: 'border-neutral-500/50', header: 'bg-neutral-900/30', badge: 'bg-neutral-900/50 text-neutral-300' },
  ecr_repository: { border: 'border-blue-400/50', header: 'bg-blue-900/30', badge: 'bg-blue-900/50 text-blue-300' },
  ecs_cluster: { border: 'border-cyan-400/50', header: 'bg-cyan-900/30', badge: 'bg-cyan-900/50 text-cyan-300' },
  efs: { border: 'border-green-400/50', header: 'bg-green-900/30', badge: 'bg-green-900/50 text-green-300' },
  elasticache: { border: 'border-red-400/50', header: 'bg-red-900/30', badge: 'bg-red-900/50 text-red-300' },
  aurora: { border: 'border-indigo-400/50', header: 'bg-indigo-900/30', badge: 'bg-indigo-900/50 text-indigo-300' },
  redshift: { border: 'border-pink-500/50', header: 'bg-pink-900/30', badge: 'bg-pink-900/50 text-pink-300' },
  kinesis_stream: { border: 'border-sky-400/50', header: 'bg-sky-900/30', badge: 'bg-sky-900/50 text-sky-300' },
  sqs: { border: 'border-orange-400/50', header: 'bg-orange-900/30', badge: 'bg-orange-900/50 text-orange-300' },
  sns: { border: 'border-amber-400/50', header: 'bg-amber-900/30', badge: 'bg-amber-900/50 text-amber-300' },
  step_function: { border: 'border-purple-400/50', header: 'bg-purple-900/30', badge: 'bg-purple-900/50 text-purple-300' },
  secretsmanager: { border: 'border-red-300/50', header: 'bg-red-900/30', badge: 'bg-red-900/50 text-red-300' },
  cloudwatch_alarm: { border: 'border-yellow-400/50', header: 'bg-yellow-900/30', badge: 'bg-yellow-900/50 text-yellow-300' },
  cloudwatch_log_group: { border: 'border-slate-400/50', header: 'bg-slate-900/30', badge: 'bg-slate-900/50 text-slate-300' },
  kms_key: { border: 'border-teal-400/50', header: 'bg-teal-900/30', badge: 'bg-teal-900/50 text-teal-300' },
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
    case 'internet_gateway': return 'VPC Internet Access';
    case 'route_table': return 'Network Routes';
    case 'nat_gateway': return props.allocationId || 'Private Subnet Egress';
    case 'lambda': return `${props.runtime || 'python3.12'} · ${props.handler || 'app.handler'}`;
    case 'dynamodb': return `${props.billingMode || 'PAY_PER_REQUEST'} · ${props.hashKey || 'id'}`;
    case 'iam_role': return props.service || 'IAM Permissions';
    case 'cloudfront': return props.originDomain || 'CDN Distribution';
    case 'api_gateway': return `${props.protocol || 'HTTP'} API`;
    case 'route53_zone': return props.domainName || 'Hosted Zone';
    case 'route53_record': return `${props.recordType || 'A'} Record`;
    case 'elastic_ip': return 'Static IPv4 Address';
    case 'ebs_volume': return `${props.size || 8} GB · ${props.volumeType || 'gp3'}`;
    case 'ecr_repository': return props.name || 'Container Registry';
    case 'ecs_cluster': return 'Container Orchestration';
    case 'efs': return 'Shared File Storage';
    case 'elasticache': return `${props.engine || 'redis'} · ${props.nodeType || 'cache.t3.micro'}`;
    case 'aurora': return `${props.engine || 'aurora-mysql'} · ${props.identifier || 'app-cluster'}`;
    case 'redshift': return `${props.nodeType || 'dc2.large'} · Data Warehouse`;
    case 'kinesis_stream': return `${props.shardCount || 1} shard(s)`;
    case 'sqs': return props.name || 'Message Queue';
    case 'sns': return props.name || 'Pub/Sub Notifications';
    case 'step_function': return 'Workflow Orchestration';
    case 'secretsmanager': return props.name || 'Secret Storage';
    case 'cloudwatch_alarm': return `${props.metric || 'CPUUtilization'} ${props.comparison === 'LessThanThreshold' ? '<' : '>'} ${props.threshold ?? 80}`;
    case 'cloudwatch_log_group': return `retain ${props.retentionDays || 30}d`;
    case 'kms_key': return 'Encryption Keys';
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
