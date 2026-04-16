# Omniverse Retail Shop - System Architecture

## Overview
This document describes the complete system architecture for the Omniverse Retail Shop digital twin platform with AI-powered chat assistance.

---

## High-Level System Diagram

```mermaid
flowchart TB
    subgraph USER["User Layer"]
        UI["Web UI\n(React/Next.js)\n📱 Host Machine"]
    end

    subgraph HOST["Host Machine"]
        subgraph AGENT_BACKEND["Agent Backend (FastAPI)"]
            API["REST API\n/api/chat\n/api/analyze"]
            LANGGRAPH["LangGraph\nChat Pipeline"]

            subgraph AGENTS["AI Agents"]
                IC["Intent Classifier"]
                VA["Vision Agent"]
                DFA["Demand Forecast\nAgent"]
                ECA["E-Commerce\nSearch Agent"]
            end

            subgraph SERVICES["Services"]
                MO["Model\nOrchestrator"]
                SM["Session\nManager"]
                KB["Knowledge\nBase"]
            end
        end
    end

    subgraph L40S["L40s GPU Server"]
        subgraph KIT_APP["NVIDIA Omniverse Kit App"]
            USD["USD Viewer\n& Renderer"]

            subgraph MESSAGING["Custom Messaging System"]
                CMM["CustomMessageManager"]
                AC["AgentClient"]
                VC["ViewportCapture"]
                CN["CameraNavigation"]
            end

            LIVESTREAM["Kit Livestream\nWebSocket"]
        end
    end

    subgraph DYNAMO["Dynamo Cluster (H100)"]
        NEMOTRON["Nemotron 30B\n(nvidia/NVIDIA-Nemotron-3-Nano-30B)\n⚡ Fast Responses\nvLLM Server"]
    end

    subgraph GX10["GX10 (NVIDIA Spark)"]
        COSMOS["Cosmos Reason 2\n🔮 Vision Analysis\nImage Understanding"]
        GLM["GLM 4.7 Flash\n🧠 Extended Thinking\nComplex Reasoning\nvLLM Server"]
    end

    %% User to UI
    UI -->|"User Chat\n& Navigation"| LIVESTREAM
    LIVESTREAM -->|"Video Stream\n& Events"| UI

    %% UI to Kit App
    LIVESTREAM <-->|"WebSocket\nMessages"| CMM

    %% Kit App Internal
    CMM --> AC
    CMM --> VC
    CMM --> CN
    AC <-->|"HTTP REST"| API

    %% Agent Backend Flow
    API --> LANGGRAPH
    LANGGRAPH --> IC
    IC -->|"Route by Intent"| VA
    IC -->|"Route by Intent"| DFA
    IC -->|"Route by Intent"| ECA

    VA --> MO
    DFA --> MO
    ECA --> MO

    LANGGRAPH --> SM
    LANGGRAPH --> KB

    %% Model Orchestrator to Models
    MO -->|"Simple Q&A\n(reasoning OFF)"| NEMOTRON
    MO -->|"Complex Tasks\n(deep thinking)"| GLM
    VA -->|"Image Analysis"| COSMOS

    %% Responses back
    NEMOTRON -->|"Fast Response"| MO
    GLM -->|"Reasoned Response"| MO
    COSMOS -->|"Scene Analysis"| VA

    classDef userLayer fill:#e1f5fe,stroke:#01579b
    classDef hostLayer fill:#fff3e0,stroke:#e65100
    classDef gpuLayer fill:#f3e5f5,stroke:#7b1fa2
    classDef dynamoLayer fill:#e8f5e9,stroke:#2e7d32
    classDef sparkLayer fill:#fce4ec,stroke:#c2185b

    class USER userLayer
    class HOST,AGENT_BACKEND,AGENTS,SERVICES hostLayer
    class L40S,KIT_APP,MESSAGING gpuLayer
    class DYNAMO dynamoLayer
    class GX10 sparkLayer
```

---

## Detailed Component Architecture

```mermaid
flowchart LR
    subgraph UI_LAYER["UI Layer - Host Machine"]
        WEB["Web Browser"]
        REACT["React/Next.js\nFrontend"]
    end

    subgraph STREAMING["Streaming Layer - L40s"]
        WS["WebSocket\nConnection"]
        PIXELSTREAM["Kit Livestream\nPixel Streaming"]
    end

    subgraph KIT["Kit Application - L40s GPU"]
        direction TB

        subgraph CORE["Core Components"]
            USD_STAGE["USD Stage\n& Scene Graph"]
            VIEWPORT["Viewport\nRenderer"]
            TIMELINE["Timeline\nController"]
        end

        subgraph EXT["USD Viewer Messaging Extension"]
            CMM2["CustomMessageManager"]

            subgraph HANDLERS["Message Handlers"]
                CHAT_H["chatMessage\nHandler"]
                NAV_H["Navigation\nHandler"]
                PARAM_H["Parameter\nHandler"]
            end

            subgraph UTILS["Utilities"]
                VC2["ViewportCapture\n(Frame Grabber)"]
                CN2["CameraNavigation\n(Location Presets)"]
                AC2["AgentClient\n(HTTP Client)"]
            end
        end
    end

    WEB <--> REACT
    REACT <--> WS
    WS <--> PIXELSTREAM
    PIXELSTREAM <--> VIEWPORT
    PIXELSTREAM <--> CMM2

    CMM2 --> HANDLERS
    CMM2 --> UTILS
    UTILS --> USD_STAGE
    UTILS --> VIEWPORT

    classDef ui fill:#bbdefb
    classDef streaming fill:#c8e6c9
    classDef kit fill:#ffe0b2

    class UI_LAYER ui
    class STREAMING streaming
    class KIT,CORE,EXT,HANDLERS,UTILS kit
```

---

## AI Agent Pipeline (LangGraph)

```mermaid
flowchart TB
    subgraph INPUT["Input"]
        REQ["ChatRequest\n• message\n• session_id\n• frame_data\n• context"]
    end

    subgraph GRAPH["LangGraph Chat Pipeline"]
        direction TB

        CLASSIFY["classify_intent"]
        LOAD_CTX["load_context"]

        subgraph ROUTE["Intent Router"]
            GREETING["handle_greeting"]
            PRODUCT["handle_product_inquiry"]
            SCENE["handle_scene_query"]
            NAV["handle_navigation"]
            DEMAND["handle_demand_forecast"]
            EC["handle_ec_search"]
            QA["handle_general_qa"]
        end

        SAVE["save_to_history"]
    end

    subgraph MODELS["Model Selection"]
        direction LR
        NEM_FAST["Nemotron\n⚡ Fast\n(reasoning OFF)"]
        NEM_THINK["Nemotron\n💭 Thinking\n(reasoning ON)"]
        GLM_DEEP["GLM 4.7\n🧠 Deep\nThinking"]
        COSMOS_VIS["Cosmos Reason2\n👁️ Vision"]
    end

    subgraph OUTPUT["Output"]
        RESP["ChatResponse\n• message\n• action\n• action_params\n• metadata"]
    end

    REQ --> CLASSIFY
    CLASSIFY --> LOAD_CTX

    LOAD_CTX -->|"GREETING"| GREETING
    LOAD_CTX -->|"PRODUCT_INQUIRY"| PRODUCT
    LOAD_CTX -->|"SCENE_QUERY"| SCENE
    LOAD_CTX -->|"NAVIGATION"| NAV
    LOAD_CTX -->|"DEMAND_FORECAST"| DEMAND
    LOAD_CTX -->|"EC_SEARCH"| EC
    LOAD_CTX -->|"GENERAL_QA"| QA

    GREETING --> SAVE
    PRODUCT --> SAVE
    SCENE --> SAVE
    NAV --> SAVE
    DEMAND --> SAVE
    EC --> SAVE
    QA --> SAVE

    PRODUCT -->|"Visual Query"| COSMOS_VIS
    SCENE -->|"Visual Query"| COSMOS_VIS
    QA -->|"Simple"| NEM_FAST
    DEMAND -->|"Analysis"| NEM_THINK
    EC -->|"Search"| NEM_FAST

    COSMOS_VIS -->|"Enriched\nResponse"| GLM_DEEP

    SAVE --> RESP

    classDef input fill:#e3f2fd
    classDef graph fill:#fff8e1
    classDef models fill:#fce4ec
    classDef output fill:#e8f5e9

    class INPUT input
    class GRAPH,ROUTE graph
    class MODELS models
    class OUTPUT output
```

---

## Infrastructure Topology

```mermaid
flowchart TB
    subgraph NETWORK["Network Infrastructure"]
        direction TB

        subgraph HOST_ZONE["Host Zone"]
            HOST_MACHINE["🖥️ Host Machine\n━━━━━━━━━━━━━\n• Web UI (React/Next.js)\n• Agent Backend (FastAPI)\n• Port 8000: API\n• Port 3000: Frontend"]
        end

        subgraph GPU_ZONE["GPU Rendering Zone"]
            L40S_SERVER["🎮 L40s Server\n━━━━━━━━━━━━━\n• NVIDIA Omniverse Kit\n• USD Viewer Extension\n• Real-time RTX Rendering\n• Kit Livestream\n• WebSocket: 8899"]
        end

        subgraph AI_ZONE["AI Inference Zone"]
            direction LR

            DYNAMO_H100["⚡ Dynamo (H100)\n━━━━━━━━━━━━━\nNemotron 30B\n• vLLM Server\n• Fast inference\n• 172.20.166.1:8353"]

            GX10_SPARK["🧠 GX10 (NVIDIA Spark)\n━━━━━━━━━━━━━\nCosmos Reason 2\n• 172.20.166.5:8000\n━━━━━━━━━━━━━\nGLM 4.7 Flash\n• Deep Thinking\n• 172.20.166.6:8000"]
        end
    end

    HOST_MACHINE <-->|"HTTP\nPort 8000"| L40S_SERVER
    HOST_MACHINE <-->|"HTTP/REST\nAPI Calls"| DYNAMO_H100
    HOST_MACHINE <-->|"HTTP/REST\nAPI Calls"| GX10_SPARK
    L40S_SERVER <-->|"WebSocket\nPixel Stream"| HOST_MACHINE

    classDef host fill:#e3f2fd,stroke:#1565c0
    classDef gpu fill:#f3e5f5,stroke:#7b1fa2
    classDef ai fill:#e8f5e9,stroke:#2e7d32

    class HOST_ZONE host
    class GPU_ZONE gpu
    class AI_ZONE ai
```

---

## Message Flow Sequence

```mermaid
sequenceDiagram
    participant U as User (Browser)
    participant UI as Web UI
    participant WS as WebSocket
    participant KIT as Kit App (L40s)
    participant CMM as CustomMessageManager
    participant API as Agent Backend
    participant IC as Intent Classifier
    participant MO as Model Orchestrator
    participant NEM as Nemotron (H100)
    participant COS as Cosmos (GX10)
    participant GLM as GLM 4.7 (GX10)

    Note over U,GLM: User asks about products they're viewing

    U->>UI: "What snacks are on this shelf?"
    UI->>WS: chatMessage event
    WS->>KIT: Forward message
    KIT->>CMM: Handle chatMessage

    CMM->>CMM: Capture camera position
    CMM->>API: POST /api/chat
    API->>IC: Classify intent
    IC-->>API: SCENE_QUERY (requires_visual=true)

    API-->>CMM: action: capture_frame
    CMM->>CMM: ViewportCapture
    CMM->>API: POST /api/analyze (with frame)

    API->>COS: Analyze image
    COS-->>API: Scene analysis + products detected

    API->>MO: Generate response
    MO->>NEM: Simple response (fast)
    NEM-->>MO: Response text

    MO-->>API: Final response
    API-->>CMM: ChatResponse
    CMM->>WS: chatResponse event
    WS->>UI: Display response
    UI->>U: "I can see Pringles and Cheetos..."

    Note over U,GLM: User asks complex question

    U->>UI: "Compare demand forecast for these products"
    UI->>WS: chatMessage
    WS->>KIT: Forward
    KIT->>CMM: Handle
    CMM->>API: POST /api/chat
    API->>IC: Classify
    IC-->>API: DEMAND_FORECAST

    API->>MO: Complex analysis needed
    MO->>GLM: Deep thinking mode
    GLM-->>MO: Detailed analysis

    MO-->>API: Response with reasoning
    API-->>CMM: ChatResponse
    CMM->>WS: chatResponse
    WS->>UI: Display with expandable reasoning
```

---

## Data Flow Summary

```mermaid
flowchart LR
    subgraph USER_INPUT["User Input"]
        MSG["Chat Message"]
        NAV["Navigation\nRequest"]
        VIS["Visual\nQuery"]
    end

    subgraph PROCESSING["Processing Pipeline"]
        direction TB

        INTENT["Intent\nClassification"]

        subgraph ACTIONS["Agent Actions"]
            FRAME["Capture\nFrame"]
            NAVIGATE["Camera\nNavigation"]
            SEARCH["Knowledge\nSearch"]
        end

        subgraph AI_PROC["AI Processing"]
            VISION["Vision\nAnalysis"]
            TEXT["Text\nGeneration"]
            REASONING["Extended\nReasoning"]
        end
    end

    subgraph MODELS_USED["Models Used"]
        N30B["Nemotron 30B\n(Dynamo H100)"]
        CR2["Cosmos Reason2\n(GX10)"]
        G47["GLM 4.7\n(GX10)"]
    end

    subgraph OUTPUT_RESP["Response"]
        CHAT_RESP["Chat\nResponse"]
        ACTION_CMD["Action\nCommand"]
        META["Metadata\n& Context"]
    end

    MSG --> INTENT
    NAV --> INTENT
    VIS --> INTENT

    INTENT --> FRAME
    INTENT --> NAVIGATE
    INTENT --> SEARCH

    FRAME --> VISION
    SEARCH --> TEXT
    VISION --> REASONING

    VISION -.-> CR2
    TEXT -.-> N30B
    REASONING -.-> G47

    VISION --> CHAT_RESP
    TEXT --> CHAT_RESP
    REASONING --> CHAT_RESP
    NAVIGATE --> ACTION_CMD

    CHAT_RESP --> META
    ACTION_CMD --> META

    classDef input fill:#e1f5fe
    classDef process fill:#fff3e0
    classDef models fill:#f3e5f5
    classDef output fill:#e8f5e9

    class USER_INPUT input
    class PROCESSING,ACTIONS,AI_PROC process
    class MODELS_USED models
    class OUTPUT_RESP output
```

---

## Component Summary Table

| Component | Location | Purpose | Technology |
|-----------|----------|---------|------------|
| **Web UI** | Host Machine | User interface for chat & visualization | React/Next.js |
| **Agent Backend** | Host Machine | AI orchestration & API | FastAPI + LangGraph |
| **Kit App** | L40s GPU | USD rendering & streaming | NVIDIA Omniverse Kit |
| **Custom Messaging** | L40s GPU | Kit ↔ Backend communication | Python Extension |
| **Nemotron 30B** | Dynamo (H100) | Fast text generation | vLLM Server |
| **Cosmos Reason2** | GX10 (Spark) | Vision/image analysis | Custom API |
| **GLM 4.7 Flash** | GX10 (Spark) | Extended thinking/reasoning | vLLM Server |

---

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/chat` | POST | Process chat messages |
| `/api/analyze` | POST | Analyze captured frames |
| `/api/session/{id}` | GET | Get session info |
| `/api/products/search` | GET | Search product catalog |
| `/health` | GET | Health check |

---

## Intent Types & Routing

| Intent | Handler | Model Used | Action |
|--------|---------|------------|--------|
| `GREETING` | `handle_greeting` | None (static) | None |
| `PRODUCT_INQUIRY` | `handle_product_inquiry` | Nemotron/Cosmos | capture_frame |
| `SCENE_QUERY` | `handle_scene_query` | Cosmos → Nemotron | capture_frame |
| `NAVIGATION` | `handle_navigation` | None | navigate_to |
| `DEMAND_FORECAST` | `handle_demand_forecast` | Nemotron/GLM | forecast_demand |
| `EC_SEARCH` | `handle_ec_search` | Nemotron | search_ec |
| `GENERAL_QA` | `handle_general_qa` | Nemotron | None |
