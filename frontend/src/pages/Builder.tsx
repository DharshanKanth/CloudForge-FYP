import { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ReactFlow,
  ConnectionMode,
  Background,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  type Connection,
  type ReactFlowInstance,
  BackgroundVariant,
  MarkerType,
  type Node,
  type Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from 'dagre';

import {
  CheckSquare,
  Code2,
  Trash2,
  RotateCcw,
  Cloud,
  Loader2,
  ArrowLeft,
  LayoutTemplate,
  Sparkles,
} from 'lucide-react';

import { ResourceNodeComponent } from '../features/builder/ResourceNode';
import { GroupNodeComponent, CONTAINER_TYPES } from '../features/builder/GroupNode';
import { BuilderSidebar, type SidebarItem } from '../features/builder/BuilderSidebar';
import {
  CONTAINMENT_CHILDREN,
  nestNode,
  detachNode,
  nestFromEdges,
  containmentPair,
  findContainerFor,
  type CloudNode,
} from '../features/builder/nesting';
import { BuilderToolbar } from '../features/builder/BuilderToolbar';
import { Breadcrumb } from '../features/builder/Breadcrumb';
import { ConfigPanel } from '../features/builder/ConfigPanel';
import { ValidationPanel } from '../features/builder/ValidationPanel';
import { TemplateModal } from '../features/builder/TemplateModal';
import { AiArchitectModal } from '../features/builder/AiArchitectModal';
import { InsightsModal } from '../features/builder/InsightsModal';
import { architectureApi, projectsApi, aiApi } from '../services/api';
import type { ValidationResult, Project } from '../types';
import toast from 'react-hot-toast';

/* ── Node types ─────────────────────────────────────────────────────── */

const nodeTypes = {
  resourceNode: ResourceNodeComponent,
  groupNode: GroupNodeComponent,
};

const defaultEdgeOptions = {
  style: { stroke: '#3b82f6', strokeWidth: 2 },
  markerEnd: { type: MarkerType.ArrowClosed, color: '#3b82f6' },
};

let nodeCounter = 0;

/** Walk up the parent chain to build the focus breadcrumb path. */
function buildFocusPath(
  nodes: CloudNode[],
  focusedId: string | null
): CloudNode[] {
  if (!focusedId) return [];
  const nodeMap = new Map(nodes.map((n) => [n.id, n]));
  const path: CloudNode[] = [];
  let current = nodeMap.get(focusedId);
  while (current && CONTAINER_TYPES.has(current.data.resourceType)) {
    path.unshift(current);
    current = current.parentId ? nodeMap.get(current.parentId) : undefined;
  }
  return path;
}

/** Compute visible nodes: hide descendants of collapsed groups. */
function computeVisibleNodeIds(nodes: CloudNode[]): Set<string> {
  const visible = new Set<string>();
  const nodeMap = new Map(nodes.map((n) => [n.id, n]));

  for (const node of nodes) {
    let hide = false;
    let current: CloudNode | undefined = node;
    while (current?.parentId) {
      const parent = nodeMap.get(current.parentId);
      if (parent?.data?.collapsed) {
        hide = true;
        break;
      }
      current = parent;
    }
    if (!hide) visible.add(node.id);
  }
  return visible;
}

/** Count descendant non-container resources inside a group. */
function countDescendants(nodes: CloudNode[], groupId: string): number {
  const children = nodes.filter((n) => n.parentId === groupId);
  let count = 0;
  for (const child of children) {
    if (CONTAINER_TYPES.has(child.data.resourceType)) {
      count += countDescendants(nodes, child.id);
    } else {
      count++;
    }
  }
  return count;
}

/** Auto-layout using dagre, respecting parent-child containment. */
function applyAutoLayout(nodes: CloudNode[], edges: Edge[]): CloudNode[] {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: 'TB', nodesep: 60, ranksep: 70, marginx: 30, marginy: 30 });

  const containers = nodes.filter((n) => CONTAINER_TYPES.has(n.data.resourceType));
  const leaves = nodes.filter((n) => !CONTAINER_TYPES.has(n.data.resourceType));

  for (const c of containers) g.setNode(c.id, { width: 360, height: 220 });
  for (const l of leaves) g.setNode(l.id, { width: 200, height: 80 });

  const nodeMap = new Map(nodes.map((n) => [n.id, n]));
  for (const e of edges) {
    if (!e.source || !e.target) continue;
    const src = nodeMap.get(e.source);
    const tgt = nodeMap.get(e.target);
    // Skip containment edges (parent<->child)
    if (src?.parentId === e.target || tgt?.parentId === e.source) continue;
    g.setEdge(e.source, e.target);
  }

  dagre.layout(g);

  return nodes.map((node) => {
    const pos = g.node(node.id);
    if (!pos) return node;

    if (node.parentId) {
      const parent = nodeMap.get(node.parentId);
      if (parent) {
        const parentPos = g.node(parent.id);
        if (parentPos) {
          return {
            ...node,
            position: { x: pos.x - parentPos.x, y: pos.y - parentPos.y },
          };
        }
      }
    }
    return { ...node, position: { x: pos.x - 100, y: pos.y - 40 } };
  });
}

function isPositionInsideNode(
  point: { x: number; y: number },
  node: CloudNode
): boolean {
  const w = CONTAINER_TYPES.has(node.data.resourceType) ? 360 : 190;
  const h = node.data.resourceType === 'subnet' || node.data.resourceType === 'vpc' ? 220 : 80;
  return (
    point.x >= node.position.x &&
    point.x <= node.position.x + w &&
    point.y >= node.position.y &&
    point.y <= node.position.y + h
  );
}

/* ── MiniMap colors ─────────────────────────────────────────────────── */

const RESOURCE_COLORS: Record<string, string> = {
  vpc: '#3b82f6', subnet: '#06b6d4', ec2: '#f97316',
  s3: '#22c55e', rds: '#a855f7', security_group: '#ef4444',
  load_balancer: '#eab308', internet_gateway: '#0ea5e9',
  route_table: '#6366f1', nat_gateway: '#f59e0b', lambda: '#f43f5e',
  dynamodb: '#14b8a6', iam_role: '#84cc16', cloudfront: '#8b5cf6',
  api_gateway: '#d946ef', route53_zone: '#10b981', route53_record: '#34d399',
  elastic_ip: '#a8a29e', ebs_volume: '#d6d3d1', ecr_repository: '#60a5fa',
  ecs_cluster: '#22d3ee', efs: '#4ade80', elasticache: '#f87171',
  aurora: '#818cf8', redshift: '#ec4899', kinesis_stream: '#38bdf8',
  sqs: '#fb923c', sns: '#fbbf24', step_function: '#c084fc',
  secretsmanager: '#fca5a5', cloudwatch_alarm: '#facc15',
  cloudwatch_log_group: '#94a3b8', kms_key: '#2dd4bf',
};

export default function Builder() {
  const { id: projectId } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [project, setProject] = useState<Project | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState<CloudNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedNode, setSelectedNode] = useState<CloudNode | null>(null);
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
  const [rfInstance, setRfInstance] = useState<ReactFlowInstance<CloudNode, Edge> | null>(null);

  const [loadingProject, setLoadingProject] = useState(true);
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [fixing, setFixing] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);
  const [showAi, setShowAi] = useState(false);
  const [showInsights, setShowInsights] = useState(false);
  const [focusedNodeId, setFocusedNodeId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [highlightedNodeId, setHighlightedNodeId] = useState<string | null>(null);
  const [selectedRegion, setSelectedRegion] = useState("us-east-1");
  const [costTotal, setCostTotal] = useState<number | null>(null);
  const [securityHigh, setSecurityHigh] = useState<number | null>(null);

  const AWS_REGIONS = [
    { label: "US East (N. Virginia)", value: "us-east-1" },
    { label: "US East (Ohio)", value: "us-east-2" },
    { label: "Asia Pacific (Tokyo)", value: "ap-northeast-1" },
    { label: "Europe (Ireland)", value: "eu-west-1" },
    { label: "US West (Oregon)", value: "us-west-2" },
  ]

  const reactFlowWrapper = useRef<HTMLDivElement>(null);

  // ── Load project ────────────────────────────────────────────────────

  // Cost + security insights are computed from the saved architecture, so
  // refresh them after loading and after each successful save/validate.
  const refreshInsights = useCallback(async (pid: string) => {
    try {
      const [costRes, secRes] = await Promise.all([
        architectureApi.cost(pid),
        architectureApi.security(pid),
      ]);
      setCostTotal(costRes.data.monthly_total ?? null);
      setSecurityHigh(secRes.data.counts?.high ?? 0);
    } catch {
      // No saved architecture yet — leave the figures unset.
    }
  }, []);

  useEffect(() => {
    if (!projectId) return;
    const load = async () => {
      try {
        const [projRes, archRes] = await Promise.all([
          projectsApi.get(projectId),
          architectureApi.get(projectId),
        ]);
        setProject(projRes.data);
        if (archRes.data.nodes && archRes.data.nodes.length > 0) {
          const loadedNodes = (archRes.data.nodes as CloudNode[]).map((n) => ({
            ...n,
            type: CONTAINER_TYPES.has(n.data?.resourceType)
              ? 'groupNode'
              : 'resourceNode',
            data: { ...n.data, collapsed: false },
          }));
          const loadedEdges = archRes.data.edges || [];
          setNodes(nestFromEdges(loadedNodes, loadedEdges));
          setEdges(loadedEdges);
          if (archRes.data.aws_region) setSelectedRegion(archRes.data.aws_region);
        } else {
          setShowTemplates(true);
        }
        void refreshInsights(projectId);
      } catch (err: any) {
        if (err.response?.status !== 404) {
          toast.error('Failed to load architecture');
        }
        try {
          const projRes = await projectsApi.get(projectId!);
          setProject(projRes.data);
          setShowTemplates(true);
        } catch {
          toast.error('Project not found');
          navigate('/dashboard');
        }
      } finally {
        setLoadingProject(false);
      }
    };
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  // Keep each resource's Availability Zone in the selected region. Switching
  // region must not leave nodes pinned to a stale zone (e.g. an EBS volume
  // still in us-east-1a while deploying to eu-west-1, which cannot attach).
  useEffect(() => {
    setNodes((nds) => {
      let changed = false;
      const next = nds.map((n) => {
        const az = n.data?.properties?.availabilityZone;
        if (typeof az !== 'string' || az.length < 2) return n;
        const remapped = `${selectedRegion}${az.slice(-1)}`;
        if (az === remapped) return n;
        changed = true;
        return {
          ...n,
          data: { ...n.data, properties: { ...n.data.properties, availabilityZone: remapped } },
        } as CloudNode;
      });
      return changed ? next : nds;
    });
  }, [selectedRegion, setNodes]);

  // Keep the currently-selected node's snapshot in sync with the remap above,
  // otherwise editing any other property would write the stale AZ back.
  useEffect(() => {
    setSelectedNode((prev) => {
      if (!prev) return prev;
      const az = prev.data?.properties?.availabilityZone;
      if (typeof az !== 'string' || az.length < 2) return prev;
      const remapped = `${selectedRegion}${az.slice(-1)}`;
      if (az === remapped) return prev;
      return {
        ...prev,
        data: { ...prev.data, properties: { ...prev.data.properties, availabilityZone: remapped } },
      } as CloudNode;
    });
  }, [selectedRegion]);

  // ── Listen for collapse toggle events from GroupNode ────────────────

  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail?.nodeId) toggleCollapse(detail.nodeId);
    };
    window.addEventListener('group:toggle', handler);
    return () => window.removeEventListener('group:toggle', handler);
  });

  // ── Collapse / expand logic ─────────────────────────────────────────

  const toggleCollapse = useCallback(
    (nodeId: string) => {
      setNodes((nds) =>
        nds.map((n) => {
          if (n.id !== nodeId) return n;
          const newCollapsed = !n.data.collapsed;
          return {
            ...n,
            data: {
              ...n.data,
              collapsed: newCollapsed,
              childCount: newCollapsed ? countDescendants(nds, n.id) : 0,
            },
          } as CloudNode;
        })
      );
    },
    [setNodes]
  );

  const expandAll = useCallback(() => {
    setNodes(
      (nds) =>
        nds.map((n) => ({
          ...n,
          data: { ...n.data, collapsed: false },
        })) as CloudNode[]
    );
  }, [setNodes]);

  const collapseAll = useCallback(() => {
    setNodes(
      (nds) =>
        nds.map((n) => {
          if (!CONTAINER_TYPES.has(n.data.resourceType)) return n;
          return {
            ...n,
            data: {
              ...n.data,
              collapsed: true,
              childCount: countDescendants(nds, n.id),
            },
          } as CloudNode;
        })
    );
  }, [setNodes]);

  // ── Visible nodes (respect collapsed state) ─────────────────────────

  const visibleNodeIds = useMemo(() => computeVisibleNodeIds(nodes), [nodes]);
  const visibleNodes = useMemo(
    () => nodes.filter((n) => visibleNodeIds.has(n.id)),
    [nodes, visibleNodeIds]
  );

  // ── Search + focus ──────────────────────────────────────────────────

  const handleSearch = useCallback(
    (query: string) => {
      setSearchQuery(query);
      if (!query.trim()) {
        setHighlightedNodeId(null);
        return;
      }
      const q = query.toLowerCase();
      const match = nodes.find((n) => {
        const props = (n.data.properties as Record<string, any>) || {};
        const name =
          props.name || props.bucketName || props.identifier || props.functionName || '';
        const type = (n.data.resourceType || '').toLowerCase();
        return (
          String(name).toLowerCase().includes(q) ||
          type.includes(q) ||
          n.id.toLowerCase().includes(q)
        );
      });

      if (match) {
        // Auto-expand collapsed ancestors so the node is visible
        setNodes((nds) => {
          const nodeMap = new Map(nds.map((n) => [n.id, n]));
          const toExpand: string[] = [];
          let current = nds.find((n) => n.id === match.id);
          while (current?.parentId) {
            const parent = nodeMap.get(current.parentId);
            if (parent?.data.collapsed) toExpand.push(parent.id);
            current = parent;
          }
          if (toExpand.length === 0) return nds;
          return nds.map((n) =>
            toExpand.includes(n.id)
              ? ({ ...n, data: { ...n.data, collapsed: false } } as CloudNode)
              : n
          );
        });
        // Clear any prior focus so we see the whole canvas, then fit to node
        setFocusedNodeId(null);
        setHighlightedNodeId(match.id);
        setTimeout(() => {
          rfInstance?.fitView({
            nodes: [{ id: match.id }],
            padding: 0.4,
            duration: 300,
          });
        }, 80);
      } else {
        setHighlightedNodeId(null);
        toast(`No resource matching "${query}"`, { icon: '🔍' });
      }
    },
    [nodes, rfInstance, setNodes]
  );

  const handleClearSearch = useCallback(() => {
    setSearchQuery('');
    setHighlightedNodeId(null);
  }, []);

  // ── Focus / drill-down ──────────────────────────────────────────────

  const focusPath = useMemo(
    () => buildFocusPath(nodes, focusedNodeId),
    [nodes, focusedNodeId]
  );

  const handleBreadcrumbNavigate = useCallback(
    (nodeId: string | null) => {
      setFocusedNodeId(nodeId);
      setTimeout(() => {
        if (nodeId) {
          rfInstance?.fitView({
            nodes: [{ id: nodeId }],
            padding: 0.35,
            duration: 300,
          });
        } else {
          rfInstance?.fitView({ padding: 0.2, duration: 300 });
        }
      }, 80);
    },
    [rfInstance]
  );

  const handleNodeDoubleClick = useCallback(
    (_: React.MouseEvent, node: CloudNode) => {
      if (CONTAINER_TYPES.has(node.data.resourceType)) {
        handleBreadcrumbNavigate(node.id);
      }
    },
    [handleBreadcrumbNavigate]
  );

  // ── Auto layout ─────────────────────────────────────────────────────

  const handleAutoLayout = useCallback(() => {
    setNodes((nds) => applyAutoLayout(nds, edges));
    setTimeout(() => rfInstance?.fitView({ padding: 0.2, duration: 400 }), 120);
    toast.success('Layout applied');
  }, [edges, rfInstance, setNodes]);

  // ── Templates ───────────────────────────────────────────────────────

  const handleTemplateSelect = useCallback(
    (templateNodes: Node[], templateEdges: Edge[]) => {
      const newNodes = (templateNodes as CloudNode[]).map((n) => ({
        ...n,
        type: CONTAINER_TYPES.has(n.data?.resourceType)
          ? 'groupNode'
          : 'resourceNode',
        data: { ...n.data, collapsed: false },
      }));
      setNodes(newNodes);
      setEdges(templateEdges);
      setSelectedNode(null);
      setValidationResult(null);
      setHighlightedNodeId(null);
      setTimeout(() => {
        rfInstance?.fitView({ padding: 0.2, duration: 400 });
      }, 80);
      toast.success('Template applied');
    },
    [rfInstance, setNodes, setEdges]
  );

  // ── Connections ─────────────────────────────────────────────────────

  const onConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target || connection.source === connection.target) {
        toast.error('Choose two different resources to connect.');
        return;
      }

      setEdges((eds) => {
        const alreadyConnected = eds.some(
          (edge) =>
            (edge.source === connection.source && edge.target === connection.target) ||
            (edge.source === connection.target && edge.target === connection.source)
        );
        if (alreadyConnected) {
          toast.error('Those resources are already connected.');
          return eds;
        }

        toast.success('Resources connected');
        return addEdge(
          {
            ...connection,
            style: { stroke: '#3b82f6', strokeWidth: 2 },
            markerEnd: { type: MarkerType.ArrowClosed, color: '#3b82f6' },
          },
          eds
        );
      });

      // Nest related resources inside their container so collapsing the big
      // node hides them: subnet -> VPC, compute/data resources -> Subnet.
      setNodes((nds) => {
        const source = nds.find((n) => n.id === connection.source);
        const target = nds.find((n) => n.id === connection.target);
        if (!source || !target) return nds;
        const sourceType = source.data.resourceType;
        const targetType = target.data.resourceType;
        if (CONTAINMENT_CHILDREN[targetType]?.has(sourceType)) {
          return nestNode(nds, source.id, target.id);
        }
        if (CONTAINMENT_CHILDREN[sourceType]?.has(targetType)) {
          return nestNode(nds, target.id, source.id);
        }
        return nds;
      });
    },
    [setEdges, setNodes]
  );

  // ── Drag & drop (with drop-into-container) ──────────────────────────

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      if (!rfInstance) return;

      const itemJson = event.dataTransfer.getData('application/cloudforge-node');
      if (!itemJson) return;

      const item: SidebarItem = JSON.parse(itemJson);

      const position = rfInstance.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      nodeCounter++;
      const id = `${item.type}-${Date.now()}-${nodeCounter}`;

      // Determine if the drop landed inside a container (group) node.
      let parentId: string | undefined;
      let childPosition = position;

      setNodes((nds) => {
        const containers = nds.filter((n) => CONTAINER_TYPES.has(n.data.resourceType));
        // Pick the innermost container under the drop point (nested last).
        const isInside = containers
          .filter((c) => isPositionInsideNode(position, c))
          .sort((a, b) => (b.parentId ? 1 : 0) - (a.parentId ? 1 : 0));

        if (isInside.length > 0) {
          const target = isInside[0];
          parentId = target.id;
          // Position relative to parent for React Flow containment.
          childPosition = {
            x: position.x - target.position.x,
            y: position.y - target.position.y,
          };
        }

        const newNode: CloudNode = {
          id,
          ...(parentId ? { parentId } : {}),
          // Container types (VPC/Subnet) must render as group nodes immediately;
          // otherwise a freshly dropped VPC is a plain resource node until the
          // page reloads and re-types it, giving two different behaviours.
          type: CONTAINER_TYPES.has(item.type) ? 'groupNode' : 'resourceNode',
          position: childPosition,
          data: {
            label: item.label,
            resourceType: item.type,
            provider: 'aws',
            properties: { ...item.defaultProperties },
          },
        };

        return [...nds, newNode];
      });
    },
    [rfInstance, setNodes]
  );

  const handleDragStart = (event: React.DragEvent, item: SidebarItem) => {
    event.dataTransfer.setData('application/cloudforge-node', JSON.stringify(item));
    event.dataTransfer.effectAllowed = 'move';
  };

  // ── Selection / deletion ────────────────────────────────────────────

  const handleNodeClick = useCallback((_: React.MouseEvent, node: CloudNode) => {
    // Clicking a big node (VPC/Subnet) also expands it so the resources nested
    // inside become visible; collapse stays on the header chevron.
    const isContainer = CONTAINER_TYPES.has(node.data.resourceType);
    const shouldExpand = isContainer && !!node.data.collapsed;
    if (shouldExpand) {
      const expanded = {
        ...node,
        data: { ...node.data, collapsed: false, childCount: 0 },
      } as CloudNode;
      setSelectedNode(expanded);
      setNodes((nds) =>
        nds.map((n) =>
          n.id === node.id
            ? ({ ...n, data: { ...n.data, collapsed: false, childCount: 0 } } as CloudNode)
            : n
        )
      );
    } else {
      setSelectedNode(node);
    }
  }, [setNodes]);

  const handlePaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  const handleNodesDelete = useCallback(
    (deleted: CloudNode[]) => {
      setSelectedNode((prev) =>
        prev && deleted.some((n) => n.id === prev.id) ? null : prev
      );
      const deletedIds = new Set(deleted.map((d) => d.id));

      // Deleting a container must not strand its children: float any surviving
      // descendant up to the top level, keeping its on-canvas position.
      setNodes((nds) => {
        let result = nds;
        for (const gone of deleted) {
          if (!CONTAINER_TYPES.has(gone.data.resourceType)) continue;
          for (const child of nds) {
            if (child.parentId === gone.id && !deletedIds.has(child.id)) {
              result = detachNode(result, child.id);
            }
          }
        }
        return result;
      });

      setEdges((eds) =>
        eds.filter(
          (e) => !deletedIds.has(e.source) && !deletedIds.has(e.target)
        )
      );
    },
    [setEdges, setNodes]
  );

  // Dragging a node into a container nests it; dragging it out detaches it and
  // marks it so edge-based re-nesting on the next load leaves it alone.
  const handleNodeDragStop = useCallback(
    (_: MouseEvent | TouchEvent, dragged: CloudNode) => {
      const merged = nodes.map((n) =>
        n.id === dragged.id ? { ...n, position: dragged.position } : n
      );
      const current = merged.find((n) => n.id === dragged.id);
      if (!current) return;
      const target = findContainerFor(current, merged);
      const currentParent = current.parentId ?? null;
      if (target === currentParent) return;

      setNodes((nds) => {
        if (target) return nestNode(nds, current.id, target);
        const detached = detachNode(nds, current.id);
        return detached.map((n) =>
          n.id === current.id
            ? ({ ...n, data: { ...n.data, detached: true } } as CloudNode)
            : n
        );
      });
    },
    [nodes, setNodes]
  );

  // Deleting a containment edge pulls its child back out of the big node
  // (unless another remaining edge still implies the same nesting).
  const handleEdgesDelete = useCallback(
    (deleted: Edge[]) => {
      if (deleted.length === 0) return;
      const deletedKeys = new Set(deleted.map((e) => `${e.source}->${e.target}`));
      const remaining = edges.filter((e) => !deletedKeys.has(`${e.source}->${e.target}`));
      setNodes((nds) => {
        let result = nds;
        for (const edge of deleted) {
          const pair = containmentPair(result, edge);
          if (!pair) continue;
          const stillNested = remaining.some(
            (e) =>
              (e.source === pair.childId && e.target === pair.parentId) ||
              (e.source === pair.parentId && e.target === pair.childId)
          );
          if (!stillNested) result = detachNode(result, pair.childId);
        }
        return result;
      });
    },
    [edges, setNodes]
  );

  const handlePropertyChange = useCallback(
    (nodeId: string, newProperties: Record<string, any>) => {
      setNodes((nds) =>
        nds.map((n) =>
          n.id === nodeId
            ? ({ ...n, data: { ...n.data, properties: newProperties } } as CloudNode)
            : n
        )
      );
      setSelectedNode((prev) =>
        prev?.id === nodeId
          ? ({ ...prev, data: { ...prev.data, properties: newProperties } } as CloudNode)
          : prev
      );
    },
    [setNodes]
  );

  // ── Actions ─────────────────────────────────────────────────────────

  const handleSave = async () => {
    if (!projectId) return;
    setSaving(true);
    try {
      await architectureApi.save(projectId, { nodes, edges, aws_region: selectedRegion });
      toast.success('Architecture saved successfully!');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save architecture');
    } finally {
      setSaving(false);
    }
  };

  const handleValidate = async () => {
    if (!projectId) return;
    setValidating(true);
    try {
      await architectureApi.save(projectId, { nodes, edges, aws_region: selectedRegion });
      const res = await architectureApi.validate(projectId);
      setValidationResult(res.data);
      void refreshInsights(projectId);
      if (res.data.valid) {
        toast.success('Validation passed!');
      } else {
        const errCount = res.data.issues.filter((i: any) => i.level === 'error').length;
        toast.error(`Validation: ${errCount} error(s) found`);
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Validation failed');
    } finally {
      setValidating(false);
    }
  };

  // Advisory: ask the AI to repair the current design's validation problems.
  // The corrected design is re-validated by the backend and applied only on
  // the user's click; nothing is deployed.
  const handleFixWithAi = async () => {
    if (!projectId) return;
    setFixing(true);
    try {
      const res = await aiApi.fix(projectId);
      if (res.data.source === 'none') {
        toast(res.data.message || 'No automatic fix found', { icon: '🤖' });
        return;
      }
      if (!res.data.nodes || res.data.nodes.length === 0) {
        toast(res.data.message || 'No fix returned', { icon: '🤖' });
        return;
      }
      const bErr = (res.data.before?.issues || []).filter((i: any) => i.level === 'error').length;
      const aErr = (res.data.after?.issues || []).filter((i: any) => i.level === 'error').length;
      if (aErr > bErr) {
        // Never make it worse: offer nothing rather than apply a regression.
        toast.error(`Fix would not help (errors ${bErr} → ${aErr})`);
        return;
      }
      handleTemplateSelect(res.data.nodes, res.data.edges);
      if (res.data.after) setValidationResult(res.data.after);
      const who = res.data.source === 'ai' ? 'AI' : 'validation engine';
      if (aErr < bErr) toast.success(`${who} fix applied — errors ${bErr} → ${aErr}`);
      else toast(`${who} fix applied (errors ${bErr} → ${aErr})`, { icon: '🛠' });
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'AI fix failed');
    } finally {
      setFixing(false);
    }
  };

  const handleGenerateTerraform = async () => {
    if (!projectId) return;
    setSaving(true);
    try {
      await architectureApi.save(projectId, { nodes, edges, aws_region: selectedRegion });
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save architecture');
      return;
    } finally {
      setSaving(false);
    }
    navigate(`/projects/${projectId}/terraform`);
  };

  const handleClearCanvas = () => {
    if (!confirm('Clear all resources from the canvas?')) return;
    setNodes([]);
    setEdges([]);
    setSelectedNode(null);
    setValidationResult(null);
    setShowTemplates(true);
  };

  const handleDeleteSelected = () => {
    if (selectedNode) {
      setNodes((nds) => nds.filter((n) => n.id !== selectedNode.id));
      setEdges((eds) =>
        eds.filter(
          (e) => e.source !== selectedNode.id && e.target !== selectedNode.id
        )
      );
      setSelectedNode(null);
    }
  };

  if (loadingProject) {
    return (
      <div className="h-screen flex items-center justify-center bg-dark-950">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-8 h-8 text-primary-400 animate-spin" />
          <p className="text-dark-400 text-sm">Loading project...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-dark-950 overflow-hidden">
      {/* Top header bar */}
      <header className="flex items-center gap-3 px-4 py-2.5 bg-dark-900 border-b border-dark-800 flex-shrink-0">
        <button
          onClick={() => navigate('/dashboard')}
          className="btn-ghost p-2 -ml-1"
          title="Back to Dashboard"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>

        <div className="flex items-center gap-2 mr-4">
          <div className="w-6 h-6 bg-gradient-to-br from-primary-500 to-accent-600 rounded-md flex items-center justify-center">
            <Cloud className="w-3 h-3 text-white" />
          </div>
          <div>
            <div className="text-sm font-semibold text-white leading-none">
              {project?.name || 'Builder'}
            </div>
            <select
              value={selectedRegion}
              onChange={(e) => setSelectedRegion(e.target.value)}
              className="bg-dark-800 border border-dark-700 rounded-lg px-2 py-1 text-xs text-dark-200 focus:outline-none focus:border-primary-500 mt-1"
              title="AWS Region"
            >
              {AWS_REGIONS.map((r) => (
                <option key={r.value} value={r.value} style={{ background: '#1f2937' }}>
                  {r.label}
                </option>
              ))}
            </select>
            <div className="text-[10px] text-dark-500 capitalize">
              {project?.provider} · Visual Builder
            </div>
          </div>
        </div>

        <div className="flex-1" />

        <div className="flex items-center gap-2">
          {selectedNode && (
            <button
              onClick={handleDeleteSelected}
              className="btn-danger text-xs"
              title="Delete selected"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Delete
            </button>
          )}
          <button onClick={handleClearCanvas} className="btn-ghost text-xs">
            <RotateCcw className="w-3.5 h-3.5" />
            Clear
          </button>
          <button
            onClick={() => setShowTemplates(true)}
            className="btn-ghost text-xs"
            title="Architecture templates"
          >
            <LayoutTemplate className="w-3.5 h-3.5" />
            Templates
          </button>
          <button
            onClick={() => setShowAi(true)}
            className="btn-ghost text-xs"
            title="AI architecture assistant (advisory)"
          >
            <Sparkles className="w-3.5 h-3.5" />
            AI
          </button>
          <button
            onClick={handleValidate}
            disabled={validating || saving}
            className="btn-secondary text-xs"
          >
            {validating ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <CheckSquare className="w-3.5 h-3.5" />
            )}
            {validating ? 'Validating...' : 'Validate'}
          </button>
          <button
            onClick={handleGenerateTerraform}
            disabled={saving}
            className="btn-primary text-xs"
          >
            <Code2 className="w-3.5 h-3.5" />
            Generate Terraform
          </button>
        </div>
      </header>

      {/* Builder toolbar (search, zoom, layout, collapse, save) */}
      <BuilderToolbar
        rfInstance={rfInstance}
        saving={saving}
        resourceCount={nodes.length}
        edgeCount={edges.length}
        onSave={handleSave}
        onAutoLayout={handleAutoLayout}
        onExpandAll={expandAll}
        onCollapseAll={collapseAll}
        onSearch={handleSearch}
        onClearSearch={handleClearSearch}
        searchQuery={searchQuery}
        costTotal={costTotal}
        securityHigh={securityHigh}
        onOpenInsights={() => setShowInsights(true)}
      />

      {/* Breadcrumb (drill-down) */}
      <Breadcrumb
        focusPath={focusPath}
        onNavigate={handleBreadcrumbNavigate}
      />

      {/* Builder */}
      <div className="flex flex-1 overflow-hidden">
        <BuilderSidebar onDragStart={handleDragStart} />

        <div className="flex-1 flex flex-col overflow-hidden">
          <div ref={reactFlowWrapper} className="flex-1">
            <ReactFlow<CloudNode, Edge>
              nodes={visibleNodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onEdgesDelete={handleEdgesDelete}
              onNodesDelete={handleNodesDelete}
              onNodeDragStop={handleNodeDragStop}
              onConnect={onConnect}
              connectionMode={ConnectionMode.Loose}
              onDrop={onDrop}
              onDragOver={onDragOver}
              onInit={setRfInstance}
              onNodeClick={handleNodeClick}
              onNodeDoubleClick={handleNodeDoubleClick}
              onPaneClick={handlePaneClick}
              nodeTypes={nodeTypes}
              defaultEdgeOptions={defaultEdgeOptions}
              fitView
              snapToGrid
              snapGrid={[16, 16]}
              minZoom={0.2}
              maxZoom={2.5}
            >
              <Background
                variant={BackgroundVariant.Dots}
                gap={20}
                size={1}
                color="#1f2937"
              />
              <MiniMap
                nodeColor={(n) => {
                  const t = n.data?.resourceType as string;
                  if (n.id === highlightedNodeId) return '#fbbf24';
                  return RESOURCE_COLORS[t] || '#6b7280';
                }}
                nodeStrokeWidth={2}
                maskColor="rgba(0,0,0,0.6)"
                style={{ background: '#111827', bottom: 16, right: 16 }}
                pannable
                zoomable
              />
            </ReactFlow>
          </div>

          {validationResult && (
            <ValidationPanel
              result={validationResult}
              onClose={() => setValidationResult(null)}
              onFixWithAi={handleFixWithAi}
              fixing={fixing}
            />
          )}
        </div>

        {selectedNode && (
          <ConfigPanel
            node={selectedNode as any}
            region={selectedRegion}
            onClose={() => setSelectedNode(null)}
            onChange={handlePropertyChange}
          />
        )}
      </div>

      {showTemplates && (
        <TemplateModal
          onSelect={handleTemplateSelect}
          onClose={() => setShowTemplates(false)}
        />
      )}

      {showAi && (
        <AiArchitectModal
          onApply={handleTemplateSelect}
          onClose={() => setShowAi(false)}
        />
      )}

      {showInsights && projectId && (
        <InsightsModal
          projectId={projectId}
          onApply={handleTemplateSelect}
          onClose={() => setShowInsights(false)}
        />
      )}
    </div>
  );
}
