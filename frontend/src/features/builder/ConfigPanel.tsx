import { type Node } from '@xyflow/react';
import { X, Settings } from 'lucide-react';
import type { ResourceType } from '../../types';

interface ConfigPanelProps {
  node: Node | null;
  onClose: () => void;
  onChange: (nodeId: string, properties: Record<string, any>) => void;
}

function FieldInput({
  label,
  value,
  onChange,
  type = 'text',
  placeholder,
  options,
}: {
  label: string;
  value: any;
  onChange: (v: any) => void;
  type?: string;
  placeholder?: string;
  options?: { label: string; value: string }[];
}) {
  if (type === 'boolean') {
    return (
      <div className="flex items-center justify-between">
        <label className="text-xs text-dark-400">{label}</label>
        <button
          onClick={() => onChange(!value)}
          className={`w-9 h-5 rounded-full transition-all duration-200 relative ${
            value ? 'bg-primary-600' : 'bg-dark-700'
          }`}
        >
          <div
            className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all duration-200 shadow ${
              value ? 'left-4' : 'left-0.5'
            }`}
          />
        </button>
      </div>
    );
  }

  if (options) {
    return (
      <div>
        <label className="label">{label}</label>
        <select
          value={value || ''}
          onChange={(e) => onChange(e.target.value)}
          className="input"
        >
          {options.map((o) => (
            <option key={o.value} value={o.value} style={{ background: '#1f2937' }}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
    );
  }

  return (
    <div>
      <label className="label">{label}</label>
      <input
        type={type}
        value={value ?? ''}
        onChange={(e) => onChange(type === 'number'
          ? (e.target.value === '' ? undefined : Number(e.target.value))
          : e.target.value)}
        placeholder={placeholder}
        className="input"
      />
    </div>
  );
}

function VpcConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return (
    <div className="space-y-3">
      <FieldInput label="Name" value={props.name} onChange={(v) => onChange({ ...props, name: v })} placeholder="main-vpc" />
      <FieldInput label="CIDR Block" value={props.cidr} onChange={(v) => onChange({ ...props, cidr: v })} placeholder="10.0.0.0/16" />
      <FieldInput label="Environment" value={props.environment} onChange={(v) => onChange({ ...props, environment: v })} placeholder="development" />
    </div>
  );
}

function SubnetConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return (
    <div className="space-y-3">
      <FieldInput label="Name" value={props.name} onChange={(v) => onChange({ ...props, name: v })} placeholder="public-subnet" />
      <FieldInput label="CIDR Block" value={props.cidr} onChange={(v) => onChange({ ...props, cidr: v })} placeholder="10.0.1.0/24" />
      <FieldInput
        label="Availability Zone"
        value={props.availabilityZone}
        onChange={(v) => onChange({ ...props, availabilityZone: v })}
        options={[
          { label: 'us-east-1a', value: 'us-east-1a' },
          { label: 'us-east-1b', value: 'us-east-1b' },
          { label: 'us-east-1c', value: 'us-east-1c' },
          { label: 'us-west-2a', value: 'us-west-2a' },
          { label: 'us-west-2b', value: 'us-west-2b' },
          { label: 'eu-west-1a', value: 'eu-west-1a' },
        ]}
      />
      <FieldInput label="Map Public IP" value={props.mapPublicIp ?? true} onChange={(v) => onChange({ ...props, mapPublicIp: v })} type="boolean" />
    </div>
  );
}

function Ec2Config({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return (
    <div className="space-y-3">
      <FieldInput label="Name" value={props.name} onChange={(v) => onChange({ ...props, name: v })} placeholder="web-server" />
      <FieldInput
        label="Instance Type"
        value={props.instanceType}
        onChange={(v) => onChange({ ...props, instanceType: v })}
        options={[
          { label: 't3.micro (Free tier — all regions)', value: 't3.micro' },
          { label: 't2.micro (Free tier in some regions only)', value: 't2.micro' },
          { label: 't2.small', value: 't2.small' },
          { label: 't2.medium', value: 't2.medium' },
          { label: 't2.large', value: 't2.large' },
          { label: 't3.small', value: 't3.small' },
          { label: 't3.medium', value: 't3.medium' },
          { label: 'm5.large', value: 'm5.large' },
          { label: 'c5.large', value: 'c5.large' },
        ]}
      />
      <FieldInput label="Custom AMI ID (optional)" value={props.amiId} onChange={(v) => onChange({ ...props, amiId: v })} placeholder="Leave empty for latest Amazon Linux 2023" />
      <FieldInput label="Associate Public IP" value={props.associatePublicIp ?? true} onChange={(v) => onChange({ ...props, associatePublicIp: v })} type="boolean" />
      <FieldInput label="Key Pair Name" value={props.keyPairName} onChange={(v) => onChange({ ...props, keyPairName: v })} placeholder="my-key-pair" />
      <FieldInput label="Root Volume Size (GB)" value={props.rootVolumeSize ?? 8} onChange={(v) => onChange({ ...props, rootVolumeSize: v })} type="number" placeholder="8" />
      <FieldInput label="Root Volume Type" value={props.rootVolumeType || 'gp3'} onChange={(v) => onChange({ ...props, rootVolumeType: v })} options={[
        { label: 'gp3 (SSD)', value: 'gp3' }, { label: 'gp2 (SSD)', value: 'gp2' },
      ]} />
      <FieldInput label="Detailed Monitoring" value={props.monitoring ?? false} onChange={(v) => onChange({ ...props, monitoring: v })} type="boolean" />
    </div>
  );
}

function S3Config({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return (
    <div className="space-y-3">
      <FieldInput label="Bucket Name" value={props.bucketName} onChange={(v) => onChange({ ...props, bucketName: v })} placeholder="my-app-storage" />
      <FieldInput label="Environment" value={props.environment} onChange={(v) => onChange({ ...props, environment: v })} placeholder="development" />
      <FieldInput label="Enable Versioning" value={props.versioning ?? false} onChange={(v) => onChange({ ...props, versioning: v })} type="boolean" />
    </div>
  );
}

function RdsConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return (
    <div className="space-y-3">
      <FieldInput label="Identifier" value={props.identifier} onChange={(v) => onChange({ ...props, identifier: v })} placeholder="my-database" />
      <FieldInput
        label="Engine"
        value={props.engine}
        onChange={(v) => onChange({ ...props, engine: v })}
        options={[
          { label: 'MySQL 8.0', value: 'mysql' },
          { label: 'PostgreSQL 15', value: 'postgres' },
          { label: 'MariaDB', value: 'mariadb' },
        ]}
      />
      <FieldInput label="Engine Version" value={props.engineVersion} onChange={(v) => onChange({ ...props, engineVersion: v })} placeholder="8.0" />
      <FieldInput
        label="Instance Class"
        value={props.instanceClass}
        onChange={(v) => onChange({ ...props, instanceClass: v })}
        options={[
          { label: 'db.t3.micro', value: 'db.t3.micro' },
          { label: 'db.t3.small', value: 'db.t3.small' },
          { label: 'db.t3.medium', value: 'db.t3.medium' },
          { label: 'db.r5.large', value: 'db.r5.large' },
        ]}
      />
      <FieldInput label="Storage (GB)" value={props.storage || 20} onChange={(v) => onChange({ ...props, storage: v })} type="number" placeholder="20" />
      <FieldInput label="Database Name" value={props.dbName} onChange={(v) => onChange({ ...props, dbName: v })} placeholder="appdb" />
      <FieldInput label="Username" value={props.username} onChange={(v) => onChange({ ...props, username: v })} placeholder="admin" />
      <FieldInput label="Multi-AZ" value={props.multiAz ?? false} onChange={(v) => onChange({ ...props, multiAz: v })} type="boolean" />
      <FieldInput
        label="Storage Type"
        value={props.storageType ?? 'gp2'}
        onChange={(v) => onChange({ ...props, storageType: v })}
        options={[
          { label: 'gp2', value: 'gp2' },
          { label: 'gp3', value: 'gp3' },
          { label: 'io1', value: 'io1' },
        ]}
      />
    </div>
  );
}

function SgConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return (
    <div className="space-y-3">
      <FieldInput label="Name" value={props.name} onChange={(v) => onChange({ ...props, name: v })} placeholder="web-sg" />
      <FieldInput label="Description" value={props.description} onChange={(v) => onChange({ ...props, description: v })} placeholder="Security group for web servers" />
      <FieldInput label="Allow HTTP (80)" value={props.allowHttp ?? true} onChange={(v) => onChange({ ...props, allowHttp: v })} type="boolean" />
      <FieldInput label="Allow HTTPS (443)" value={props.allowHttps ?? true} onChange={(v) => onChange({ ...props, allowHttps: v })} type="boolean" />
      <FieldInput label="Web Inbound CIDR" value={props.webCidr || '0.0.0.0/0'} onChange={(v) => onChange({ ...props, webCidr: v })} placeholder="0.0.0.0/0" />
      <FieldInput label="Allow SSH (22)" value={props.allowSsh ?? false} onChange={(v) => onChange({ ...props, allowSsh: v })} type="boolean" />
      <FieldInput label="SSH Inbound CIDR" value={props.sshCidr || '10.0.0.0/8'} onChange={(v) => onChange({ ...props, sshCidr: v })} placeholder="10.0.0.0/8" />
      <FieldInput label="Allow All Outbound" value={props.allowAllOutbound ?? true} onChange={(v) => onChange({ ...props, allowAllOutbound: v })} type="boolean" />
    </div>
  );
}

function LbConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return (
    <div className="space-y-3">
      <FieldInput label="Name" value={props.name} onChange={(v) => onChange({ ...props, name: v })} placeholder="app-lb" />
      <FieldInput
        label="Type"
        value={props.lbType}
        onChange={(v) => onChange({ ...props, lbType: v })}
        options={[
          { label: 'Application (ALB)', value: 'application' },
          { label: 'Network (NLB)', value: 'network' },
        ]}
      />
      <FieldInput label="Internal" value={props.internal ?? false} onChange={(v) => onChange({ ...props, internal: v })} type="boolean" />
    </div>
  );
}

function InternetGatewayConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return <div className="space-y-3">
    <FieldInput label="Name" value={props.name} onChange={(v) => onChange({ ...props, name: v })} placeholder="main-igw" />
  </div>;
}

function RouteTableConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return <div className="space-y-3">
    <FieldInput label="Name" value={props.name} onChange={(v) => onChange({ ...props, name: v })} placeholder="public-routes" />
    <FieldInput label="Destination CIDR" value={props.destinationCidr || '0.0.0.0/0'} onChange={(v) => onChange({ ...props, destinationCidr: v })} placeholder="0.0.0.0/0" />
  </div>;
}

function NatGatewayConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return <div className="space-y-3">
    <FieldInput label="Name" value={props.name} onChange={(v) => onChange({ ...props, name: v })} placeholder="main-nat" />
    <FieldInput label="Elastic IP Allocation ID" value={props.allocationId} onChange={(v) => onChange({ ...props, allocationId: v })} placeholder="eipalloc-..." />
  </div>;
}

function LambdaConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return <div className="space-y-3">
    <FieldInput label="Function Name" value={props.functionName} onChange={(v) => onChange({ ...props, functionName: v })} placeholder="app-function" />
    <FieldInput label="Runtime" value={props.runtime} onChange={(v) => onChange({ ...props, runtime: v })} options={[
      { label: 'Python 3.12', value: 'python3.12' }, { label: 'Node.js 22.x', value: 'nodejs22.x' }, { label: 'Java 21', value: 'java21' },
    ]} />
    <FieldInput label="Handler" value={props.handler} onChange={(v) => onChange({ ...props, handler: v })} placeholder="app.handler" />
    <FieldInput label="Deployment Package" value={props.filename} onChange={(v) => onChange({ ...props, filename: v })} placeholder="lambda.zip" />
    <FieldInput label="Memory (MB)" value={props.memorySize || 128} onChange={(v) => onChange({ ...props, memorySize: v })} type="number" />
    <FieldInput label="Timeout (seconds)" value={props.timeout || 30} onChange={(v) => onChange({ ...props, timeout: v })} type="number" />
  </div>;
}

function DynamoDbConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return <div className="space-y-3">
    <FieldInput label="Table Name" value={props.tableName} onChange={(v) => onChange({ ...props, tableName: v })} placeholder="app-table" />
    <FieldInput label="Billing Mode" value={props.billingMode} onChange={(v) => onChange({ ...props, billingMode: v })} options={[
      { label: 'On demand', value: 'PAY_PER_REQUEST' }, { label: 'Provisioned', value: 'PROVISIONED' },
    ]} />
    <FieldInput label="Read Capacity (Provisioned)" value={props.readCapacity ?? 5} onChange={(v) => onChange({ ...props, readCapacity: v })} type="number" placeholder="5" />
    <FieldInput label="Write Capacity (Provisioned)" value={props.writeCapacity ?? 5} onChange={(v) => onChange({ ...props, writeCapacity: v })} type="number" placeholder="5" />
    <FieldInput label="Partition Key" value={props.hashKey} onChange={(v) => onChange({ ...props, hashKey: v })} placeholder="id" />
    <FieldInput label="Key Type" value={props.hashKeyType || 'S'} onChange={(v) => onChange({ ...props, hashKeyType: v })} options={[
      { label: 'String', value: 'S' }, { label: 'Number', value: 'N' }, { label: 'Binary', value: 'B' },
    ]} />
  </div>;
}

function IamRoleConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return <div className="space-y-3">
    <FieldInput label="Role Name" value={props.name} onChange={(v) => onChange({ ...props, name: v })} placeholder="app-role" />
    <FieldInput label="Trusted Service" value={props.service || 'lambda.amazonaws.com'} onChange={(v) => onChange({ ...props, service: v })} placeholder="lambda.amazonaws.com" />
  </div>;
}

function CloudFrontConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return <div className="space-y-3">
    <FieldInput label="Name" value={props.name} onChange={(v) => onChange({ ...props, name: v })} placeholder="cdn-distribution" />
    <FieldInput label="Origin Domain" value={props.originDomain} onChange={(v) => onChange({ ...props, originDomain: v })} placeholder="Connect an S3 bucket or enter a domain" />
    <FieldInput label="Price Class" value={props.priceClass || 'PriceClass_100'} onChange={(v) => onChange({ ...props, priceClass: v })} options={[
      { label: '100 (US/EU)', value: 'PriceClass_100' },
      { label: '200 (US/EU/Asia)', value: 'PriceClass_200' },
      { label: 'All Edges', value: 'PriceClass_All' },
    ]} />
  </div>;
}

function ApiGatewayConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return <div className="space-y-3">
    <FieldInput label="Name" value={props.name} onChange={(v) => onChange({ ...props, name: v })} placeholder="app-api" />
    <FieldInput label="Protocol" value={props.protocol || 'HTTP'} onChange={(v) => onChange({ ...props, protocol: v })} options={[
      { label: 'HTTP', value: 'HTTP' },
      { label: 'REST', value: 'REST' },
      { label: 'WebSocket', value: 'WEBSOCKET' },
    ]} />
  </div>;
}

function Route53ZoneConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return <div className="space-y-3">
    <FieldInput label="Name" value={props.name} onChange={(v) => onChange({ ...props, name: v })} placeholder="main-zone" />
    <FieldInput label="Domain Name" value={props.domainName} onChange={(v) => onChange({ ...props, domainName: v })} placeholder="example.com" />
  </div>;
}

function Route53RecordConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return <div className="space-y-3">
    <FieldInput label="Record Name" value={props.name} onChange={(v) => onChange({ ...props, name: v })} placeholder="www" />
    <FieldInput label="Record Type" value={props.recordType || 'A'} onChange={(v) => onChange({ ...props, recordType: v })} options={[
      { label: 'A', value: 'A' }, { label: 'AAAA', value: 'AAAA' }, { label: 'CNAME', value: 'CNAME' },
      { label: 'MX', value: 'MX' }, { label: 'TXT', value: 'TXT' }, { label: 'NS', value: 'NS' },
      { label: 'SOA', value: 'SOA' }, { label: 'SRV', value: 'SRV' }, { label: 'PTR', value: 'PTR' },
    ]} />
    <FieldInput label="Value" value={props.recordValue} onChange={(v) => onChange({ ...props, recordValue: v })} placeholder="10.0.0.10" />
    <FieldInput label="TTL (seconds)" value={props.ttl ?? 300} onChange={(v) => onChange({ ...props, ttl: v })} type="number" />
  </div>;
}

function ElasticIpConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return <div className="space-y-3">
    <FieldInput label="Name" value={props.name} onChange={(v) => onChange({ ...props, name: v })} placeholder="static-ip" />
  </div>;
}

function EbsVolumeConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return <div className="space-y-3">
    <FieldInput label="Name" value={props.name} onChange={(v) => onChange({ ...props, name: v })} placeholder="data-volume" />
    <FieldInput label="Size (GB)" value={props.size ?? 8} onChange={(v) => onChange({ ...props, size: v })} type="number" placeholder="8" />
    <FieldInput label="Volume Type" value={props.volumeType || 'gp3'} onChange={(v) => onChange({ ...props, volumeType: v })} options={[
      { label: 'gp3 (SSD)', value: 'gp3' }, { label: 'gp2 (SSD)', value: 'gp2' },
      { label: 'io1 (Provisioned IOPS)', value: 'io1' }, { label: 'io2', value: 'io2' },
      { label: 'st1 (Throughput HDD)', value: 'st1' }, { label: 'sc1 (Cold HDD)', value: 'sc1' },
    ]} />
    <FieldInput label="Availability Zone" value={props.availabilityZone || 'us-east-1a'} onChange={(v) => onChange({ ...props, availabilityZone: v })} options={[
      { label: 'us-east-1a', value: 'us-east-1a' }, { label: 'us-east-1b', value: 'us-east-1b' }, { label: 'us-east-1c', value: 'us-east-1c' },
    ]} />
  </div>;
}

function EcrRepositoryConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return <div className="space-y-3">
    <FieldInput label="Repository Name" value={props.name} onChange={(v) => onChange({ ...props, name: v })} placeholder="app-images" />
    <FieldInput label="Image Tag Mutability" value={props.imageTagMutability || 'MUTABLE'} onChange={(v) => onChange({ ...props, imageTagMutability: v })} options={[
      { label: 'Mutable (tags can be overwritten)', value: 'MUTABLE' },
      { label: 'Immutable (tags cannot be overwritten)', value: 'IMMUTABLE' },
    ]} />
    <FieldInput label="Scan on Push" value={props.scanOnPush ?? true} onChange={(v) => onChange({ ...props, scanOnPush: v })} type="boolean" />
  </div>;
}

function EcsClusterConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return <div className="space-y-3">
    <FieldInput label="Cluster Name" value={props.name} onChange={(v) => onChange({ ...props, name: v })} placeholder="app-cluster" />
    <FieldInput label="Container Insights" value={props.containerInsights ?? false} onChange={(v) => onChange({ ...props, containerInsights: v })} type="boolean" />
  </div>;
}

function EfsConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return <div className="space-y-3">
    <FieldInput label="Name" value={props.name} onChange={(v) => onChange({ ...props, name: v })} placeholder="shared-files" />
    <FieldInput label="Performance Mode" value={props.performanceMode || 'generalPurpose'} onChange={(v) => onChange({ ...props, performanceMode: v })} options={[
      { label: 'General Purpose', value: 'generalPurpose' }, { label: 'Max I/O', value: 'maxIO' },
    ]} />
    <FieldInput label="Throughput Mode" value={props.throughputMode || 'bursting'} onChange={(v) => onChange({ ...props, throughputMode: v })} options={[
      { label: 'Bursting', value: 'bursting' }, { label: 'Elastic', value: 'elastic' }, { label: 'Provisioned', value: 'provisioned' },
    ]} />
  </div>;
}

function ElasticacheConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return <div className="space-y-3">
    <FieldInput label="Name" value={props.name} onChange={(v) => onChange({ ...props, name: v })} placeholder="app-cache" />
    <FieldInput label="Engine" value={props.engine || 'redis'} onChange={(v) => onChange({ ...props, engine: v })} options={[
      { label: 'Redis', value: 'redis' }, { label: 'Memcached', value: 'memcached' },
    ]} />
    <FieldInput label="Node Type" value={props.nodeType || 'cache.t3.micro'} onChange={(v) => onChange({ ...props, nodeType: v })} options={[
      { label: 'cache.t3.micro', value: 'cache.t3.micro' }, { label: 'cache.t3.small', value: 'cache.t3.small' },
      { label: 'cache.t3.medium', value: 'cache.t3.medium' }, { label: 'cache.m5.large', value: 'cache.m5.large' },
      { label: 'cache.m5.xlarge', value: 'cache.m5.xlarge' }, { label: 'cache.r5.large', value: 'cache.r5.large' },
    ]} />
    <FieldInput label="Number of Nodes" value={props.numCacheNodes ?? 1} onChange={(v) => onChange({ ...props, numCacheNodes: v })} type="number" />
  </div>;
}

function AuroraConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return <div className="space-y-3">
    <FieldInput label="Cluster Identifier" value={props.identifier} onChange={(v) => onChange({ ...props, identifier: v })} placeholder="app-cluster" />
    <FieldInput label="Engine" value={props.engine || 'aurora-mysql'} onChange={(v) => onChange({ ...props, engine: v })} options={[
      { label: 'Aurora MySQL', value: 'aurora-mysql' }, { label: 'Aurora PostgreSQL', value: 'aurora-postgresql' },
    ]} />
    <FieldInput label="Database Name" value={props.dbName} onChange={(v) => onChange({ ...props, dbName: v })} placeholder="appdb" />
    <FieldInput label="Username" value={props.username || 'admin'} onChange={(v) => onChange({ ...props, username: v })} placeholder="admin" />
  </div>;
}

function RedshiftConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return <div className="space-y-3">
    <FieldInput label="Cluster Identifier" value={props.clusterIdentifier} onChange={(v) => onChange({ ...props, clusterIdentifier: v })} placeholder="analytics-cluster" />
    <FieldInput label="Database Name" value={props.dbName} onChange={(v) => onChange({ ...props, dbName: v })} placeholder="analytics" />
    <FieldInput label="Master Username" value={props.username} onChange={(v) => onChange({ ...props, username: v })} placeholder="admin" />
    <FieldInput label="Node Type" value={props.nodeType || 'dc2.large'} onChange={(v) => onChange({ ...props, nodeType: v })} options={[
      { label: 'dc2.large', value: 'dc2.large' }, { label: 'dc2.8xlarge', value: 'dc2.8xlarge' },
      { label: 'ra3.xlplus', value: 'ra3.xlplus' }, { label: 'ra3.4xlargeplus', value: 'ra3.4xlargeplus' },
      { label: 'ra3.16xlargeplus', value: 'ra3.16xlargeplus' },
    ]} />
    <FieldInput label="Number of Nodes" value={props.numberOfNodes ?? 2} onChange={(v) => onChange({ ...props, numberOfNodes: v })} type="number" />
  </div>;
}

function KinesisStreamConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return <div className="space-y-3">
    <FieldInput label="Stream Name" value={props.name} onChange={(v) => onChange({ ...props, name: v })} placeholder="events-stream" />
    <FieldInput label="Shard Count" value={props.shardCount ?? 1} onChange={(v) => onChange({ ...props, shardCount: v })} type="number" placeholder="1" />
    <FieldInput label="Retention (hours)" value={props.retentionHours ?? 24} onChange={(v) => onChange({ ...props, retentionHours: v })} type="number" placeholder="24" />
  </div>;
}

function SqsConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return <div className="space-y-3">
    <FieldInput label="Queue Name" value={props.name} onChange={(v) => onChange({ ...props, name: v })} placeholder="tasks-queue" />
    <FieldInput label="Visibility Timeout (s)" value={props.visibilityTimeout ?? 30} onChange={(v) => onChange({ ...props, visibilityTimeout: v })} type="number" />
    <FieldInput label="Delivery Delay (s)" value={props.delaySeconds ?? 0} onChange={(v) => onChange({ ...props, delaySeconds: v })} type="number" />
    <FieldInput label="Message Retention (s)" value={props.messageRetention ?? 345600} onChange={(v) => onChange({ ...props, messageRetention: v })} type="number" />
    <FieldInput label="Max Message Size (KB)" value={props.maxMessageSize ?? 262144} onChange={(v) => onChange({ ...props, maxMessageSize: v })} type="number" />
  </div>;
}

function SnsConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return <div className="space-y-3">
    <FieldInput label="Topic Name" value={props.name} onChange={(v) => onChange({ ...props, name: v })} placeholder="notifications" />
    <FieldInput label="Display Name" value={props.displayName} onChange={(v) => onChange({ ...props, displayName: v })} placeholder="App Notifications" />
  </div>;
}

function StepFunctionConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return <div className="space-y-3">
    <FieldInput label="State Machine Name" value={props.name} onChange={(v) => onChange({ ...props, name: v })} placeholder="workflow" />
  </div>;
}

function SecretsManagerConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return <div className="space-y-3">
    <FieldInput label="Secret Name" value={props.name} onChange={(v) => onChange({ ...props, name: v })} placeholder="app-secrets" />
    <FieldInput label="Description" value={props.description} onChange={(v) => onChange({ ...props, description: v })} placeholder="Application secrets" />
    <FieldInput label="Recovery Window (days)" value={props.recoveryWindowDays ?? 7} onChange={(v) => onChange({ ...props, recoveryWindowDays: v })} type="number" />
  </div>;
}

function CloudWatchAlarmConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return <div className="space-y-3">
    <FieldInput label="Alarm Name" value={props.name} onChange={(v) => onChange({ ...props, name: v })} placeholder="cpu-alarm" />
    <FieldInput label="Description" value={props.description} onChange={(v) => onChange({ ...props, description: v })} placeholder="Alarm managed by CloudForge" />
    <FieldInput label="Metric" value={props.metric || 'CPUUtilization'} onChange={(v) => onChange({ ...props, metric: v })} options={[
      { label: 'CPUUtilization', value: 'CPUUtilization' }, { label: 'MemoryUtilization', value: 'MemoryUtilization' },
      { label: 'NetworkIn', value: 'NetworkIn' }, { label: 'NetworkOut', value: 'NetworkOut' },
      { label: 'DatabaseConnections', value: 'DatabaseConnections' }, { label: 'Latency', value: 'Latency' },
      { label: 'RequestCount', value: 'RequestCount' },
    ]} />
    <FieldInput label="Namespace" value={props.namespace || 'AWS/EC2'} onChange={(v) => onChange({ ...props, namespace: v })} placeholder="AWS/EC2" />
    <FieldInput label="Threshold" value={props.threshold ?? 80} onChange={(v) => onChange({ ...props, threshold: v })} type="number" placeholder="80" />
    <FieldInput label="Comparison" value={props.comparison || 'GreaterThanThreshold'} onChange={(v) => onChange({ ...props, comparison: v })} options={[
      { label: 'Greater than', value: 'GreaterThanThreshold' }, { label: 'Greater or equal', value: 'GreaterThanOrEqualToThreshold' },
      { label: 'Less than', value: 'LessThanThreshold' }, { label: 'Less or equal', value: 'LessThanOrEqualToThreshold' },
    ]} />
    <FieldInput label="Evaluation Periods" value={props.evaluationPeriods ?? 2} onChange={(v) => onChange({ ...props, evaluationPeriods: v })} type="number" />
    <FieldInput label="Period (s)" value={props.period ?? 60} onChange={(v) => onChange({ ...props, period: v })} type="number" />
    <FieldInput label="Statistic" value={props.statistic || 'Average'} onChange={(v) => onChange({ ...props, statistic: v })} options={[
      { label: 'Average', value: 'Average' }, { label: 'Sum', value: 'Sum' },
      { label: 'Minimum', value: 'Minimum' }, { label: 'Maximum', value: 'Maximum' },
    ]} />
  </div>;
}

function CloudWatchLogGroupConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return <div className="space-y-3">
    <FieldInput label="Log Group Name" value={props.name} onChange={(v) => onChange({ ...props, name: v })} placeholder="app-logs" />
    <FieldInput label="Retention (days)" value={props.retentionDays ?? 30} onChange={(v) => onChange({ ...props, retentionDays: v })} type="number" options={[
      { label: '1 day', value: '1' }, { label: '7 days', value: '7' }, { label: '30 days', value: '30' },
      { label: '90 days', value: '90' }, { label: '1 year', value: '365' }, { label: '10 years', value: '3653' },
    ]} />
  </div>;
}

function KmsKeyConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return <div className="space-y-3">
    <FieldInput label="Key Name" value={props.name} onChange={(v) => onChange({ ...props, name: v })} placeholder="app-key" />
    <FieldInput label="Description" value={props.description} onChange={(v) => onChange({ ...props, description: v })} placeholder="Application encryption key" />
    <FieldInput label="Deletion Window (days)" value={props.deletionWindowDays ?? 7} onChange={(v) => onChange({ ...props, deletionWindowDays: v })} type="number" />
  </div>;
}

const configComponents: Record<ResourceType, React.ComponentType<{ props: Record<string, any>; onChange: (v: any) => void }>> = {
  vpc: VpcConfig,
  subnet: SubnetConfig,
  ec2: Ec2Config,
  s3: S3Config,
  rds: RdsConfig,
  security_group: SgConfig,
  load_balancer: LbConfig,
  internet_gateway: InternetGatewayConfig,
  route_table: RouteTableConfig,
  nat_gateway: NatGatewayConfig,
  lambda: LambdaConfig,
  dynamodb: DynamoDbConfig,
  iam_role: IamRoleConfig,
  cloudfront: CloudFrontConfig,
  api_gateway: ApiGatewayConfig,
  route53_zone: Route53ZoneConfig,
  route53_record: Route53RecordConfig,
  elastic_ip: ElasticIpConfig,
  ebs_volume: EbsVolumeConfig,
  ecr_repository: EcrRepositoryConfig,
  ecs_cluster: EcsClusterConfig,
  efs: EfsConfig,
  elasticache: ElasticacheConfig,
  aurora: AuroraConfig,
  redshift: RedshiftConfig,
  kinesis_stream: KinesisStreamConfig,
  sqs: SqsConfig,
  sns: SnsConfig,
  step_function: StepFunctionConfig,
  secretsmanager: SecretsManagerConfig,
  cloudwatch_alarm: CloudWatchAlarmConfig,
  cloudwatch_log_group: CloudWatchLogGroupConfig,
  kms_key: KmsKeyConfig,
};

export function ConfigPanel({ node, onClose, onChange }: ConfigPanelProps) {
  if (!node) return null;

  const resourceType = node.data.resourceType as ResourceType;
  const properties = (node.data.properties as Record<string, any>) || {};
  const ConfigComponent = configComponents[resourceType];

  return (
    <div className="w-64 bg-dark-900 border-l border-dark-800 flex flex-col flex-shrink-0 overflow-y-auto">
      <div className="flex items-center justify-between px-4 py-3 border-b border-dark-800">
        <div className="flex items-center gap-2">
          <Settings className="w-3.5 h-3.5 text-primary-400" />
          <span className="text-xs font-semibold text-dark-200 uppercase tracking-wide">
            Configure
          </span>
        </div>
        <button
          onClick={onClose}
          className="text-dark-500 hover:text-dark-200 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="px-4 py-3 border-b border-dark-800">
        <div className="text-sm font-medium text-white">{node.data.label as string}</div>
        <div className="text-xs text-dark-500 mt-0.5">{resourceType.replace('_', ' ').toUpperCase()}</div>
        <div className="text-[10px] text-dark-600 mt-1 font-mono">ID: {node.id}</div>
      </div>

      <div className="flex-1 px-4 py-4">
        {ConfigComponent ? (
          <ConfigComponent
            props={properties}
            onChange={(newProps) => onChange(node.id, newProps)}
          />
        ) : (
          <p className="text-dark-500 text-sm">No configuration available.</p>
        )}
      </div>
    </div>
  );
}
