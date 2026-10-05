import type { Node } from '@xyflow/react';
import { CONTAINER_TYPES } from './GroupNode';

/** Node shape used by the builder canvas. */
export type CloudNode = Node<{
  label: string;
  resourceType: string;
  provider: string;
  properties: Record<string, any>;
  collapsed?: boolean;
  childCount?: number;
  detached?: boolean;
}>;

/** Which resource types belong inside each container when connected. */
export const CONTAINMENT_CHILDREN: Record<string, Set<string>> = {
  vpc: new Set(['subnet', 'internet_gateway', 'route_table', 'nat_gateway', 'lambda', 'ecs_cluster', 'efs']),
  subnet: new Set(['ec2', 'rds', 'nat_gateway', 'lambda', 'elasticache', 'aurora', 'redshift', 'efs', 'ebs_volume']),
};

/** Absolute (canvas) position of a node, walking up its parent chain. */
export function absolutePosition(node: CloudNode, byId: Map<string, CloudNode>): { x: number; y: number } {
  let x = node.position.x;
  let y = node.position.y;
  let parentId = node.parentId;
  const seen = new Set<string>();
  while (parentId && !seen.has(parentId)) {
    seen.add(parentId);
    const parent = byId.get(parentId);
    if (!parent) break;
    x += parent.position.x;
    y += parent.position.y;
    parentId = parent.parentId;
  }
  return { x, y };
}

/** React Flow requires every parent to appear before its children. */
export function parentsFirst(nodes: CloudNode[]): CloudNode[] {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const depth = (start: CloudNode) => {
    let d = 0;
    let parentId = start.parentId;
    const seen = new Set<string>();
    while (parentId && !seen.has(parentId)) {
      seen.add(parentId);
      d += 1;
      parentId = byId.get(parentId)?.parentId;
    }
    return d;
  };
  return [...nodes].sort((a, b) => depth(a) - depth(b));
}

/** Move `childId` inside `parentId`, keeping its on-canvas position. */
export function nestNode(nodes: CloudNode[], childId: string, parentId: string): CloudNode[] {
  if (childId === parentId) return nodes;
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const child = byId.get(childId);
  const parent = byId.get(parentId);
  if (!child || !parent || child.parentId === parentId) return nodes;

  const absChild = absolutePosition(child, byId);
  const absParent = absolutePosition(parent, byId);

  const updated = nodes.map((n) => {
    if (n.id === childId) {
      return {
        ...n,
        parentId,
        position: { x: absChild.x - absParent.x, y: absChild.y - absParent.y },
        data: { ...n.data, detached: false },
      } as CloudNode;
    }
    // Expand the container so the newly nested resource is actually visible.
    if (n.id === parentId && n.data.collapsed) {
      return { ...n, data: { ...n.data, collapsed: false, childCount: 0 } } as CloudNode;
    }
    return n;
  });
  return parentsFirst(updated);
}

/** Un-nest a node, preserving its absolute canvas position. */
export function detachNode(nodes: CloudNode[], childId: string): CloudNode[] {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const child = byId.get(childId);
  if (!child || !child.parentId) return nodes;
  const abs = absolutePosition(child, byId);
  return parentsFirst(
    nodes.map((n) =>
      n.id === childId
        ? ({ ...n, parentId: undefined, position: { x: abs.x, y: abs.y } } as CloudNode)
        : n
    )
  );
}

/** The child/parent pair an edge implies, or null if it is not a containment edge. */
export function containmentPair(
  nodes: CloudNode[],
  edge: { source: string; target: string }
): { childId: string; parentId: string } | null {
  const source = nodes.find((n) => n.id === edge.source);
  const target = nodes.find((n) => n.id === edge.target);
  if (!source || !target) return null;
  const sourceType = source.data.resourceType;
  const targetType = target.data.resourceType;
  if (CONTAINMENT_CHILDREN[targetType]?.has(sourceType)) {
    return { childId: source.id, parentId: target.id };
  }
  if (CONTAINMENT_CHILDREN[sourceType]?.has(targetType)) {
    return { childId: target.id, parentId: source.id };
  }
  return null;
}

/** Nest every edge-implied child into its container (idempotent). */
export function nestFromEdges(
  nodes: CloudNode[],
  edges: { source: string; target: string }[]
): CloudNode[] {
  let result = nodes;
  for (const edge of edges) {
    const pair = containmentPair(result, edge);
    if (!pair) continue;
    const child = result.find((n) => n.id === pair.childId);
    // Respect a node the user deliberately dragged out of its container.
    if (child?.data.detached) continue;
    result = nestNode(result, pair.childId, pair.parentId);
  }
  return result;
}

/** Every descendant node id of `id` (used to prevent nesting cycles). */
export function descendantsOf(nodes: CloudNode[], id: string): Set<string> {
  const result = new Set<string>();
  const stack = [id];
  while (stack.length) {
    const current = stack.pop() as string;
    for (const n of nodes) {
      if (n.parentId === current && !result.has(n.id)) {
        result.add(n.id);
        stack.push(n.id);
      }
    }
  }
  return result;
}

export function nodeDepth(node: CloudNode, byId: Map<string, CloudNode>): number {
  let depth = 0;
  let parentId = node.parentId;
  const seen = new Set<string>();
  while (parentId && !seen.has(parentId)) {
    seen.add(parentId);
    depth += 1;
    parentId = byId.get(parentId)?.parentId;
  }
  return depth;
}

/** The innermost container whose bounds contain `node`'s centre, or null. */
export function findContainerFor(node: CloudNode, nodes: CloudNode[]): string | null {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const abs = absolutePosition(node, byId);
  const center = { x: abs.x + 95, y: abs.y + 40 };
  const excluded = descendantsOf(nodes, node.id);
  excluded.add(node.id);

  const inside = nodes.filter((c) => {
    if (!CONTAINER_TYPES.has(c.data.resourceType) || excluded.has(c.id)) return false;
    const cb = absolutePosition(c, byId);
    const w = 360;
    const h = 220;
    return center.x >= cb.x && center.x <= cb.x + w && center.y >= cb.y && center.y <= cb.y + h;
  });
  inside.sort((a, b) => nodeDepth(b, byId) - nodeDepth(a, byId));
  return inside[0]?.id ?? null;
}
