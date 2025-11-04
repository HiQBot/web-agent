# QA Automation Agent

AI-powered QA automation agent using LangGraph for orchestration and browser-use components for browser automation.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    LangGraph Workflow                        │
│  ┌─────────┐    ┌─────────┐    ┌──────────┐    ┌─────────┐│
│  │  Think  │───▶│   Act   │───▶│  Verify  │───▶│ Report  ││
│  └─────────┘    └─────────┘    └──────────┘    └─────────┘│
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Browser-Use Components Layer                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ BrowserSession│  │  DomService  │  │ Tools/Registry│    │
│  │   (CDP)      │  │  (Serializer)│  │  (Actions)    │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

```
onkernal/
├── qa_agent/              # Core QA agent package
│   ├── state.py           # LangGraph state model
│   ├── workflow.py        # LangGraph workflow definition
│   ├── config.py          # Configuration settings
│   ├── nodes/             # LangGraph nodes
│   │   ├── think.py
│   │   ├── act.py
│   │   ├── verify.py
│   │   └── report.py
│   └── ...                # Other modules (to be added)
│
├── api/                   # FastAPI application
│   ├── main.py           # FastAPI app entry point
│   └── routes/           # API routes
│       ├── health.py
│       └── workflow.py
│
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
└── README.md             # This file
```

## Setup

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Configure environment:**
```bash
cp env.example .env
# Edit .env with your API keys
```

3. **Run the API:**
```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### Health Check
- `GET /api/v1/health` - Health check
- `GET /api/v1/ready` - Readiness check

### Workflow
- `POST /api/v1/workflow/run` - Run a QA automation task
- `POST /api/v1/workflow/test-phase-1` - Test Phase 1 structure
- `GET /api/v1/workflow/state/{task_id}` - Get workflow state (TODO)

## Development Phases

### Phase 1: Foundation Setup ✅
- [x] LangGraph state model
- [x] Basic workflow structure
- [x] Node placeholders
- [x] FastAPI structure
- [ ] Browser session integration

### Phase 2: DOM & Browser State Integration
- [ ] DOM service integration
- [ ] Browser state extractor
- [ ] Think node with browser state

### Phase 3: Tools & Actions Integration
- [ ] Tools registry integration
- [ ] Action execution
- [ ] Act node implementation

### Phase 4: Prompt & LLM Integration
- [ ] LLM adapters
- [ ] System prompt adaptation
- [ ] Think node with LLM

### Phase 5: Verification & Validation
- [ ] Verification logic
- [ ] Verify node implementation
- [ ] Conditional routing

### Phase 6: Reporting & Observability
- [ ] Report generation
- [ ] Screenshot capture
- [ ] Result aggregation

### Phase 7: Integration & Testing
- [ ] End-to-end testing
- [ ] Error handling
- [ ] Performance optimization
- [ ] Documentation

## Testing

Test Phase 1 structure:
```bash
curl -X POST http://localhost:8000/api/v1/workflow/test-phase-1
```

Run a task:
```bash
curl -X POST http://localhost:8000/api/v1/workflow/run \
  -H "Content-Type: application/json" \
  -d '{"task": "Navigate to example.com"}'
```

## License

[Your License Here]

