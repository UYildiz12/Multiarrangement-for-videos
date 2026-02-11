type NodeSpec = {
    id: string;
    targetX: number;
    targetY: number;
    radius: number;
    incomingPath: string;
    outgoingPath: string;
    inStart: number;
    inEnd: number;
    outStart: number;
    outEnd: number;
    tone: "bright" | "soft";
};
type ConstellationNode = Pick<NodeSpec, "id" | "targetX" | "targetY" | "radius" | "tone">;

const ACTIVE_SEQUENCE_SECONDS = 13.8;
const RESET_HOLD_SECONDS = 3;
const CYCLE_SECONDS = ACTIVE_SEQUENCE_SECONDS + RESET_HOLD_SECONDS;
const ACTIVE_SEGMENT_RATIO = ACTIVE_SEQUENCE_SECONDS / CYCLE_SECONDS;
const NODE_RADIUS = 2.3;

function t(value: number): string {
    const clamped = Math.max(0, Math.min(1, value));
    return Number(clamped.toFixed(3)).toString();
}

function c(value: number): string {
    return t(value * ACTIVE_SEGMENT_RATIO);
}

const NODES: NodeSpec[] = [
    {
        id: "a",
        targetX: 33,
        targetY: 30,
        radius: NODE_RADIUS,
        incomingPath: "M 8 12 Q 22 6 33 30",
        outgoingPath: "M 33 30 Q 19 20 4 4",
        inStart: 0.016,
        inEnd: 0.133,
        outStart: 0.671,
        outEnd: 0.797,
        tone: "bright",
    },
    {
        id: "b",
        targetX: 66,
        targetY: 27,
        radius: NODE_RADIUS,
        incomingPath: "M 94 20 Q 80 8 66 27",
        outgoingPath: "M 66 27 Q 79 16 92 7",
        inStart: 0.063,
        inEnd: 0.188,
        outStart: 0.703,
        outEnd: 0.836,
        tone: "soft",
    },
    {
        id: "c",
        targetX: 27,
        targetY: 52,
        radius: NODE_RADIUS,
        incomingPath: "M 12 86 Q 19 67 27 52",
        outgoingPath: "M 27 52 Q 14 66 5 90",
        inStart: 0.125,
        inEnd: 0.243,
        outStart: 0.75,
        outEnd: 0.922,
        tone: "bright",
    },
    {
        id: "d",
        targetX: 50,
        targetY: 63,
        radius: NODE_RADIUS,
        incomingPath: "M 52 97 Q 44 78 50 63",
        outgoingPath: "M 50 63 Q 53 80 49 96",
        inStart: 0.188,
        inEnd: 0.313,
        outStart: 0.781,
        outEnd: 0.961,
        tone: "soft",
    },
    {
        id: "e",
        targetX: 72,
        targetY: 55,
        radius: NODE_RADIUS,
        incomingPath: "M 88 81 Q 81 61 72 55",
        outgoingPath: "M 72 55 Q 86 68 96 86",
        inStart: 0.258,
        inEnd: 0.391,
        outStart: 0.734,
        outEnd: 0.907,
        tone: "bright",
    },
    {
        id: "f",
        targetX: 57,
        targetY: 41,
        radius: NODE_RADIUS,
        incomingPath: "M 70 6 Q 70 24 57 41",
        outgoingPath: "M 57 41 Q 66 22 80 4",
        inStart: 0.321,
        inEnd: 0.446,
        outStart: 0.812,
        outEnd: 0.984,
        tone: "soft",
    },
];

const CONSTELLATION_EDGES: Array<[NodeSpec["id"], NodeSpec["id"]]> = [
    ["a", "b"],
    ["a", "c"],
    ["a", "f"],
    ["b", "e"],
    ["f", "e"],
    ["c", "d"],
    ["d", "e"],
    ["c", "f"],
];

const NODE_BY_ID: Record<string, NodeSpec> = Object.fromEntries(NODES.map((node) => [node.id, node]));

const STATIC_NODES: ConstellationNode[] = [
    { id: "a", targetX: 36, targetY: 36, radius: NODE_RADIUS, tone: "bright" },
    { id: "b", targetX: 64, targetY: 36, radius: NODE_RADIUS, tone: "soft" },
    { id: "c", targetX: 31, targetY: 50, radius: NODE_RADIUS, tone: "soft" },
    { id: "d", targetX: 50, targetY: 65, radius: NODE_RADIUS, tone: "bright" },
    { id: "e", targetX: 69, targetY: 50, radius: NODE_RADIUS, tone: "soft" },
    { id: "f", targetX: 50, targetY: 28, radius: NODE_RADIUS, tone: "bright" },
];

const STATIC_CONSTELLATION_EDGES: Array<[ConstellationNode["id"], ConstellationNode["id"]]> = [
    ["f", "a"],
    ["f", "b"],
    ["a", "b"],
    ["a", "c"],
    ["b", "e"],
    ["c", "d"],
    ["e", "d"],
    ["c", "e"],
];

const STATIC_NODE_BY_ID: Record<string, ConstellationNode> = Object.fromEntries(
    STATIC_NODES.map((node) => [node.id, node])
);

export default function Logo({
    size = 32,
    variant = "color",
    animated = true,
}: {
    size?: number;
    variant?: "color" | "mono";
    animated?: boolean;
}) {
    const isMono = variant === "mono";
    const bg = "#101113";
    const arenaStroke = isMono ? "#c3c3c3" : "#dddddd";
    const innerGuide = isMono ? "#777777" : "#8a8a8a";
    const dotBright = "#f4f4f4";
    const dotSoft = isMono ? "#cecece" : "#e2e2e2";
    const lineColor = isMono ? "#a6a6a6" : "#b4b4b4";
    const lineAccent = isMono ? "#b24b4b" : "#d24f4f";
    const showGuidePaths = animated && size >= 28;

    return (
        <svg
            width={size}
            height={size}
            viewBox="0 0 100 100"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            aria-label="Multiarrangement logo"
        >
            <circle cx="50" cy="50" r="47" fill={bg} />

            {showGuidePaths && (
                <g stroke={innerGuide} strokeOpacity="0.2" strokeWidth="0.75" fill="none" strokeDasharray="1.2 3.2">
                    {NODES.map((node) => (
                        <path key={`guide-in-${node.id}`} d={node.incomingPath} />
                    ))}
                    {NODES.map((node) => (
                        <path key={`guide-out-${node.id}`} d={node.outgoingPath} />
                    ))}
                </g>
            )}

            {animated ? (
                <>
                    <g strokeLinecap="round" fill="none">
                        {CONSTELLATION_EDGES.map((edge, idx) => {
                            const from = NODE_BY_ID[edge[0]];
                            const to = NODE_BY_ID[edge[1]];
                            const overlapStart = Math.max(from.inEnd, to.inEnd);
                            const overlapEnd = Math.min(from.outStart, to.outStart);
                            let linkStart = overlapStart + 0.01;
                            let linkEnd = overlapEnd - 0.01;
                            if (linkEnd <= linkStart) {
                                const mid = (overlapStart + overlapEnd) / 2;
                                linkStart = Math.max(0, mid - 0.012);
                                linkEnd = Math.min(1, mid + 0.012);
                            }
                            const linkPeak = linkStart + (linkEnd - linkStart) * 0.58;
                            return (
                                <g key={`line-${idx}`}>
                                    <line x1={from.targetX} y1={from.targetY} x2={to.targetX} y2={to.targetY} stroke={lineColor} strokeWidth="0.9" opacity={0.08}>
                                        <animate
                                            attributeName="opacity"
                                            values="0.02;0.05;0.1;0.12;0.05;0.02"
                                            keyTimes={`0;${c(0.22)};${c(0.42)};${c(0.62)};${c(0.82)};1`}
                                            dur={`${CYCLE_SECONDS}s`}
                                            begin={`${idx * 0.12}s`}
                                            repeatCount="indefinite"
                                        />
                                    </line>

                                    <line
                                        x1={from.targetX}
                                        y1={from.targetY}
                                        x2={to.targetX}
                                        y2={to.targetY}
                                        stroke={lineAccent}
                                        strokeWidth="1.05"
                                        pathLength={100}
                                        strokeDasharray="0 100"
                                        opacity={0}
                                    >
                                        <animate
                                            attributeName="opacity"
                                            values="0;0;0.16;0.34;0.2;0;0"
                                            keyTimes={`0;${c(linkStart - 0.04)};${c(linkStart)};${c(linkPeak)};${c(linkEnd)};${c(linkEnd + 0.05)};1`}
                                            dur={`${CYCLE_SECONDS}s`}
                                            repeatCount="indefinite"
                                        />
                                        <animate
                                            attributeName="stroke-dasharray"
                                            values="0 100;14 86;19 81;14 86;0 100"
                                            keyTimes="0;0.18;0.5;0.82;1"
                                            dur={`${(CYCLE_SECONDS * 0.24).toFixed(2)}s`}
                                            begin={`${(idx * 0.13).toFixed(2)}s`}
                                            repeatCount="indefinite"
                                        />
                                        <animate
                                            attributeName="stroke-dashoffset"
                                            values="95;52;5;-44;-92"
                                            keyTimes="0;0.22;0.5;0.78;1"
                                            dur={`${(CYCLE_SECONDS * 0.24).toFixed(2)}s`}
                                            begin={`${(idx * 0.13 + 0.04).toFixed(2)}s`}
                                            repeatCount="indefinite"
                                        />
                                    </line>
                                </g>
                            );
                        })}
                    </g>

                    {NODES.map((node) => {
                        const fill = node.tone === "bright" ? dotBright : dotSoft;
                        const holdStart = node.inEnd + 0.02;
                        const holdEnd = node.outStart - 0.02;
                        const jitterA = Math.min(holdEnd, holdStart + 0.04);
                        const jitterB = Math.min(holdEnd, holdStart + 0.08);
                        return (
                            <g key={`node-${node.id}`}>
                                <circle cx={node.targetX} cy={node.targetY} r={node.radius} fill={fill} opacity={0}>
                                    <animate
                                        attributeName="opacity"
                                        values="0;0;1;1;0;0"
                                        keyTimes={`0;${c(node.inEnd)};${c(holdStart)};${c(holdEnd)};${c(node.outStart)};1`}
                                        dur={`${CYCLE_SECONDS}s`}
                                        repeatCount="indefinite"
                                    />
                                    <animateTransform
                                        attributeName="transform"
                                        type="translate"
                                        values="0 0;0 0;0.8 -0.7;-0.9 1.1;0 0;0 0;0 0;0 0"
                                        keyTimes={`0;${c(node.inEnd)};${c(holdStart)};${c(jitterA)};${c(jitterB)};${c(holdEnd)};${c(node.outStart)};1`}
                                        dur={`${CYCLE_SECONDS}s`}
                                        repeatCount="indefinite"
                                    />
                                </circle>

                                <circle r={node.radius + 0.2} fill={fill} opacity={0}>
                                    <animateMotion
                                        path={node.incomingPath}
                                        keyPoints="0;0;0.74;1;1"
                                        keyTimes={`0;${c(node.inStart)};${c((node.inStart + node.inEnd) / 2)};${c(node.inEnd)};1`}
                                        dur={`${CYCLE_SECONDS}s`}
                                        repeatCount="indefinite"
                                    />
                                    <animate
                                        attributeName="opacity"
                                        values="0;0;1;1;0;0"
                                        keyTimes={`0;${c(node.inStart)};${c(node.inStart + 0.02)};${c(node.inEnd)};${c(node.inEnd + 0.02)};1`}
                                        dur={`${CYCLE_SECONDS}s`}
                                        repeatCount="indefinite"
                                    />
                                </circle>

                                <circle r={node.radius + 0.2} fill={fill} opacity={0}>
                                    <animateMotion
                                        path={node.outgoingPath}
                                        keyPoints="0;0;0.75;1;1"
                                        keyTimes={`0;${c(node.outStart)};${c((node.outStart + node.outEnd) / 2)};${c(node.outEnd)};1`}
                                        dur={`${CYCLE_SECONDS}s`}
                                        repeatCount="indefinite"
                                    />
                                    <animate
                                        attributeName="opacity"
                                        values="0;0;1;1;0;0"
                                        keyTimes={`0;${c(node.outStart - 0.02)};${c(node.outStart)};${c(node.outEnd)};${c(node.outEnd + 0.02)};1`}
                                        dur={`${CYCLE_SECONDS}s`}
                                        repeatCount="indefinite"
                                    />
                                </circle>
                            </g>
                        );
                    })}
                </>
            ) : (
                <>
                    <g stroke={lineColor} strokeWidth="0.92" strokeLinecap="round" fill="none" opacity="0.26">
                        {STATIC_CONSTELLATION_EDGES.map((edge, idx) => {
                            const from = STATIC_NODE_BY_ID[edge[0]];
                            const to = STATIC_NODE_BY_ID[edge[1]];
                            return <line key={`static-base-${idx}`} x1={from.targetX} y1={from.targetY} x2={to.targetX} y2={to.targetY} />;
                        })}
                    </g>
                    <g stroke={lineAccent} strokeWidth="0.98" strokeLinecap="round" fill="none" opacity="0.18">
                        {STATIC_CONSTELLATION_EDGES.map((edge, idx) => {
                            const from = STATIC_NODE_BY_ID[edge[0]];
                            const to = STATIC_NODE_BY_ID[edge[1]];
                            return <line key={`static-accent-${idx}`} x1={from.targetX} y1={from.targetY} x2={to.targetX} y2={to.targetY} />;
                        })}
                    </g>
                    {STATIC_NODES.map((node) => {
                        const fill = node.tone === "bright" ? dotBright : dotSoft;
                        return <circle key={`static-node-${node.id}`} cx={node.targetX} cy={node.targetY} r={node.radius} fill={fill} opacity={1} />;
                    })}
                </>
            )}

            <circle cx="50" cy="50" r="47" stroke={arenaStroke} strokeWidth="2" fill="none" />
        </svg>
    );
}
