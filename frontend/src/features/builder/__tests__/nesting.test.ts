import { describe, it, expect } from 'vitest';
import {
  nestNode,
  detachNode,
  nestFromEdges,
  containmentPair,
  findContainerFor,
  parentsFirst,
  type CloudNode,
} from '../nesting';

function mk(id: string, resourceType: string, x = 0, y = 0, parentId?: string): CloudNode {
  return {
    id,
    type: 'resourceNode',
    position: { x, y },
    ...(parentId ? { parentId } : {}),
    data: { label: id, resourceType, provider: 'aws', properties: {} },
  } as unknown as CloudNode;
}

describe('nesting helpers', () => {
  it('nestNode sets the parent and converts to relative coordinates', () => {
    const vpc = mk('vpc', 'vpc', 100, 100);
    const ec2 = mk('ec2', 'ec2', 250, 300);
    const out = nestNode([vpc, ec2], 'ec2', 'vpc');
    const child = out.find((n) => n.id === 'ec2')!;
    expect(child.parentId).toBe('vpc');
    expect(child.position).toEqual({ x: 150, y: 200 });
  });

  it('nestNode clears the detached flag', () => {
    const vpc = mk('vpc', 'vpc', 0, 0);
    const ec2 = mk('ec2', 'ec2', 10, 10);
    (ec2.data as any).detached = true;
    const out = nestNode([vpc, ec2], 'ec2', 'vpc');
    expect(out.find((n) => n.id === 'ec2')!.data.detached).toBe(false);
  });

  it('detachNode restores absolute coordinates', () => {
    const vpc = mk('vpc', 'vpc', 100, 100);
    const sub = mk('sub', 'subnet', 20, 30, 'vpc');
    const out = detachNode([vpc, sub], 'sub');
    const d = out.find((n) => n.id === 'sub')!;
    expect(d.parentId).toBeUndefined();
    expect(d.position).toEqual({ x: 120, y: 130 });
  });

  it('parentsFirst orders parents before children', () => {
    const child = mk('sub', 'subnet', 0, 0, 'vpc');
    const vpc = mk('vpc', 'vpc');
    expect(parentsFirst([child, vpc])[0].id).toBe('vpc');
  });

  it('containmentPair recognises containment edges only', () => {
    const nodes = [mk('vpc', 'vpc'), mk('sub', 'subnet'), mk('ec2', 'ec2'), mk('s3', 's3')];
    expect(containmentPair(nodes, { source: 'sub', target: 'vpc' })).toEqual({ childId: 'sub', parentId: 'vpc' });
    expect(containmentPair(nodes, { source: 'ec2', target: 'sub' })).toEqual({ childId: 'ec2', parentId: 'sub' });
    expect(containmentPair(nodes, { source: 's3', target: 'vpc' })).toBeNull();
  });

  it('nestFromEdges nests a subnet in its VPC and an EC2 in its subnet', () => {
    const nodes = [mk('vpc', 'vpc', 0, 0), mk('sub', 'subnet', 50, 50), mk('ec2', 'ec2', 80, 90)];
    const edges = [
      { source: 'vpc', target: 'sub' },
      { source: 'sub', target: 'ec2' },
    ];
    const out = nestFromEdges(nodes, edges);
    expect(out.find((n) => n.id === 'sub')!.parentId).toBe('vpc');
    expect(out.find((n) => n.id === 'ec2')!.parentId).toBe('sub');
  });

  it('nestFromEdges leaves a deliberately detached node out', () => {
    const nodes = [mk('vpc', 'vpc'), mk('sub', 'subnet', 50, 50)];
    (nodes[1].data as any).detached = true;
    const out = nestFromEdges(nodes, [{ source: 'vpc', target: 'sub' }]);
    expect(out.find((n) => n.id === 'sub')!.parentId).toBeUndefined();
  });

  it('findContainerFor returns the innermost container', () => {
    const vpc = mk('vpc', 'vpc', 0, 0);
    const sub = mk('sub', 'subnet', 20, 20, 'vpc');
    const leaf = mk('ec2', 'ec2', 100, 100);
    expect(findContainerFor(leaf, [vpc, sub, leaf])).toBe('sub');
  });
});
