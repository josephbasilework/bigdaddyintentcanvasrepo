"use client";

import { useEffect, useRef, useState } from "react";
import * as d3 from "d3";

export interface GraphData {
  nodes: Array<{ id: string; label: string; group?: string }>;
  links: Array<{ source: string; target: string; value?: number }>;
}

// Type for D3 simulation nodes - combines our node data with D3's required properties
type SimulationNode = GraphData["nodes"][0] & d3.SimulationNodeDatum;

// Type for D3 simulation links
type SimulationLink = d3.SimulationLinkDatum<SimulationNode> & {
  value?: number;
};

interface VisualGraphProps {
  data: GraphData;
  width?: number;
  height?: number;
  onNodeClick?: (nodeId: string) => void;
  onNodeDoubleClick?: (nodeId: string) => void;
}

/**
 * VisualGraph component using D3.js for interactive network visualization.
 *
 * Features:
 * - Force-directed graph layout
 * - Interactive node dragging
 * - Zoom and pan
 * - Node hover effects
 * - Click and double-click handlers
 * - Customizable colors by group
 */
export function VisualGraph({
  data,
  width = 600,
  height = 400,
  onNodeClick,
  onNodeDoubleClick,
}: VisualGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [dimensions, setDimensions] = useState({ width, height });

  // Handle resize
  useEffect(() => {
    const handleResize = () => {
      const parent = svgRef.current?.parentElement;
      if (parent) {
        setDimensions({
          width: parent.clientWidth || width,
          height: parent.clientHeight || height,
        });
      }
    };

    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [width, height]);

  // Create and update the visualization
  useEffect(() => {
    if (!svgRef.current || !data.nodes.length) return;

    // Clear previous content
    d3.select(svgRef.current).selectAll("*").remove();

    const svg = d3.select(svgRef.current);
    const { width: w, height: h } = dimensions;

    // Create a group for zoom and pan
    const g = svg.append("g");

    // Add zoom behavior
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on("zoom", (event) => {
        g.attr("transform", event.transform);
      });

    svg.call(zoom);

    // Color scale for node groups
    const colorScale = d3
      .scaleOrdinal<string>()
      .domain(data.nodes.map((n) => n.group || "default").filter((v, i, a) => a.indexOf(v) === i))
      .range(d3.schemeCategory10);

    // Create the simulation with properly typed nodes
    const simulation = d3
      .forceSimulation<SimulationNode>(data.nodes as SimulationNode[])
      .force(
        "link",
        d3
          .forceLink<SimulationNode, SimulationLink>(data.links as SimulationLink[])
          .id((d: SimulationNode) => d.id)
          .distance(100)
      )
      .force("charge", d3.forceManyBody().strength(-300))
      .force("center", d3.forceCenter(w / 2, h / 2))
      .force("collision", d3.forceCollide().radius(30));

    // Create links
    const link = g
      .append("g")
      .attr("class", "links")
      .selectAll("line")
      .data(data.links)
      .enter()
      .append("line")
      .attr("stroke", "#4a5568")
      .attr("stroke-opacity", 0.6)
      .attr("stroke-width", (d) => Math.sqrt(d.value || 1) * 2);

    // Create nodes
    const node = g
      .append("g")
      .attr("class", "nodes")
      .selectAll<SVGGElement, SimulationNode>("g")
      .data(data.nodes as SimulationNode[])
      .enter()
      .append("g")
      .attr("class", "node")
      .call(
        d3
          .drag<SVGGElement, SimulationNode>()
          .on("start", dragstarted)
          .on("drag", dragged)
          .on("end", dragended)
      );

    // Node circles
    node
      .append("circle")
      .attr("r", 20)
      .attr("fill", (d) => colorScale(d.group || "default") as string)
      .attr("stroke", "#fff")
      .attr("stroke-width", 2)
      .style("cursor", "pointer")
      .on("mouseover", function () {
        d3.select(this).attr("r", 25).attr("stroke-width", 3);
      })
      .on("mouseout", function () {
        d3.select(this).attr("r", 20).attr("stroke-width", 2);
      })
      .on("click", (event, d) => {
        event.stopPropagation();
        onNodeClick?.(d.id);
      })
      .on("dblclick", (event, d) => {
        event.stopPropagation();
        onNodeDoubleClick?.(d.id);
      });

    // Node labels
    node
      .append("text")
      .text((d) => d.label)
      .attr("x", 0)
      .attr("y", 30)
      .attr("text-anchor", "middle")
      .attr("fill", "#e2e8f0")
      .attr("font-size", "12px")
      .attr("font-weight", "500")
      .style("pointer-events", "none");

    // Update positions on tick
    simulation.on("tick", () => {
      const getSourceX = (d: SimulationLink): number => {
        const src = d.source;
        if (typeof src === "string" || typeof src === "number") return 0;
        return src.x ?? 0;
      };
      const getSourceY = (d: SimulationLink): number => {
        const src = d.source;
        if (typeof src === "string" || typeof src === "number") return 0;
        return src.y ?? 0;
      };
      const getTargetX = (d: SimulationLink): number => {
        const tgt = d.target;
        if (typeof tgt === "string" || typeof tgt === "number") return 0;
        return tgt.x ?? 0;
      };
      const getTargetY = (d: SimulationLink): number => {
        const tgt = d.target;
        if (typeof tgt === "string" || typeof tgt === "number") return 0;
        return tgt.y ?? 0;
      };

      link
        .attr("x1", getSourceX)
        .attr("y1", getSourceY)
        .attr("x2", getTargetX)
        .attr("y2", getTargetY);

      node.attr("transform", (d) => `translate(${d.x ?? 0},${d.y ?? 0})`);
    });

    // Drag functions
    function dragstarted(event: d3.D3DragEvent<SVGGElement, SimulationNode, d3.SubjectPosition>, d: SimulationNode) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      d.fx = d.x;
      d.fy = d.y;
    }

    function dragged(event: d3.D3DragEvent<SVGGElement, SimulationNode, d3.SubjectPosition>, d: SimulationNode) {
      d.fx = event.x;
      d.fy = event.y;
    }

    function dragended(event: d3.D3DragEvent<SVGGElement, SimulationNode, d3.SubjectPosition>, d: SimulationNode) {
      if (!event.active) simulation.alphaTarget(0);
      d.fx = null;
      d.fy = null;
    }

    // Cleanup
    return () => {
      simulation.stop();
    };
  }, [data, dimensions, onNodeClick, onNodeDoubleClick]);

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        backgroundColor: "#0a0a0a",
        borderRadius: "8px",
        overflow: "hidden",
      }}
    >
      <svg
        ref={svgRef}
        width={dimensions.width}
        height={dimensions.height}
        style={{
          display: "block",
          cursor: "grab",
        }}
        onMouseDown={(e) => {
          e.currentTarget.style.cursor = "grabbing";
        }}
        onMouseUp={(e) => {
          e.currentTarget.style.cursor = "grab";
        }}
      />
    </div>
  );
}

/**
 * VisualGraphNode component - wrapper for graph-type nodes on the canvas.
 *
 * Displays an embedded D3.js visualization within a canvas node.
 */
interface VisualGraphNodeProps {
  data: GraphData;
  onNodeClick?: (nodeId: string) => void;
}

export function VisualGraphNode({ data, onNodeClick }: VisualGraphNodeProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 400, height: 300 });

  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    };

    updateDimensions();
    window.addEventListener("resize", updateDimensions);
    return () => window.removeEventListener("resize", updateDimensions);
  }, []);

  return (
    <div
      ref={containerRef}
      style={{
        width: "100%",
        height: "250px",
        marginTop: "8px",
      }}
    >
      <VisualGraph
        data={data}
        width={dimensions.width}
        height={dimensions.height}
        onNodeClick={onNodeClick}
      />
    </div>
  );
}
