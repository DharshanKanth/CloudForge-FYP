export interface User {
  id: string;
  email: string;
  username: string;
  created_at: string;
}

export interface Project {
  id: string;
  user_id: string;
  name: string;
  description?: string;
  provider: 'aws' | 'azure' | 'gcp';
  status: string;
  created_at: string;
  updated_at: string;
  resource_count: number;
}

export interface NodeProperties {
  // VPC
  name?: string;
  cidr?: string;
  environment?: string;

  // Subnet
  availabilityZone?: string;
  mapPublicIp?: boolean;

  // EC2
  instanceType?: string;
  amiId?: string;
  associatePublicIp?: boolean;

  // S3
  bucketName?: string;
  versioning?: boolean;

  // RDS
  identifier?: string;
  engine?: string;
  engineVersion?: string;
  instanceClass?: string;
  storage?: number;
  dbName?: string;
  username?: string;
  multiAz?: boolean;

  // Security Group
  description?: string;

  // Load Balancer
  lbType?: string;
  internal?: boolean;

  // Generic
  [key: string]: any;
}

export interface ResourceNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: {
    label: string;
    resourceType: string;
    provider: string;
    properties: NodeProperties;
  };
}

export interface ResourceEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string | null;
  targetHandle?: string | null;
  type?: string;
}

export interface Architecture {
  id: string;
  project_id: string;
  nodes: ResourceNode[];
  edges: ResourceEdge[];
  version: number;
  updated_at: string;
}

export interface ValidationIssue {
  level: 'error' | 'warning' | 'info';
  resource_id?: string;
  resource_type?: string;
  message: string;
  field?: string;
}

export interface ValidationResult {
  valid: boolean;
  issues: ValidationIssue[];
}

export interface TerraformFile {
  filename: string;
  content: string;
}

export interface TerraformResponse {
  project_id: string;
  provider: string;
  files: TerraformFile[];
  validation?: {
    valid: boolean;
    issues: ValidationIssue[];
  };
}

export type ResourceType =
  | 'vpc'
  | 'subnet'
  | 'ec2'
  | 's3'
  | 'rds'
  | 'security_group'
  | 'load_balancer';
