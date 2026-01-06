# Brain Dump Atomic Statements

## Summary
Total atoms: 98
By category:
- Features: 32
- Constraints: 8
- Workflows: 15
- Data Entities: 12
- Integrations: 10
- Non-Functional Requirements: 8
- Risks/Concerns: 5
- Vision/Philosophy: 8

---

## Atomic Statements

### Features

| ID | Statement | Source Quote | Category |
|----|-----------|--------------|----------|
| BD-001 | The system shall provide a command-driven interface (not chatbot-style) | "It's not a chatbot. It's not like you're texting someone" | Feature |
| BD-002 | The system shall provide a UI-driven interface | "It's going to be command-driven, UI-driven" | Feature |
| BD-003 | The system shall maintain long-term persistence of information | "there's going to be persistence of information long-term" | Feature |
| BD-004 | The system shall support modular connections/integrations | "modular connections as a sort of idea there" | Feature |
| BD-005 | The system shall allow configuration of MCP servers within a session | "You can configure other MCVs, you can configure other agents" | Feature |
| BD-006 | The system shall support "LLM as a judge" pattern on any input or output | "using on-the-fly patterns like LLM as a judge on any sort of input or output" | Feature |
| BD-007 | The system shall allow users to request multiple perspectives (e.g., 5 different critiques) | "you could have five different perspectives" | Feature |
| BD-008 | The system shall allow combining multiple LLM perspectives into a synthesis | "you could have a single LLM that can combine them in a way" | Feature |
| BD-009 | The system shall enable users to persist results for later reference | "even the result of that that can be for example persisted" | Feature |
| BD-010 | The system shall allow continuing work within the current session after saving | "you can continue talking about this right? And so you can continue doing work" | Feature |
| BD-011 | The system shall support observing state from API endpoints | "you could perhaps observe some state from sort of API end point" | Feature |
| BD-012 | The system shall provide visual representation of observed state | "you can have this visual representation of this state" | Feature |
| BD-013 | The system shall support live dashboards via polling or WebSocket | "you could literally have this live dashboard of this state" | Feature |
| BD-014 | The system shall support state mutation through integrations | "perhaps you could implement some integrations to alter the state" | Feature |
| BD-015 | The system shall display a task DAG (Directed Acyclic Graph) | "we have a like a task DAG, a task directed acyclic graph" | Feature |
| BD-016 | The system shall support self-modifying workflows | "self-modifying workflow... it could be self-modifying" | Feature |
| BD-017 | The system shall allow requesting new MCP servers that adhere to standards | "we could request like hey I want this mcp server and then it does it" | Feature |
| BD-018 | The system shall provide a text box input for context entry | "just imagine like a text box right... just a way to get context into this system" | Feature |
| BD-019 | The system shall support drag-and-drop file input | "maybe you could drag files to it" | Feature |
| BD-020 | The system shall support microphone/voice input | "maybe there's speech-to-speech with real-time tool calls" | Feature |
| BD-021 | The system shall provide a canvas for stateful context management | "this canvas... it's really just this place that is stateful, it can hold context" | Feature |
| BD-022 | The system shall support nodes on the canvas with labels | "you have 10 nodes open and they have labels" | Feature |
| BD-023 | The system shall support documents on the canvas | "maybe there are 5 documents" | Feature |
| BD-024 | The system shall support audio blocks on the canvas | "You have audio blocks, for example" | Feature |
| BD-025 | The system shall display streaming updates from jobs via WebSocket | "Maybe we're getting like WebSocket streaming or some sort of state streaming to the UI" | Feature |
| BD-026 | The system shall support user commands to configure MCP servers | "some sort of user commands to configure a specific model context protocol server" | Feature |
| BD-027 | The system shall render assumptions on the UI in a dedicated area | "that can be you know rendered on the ui and it can have its own like dedicated space" | Feature |
| BD-028 | The system shall support button-based responses to assumptions | "maybe there are buttons associated with it" | Feature |
| BD-029 | The system shall support capturing "random eureka" thoughts/notes | "for random eureka you know like you know thoughts to the mind" | Feature |
| BD-030 | The system shall support labeling notes quickly | "we want to be able to get down our random ass notes add a little labeling" | Feature |
| BD-031 | The system shall support highly annotatable graphs | "highly annotatable graphs, right? So we're talking about no just about relations potentially" | Feature |
| BD-032 | The system shall allow clicking nodes to bring up associated information | "I click the node and then the information is brought up" | Feature |

### Constraints

| ID | Statement | Source Quote | Category |
|----|-----------|--------------|----------|
| BD-033 | The system must NOT be a chatbot/texting interface | "It's not a chatbot. It's not like you're texting someone" | Constraint |
| BD-034 | The system must NOT be like ChatGPT's artifact-on-the-side model | "It's not like you're on that like ChatGPT or Claude... you can't really quickly update" | Constraint |
| BD-035 | New MCP servers must pass security checks | "pass some security check" | Constraint |
| BD-036 | New MCP servers must adhere to specified standards | "adhere to some specified standards" | Constraint |
| BD-037 | New MCP servers must be set up in a particular environment | "they have to be set up in some particular environment" | Constraint |
| BD-038 | Context decomposition must be granular but not redundant | "we want to be granular, but not too, not redundant" | Constraint |
| BD-039 | The system must define boundaries for user alterations to canvas | "We'll obviously have to define boundaries and stuff" | Constraint |
| BD-040 | Agents must have controlled delete capabilities | "with the agents they can up you know they can delete so that this is this is an important thing to consider" | Constraint |

### Workflows

| ID | Statement | Source Quote | Category |
|----|-----------|--------------|----------|
| BD-041 | Deep research job workflow: send off research task, receive streaming updates | "you have a deep research job that was sent off" | Workflow |
| BD-042 | LLM-as-judge workflow: critique deep research reports with multiple perspectives | "I want to do an LLM as a judge, and I want to critique something about this deep research report" | Workflow |
| BD-043 | Context routing workflow: route input to appropriate handlers | "context routing... route input to appropriate handlers" | Workflow |
| BD-044 | Intent/meaning deciphering workflow for user input | "decipher the intent/meaning. Sure, the user said some shit, and we got to figure out what the hell they mean" | Workflow |
| BD-045 | Assumption reconciliation workflow: present assumptions to user for approval | "we want to like reconcile or approve you know like with the user" | Workflow |
| BD-046 | Audio block analysis workflow: record audio, then analyze with agents | "I have an audio block and I'm just you know maybe on the canvas and I click like new like audio block or something I just have like a 30 minute spiel" | Workflow |
| BD-047 | Multiple deep research reports spawned from a single tangent | "maybe I want to do like multiple deep research reports that will go off and be sent based on this based on this tangent" | Workflow |
| BD-048 | Hypothesis testing workflow with LLM judges | "maybe we're testing hypotheses you know maybe we're debating" | Workflow |
| BD-049 | Collaborative planning workflow with agentic system | "collaborate on a plan in the agentic system, collaborate on a plan" | Workflow |
| BD-050 | Plan to task DAG conversion workflow | "you could get it and like the task tag for it" | Workflow |
| BD-051 | Task DAG to Google Docs export workflow | "send that bitch to your Google Docs" | Workflow |
| BD-052 | Task completion state mutation workflow with propagation | "you can mutate the state of the task tag in that and that mutation would propagate it" | Workflow |
| BD-053 | Associative search workflow through connected knowledge base | "some predefined like associative sort of search throughout some sort of connected knowledge base" | Workflow |
| BD-054 | Predefined analysis workflows that can be applied to thoughts | "some sort of a useful analysis workflow that we can just throw with that thing" | Workflow |
| BD-055 | Deterministic hooks after specific lifecycles | "deterministic hooks after specific life cycles or something like that" | Workflow |

### Data Entities

| ID | Statement | Source Quote | Category |
|----|-----------|--------------|----------|
| BD-056 | Canvas: stateful space holding context, nodes, documents, audio blocks | "this canvas... it's really just this place that is stateful, it can hold context" | Data |
| BD-057 | Nodes: labeled entities on the canvas | "you have 10 nodes open and they have labels" | Data |
| BD-058 | Documents: persistable text/content entities | "maybe there are 5 documents" | Data |
| BD-059 | Audio blocks: recorded audio entities on canvas | "You have audio blocks" | Data |
| BD-060 | Jobs: asynchronous tasks (e.g., deep research) | "We have jobs, I don't know, just a concept" | Data |
| BD-061 | Assumption structure: container for inferred intent/meaning | "we can have this idea of like, we have assumptions... some sort of container, some sort of state for like, assumptions" | Data |
| BD-062 | User intent/meaning index: persisted index of user behavior patterns | "utilizing a persisted user intent meaning index" | Data |
| BD-063 | Task DAG: structured task representation with granularities | "we have a like a task DAG, a task directed acyclic graph, and it has like granularities to display" | Data |
| BD-064 | Single source of truth: external state being observed/mirrored | "perhaps it's some single source of truth for something particular" | Data |
| BD-065 | Knowledge base: connected persisted information store | "connected knowledge base" | Data |
| BD-066 | Session: the current working context with agents | "in the current session with the adjunct system" | Data |
| BD-067 | Basic data structures with UI mappings (like Coda) | "maybe there are some basic data structures like in Coda that have mappings to the UI" | Data |

### Integrations

| ID | Statement | Source Quote | Category |
|----|-----------|--------------|----------|
| BD-068 | Google Calendar MCP server integration | "there could be a calendar model context protocol server. I know Google has a Google Calendar MCV server" | Integration |
| BD-069 | Agent can alter Google Calendar | "the agent can alter our calendar" | Integration |
| BD-070 | Model Context Protocol (MCP) as integration standard | "hook up a Google Calendar MCV" | Integration |
| BD-071 | Agent-to-Agent Protocol support | "do something with agent agent protocol" | Integration |
| BD-072 | WebSocket/polling for live state observation | "it's like a WebSocket or something" | Integration |
| BD-073 | API endpoint state observation | "observe some state from sort of API end point maybe the agent could grab it from a server" | Integration |
| BD-074 | Google Docs integration for task DAG export | "send that bitch to your Google Docs" | Integration |
| BD-075 | Calendar integration for reminders | "you can have that associated directly with your calendar, for example, you can get reminders sent to you" | Integration |
| BD-076 | Obsidian as potential persistence backend | "or we just kind of run like Obsidian" | Integration |
| BD-077 | Git repos for backups | "use like Git repos for for backups" | Integration |

### Non-Functional Requirements

| ID | Statement | Source Quote | Category |
|----|-----------|--------------|----------|
| BD-078 | System must be highly interactive (not static artifact generation) | "this is going to be a far more interactive experience" | NFR |
| BD-079 | System must be stateful across sessions | "a more stateful experience" | NFR |
| BD-080 | System must support high velocity/throughput workflows | "what we've described is pretty high velocity pretty high throughput" | NFR |
| BD-081 | System must be reliable | "we need reliability" | NFR |
| BD-082 | System should augment user's working memory | "augmenting my fucking working memory. That's exactly what I'm doing" | NFR |
| BD-083 | Context must be accessible to both user and agents | "it will be accessible to you, right? Accessible. And same to the agents" | NFR |
| BD-084 | System must support focus/specificity with tasks (context not always fully utilized) | "We know about context draw, we know about specificity with the tasks, right? It's important to have focus" | NFR |
| BD-085 | System must scale to complex, dynamic workflows | "this goes to very dynamic and complex workflows that are achievable here" | NFR |

### Risks/Concerns

| ID | Statement | Source Quote | Category |
|----|-----------|--------------|----------|
| BD-086 | Risk of losing information during context decomposition | "Ideally, we have a good system that's not going to sit here and lose information" | Risk |
| BD-087 | Concern about user referencing capability limitations | "Maybe they're saying something that we just don't have the capability to handle" | Risk |
| BD-088 | Need to handle cases where tooling/MCP is not set up | "maybe that we don't have the tooling, like MCP set up" | Risk |
| BD-089 | Decision needed: dedicated database vs Obsidian/Git for persistence | "do we want a whole uh database for this or we or we just kind of run like Obsidian maybe use like Git repos" | Risk |
| BD-090 | Agent delete capabilities need careful consideration | "with the agents they can up you know they can delete so that this is this is an important thing to consider" | Risk |

### Vision/Philosophy

| ID | Statement | Source Quote | Category |
|----|-----------|--------------|----------|
| BD-091 | This is an "agentic system" not a single agent | "this is not only a single agent; it's like an agentic system" | Vision |
| BD-092 | Pattern expected to be widely adopted but can be specialized | "I see this being a very widely adopted pattern, but it can be modular" | Vision |
| BD-093 | Agents are first-class citizens of the program | "the agents or like s class you know like first class right citizens to the program" | Vision |
| BD-094 | Agent experience heavily augments the software | "the agent experience can augment the software so much such that we're going to be heavily relying on the agents" | Vision |
| BD-095 | Shift from chatbot to immersive command/intent-oriented workspace | "This is more of an immersive you know command intent oriented like workspace" | Vision |
| BD-096 | Inference-time compute at user's fingertips | "That's like an example of inference time compute literally at the tip of your fingers" | Vision |
| BD-097 | User controls compute allocation ("throw more compute at it") | "You can throw more compute at it if that's what you wish" | Vision |
| BD-098 | Pre-MVP/Alpha scope acknowledgment | "that's like the alpha in our pre-MVP idea" | Vision |

---

## Ambiguous Items Flagged for Validation

| ID | Statement | Ambiguity | Needs Clarification |
|----|-----------|-----------|---------------------|
| BD-016 | Self-modifying workflows | Unclear scope - does this mean adding MCPs only, or broader self-modification? | Define boundaries of self-modification |
| BD-020 | Speech-to-speech with real-time tool calls | Mentioned as "maybe" - unclear if in scope for MVP | Confirm if voice I/O is MVP scope |
| BD-055 | Deterministic hooks after specific lifecycles | Vague on what lifecycles and what hooks | Define lifecycle events |
| BD-067 | Basic data structures with UI mappings like Coda | Coda reference unclear - needs specification | Define what data structures map to what UI |
| BD-076 | Obsidian as persistence backend | Listed as alternative, not decided | Decide persistence strategy |
| BD-077 | Git repos for backups | Listed as consideration, not decided | Decide backup strategy |
| BD-089 | Database vs Obsidian/Git decision | Explicitly marked as undecided | Requires architectural decision |

---

## Cross-Reference Index

### Input Mechanisms
- BD-018: Text box input
- BD-019: Drag-and-drop files
- BD-020: Voice/microphone input
- BD-024: Audio blocks on canvas

### Output/Display Mechanisms
- BD-012: Visual state representation
- BD-013: Live dashboards
- BD-015: Task DAG display
- BD-021: Canvas
- BD-022: Nodes with labels
- BD-025: Streaming updates
- BD-027: Assumption rendering area
- BD-031: Annotatable graphs

### Agent/AI Capabilities
- BD-006: LLM as judge
- BD-007: Multiple perspectives
- BD-008: Perspective synthesis
- BD-044: Intent/meaning deciphering
- BD-062: User intent index utilization

### Persistence & State
- BD-003: Long-term persistence
- BD-009: Result persistence
- BD-056: Canvas state
- BD-064: Single source of truth observation
- BD-065: Knowledge base
- BD-076/BD-077: Obsidian/Git options

### Integration Points
- BD-068-BD-075: All external integrations
- BD-070: MCP standard
- BD-071: Agent-to-Agent Protocol
