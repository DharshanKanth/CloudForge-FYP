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
    name: 'Networking',
    items: [
      { type: 'vpc', label: 'VPC', icon: '☁', description: 'Virtual Private Cloud', defaultProperties: { name: 'main-vpc', cidr: '10.0.0.0/16', environment: 'development' } },
      { type: 'subnet', label: 'Subnet', icon: '⬡', description: 'Network Subnet', defaultProperties: { name: 'public-subnet', cidr: '10.0.1.0/24', availabilityZone: 'us-east-1a', mapPublicIp: true } },
      { type: 'security_group', label: 'Security Group', icon: '🛡', description: 'Firewall Rules', defaultProperties: { name: 'web-sg', description: 'Security group for web servers' } },
    ],
  },
  {
    name: 'Compute',
    items: [
      { type: 'ec2', label: 'EC2 Instance', icon: '🖥', description: 'Virtual Machine', defaultProperties: { name: 'web-server', instanceType: 't2.micro', amiId: 'ami-0c55b159cbfafe1f0', associatePublicIp: true } },
    ],
  },
  {
    name: 'Storage',
    items: [
      { type: 's3', label: 'S3 Bucket', icon: '🪣', description: 'Object Storage', defaultProperties: { bucketName: 'my-app-storage', versioning: false } },
    ],
  },
  {
    name: 'Database',
    items: [
      { type: 'rds', label: 'RDS Database', icon: '🗄', description: 'Managed Database', defaultProperties: { identifier: 'my-database', engine: 'mysql', engineVersion: '8.0', instanceClass: 'db.t3.micro', storage: 20, dbName: 'appdb', username: 'admin', multiAz: false } },
    ],
  },
  {
    name: 'Application',
    items: [
      { type: 'load_balancer', label: 'Load Balancer', icon: '⚖', description: 'Application Load Balancer', defaultProperties: { name: 'app-lb', lbType: 'application', internal: false } },
    ],
  },
];

interface BuilderSidebarProps {
  onDragStart: (event: React.DragEvent, item: SidebarItem) => void;
}

export function BuilderSidebar({ onDragStart }: BuilderSidebarProps) {
  return (
    <aside className="w-56 bg-dark-900 border-r border-dark-800 flex flex-col overflow-y-auto flex-shrink-0">
      <div className="px-4 py-3 border-b border-dark-800">
        <h2 className="text-xs font-bold text-dark-400 uppercase tracking-wider">Resources</h2>
        <p className="text-[10px] text-dark-600 mt-0.5">Drag to canvas</p>
      </div>
      <div className="flex-1 py-2">
        {sidebarCategories.map((category) => (
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
      </div>
    </aside>
  );
}
