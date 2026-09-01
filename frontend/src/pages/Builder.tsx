import { useState, useCallback, useRef, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ReactFlow,
  Background,
  Controls,
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

import {
  Save,
  CheckSquare,
  Code2,
  Trash2,
  RotateCcw,
  Cloud,
  Loader2,
  ArrowLeft,
} from 'lucide-react';

import { ResourceNodeComponent } from '../features/builder/ResourceNode';
import { BuilderSidebar, type SidebarItem } from '../features/builder/BuilderSidebar';
import { ConfigPanel } from '../features/builder/ConfigPanel';
import { ValidationPanel } from '../features/builder/ValidationPanel';
import { architectureApi, projectsApi } from '../services/api';
import type { ValidationResult, Project } from '../types';
import toast from 'react-hot-toast';

const nodeTypes = { resourceNode: ResourceNodeComponent };

const defaultEdgeOptions = {
  style: { stroke: '#4b5563', strokeWidth: 2 },
  markerEnd: { type: MarkerType.ArrowClosed, color: '#4b5563' },
};

let nodeCounter = 0;

type CloudNode = Node<{
  label: string;
  resourceType: string;
  provider: string;
  properties: Record<string, any>;
}>;

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

  const reactFlowWrapper = useRef<HTMLDivElement>(null);

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
          setNodes(archRes.data.nodes as CloudNode[]);
          setEdges(archRes.data.edges || []);
        }
      } catch (err: any) {
        if (err.response?.status !== 404) {
          toast.error('Failed to load architecture');
        }
        try {
          const projRes = await projectsApi.get(projectId!);
          setProject(projRes.data);
        } catch {
          toast.error('Project not found');
          navigate('/dashboard');
        }
      } finally {
        setLoadingProject(false);
      }
    };
    load();
  }, [projectId]);

  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) =>
        addEdge(
          {
            ...connection,
            style: { stroke: '#3b82f6', strokeWidth: 2 },
            markerEnd: { type: MarkerType.ArrowClosed, color: '#3b82f6' },
          },
          eds
        )
      );
    },
    [setEdges]
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      if (!rfInstance || !reactFlowWrapper.current) return;

      const itemJson = event.dataTransfer.getData('application/cloudforge-node');
      if (!itemJson) return;

      const item: SidebarItem = JSON.parse(itemJson);
      const bounds = reactFlowWrapper.current.getBoundingClientRect();

      const position = rfInstance.screenToFlowPosition({
        x: event.clientX - bounds.left,
        y: event.clientY - bounds.top,
      });

      nodeCounter++;
      const id = `${item.type}-${Date.now()}-${nodeCounter}`;

      const newNode: CloudNode = {
        id,
        type: 'resourceNode',
        position,
        data: {
          label: item.label,
          resourceType: item.type,
          provider: 'aws',
          properties: { ...item.defaultProperties },
        },
      };

      setNodes((nds) => [...nds, newNode]);
    },
    [rfInstance, setNodes]
  );

  const handleDragStart = (event: React.DragEvent, item: SidebarItem) => {
    event.dataTransfer.setData('application/cloudforge-node', JSON.stringify(item));
    event.dataTransfer.effectAllowed = 'move';
  };

  const handleNodeClick = useCallback((_: React.MouseEvent, node: CloudNode) => {
    setSelectedNode(node);
  }, []);

  const handlePaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

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

  const doSave = async () => {
    if (!projectId) return;
    setSaving(true);
    try {
      await architectureApi.save(projectId, { nodes, edges });
      toast.success('Architecture saved successfully!');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save architecture');
    } finally {
      setSaving(false);
    }
  };

  const handleSave = async () => {
    await doSave();
    setValidationResult(null);
  };

  const handleValidate = async () => {
    if (!projectId) return;
    setSaving(true);
    try {
      await architectureApi.save(projectId, { nodes, edges });
    } catch {
      /* continue */
    } finally {
      setSaving(false);
    }

    setValidating(true);
    try {
      const res = await architectureApi.validate(projectId);
      setValidationResult(res.data);
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

  const handleGenerateTerraform = async () => {
    if (!projectId) return;
    setSaving(true);
    try {
      await architectureApi.save(projectId, { nodes, edges });
    } catch {
      /* continue */
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
  };

  const handleDeleteSelected = () => {
    if (selectedNode) {
      setNodes((nds) => nds.filter((n) => n.id !== selectedNode.id));
      setEdges((eds) => eds.filter((e) => e.source !== selectedNode.id && e.target !== selectedNode.id));
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
      {/* Toolbar */}
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
            <div className="text-sm font-semibold text-white leading-none">{project?.name || 'Builder'}</div>
            <div className="text-[10px] text-dark-500 capitalize">{project?.provider} · Visual Builder</div>
          </div>
        </div>

        <div className="text-[10px] text-dark-600 hidden lg:block">
          {nodes.length} resource{nodes.length !== 1 ? 's' : ''} · {edges.length} connection{edges.length !== 1 ? 's' : ''}
        </div>

        <div className="flex-1" />

        <div className="flex items-center gap-2">
          {selectedNode && (
            <button onClick={handleDeleteSelected} className="btn-danger text-xs" title="Delete selected">
              <Trash2 className="w-3.5 h-3.5" />
              Delete
            </button>
          )}
          <button onClick={handleClearCanvas} className="btn-ghost text-xs">
            <RotateCcw className="w-3.5 h-3.5" />
            Clear
          </button>
          <button onClick={handleSave} disabled={saving} className="btn-secondary text-xs">
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
            {saving ? 'Saving...' : 'Save'}
          </button>
          <button onClick={handleValidate} disabled={validating || saving} className="btn-secondary text-xs">
            {validating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckSquare className="w-3.5 h-3.5" />}
            {validating ? 'Validating...' : 'Validate'}
          </button>
          <button onClick={handleGenerateTerraform} disabled={saving} className="btn-primary text-xs">
            <Code2 className="w-3.5 h-3.5" />
            Generate Terraform
          </button>
        </div>
      </header>

      {/* Builder */}
      <div className="flex flex-1 overflow-hidden">
        <BuilderSidebar onDragStart={handleDragStart} />

        <div className="flex-1 flex flex-col overflow-hidden">
          <div ref={reactFlowWrapper} className="flex-1">
            <ReactFlow<CloudNode, Edge>
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onDrop={onDrop}
              onDragOver={onDragOver}
              onInit={setRfInstance}
              onNodeClick={handleNodeClick}
              onPaneClick={handlePaneClick}
              nodeTypes={nodeTypes}
              defaultEdgeOptions={defaultEdgeOptions}
              fitView
              snapToGrid
              snapGrid={[16, 16]}
              minZoom={0.3}
              maxZoom={2}
            >
              <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#1f2937" />
              <Controls />
              <MiniMap
                nodeColor={(n) => {
                  const t = n.data?.resourceType as string;
                  const c: Record<string, string> = {
                    vpc: '#3b82f6', subnet: '#06b6d4', ec2: '#f97316',
                    s3: '#22c55e', rds: '#a855f7', security_group: '#ef4444',
                    load_balancer: '#eab308',
                  };
                  return c[t] || '#6b7280';
                }}
                maskColor="rgba(0,0,0,0.6)"
                style={{ background: '#111827' }}
              />
            </ReactFlow>
          </div>

          {validationResult && (
            <ValidationPanel result={validationResult} onClose={() => setValidationResult(null)} />
          )}
        </div>

        {selectedNode && (
          <ConfigPanel
            node={selectedNode as any}
            onClose={() => setSelectedNode(null)}
            onChange={handlePropertyChange}
          />
        )}
      </div>
    </div>
  );
}
