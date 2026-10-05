import { useMemo, useState } from 'react';
import { Search, X } from 'lucide-react';
import type { ResourceType } from '../../types';

export interface SidebarItem {
  type: ResourceType;
  label: string;
  icon: string;
  description: string;
  defaultProperties: Record<string, any>;
}

export interface SidebarCategory {
  name: string;
  items: SidebarItem[];
}

export const sidebarCategories: SidebarCategory[] = [
  {
    name: 'Networking & DNS',
    items: [
      { type: 'vpc', label: 'VPC', icon: '☁', description: 'Virtual Private Cloud', defaultProperties: { name: 'main-vpc', cidr: '10.0.0.0/16', environment: 'development' } },
      { type: 'subnet', label: 'Subnet', icon: '⬡', description: 'Network Subnet', defaultProperties: { name: 'public-subnet', cidr: '10.0.1.0/24', availabilityZone: 'us-east-1a', mapPublicIp: true } },
      { type: 'security_group', label: 'Security Group', icon: '🛡', description: 'Firewall Rules', defaultProperties: { name: 'web-sg', description: 'Security group for web servers', allowHttp: true, allowHttps: true, webCidr: '0.0.0.0/0', allowSsh: false, sshCidr: '10.0.0.0/8', allowAllOutbound: true } },
      { type: 'internet_gateway', label: 'Internet Gateway', icon: '🌐', description: 'VPC Internet Access', defaultProperties: { name: 'main-igw' } },
      { type: 'route_table', label: 'Route Table', icon: '🛣', description: 'Network Routes', defaultProperties: { name: 'public-routes' } },
      { type: 'nat_gateway', label: 'NAT Gateway', icon: '↗', description: 'Private Subnet Egress', defaultProperties: { name: 'main-nat', allocationId: '' } },
      { type: 'cloudfront', label: 'CloudFront', icon: '⚡', description: 'CDN Distribution', defaultProperties: { name: 'cdn-distribution', originDomain: '', priceClass: 'PriceClass_100', defaultCacheTtl: 86400, minTtl: 0, maxTtl: 31536000 } },
      { type: 'api_gateway', label: 'API Gateway', icon: '🔀', description: 'HTTP / REST API', defaultProperties: { name: 'app-api', protocol: 'HTTP' } },
      { type: 'route53_zone', label: 'Route 53 Zone', icon: '🧭', description: 'Hosted Zone', defaultProperties: { name: 'main-zone', domainName: 'example.com' } },
      { type: 'route53_record', label: 'Route 53 Record', icon: '📍', description: 'DNS Record', defaultProperties: { name: 'www', recordType: 'A', recordValue: '10.0.0.10', ttl: 300 } },
      { type: 'elastic_ip', label: 'Elastic IP', icon: '📌', description: 'Static IPv4 Address', defaultProperties: { name: 'static-ip' } },
    ],
  },
  {
    name: 'Compute & Containers',
    items: [
      { type: 'ec2', label: 'EC2 Instance', icon: '🖥', description: 'Virtual Machine', defaultProperties: { name: 'web-server', instanceType: 't3.micro', associatePublicIp: true, keyPairName: '', rootVolumeSize: 30, rootVolumeType: 'gp3', monitoring: false } },
      { type: 'lambda', label: 'Lambda Function', icon: 'λ', description: 'Serverless Compute', defaultProperties: { functionName: 'app-function', runtime: 'python3.12', handler: 'app.handler', filename: 'lambda.zip', memorySize: 128, timeout: 30 } },
      { type: 'ebs_volume', label: 'EBS Volume', icon: '💽', description: 'Block Storage', defaultProperties: { name: 'data-volume', size: 8, volumeType: 'gp3', availabilityZone: 'us-east-1a', encrypted: false } },
      { type: 'ecr_repository', label: 'ECR Repository', icon: '📦', description: 'Container Registry', defaultProperties: { name: 'app-images', imageTagMutability: 'MUTABLE', scanOnPush: false } },
      { type: 'ecs_cluster', label: 'ECS Cluster', icon: '🐙', description: 'Container Orchestration', defaultProperties: { name: 'app-cluster', containerInsights: false } },
      { type: 'efs', label: 'EFS File System', icon: '📂', description: 'Shared File Storage', defaultProperties: { name: 'shared-files', performanceMode: 'generalPurpose', throughputMode: 'bursting' } },
    ],
  },
  {
    name: 'Storage',
    items: [
      { type: 's3', label: 'S3 Bucket', icon: '🪣', description: 'Object Storage', defaultProperties: { bucketName: 'my-app-storage', versioning: false, environment: 'development' } },
    ],
  },
  {
    name: 'Databases & Data',
    items: [
      { type: 'rds', label: 'RDS Database', icon: '🗄', description: 'Managed Database', defaultProperties: { identifier: 'my-database', engine: 'mysql', engineVersion: '8.0', instanceClass: 'db.t3.micro', storage: 20, storageType: 'gp2', dbName: 'appdb', username: 'admin', multiAz: false } },
      { type: 'dynamodb', label: 'DynamoDB Table', icon: '▦', description: 'NoSQL Database', defaultProperties: { tableName: 'app-table', billingMode: 'PAY_PER_REQUEST', hashKey: 'id', hashKeyType: 'S' } },
      { type: 'elasticache', label: 'ElastiCache', icon: '🔥', description: 'Redis / Memcached', defaultProperties: { name: 'app-cache', engine: 'redis', nodeType: 'cache.t3.micro', numCacheNodes: 1 } },
      { type: 'aurora', label: 'Aurora Cluster', icon: '🌌', description: 'Managed MySQL / Postgres', defaultProperties: { identifier: 'app-cluster', engine: 'aurora-mysql', username: 'admin', dbName: 'appdb' } },
      { type: 'redshift', label: 'Redshift', icon: '📊', description: 'Data Warehouse', defaultProperties: { clusterIdentifier: 'analytics-cluster', nodeType: 'dc2.large', numberOfNodes: 2, dbName: 'analytics', username: 'admin' } },
      { type: 'kinesis_stream', label: 'Kinesis Stream', icon: '🌊', description: 'Real-time Data Streaming', defaultProperties: { name: 'events-stream', shardCount: 1, retentionHours: 24 } },
    ],
  },
  {
    name: 'Messaging & Serverless',
    items: [
      { type: 'sqs', label: 'SQS Queue', icon: '📨', description: 'Message Queue', defaultProperties: { name: 'tasks-queue', visibilityTimeout: 30, messageRetention: 345600 } },
      { type: 'sns', label: 'SNS Topic', icon: '📢', description: 'Pub/Sub Notifications', defaultProperties: { name: 'notifications' } },
      { type: 'step_function', label: 'Step Functions', icon: '🧩', description: 'Workflow Orchestration', defaultProperties: { name: 'workflow' } },
      { type: 'secretsmanager', label: 'Secrets Manager', icon: '🔐', description: 'Secret Storage', defaultProperties: { name: 'app-secrets', description: 'Application secrets', recoveryWindowDays: 7 } },
    ],
  },
  {
    name: 'Observability & Security',
    items: [
      { type: 'cloudwatch_alarm', label: 'CloudWatch Alarm', icon: '⏰', description: 'Metric Alerts', defaultProperties: { name: 'cpu-alarm', description: 'Alarm managed by CloudForge', metric: 'CPUUtilization', threshold: 80, namespace: 'AWS/EC2', comparison: 'GreaterThanThreshold', evaluationPeriods: 2, period: 60, statistic: 'Average' } },
      { type: 'cloudwatch_log_group', label: 'CloudWatch Logs', icon: '📝', description: 'Log Group', defaultProperties: { name: 'app-logs', retentionDays: 30 } },
      { type: 'kms_key', label: 'KMS Key', icon: '🗝', description: 'Encryption Keys', defaultProperties: { name: 'app-key', description: 'Application encryption key', deletionWindowDays: 7 } },
    ],
  },
  {
    name: 'Application',
    items: [
      { type: 'load_balancer', label: 'Load Balancer', icon: '⚖', description: 'Application Load Balancer', defaultProperties: { name: 'app-lb', lbType: 'application', internal: false } },
      { type: 'iam_role', label: 'IAM Role', icon: '🔑', description: 'Permissions and Access', defaultProperties: { name: 'app-role', service: 'lambda.amazonaws.com' } },
    ],
  },
];

interface BuilderSidebarProps {
  onDragStart: (event: React.DragEvent, item: SidebarItem) => void;
}

export function BuilderSidebar({ onDragStart }: BuilderSidebarProps) {
  const [query, setQuery] = useState('');

  const filteredCategories = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return sidebarCategories;
    return sidebarCategories
      .map((category) => ({
        ...category,
        items: category.items.filter((item) =>
          item.label.toLowerCase().includes(q) ||
          item.type.toLowerCase().includes(q) ||
          item.description.toLowerCase().includes(q)
        ),
      }))
      .filter((category) => category.items.length > 0);
  }, [query]);

  const totalMatches = filteredCategories.reduce((sum, c) => sum + c.items.length, 0);

  return (
    <aside className="w-56 bg-dark-900 border-r border-dark-800 flex flex-col overflow-y-auto flex-shrink-0">
      <div className="px-4 py-3 border-b border-dark-800">
        <h2 className="text-xs font-bold text-dark-400 uppercase tracking-wider">Resources</h2>
        <p className="text-[10px] text-dark-600 mt-0.5">Drag to canvas</p>
      </div>
      <div className="px-3 py-2 border-b border-dark-800 relative">
        <Search className="w-3.5 h-3.5 text-dark-600 absolute left-6 top-1/2 -translate-y-1/2 pointer-events-none" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search resources..."
          aria-label="Search resources"
          className="w-full bg-dark-800 border border-dark-700 rounded-lg pl-8 pr-7 py-1.5 text-xs text-dark-200 placeholder-dark-600 focus:outline-none focus:border-primary-500 transition-colors"
        />
        {query && (
          <button
            onClick={() => setQuery('')}
            className="absolute right-5 top-1/2 -translate-y-1/2 text-dark-600 hover:text-dark-300"
            title="Clear search"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
      <div className="flex-1 py-2">
        {filteredCategories.length === 0 ? (
          <div className="px-4 py-6 text-center">
            <Search className="w-6 h-6 text-dark-700 mx-auto mb-2" />
            <p className="text-xs text-dark-500">No resources match "{query}"</p>
          </div>
        ) : (
          <>
            {query && (
              <div className="px-4 py-1.5 text-[10px] text-dark-600">
                {totalMatches} match{totalMatches !== 1 ? 'es' : ''}
              </div>
            )}
            {filteredCategories.map((category) => (
              <div key={category.name} className="mb-2">
                <div className="px-4 py-1.5 text-[10px] font-semibold text-dark-600 uppercase tracking-widest">
                  {category.name}
                </div>
                {category.items.map((item) => (
                  <div
                    key={item.type}
                    draggable
                    onDragStart={(e) => onDragStart(e, item)}
                    className="mx-2 mb-1 flex items-center gap-2.5 px-3 py-2.5 rounded-lg border border-dark-800 cursor-grab active:cursor-grabbing bg-dark-800/50 hover:bg-dark-800 hover:border-dark-700 transition-all duration-150 select-none group"
                  >
                    <span className="text-base leading-none group-hover:scale-110 transition-transform">{item.icon}</span>
                    <div className="min-w-0">
                      <div className="text-xs font-medium text-dark-200 group-hover:text-white transition-colors">{item.label}</div>
                      <div className="text-[10px] text-dark-600 truncate">{item.description}</div>
                    </div>
                  </div>
                ))}
              </div>
            ))}
          </>
        )}
      </div>
    </aside>
  );
}
