import { X, Layout, Globe, Server } from 'lucide-react';
import type { Node, Edge } from '@xyflow/react';

interface TemplateModalProps {
  onSelect: (nodes: Node[], edges: Edge[]) => void;
  onClose: () => void;
}

interface Template {
  name: string;
  description: string;
  icon: React.ReactNode;
  nodes: Node[];
  edges: Edge[];
}

const templates: Template[] = [
  {
    name: 'Blank Canvas',
    description: 'Start from scratch',
    icon: <Layout className="w-6 h-6" />,
    nodes: [],
    edges: [],
  },
  {
    name: '3-Tier Web Application',
    description: 'VPC with public, app, and database subnets',
    icon: <Server className="w-6 h-6" />,
    nodes: [
      { id: 'vpc-1', type: 'groupNode', position: { x: 50, y: 50 }, data: { label: 'VPC', resourceType: 'vpc', provider: 'aws', properties: { name: 'prod-vpc', cidr: '10.0.0.0/16', environment: 'production' } } },
      { id: 'igw-1', type: 'resourceNode', parentId: 'vpc-1', position: { x: 20, y: 40 }, data: { label: 'Internet Gateway', resourceType: 'internet_gateway', provider: 'aws', properties: { name: 'prod-igw' } } },
      { id: 'subnet-pub', type: 'groupNode', parentId: 'vpc-1', position: { x: 20, y: 110 }, data: { label: 'Subnet', resourceType: 'subnet', provider: 'aws', properties: { name: 'public-subnet', cidr: '10.0.1.0/24', availabilityZone: 'us-east-1a', mapPublicIp: true } } },
      { id: 'subnet-app', type: 'groupNode', parentId: 'vpc-1', position: { x: 280, y: 110 }, data: { label: 'Subnet', resourceType: 'subnet', provider: 'aws', properties: { name: 'app-subnet', cidr: '10.0.2.0/24', availabilityZone: 'us-east-1a', mapPublicIp: false } } },
      { id: 'subnet-db', type: 'groupNode', parentId: 'vpc-1', position: { x: 540, y: 110 }, data: { label: 'Subnet', resourceType: 'subnet', provider: 'aws', properties: { name: 'db-subnet', cidr: '10.0.3.0/24', availabilityZone: 'us-east-1a', mapPublicIp: false } } },
      { id: 'sg-web', type: 'resourceNode', parentId: 'subnet-pub', position: { x: 10, y: 40 }, data: { label: 'Security Group', resourceType: 'security_group', provider: 'aws', properties: { name: 'web-sg', description: 'HTTP/HTTPS ingress' } } },
      { id: 'lb-1', type: 'resourceNode', parentId: 'subnet-pub', position: { x: 10, y: 140 }, data: { label: 'Load Balancer', resourceType: 'load_balancer', provider: 'aws', properties: { name: 'app-alb', lbType: 'application', internal: false } } },
      { id: 'sg-app', type: 'resourceNode', parentId: 'subnet-app', position: { x: 10, y: 40 }, data: { label: 'Security Group', resourceType: 'security_group', provider: 'aws', properties: { name: 'app-sg', description: 'App tier ingress' } } },
      { id: 'ec2-1', type: 'resourceNode', parentId: 'subnet-app', position: { x: 10, y: 140 }, data: { label: 'EC2 Instance', resourceType: 'ec2', provider: 'aws', properties: { name: 'app-server-1', instanceType: 't3.micro', associatePublicIp: false } } },
      { id: 'ec2-2', type: 'resourceNode', parentId: 'subnet-app', position: { x: 200, y: 140 }, data: { label: 'EC2 Instance', resourceType: 'ec2', provider: 'aws', properties: { name: 'app-server-2', instanceType: 't3.micro', associatePublicIp: false } } },
      { id: 'sg-db', type: 'resourceNode', parentId: 'subnet-db', position: { x: 10, y: 40 }, data: { label: 'Security Group', resourceType: 'security_group', provider: 'aws', properties: { name: 'db-sg', description: 'Database ingress' } } },
      { id: 'rds-1', type: 'resourceNode', parentId: 'subnet-db', position: { x: 10, y: 140 }, data: { label: 'RDS Database', resourceType: 'rds', provider: 'aws', properties: { identifier: 'app-db', engine: 'mysql', engineVersion: '8.0', instanceClass: 'db.t3.micro', storage: 20, dbName: 'appdb', username: 'admin', multiAz: false } } },
    ],
    edges: [
      { id: 'e-vpc-igw', source: 'vpc-1', target: 'igw-1' },
      { id: 'e-vpc-pub', source: 'vpc-1', target: 'subnet-pub' },
      { id: 'e-vpc-app', source: 'vpc-1', target: 'subnet-app' },
      { id: 'e-vpc-db', source: 'vpc-1', target: 'subnet-db' },
      { id: 'e-pub-sgweb', source: 'subnet-pub', target: 'sg-web' },
      { id: 'e-pub-lb', source: 'subnet-pub', target: 'lb-1' },
      { id: 'e-app-sgapp', source: 'subnet-app', target: 'sg-app' },
      { id: 'e-app-ec21', source: 'subnet-app', target: 'ec2-1' },
      { id: 'e-app-ec22', source: 'subnet-app', target: 'ec2-2' },
      { id: 'e-db-sgdb', source: 'subnet-db', target: 'sg-db' },
      { id: 'e-db-rds', source: 'subnet-db', target: 'rds-1' },
      { id: 'e-sgweb-lb', source: 'sg-web', target: 'lb-1' },
      { id: 'e-lb-ec21', source: 'lb-1', target: 'ec2-1' },
      { id: 'e-lb-ec22', source: 'lb-1', target: 'ec2-2' },
      { id: 'e-sgapp-ec21', source: 'sg-app', target: 'ec2-1' },
      { id: 'e-sgapp-ec22', source: 'sg-app', target: 'ec2-2' },
      { id: 'e-sgdb-rds', source: 'sg-db', target: 'rds-1' },
      { id: 'e-ec21-rds', source: 'ec2-1', target: 'rds-1' },
    ],
  },
  {
    name: 'Basic AWS Application',
    description: 'VPC with public subnet, EC2, S3, and Lambda',
    icon: <Globe className="w-6 h-6" />,
    nodes: [
      { id: 'vpc-1', type: 'groupNode', position: { x: 50, y: 50 }, data: { label: 'VPC', resourceType: 'vpc', provider: 'aws', properties: { name: 'main-vpc', cidr: '10.0.0.0/16' } } },
      { id: 'igw-1', type: 'resourceNode', parentId: 'vpc-1', position: { x: 20, y: 20 }, data: { label: 'Internet Gateway', resourceType: 'internet_gateway', provider: 'aws', properties: { name: 'main-igw' } } },
      { id: 'subnet-1', type: 'groupNode', parentId: 'vpc-1', position: { x: 20, y: 80 }, data: { label: 'Subnet', resourceType: 'subnet', provider: 'aws', properties: { name: 'public-subnet', cidr: '10.0.1.0/24', availabilityZone: 'us-east-1a', mapPublicIp: true } } },
      { id: 'ec2-1', type: 'resourceNode', parentId: 'subnet-1', position: { x: 10, y: 40 }, data: { label: 'EC2 Instance', resourceType: 'ec2', provider: 'aws', properties: { name: 'web-server', instanceType: 't3.micro', associatePublicIp: true } } },
      { id: 's3-1', type: 'resourceNode', position: { x: 400, y: 80 }, data: { label: 'S3 Bucket', resourceType: 's3', provider: 'aws', properties: { bucketName: 'app-storage-bucket', versioning: true } } },
      { id: 'fn-1', type: 'resourceNode', position: { x: 400, y: 220 }, data: { label: 'Lambda Function', resourceType: 'lambda', provider: 'aws', properties: { functionName: 'process-uploads', runtime: 'python3.12', handler: 'app.handler', filename: 'lambda.zip', memorySize: 256, timeout: 60 } } },
      { id: 'role-1', type: 'resourceNode', position: { x: 400, y: 360 }, data: { label: 'IAM Role', resourceType: 'iam_role', provider: 'aws', properties: { name: 'lambda-role', service: 'lambda.amazonaws.com' } } },
    ],
    edges: [
      { id: 'e-vpc-igw', source: 'vpc-1', target: 'igw-1' },
      { id: 'e-vpc-sub', source: 'vpc-1', target: 'subnet-1' },
      { id: 'e-sub-ec2', source: 'subnet-1', target: 'ec2-1' },
      { id: 'e-ec2-s3', source: 'ec2-1', target: 's3-1' },
      { id: 'e-ec2-fn', source: 'ec2-1', target: 'fn-1' },
      { id: 'e-fn-s3', source: 'fn-1', target: 's3-1' },
      { id: 'e-fn-role', source: 'fn-1', target: 'role-1' },
    ],
  },
];

export function TemplateModal({ onSelect, onClose }: TemplateModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-dark-900 border border-dark-700 rounded-2xl w-full max-w-2xl mx-4 overflow-hidden shadow-2xl">
        <div className="flex items-center justify-between px-6 py-4 border-b border-dark-800">
          <div>
            <h2 className="text-sm font-bold text-white">Create Architecture</h2>
            <p className="text-xs text-dark-500 mt-0.5">Choose a template to get started</p>
          </div>
          <button onClick={onClose} className="text-dark-500 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-6 grid grid-cols-3 gap-4">
          {templates.map((t) => (
            <button
              key={t.name}
              onClick={() => { onSelect(t.nodes, t.edges); onClose(); }}
              className="flex flex-col items-center gap-3 p-5 rounded-xl border border-dark-700 bg-dark-800/50 hover:bg-dark-800 hover:border-primary-500/50 transition-all text-center group"
            >
              <div className="w-12 h-12 rounded-lg bg-dark-700 group-hover:bg-primary-900/30 flex items-center justify-center text-dark-400 group-hover:text-primary-400 transition-colors">
                {t.icon}
              </div>
              <div>
                <div className="text-xs font-semibold text-white">{t.name}</div>
                <div className="text-[10px] text-dark-500 mt-0.5">{t.description}</div>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
