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
        value={value || ''}
        onChange={(e) => onChange(type === 'number' ? Number(e.target.value) : e.target.value)}
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
          { label: 't2.micro (Free tier)', value: 't2.micro' },
          { label: 't2.small', value: 't2.small' },
          { label: 't2.medium', value: 't2.medium' },
          { label: 't2.large', value: 't2.large' },
          { label: 't3.micro', value: 't3.micro' },
          { label: 't3.small', value: 't3.small' },
          { label: 't3.medium', value: 't3.medium' },
          { label: 'm5.large', value: 'm5.large' },
          { label: 'c5.large', value: 'c5.large' },
        ]}
      />
      <FieldInput label="AMI ID" value={props.amiId} onChange={(v) => onChange({ ...props, amiId: v })} placeholder="ami-0c55b159cbfafe1f0" />
      <FieldInput label="Associate Public IP" value={props.associatePublicIp ?? true} onChange={(v) => onChange({ ...props, associatePublicIp: v })} type="boolean" />
    </div>
  );
}

function S3Config({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return (
    <div className="space-y-3">
      <FieldInput label="Bucket Name" value={props.bucketName} onChange={(v) => onChange({ ...props, bucketName: v })} placeholder="my-app-storage" />
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
    </div>
  );
}

function SgConfig({ props, onChange }: { props: Record<string, any>; onChange: (v: any) => void }) {
  return (
    <div className="space-y-3">
      <FieldInput label="Name" value={props.name} onChange={(v) => onChange({ ...props, name: v })} placeholder="web-sg" />
      <FieldInput label="Description" value={props.description} onChange={(v) => onChange({ ...props, description: v })} placeholder="Security group for web servers" />
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

const configComponents: Record<ResourceType, React.ComponentType<{ props: Record<string, any>; onChange: (v: any) => void }>> = {
  vpc: VpcConfig,
  subnet: SubnetConfig,
  ec2: Ec2Config,
  s3: S3Config,
  rds: RdsConfig,
  security_group: SgConfig,
  load_balancer: LbConfig,
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
