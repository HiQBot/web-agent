# OnKernal QA Automation Dashboard - Production Enhancement Project

**Status**: Active Development
**Created**: 2025-11-12
**Target Completion**: 2025-11-30
**Version**: 2.0.0 (Production)

---

## PROJECT VISION

Transform the OnKernal QA automation platform from a basic prototype into a **production-grade, modern QA automation dashboard** (2025-2026 standard) with:
- Professional, enterprise-level UI/UX with responsive design
- Real-time WebSocket streaming for live test execution monitoring
- Modal-based browser preview with adaptive sizing
- Modern design patterns using Tailwind CSS + shadcn/ui
- Complete backend API endpoints for real-time communication
- Full TypeScript support across both frontend and backend

---

## PHASE 1: FRONTEND MODERNIZATION & UI ENHANCEMENT

### Goals
- Transform dashboard from basic to production-grade UI
- Implement modern 2025-2026 design patterns
- Add responsive modal for test execution preview
- Implement adaptive browser view component

### Sprint 1.1: UI Library Integration & Design System

**Tasks**:

1. **Install shadcn/ui component library**
   - Add shadcn/ui to frontend (button, modal, tabs, card components)
   - Install required dependencies (radix-ui, class-variance-authority)
   - Update tailwind.config.js with shadcn/ui configuration
   - Status: `pending`

2. **Create design system foundation**
   - Define color palette (modern 2025 theme - maintain dark mode)
   - Create typography system (font hierarchy)
   - Define spacing scale and grid system
   - Document component patterns in design-system.md
   - Status: `pending`

3. **Implement reusable component library**
   - Button variants (primary, secondary, ghost, destructive)
   - Card component with variants
   - Modal/Dialog component wrapper
   - Badge component for test statuses
   - Spinner/Loading states
   - Toast notifications (enhance existing React Hot Toast)
   - Status: `pending`

### Sprint 1.2: Dashboard Redesign

**Tasks**:

1. **Redesign main dashboard layout**
   - Create modern grid-based dashboard
   - Add key metrics cards (Tests Run, Pass Rate, Coverage %)
   - Implement test execution queue/history section
   - Add real-time status indicator
   - Create recent activities/logs section
   - Status: `pending`

2. **Enhance sidebar navigation**
   - Add icons to navigation items
   - Implement collapsible menu with icons-only mode
   - Add breadcrumb navigation
   - Status: `pending`

3. **Implement responsive grid system**
   - Ensure dashboard works on mobile/tablet/desktop
   - Create mobile-first responsive breakpoints
   - Test on various screen sizes
   - Status: `pending`

### Sprint 1.3: Modal-Based Test Execution Preview

**Tasks**:

1. **Create ExecutionModal component**
   - Build modal wrapper with customizable sizing
   - Implement header with close button and test info
   - Add adaptive/resizable container
   - Support fullscreen toggle
   - Status: `pending`

2. **Move browser preview to modal**
   - Extract BrowserView from fixed iframe layout
   - Integrate BrowserView into ExecutionModal
   - Ensure proper iframe sizing within modal
   - Status: `pending`

3. **Implement adaptive sizing**
   - Add resize handles on modal edges
   - Store modal size in localStorage
   - Implement fullscreen toggle
   - Add preset sizes (80%, 90%, 100%)
   - Support manual dimension input
   - Status: `pending`

4. **Add modal trigger to dashboard**
   - "Run Test" button opens ExecutionModal
   - Pass test/plan data to modal
   - Implement modal state management with React Router
   - Status: `pending`

### Sprint 1.4: Test Plans & Execution UI

**Tasks**:

1. **Redesign TestPlans page**
   - Modern test plan card layout
   - Quick actions (Edit, Run, Clone, Delete)
   - Search and filter capabilities
   - Sort options (by date, status, name)
   - Status: `pending`

2. **Enhance TestExecution page**
   - Show execution timeline
   - Display current step information
   - Show action history with results
   - Real-time step counter and progress indicator
   - Status: `pending`

3. **Create Settings page**
   - Add configuration panels (API keys, browser settings)
   - Add preferences section
   - Add about/documentation section
   - Status: `pending`

---

## PHASE 2: WEBSOCKET REAL-TIME STREAMING

### Goals
- Implement WebSocket server in backend
- Create WebSocket client in frontend
- Stream real-time test execution events
- Display live updates on dashboard and modal

### Sprint 2.1: Backend WebSocket Implementation

**Tasks**:

1. **Create WebSocket endpoint**
   - Implement `POST /api/v1/workflow/run-stream` WebSocket endpoint
   - Add session-based WebSocket connection management
   - Implement connection lifecycle (open, message, close, error)
   - Status: `pending`

2. **Implement streaming event system**
   - Create event types enum (WORKFLOW_START, STEP_START, STEP_COMPLETE, ACTION_START, ACTION_COMPLETE, WORKFLOW_COMPLETE, ERROR)
   - Modify workflow nodes to emit events
   - Create event broadcaster/emitter
   - Status: `pending`

3. **Stream node lifecycle events**
   - INIT: emit on browser session creation
   - PLAN: emit on goal decomposition
   - THINK: emit on LLM analysis + action planning
   - ACT: emit on action execution with detailed results
   - VERIFY: emit on verification status
   - REPORT: emit on completion with report
   - Status: `pending`

4. **Handle concurrent WebSocket connections**
   - Implement connection registry (session_id → WebSocket)
   - Handle multiple clients per session (optional)
   - Implement graceful disconnect handling
   - Status: `pending`

### Sprint 2.2: Frontend WebSocket Client

**Tasks**:

1. **Create WebSocket hook**
   - Build useWebSocket custom hook
   - Handle connection lifecycle
   - Implement automatic reconnection with exponential backoff
   - Handle message parsing and event dispatch
   - Status: `pending`

2. **Integrate WebSocket into ExecutionModal**
   - Connect to WebSocket on "Run Test" button click
   - Display real-time status updates
   - Update step counter as events arrive
   - Status: `pending`

3. **Create event listener system**
   - Parse incoming WebSocket messages
   - Dispatch events to UI components
   - Update state based on event type
   - Handle error events with user feedback
   - Status: `pending`

### Sprint 2.3: Real-Time UI Updates

**Tasks**:

1. **Implement live execution timeline**
   - Display steps as they execute
   - Show action results in real-time
   - Highlight current step
   - Status: `pending`

2. **Create live metrics display**
   - Real-time step counter
   - Token usage tracking
   - Estimated cost display
   - Execution time counter
   - Status: `pending`

3. **Add live action log**
   - Display each action as it executes
   - Show action parameters
   - Show action results/errors
   - Support collapsible details
   - Status: `pending`

---

## PHASE 3: BACKEND API ENDPOINTS

### Goals
- Create new REST endpoints for dashboard functionality
- Implement test history/results endpoints
- Create test configuration endpoints
- Add WebSocket streaming endpoint

### Sprint 3.1: Test Management Endpoints

**Tasks**:

1. **GET /api/v1/tests** - List all tests
   - Query parameters: `skip`, `limit`, `status`, `search`
   - Response: List of test plans with metadata
   - Status: `pending`

2. **POST /api/v1/tests** - Create new test
   - Request: Test configuration (name, description, selectors)
   - Response: Created test with ID
   - Status: `pending`

3. **GET /api/v1/tests/{test_id}** - Get test details
   - Response: Full test configuration
   - Status: `pending`

4. **PUT /api/v1/tests/{test_id}** - Update test
   - Request: Updated test configuration
   - Response: Updated test
   - Status: `pending`

5. **DELETE /api/v1/tests/{test_id}** - Delete test
   - Response: Confirmation
   - Status: `pending`

### Sprint 3.2: Test Execution & Results Endpoints

**Tasks**:

1. **POST /api/v1/workflow/run-stream** - Stream test execution (WebSocket)
   - WebSocket endpoint for real-time updates
   - Request: Task, start_url, max_steps
   - Streaming: Event-based messages
   - Status: `pending`

2. **GET /api/v1/executions** - Get execution history
   - Query: `skip`, `limit`, `test_id`, `status`, `date_range`
   - Response: List of past executions with results
   - Status: `pending`

3. **GET /api/v1/executions/{execution_id}** - Get execution details
   - Response: Full execution log, screenshots, GIF
   - Status: `pending`

4. **GET /api/v1/executions/{execution_id}/report** - Get execution report
   - Response: Judge evaluation, summary, metrics
   - Status: `pending`

### Sprint 3.3: Dashboard Metrics Endpoints

**Tasks**:

1. **GET /api/v1/dashboard/metrics** - Dashboard overview metrics
   - Response: Total tests, pass rate, coverage, recent executions
   - Status: `pending`

2. **GET /api/v1/dashboard/activity** - Recent activity log
   - Response: Last 20 executions with status
   - Status: `pending`

3. **GET /api/v1/dashboard/trends** - Execution trends
   - Query: `days` (7, 30, 90)
   - Response: Pass/fail counts per day
   - Status: `pending`

### Sprint 3.4: Configuration Endpoints

**Tasks**:

1. **GET /api/v1/config** - Get configuration
   - Response: Max steps, timeout, model settings
   - Status: `pending`

2. **PUT /api/v1/config** - Update configuration
   - Request: Updated settings
   - Response: Updated config
   - Status: `pending`

---

## PHASE 4: PERSISTENCE & STORAGE

### Goals
- Persist test plans and execution history
- Store execution artifacts (screenshots, GIFs)
- Implement result analysis and reporting

### Tasks (Future):

1. Add database layer (PostgreSQL + SQLAlchemy)
2. Create schemas for tests, executions, results
3. Implement artifact storage (local filesystem or S3)
4. Add result analysis and trend tracking

---

## TECHNICAL SPECIFICATIONS

### Frontend Stack
- **React 18** with TypeScript
- **React Router v6** for routing
- **TanStack React Query** for server state
- **Tailwind CSS** for styling
- **shadcn/ui** for component library
- **Lucide React** for icons
- **React Hot Toast** for notifications
- **Custom WebSocket hook** for real-time updates

### Backend Stack
- **FastAPI** with async support
- **LangGraph** for workflow orchestration
- **Uvicorn** ASGI server
- **Pydantic** for data validation
- **WebSocket support** via FastAPI/Uvicorn
- **JSON logging** for structured logs

### Design Standards
- **Color Scheme**: Dark theme with cyan accents (#22d3ee)
- **Typography**: Inter font family
- **Spacing**: Tailwind's default 4px spacing scale
- **Border Radius**: Consistent rounded corners (md: 6px)
- **Transitions**: Smooth 300ms transitions for interactive elements
- **Responsive Breakpoints**: Mobile (< 640px), Tablet (640-1024px), Desktop (> 1024px)

### Code Standards
- **TypeScript**: Strict mode enabled
- **ESLint**: Configured for React + TypeScript
- **Component Structure**: Functional components with hooks
- **Props**: Typed with TypeScript interfaces/types
- **State Management**: React hooks + Context API + React Query
- **File Organization**: Features-based folder structure

---

## DEPENDENCIES TO ADD

### Frontend
```json
{
  "dependencies": {
    "shadcn-ui": "latest",
    "class-variance-authority": "^0.7.0",
    "cmdk": "^0.2.0",
    "@radix-ui/react-dialog": "^1.1.1",
    "@radix-ui/react-tabs": "^1.0.4",
    "@radix-ui/react-dropdown-menu": "^2.0.5"
  }
}
```

### Backend
```
# WebSocket support (already in Uvicorn)
# Structured logging enhancements
python-json-logger>=2.0.7
```

---

## DELIVERY CHECKLIST

### Phase 1: Frontend UI
- [ ] shadcn/ui installed and configured
- [ ] Design system documented
- [ ] Dashboard redesigned with modern layout
- [ ] Modal component implemented with adaptive sizing
- [ ] TestPlans page modernized
- [ ] TestExecution page enhanced with live indicators
- [ ] Mobile responsiveness verified
- [ ] All components styled with Tailwind + shadcn/ui

### Phase 2: WebSocket
- [ ] WebSocket endpoint implemented
- [ ] Event streaming system working
- [ ] Frontend WebSocket client created
- [ ] Real-time updates displaying in modal
- [ ] Connection management and error handling

### Phase 3: Backend APIs
- [ ] Test management endpoints created
- [ ] Execution history endpoints created
- [ ] Dashboard metrics endpoints created
- [ ] Configuration endpoints created
- [ ] API documentation updated
- [ ] Error handling consistent across endpoints

### Phase 4: Testing & Polish
- [ ] End-to-end tests passing
- [ ] Manual testing on multiple screen sizes
- [ ] Performance optimization (bundle size, API response time)
- [ ] Error messages user-friendly
- [ ] Accessibility (keyboard navigation, screen readers)
- [ ] Browser compatibility verified

---

## SUCCESS METRICS

1. **UI/UX**: Dashboard looks like 2025+ production application
2. **Real-Time**: WebSocket streaming shows live updates without latency
3. **Responsiveness**: Modal works on mobile (320px), tablet (768px), desktop (1920px)
4. **Performance**: Dashboard loads in < 2 seconds
5. **API**: All endpoints documented and tested
6. **Code Quality**: TypeScript strict mode, ESLint passing
7. **Documentation**: PROJECT.md kept updated as source of truth

---

## NEXT STEPS

1. Start with Phase 1, Sprint 1.1 (shadcn/ui installation)
2. Build design system components
3. Redesign dashboard layout
4. Implement modal execution preview
5. Proceed to Phase 2 (WebSocket)
6. Implement Phase 3 (Backend APIs)

---

## GIT WORKFLOW

- **Branch**: `feat/nodes_enhancement_thinking`
- **Commits**: Small, focused commits per feature
- **PR**: Create PR to main branch when phase complete
- **Rollback**: Can revert to specific commits if needed

---

## NOTES

- This is the single source of truth for project requirements
- Update this document as decisions are made
- Each completed task should have timestamp noted
- Keep all implementation decisions documented

---

**Last Updated**: 2025-11-12
**Next Review**: After Phase 1 completion
