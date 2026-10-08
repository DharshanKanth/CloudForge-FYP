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
  parentId?: string;
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
  aws_region?: string;
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
  | 'load_balancer'
  | 'internet_gateway'
  | 'route_table'
  | 'nat_gateway'
  | 'lambda'
  | 'dynamodb'
  | 'iam_role'
  | 'cloudfront'
  | 'api_gateway'
  | 'route53_zone'
  | 'route53_record'
  | 'elastic_ip'
  | 'ebs_volume'
  | 'ecr_repository'
  | 'ecs_cluster'
  | 'efs'
  | 'elasticache'
  | 'aurora'
  | 'redshift'
  | 'kinesis_stream'
  | 'sqs'
  | 'sns'
  | 'step_function'
  | 'secretsmanager'
  | 'cloudwatch_alarm'
  | 'cloudwatch_log_group'
  | 'kms_key';

// ── Live infrastructure (read from Terraform state after a successful apply) ─
export interface InfraResource {
  address: string;
  type: string;
  name: string;
  label: string;
  id: string;
  category: 'compute' | 'network' | 'data';
  attributes: Record<string, any>;
  /** Whether an in-place start/stop is supported (e.g. EC2). */
  controllable?: boolean;
}

export interface Infrastructure {
  status: 'deployed' | 'not_deployed';
  resources: InfraResource[];
  outputs: Record<string, any>;
  region: string;
  state_updated_at: number | null;
  destroy_plan_ready?: boolean;
}

// Dashboard bulk summary (GET /api/infrastructure)
export interface InfraStackSummary extends Infrastructure {
  project_id: string;
  name?: string;
  provider?: string;
  resource_count: number;
  categories: Record<string, number>;
  recent_events?: DeploymentEvent[];
}

// Deployment history (audit log) — one entry per plan/apply/destroy action
export interface DeploymentEvent {
  id: string;
  project_id: string;
  event_type: 'plan' | 'apply' | 'plan_destroy' | 'destroy' | 'clear';
  status: 'succeeded' | 'failed' | 'blocked';
  detail?: string;
  resource_count?: number | null;
  created_at: string | null;
}

// Connected cloud account (metadata only — credentials are never returned)
export interface CloudAccount {
  id: string;
  provider: string;
  name: string;
  region: string;
  created_at: string;
}
