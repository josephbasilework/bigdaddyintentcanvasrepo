import type { NodeContext } from "../types/contextPreview";
import { AudioBlockNode } from "../components/Canvas/AudioBlockNode";
import { DAGNode } from "../components/Canvas/DAGNode";
import { DashboardNode } from "../components/Canvas/DashboardNode";
import { JobNode } from "../components/Canvas/JobNode";
import { PlanNode } from "../components/Canvas/PlanNode";
import type { CanvasNode, DAGData, DAGTask, JobData, PlanData } from "../state/canvasStore";
import {
  registerNodeTypes,
  type NodeRendererProps,
  type NodeTypeDefinition,
  type NodeTypeStyle,
} from "./registry";

const STYLE_BY_TYPE: Record<string, NodeTypeStyle> = {
  text: {
    backgroundColor: "#1a1a2e",
    borderColor: "#333",
    selectedBorderColor: "#4a9eff",
    shadowColor: "rgba(0, 0, 0, 0.3)",
    selectedShadowColor: "rgba(74, 158, 255, 0.3)",
  },
  document: {
    backgroundColor: "#16213e",
    borderColor: "#1a3a5a",
    selectedBorderColor: "#00d4aa",
    shadowColor: "rgba(0, 0, 0, 0.3)",
    selectedShadowColor: "rgba(0, 212, 170, 0.3)",
  },
  audio: {
    backgroundColor: "#1f1f3a",
    borderColor: "#3a2a2a",
    selectedBorderColor: "#ff6b6b",
    shadowColor: "rgba(0, 0, 0, 0.3)",
    selectedShadowColor: "rgba(255, 107, 107, 0.3)",
  },
  graph: {
    backgroundColor: "#1a1a3a",
    borderColor: "#3a2a3a",
    selectedBorderColor: "#ffd93d",
    shadowColor: "rgba(0, 0, 0, 0.3)",
    selectedShadowColor: "rgba(255, 217, 61, 0.3)",
  },
  plan: {
    backgroundColor: "#132a2d",
    borderColor: "#285e61",
    selectedBorderColor: "#38b2ac",
    shadowColor: "rgba(0, 0, 0, 0.3)",
    selectedShadowColor: "rgba(56, 178, 172, 0.3)",
  },
  dag: {
    backgroundColor: "#241a2d",
    borderColor: "#553c9a",
    selectedBorderColor: "#9f7aea",
    shadowColor: "rgba(0, 0, 0, 0.3)",
    selectedShadowColor: "rgba(159, 122, 234, 0.3)",
  },
  dashboard: {
    backgroundColor: "#141c2f",
    borderColor: "#1e3a5f",
    selectedBorderColor: "#38bdf8",
    shadowColor: "rgba(0, 0, 0, 0.3)",
    selectedShadowColor: "rgba(56, 189, 248, 0.3)",
  },
  job: {
    backgroundColor: "#1f1a2d",
    borderColor: "#4a2a4a",
    selectedBorderColor: "#f472b6",
    shadowColor: "rgba(0, 0, 0, 0.3)",
    selectedShadowColor: "rgba(244, 114, 182, 0.3)",
  },
  container: {
    backgroundColor: "rgba(20, 30, 48, 0.6)",
    borderColor: "rgba(148, 163, 184, 0.35)",
    selectedBorderColor: "rgba(56, 189, 248, 0.8)",
    shadowColor: "rgba(15, 23, 42, 0.3)",
    selectedShadowColor: "rgba(56, 189, 248, 0.35)",
  },
};

const buildBaseContext = (node: CanvasNode): NodeContext => ({
  id: node.id,
  title: node.title,
  node_type: node.type,
  ...(node.content ? { content: node.content } : {}),
  ...(node.metadata ? { metadata: node.metadata } : {}),
});

const buildPlanContext = (node: CanvasNode): NodeContext => {
  const plan = node.planData;
  if (!plan) {
    return buildBaseContext(node);
  }
  const lines = [`Goal: ${plan.goal}`, `Approach: ${plan.approach}`];
  if (plan.estimatedTotalEffort) {
    lines.push(`Effort: ${plan.estimatedTotalEffort}`);
  }
  if (plan.assumptions?.length) {
    lines.push(`Assumptions: ${plan.assumptions.join("; ")}`);
  }
  if (plan.risks?.length) {
    lines.push(`Risks: ${plan.risks.join("; ")}`);
  }
  return {
    id: node.id,
    title: node.title,
    node_type: node.type,
    content: lines.join("\n"),
    ...(node.metadata ? { metadata: node.metadata } : {}),
  };
};

const buildDagContext = (node: CanvasNode): NodeContext => {
  const dag = node.dagData;
  if (!dag) {
    return buildBaseContext(node);
  }
  const tasks = dag.tasks ?? [];
  const lines = tasks.slice(0, 6).map((task) => `- ${task.title} (${task.status})`);
  const completedCount = tasks.filter((task) => task.status === "completed").length;
  const metadata = node.metadata
    ? { ...node.metadata, task_count: tasks.length, completed_count: completedCount }
    : { task_count: tasks.length, completed_count: completedCount };
  return {
    id: node.id,
    title: node.title,
    node_type: node.type,
    ...(lines.length > 0
      ? { content: `Tasks (${tasks.length}):\n${lines.join("\n")}` }
      : {}),
    metadata,
  };
};

const buildJobContext = (node: CanvasNode): NodeContext => {
  const job = node.jobData;
  if (!job) {
    return buildBaseContext(node);
  }
  const summary = `${job.jobType} • ${job.status} (${job.progressPercent}%)`;
  return {
    id: node.id,
    title: node.title,
    node_type: node.type,
    content: summary,
    ...(node.metadata ? { metadata: node.metadata } : {}),
  };
};

const buildAudioContext = (node: CanvasNode): NodeContext => {
  const transcription = node.metadata?.transcription;
  const content =
    typeof transcription === "string" && transcription.trim().length > 0
      ? transcription
      : node.content;
  return {
    id: node.id,
    title: node.title,
    node_type: node.type,
    ...(content ? { content } : {}),
    ...(node.metadata ? { metadata: node.metadata } : {}),
  };
};

const defaultSerialize = (_node: CanvasNode, base: Record<string, unknown>) => base;

const renderInlineContent = (content?: string | null) => {
  if (!content) return null;
  return (
    <div
      style={{
        fontSize: "13px",
        color: "#aaa",
        lineHeight: "1.5",
        maxHeight: "200px",
        overflow: "auto",
        wordBreak: "break-word",
      }}
    >
      {content}
    </div>
  );
};

const renderAudioNode = ({ node }: NodeRendererProps) => {
  const canvasNode = node as CanvasNode;
  if (!canvasNode.metadata && !canvasNode.content) {
    return null;
  }
  return <AudioBlockNode node={canvasNode} />;
};

const renderPlanNode = ({ node }: NodeRendererProps) => {
  const canvasNode = node as CanvasNode;
  const plan = canvasNode.planData;
  if (!plan) {
    return renderInlineContent(canvasNode.content ?? null);
  }
  return <PlanNode plan={plan as PlanData} />;
};

const renderDagNode = ({ node, onDagTaskStatusChange }: NodeRendererProps) => {
  const canvasNode = node as CanvasNode;
  const dag = canvasNode.dagData;
  if (!dag) {
    return renderInlineContent(canvasNode.content ?? null);
  }
  return (
    <DAGNode
      dag={dag as DAGData}
      onTaskStatusChange={onDagTaskStatusChange as ((
        taskId: string,
        nextStatus: DAGTask["status"]
      ) => void) | undefined}
    />
  );
};

const renderDashboardNode = ({ node }: NodeRendererProps) => (
  <DashboardNode nodeId={node.id} />
);

const renderJobNode = ({
  node,
  isSelected,
  onSelect,
  onRerunWithMoreCompute,
  onRouteResults,
}: NodeRendererProps) => {
  const canvasNode = node as CanvasNode;
  const job = canvasNode.jobData;
  if (!job) {
    return renderInlineContent(canvasNode.content ?? null);
  }
  return (
    <JobNode
      id={node.id}
      title={node.title}
      jobData={job as JobData}
      isSelected={Boolean(isSelected)}
      onSelect={onSelect}
      onRerunWithMoreCompute={onRerunWithMoreCompute}
      onRouteResults={onRouteResults}
    />
  );
};

const BUILTIN_NODE_DEFINITIONS: NodeTypeDefinition<CanvasNode>[] = [
  {
    type: "text",
    label: "Text / Entity",
    description: "Freeform note or entity summary.",
    icon: "📝",
    style: STYLE_BY_TYPE.text,
    schema: {
      fields: [
        { key: "title", type: "string", required: true, description: "Node title." },
        { key: "content", type: "string", description: "Optional details." },
        { key: "metadata", type: "object", description: "Optional metadata." },
      ],
    },
    buildContext: buildBaseContext,
    serialize: defaultSerialize,
    creation: {
      label: "Text / Entity",
      description: "Capture a quick thought or entity snapshot.",
      buildDefaults: () => ({ title: "New note", content: "" }),
    },
  },
  {
    type: "document",
    label: "Document",
    description: "Rich document block with longer content.",
    icon: "📄",
    style: STYLE_BY_TYPE.document,
    schema: {
      fields: [
        { key: "title", type: "string", required: true, description: "Document title." },
        { key: "content", type: "string", description: "Document body." },
        { key: "metadata", type: "object", description: "Optional metadata." },
      ],
    },
    buildContext: buildBaseContext,
    serialize: defaultSerialize,
    creation: {
      label: "Document",
      description: "Start a longer artifact or report.",
      buildDefaults: () => ({ title: "New document", content: "" }),
    },
  },
  {
    type: "audio",
    label: "Audio Block",
    description: "Audio recording with transcription metadata.",
    icon: "🎙️",
    style: STYLE_BY_TYPE.audio,
    schema: {
      fields: [
        { key: "metadata.audioUrl", type: "string", description: "Audio asset URL." },
        { key: "metadata.transcription", type: "string", description: "Speech transcript." },
        { key: "metadata.summary", type: "string", description: "Optional summary." },
      ],
    },
    buildContext: buildAudioContext,
    serialize: defaultSerialize,
    render: renderAudioNode,
    creation: {
      label: "Audio Block",
      description: "Record or attach a voice snippet.",
    },
  },
  {
    type: "graph",
    label: "Graph",
    description: "Graph nodes with annotations and tags.",
    icon: "📊",
    style: STYLE_BY_TYPE.graph,
    schema: {
      fields: [
        { key: "graphAnnotation.bullets", type: "array", description: "Annotation bullets." },
        { key: "graphAnnotation.tags", type: "array", description: "Tag list." },
        { key: "graphAnnotation.status", type: "string", description: "Status flag." },
      ],
    },
    buildContext: buildBaseContext,
    serialize: defaultSerialize,
    creation: {
      label: "Graph",
      description: "Visual graph or relationship node.",
      buildDefaults: () => ({ title: "New graph" }),
    },
  },
  {
    type: "plan",
    label: "Plan",
    description: "Structured plan with approach and risks.",
    icon: "🧭",
    style: STYLE_BY_TYPE.plan,
    schema: {
      fields: [
        { key: "planData.goal", type: "string", required: true, description: "Plan goal." },
        { key: "planData.approach", type: "string", description: "Approach outline." },
        { key: "planData.assumptions", type: "array", description: "Assumptions." },
        { key: "planData.risks", type: "array", description: "Risks." },
      ],
    },
    buildContext: buildPlanContext,
    serialize: defaultSerialize,
    render: renderPlanNode,
    creation: {
      label: "Plan",
      description: "Draft a structured plan.",
      buildDefaults: () => ({ title: "New plan" }),
    },
  },
  {
    type: "dag",
    label: "Task DAG",
    description: "Task dependency graph with statuses.",
    icon: "🧩",
    style: STYLE_BY_TYPE.dag,
    schema: {
      fields: [
        { key: "dagData.tasks", type: "array", description: "Task list." },
        { key: "dagData.dependencies", type: "array", description: "Task dependencies." },
      ],
    },
    buildContext: buildDagContext,
    serialize: defaultSerialize,
    render: renderDagNode,
    creation: {
      label: "Task DAG",
      description: "Track tasks and dependencies.",
      buildDefaults: () => ({ title: "New task DAG" }),
    },
  },
  {
    type: "dashboard",
    label: "Dashboard",
    description: "Live dashboard with workspace insights.",
    icon: "📈",
    style: STYLE_BY_TYPE.dashboard,
    schema: {
      fields: [
        { key: "metadata.dashboardConfig", type: "object", description: "Dashboard config." },
      ],
    },
    buildContext: buildBaseContext,
    serialize: defaultSerialize,
    render: renderDashboardNode,
    creation: {
      label: "Dashboard",
      description: "Monitor workspace activity.",
      buildDefaults: () => ({ title: "New dashboard" }),
    },
  },
  {
    type: "job",
    label: "Job",
    description: "Background job with progress details.",
    icon: "⚙️",
    style: STYLE_BY_TYPE.job,
    schema: {
      fields: [
        { key: "jobData.jobId", type: "string", required: true, description: "Job ID." },
        { key: "jobData.jobType", type: "string", description: "Job type." },
        { key: "jobData.status", type: "string", description: "Job status." },
        { key: "jobData.progressPercent", type: "number", description: "Progress percent." },
      ],
    },
    buildContext: buildJobContext,
    serialize: defaultSerialize,
    render: renderJobNode,
    creation: {
      label: "Job",
      description: "Background processing job.",
      buildDefaults: () => ({ title: "New job" }),
    },
  },
  {
    type: "container",
    label: "Container",
    description: "Group related nodes inside a collapsible container.",
    icon: "🧺",
    style: STYLE_BY_TYPE.container,
    schema: {
      fields: [
        { key: "title", type: "string", required: true, description: "Container title." },
        { key: "metadata.container.collapsed", type: "boolean", description: "Collapse children." },
      ],
    },
    buildContext: buildBaseContext,
    serialize: defaultSerialize,
    creation: {
      label: "Container",
      description: "Organize nodes into a collapsible group.",
      buildDefaults: () => ({ title: "New container" }),
    },
  },
];

registerNodeTypes(BUILTIN_NODE_DEFINITIONS);
