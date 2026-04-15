# Omniverse Retail Shop - Architecture Slide

## Single Slide Version (White Background)

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#4285f4', 'primaryTextColor': '#1a1a1a', 'primaryBorderColor': '#1a1a1a', 'lineColor': '#5f6368', 'secondaryColor': '#f8f9fa', 'tertiaryColor': '#ffffff', 'background': '#ffffff', 'mainBkg': '#ffffff', 'nodeBorder': '#dadce0', 'clusterBkg': '#f8f9fa', 'clusterBorder': '#dadce0', 'titleColor': '#1a1a1a', 'edgeLabelBackground': '#ffffff'}}}%%

flowchart LR
    subgraph USER[" "]
        direction TB
        BROWSER["🖥️ Web Browser"]
    end

    subgraph HOST["HOST MACHINE"]
        direction TB
        UI["Web UI<br/>React/Next.js"]
        BACKEND["Agent Backend<br/>FastAPI + LangGraph"]

        subgraph AGENTS[" "]
            IC["Intent<br/>Classifier"]
            VA["Vision<br/>Agent"]
            DFA["Demand<br/>Agent"]
        end
    end

    subgraph L40S["L40s GPU"]
        direction TB
        KIT["Omniverse Kit<br/>USD Viewer"]
        MSG["Custom Messaging<br/>+ Viewport Capture"]
        STREAM["Kit Livestream<br/>WebSocket"]
    end

    subgraph DYNAMO["DYNAMO - H100"]
        NEM["⚡ Nemotron 30B<br/>Fast Inference"]
    end

    subgraph GX10["GX10 - NVIDIA SPARK"]
        COS["👁️ Cosmos Reason 2<br/>Vision Analysis"]
        GLM["🧠 GLM 4.7<br/>Extended Thinking"]
    end

    BROWSER <--> UI
    UI <--> STREAM
    STREAM <--> KIT
    KIT <--> MSG
    MSG <--> BACKEND

    BACKEND --> IC
    IC --> VA
    IC --> DFA

    VA --> COS
    BACKEND --> NEM
    BACKEND --> GLM

    style USER fill:#ffffff,stroke:#dadce0,stroke-width:0px
    style HOST fill:#e8f0fe,stroke:#4285f4,stroke-width:2px
    style L40S fill:#fce8e6,stroke:#ea4335,stroke-width:2px
    style DYNAMO fill:#e6f4ea,stroke:#34a853,stroke-width:2px
    style GX10 fill:#fef7e0,stroke:#fbbc04,stroke-width:2px
    style AGENTS fill:#ffffff,stroke:#dadce0,stroke-width:1px
```

---

## Horizontal Layout (Better for Wide Slides)

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#4285f4', 'primaryTextColor': '#1a1a1a', 'lineColor': '#5f6368', 'background': '#ffffff', 'mainBkg': '#ffffff', 'clusterBkg': '#f8f9fa'}}}%%

flowchart LR
    subgraph UI_LAYER["👤 USER INTERFACE"]
        WEB["Web Browser<br/>+ React UI"]
    end

    subgraph RENDER_LAYER["🎮 RENDERING - L40s"]
        KIT["Kit App<br/>USD Viewer"]
        LIVE["Livestream<br/>WebSocket"]
        CAP["Viewport<br/>Capture"]
    end

    subgraph AGENT_LAYER["🤖 AI BACKEND - Host"]
        API["FastAPI"]
        GRAPH["LangGraph<br/>Pipeline"]
        ORCH["Model<br/>Orchestrator"]
    end

    subgraph MODEL_LAYER["🧠 AI MODELS"]
        subgraph H100["H100 Dynamo"]
            NEM["Nemotron 30B<br/>⚡ Fast"]
        end
        subgraph SPARK["GX10 Spark"]
            COS["Cosmos R2<br/>👁️ Vision"]
            GLM["GLM 4.7<br/>🧠 Think"]
        end
    end

    WEB <-->|"Stream"| LIVE
    LIVE <--> KIT
    KIT --> CAP
    CAP -->|"Frame"| API
    WEB -->|"Chat"| API

    API --> GRAPH
    GRAPH --> ORCH

    ORCH -->|"Simple Q&A"| NEM
    ORCH -->|"Visual Query"| COS
    ORCH -->|"Complex"| GLM

    style UI_LAYER fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style RENDER_LAYER fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    style AGENT_LAYER fill:#e8f5e9,stroke:#388e3c,stroke-width:2px
    style MODEL_LAYER fill:#fff8e1,stroke:#f57c00,stroke-width:2px
    style H100 fill:#c8e6c9,stroke:#2e7d32,stroke-width:1px
    style SPARK fill:#ffe0b2,stroke:#ef6c00,stroke-width:1px
```

---

## Compact Version (Minimal)

```mermaid
%%{init: {'theme': 'neutral', 'themeVariables': { 'background': '#ffffff'}}}%%

flowchart TB
    USER["👤 User"] --> UI["Web UI"]

    subgraph INFRA["Infrastructure"]
        direction LR

        subgraph L40["🎮 L40s"]
            KIT["Kit App<br/>USD Viewer"]
        end

        subgraph HOST["🖥️ Host"]
            AGENT["Agent Backend<br/>LangGraph"]
        end

        subgraph AI["🧠 AI Cluster"]
            NEM["Nemotron<br/>H100"]
            COS["Cosmos<br/>GX10"]
            GLM["GLM 4.7<br/>GX10"]
        end
    end

    UI <-->|"WebSocket"| KIT
    KIT <-->|"HTTP"| AGENT
    AGENT --> NEM
    AGENT --> COS
    AGENT --> GLM

    style L40 fill:#ffcdd2,stroke:#c62828
    style HOST fill:#bbdefb,stroke:#1565c0
    style AI fill:#c8e6c9,stroke:#2e7d32
```

---

## Data Flow Version

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'background': '#ffffff', 'primaryColor': '#1a73e8', 'lineColor': '#5f6368'}}}%%

flowchart LR
    subgraph INPUT["Input"]
        Q["💬 User Query"]
        V["📷 Viewport"]
    end

    subgraph PROCESS["Processing"]
        INTENT["🎯 Intent<br/>Classification"]

        subgraph ROUTE["Routing"]
            R1["Product"]
            R2["Scene"]
            R3["Forecast"]
            R4["Navigation"]
        end
    end

    subgraph MODELS["AI Models"]
        M1["⚡ Nemotron 30B<br/>H100 Dynamo<br/>Fast Response"]
        M2["👁️ Cosmos R2<br/>GX10 Spark<br/>Vision"]
        M3["🧠 GLM 4.7<br/>GX10 Spark<br/>Deep Think"]
    end

    subgraph OUTPUT["Output"]
        RESP["💬 Response"]
        ACT["🎬 Action"]
    end

    Q --> INTENT
    V --> INTENT
    INTENT --> ROUTE

    R1 --> M2
    R2 --> M2
    R3 --> M1
    R4 --> ACT

    M2 --> M1
    M1 --> RESP
    M3 --> RESP

    style INPUT fill:#e8f0fe,stroke:#4285f4,stroke-width:2px
    style PROCESS fill:#fef7e0,stroke:#f9ab00,stroke-width:2px
    style MODELS fill:#e6f4ea,stroke:#34a853,stroke-width:2px
    style OUTPUT fill:#fce8e6,stroke:#ea4335,stroke-width:2px
    style ROUTE fill:#ffffff,stroke:#dadce0
```

---

## Export Instructions

### Option 1: Mermaid Live Editor
1. Go to https://mermaid.live
2. Paste the diagram code
3. Click "PNG" or "SVG" to download
4. Set background to white in settings

### Option 2: VS Code
1. Install "Markdown Preview Mermaid Support" extension
2. Right-click diagram → "Export as PNG"

### Option 3: GitHub
- Push this file to GitHub, diagrams render automatically

### Recommended Slide Size
- **16:9 aspect ratio** (1920x1080)
- Use the **Horizontal Layout** for wide presentations
- Use **Compact Version** for overview slides
