# web-agent

**Agentic Web AI automation powered by LangGraph, integrated with OnKernal Browser**

An open-source project by [HiQBot](https://hiqbot.com) for computer-use style web automation driven by AI agents.

## What It Does

`web-agent` is an intelligent web automation system that leverages Large Language Models to autonomously navigate websites, interact with web elements, and complete complex multi-step tasks—just like a human user would. Simply provide natural language instructions, and the agent handles the rest: analyzing page structures, filling forms, clicking buttons, extracting data, and adapting to dynamic content.

## How It Works

Built on **LangGraph** (state graph orchestration), the agent follows a structured AI-driven workflow:

1. **INIT** → Launches OnKernal Browser session via Chrome DevTools Protocol (CDP)
2. **PLAN** → LLM decomposes complex tasks into major phases with completion signals
3. **THINK** → Analyzes real-time DOM state, plans next actions, updates task progress
4. **ACT** → Executes browser actions (click, type, navigate, scroll) and waits for page stability
5. **Loop** → THINK ⟷ ACT cycle repeats until task completion or max steps reached
6. **REPORT** → Generates execution summary with optional LLM judge evaluation and GIF visualization

The agent uses **OpenAI models** (currently) to make intelligent decisions based on:
- Full DOM tree with semantic accessibility attributes
- Dynamic element detection (new elements marked after actions)
- Task progress tracked in auto-generated `todo.md` files
- Multi-tab handling and navigation context
- Screenshot capture for multimodal understanding

**Architecture**: Computer-use style with enhanced state tracking—THINK sees the full browser state (like a QA tester), ACT executes and detects changes, and the LangGraph workflow manages iterative loops with built-in error recovery.

## Key Features

- 🤖 **AI-Powered**: LLM decision-making with full DOM awareness and contextual reasoning
- 🌐 **OnKernal Browser**: Seamless automation via CDP (Chrome DevTools Protocol)
- 🔄 **Adaptive Loop**: THINK-ACT cycle dynamically responds to page changes
- 📸 **Visual Intelligence**: Screenshot capture, GIF generation, and judge evaluation
- 📊 **Auto Task Management**: LLM-generated `todo.md` with progress tracking
- 🔌 **API-First Design**: FastAPI with RESTful endpoints + WebSocket streaming
- 🧠 **Stateful Workflow**: LangGraph state management with session persistence
- 🎯 **Goal Detection**: Identifies phase completion via URL/title changes
- 🖥️ **Modern Frontend**: React-based UI for real-time monitoring and control

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **Workflow Engine** | LangGraph v1.0 (StateGraph) |
| **LLM Provider** | OpenAI API (gpt-4-mini, gpt-4, o1-preview) |
| **Browser Automation** | OnKernal Browser + CDP |
| **API Framework** | FastAPI (async, WebSocket support) |
| **Frontend** | React 18 + TypeScript + Tailwind CSS |
| **Language** | Python 3.12+ |
| **DOM Serialization** | Custom CDP-based extractor with accessibility tree |

## Coming Soon

- 🔍 **In-Node Scraping**: Enhanced data extraction within workflow nodes
- 👁️ **Multimodal Support**: Vision-based page understanding (screenshot analysis)
- 🔌 **Multi-LLM Integration**: Anthropic (Claude), Google (Gemini), and open-source models
- ⚡ **Performance Optimizations**: Faster DOM processing and action execution

## Quick Start

### Browser Provider Selection

This project supports two browser providers:
- **OnKernal**: Remote browser via Docker (recommended for production)
- **Chrome**: Local Chrome/Chromium browser (easier for development)

Select your provider by setting `BROWSER_PROVIDER` in your `.env` file:
```bash
BROWSER_PROVIDER=onkernal  # or "chrome"
```

### Live Preview Support 🎥

Both browser providers support **Live Preview** - watch the browser in real-time as the AI performs actions:

#### OnKernal Browser
Streams via WebRTC iframe (runs in Docker container). No additional setup needed.

#### Local Chrome Browser
Streams via CDP screencast to a canvas element. Chrome window will be visible on your desktop AND streamed to Live Preview.

### OnKernal Browser Setup

**Required when `BROWSER_PROVIDER=onkernal`**

OnKernal provides a Docker-based browser service that exposes Chrome DevTools Protocol (CDP) for automation.

```bash
# Clone the OnKernal repository
git clone https://github.com/onkernel/kernel-images.git
cd kernel-images/images/chromium-headful

# Build the Docker image
./build-docker.sh

# Run the browser with WebRTC enabled (for live streaming UI to frontend)
# Note: UKC_TOKEN is not required for local development
export IMAGE=kernel-docker && \
export ENABLE_WEBRTC=true && \
export WITH_KERNEL_IMAGES_API=true && \
./run-docker.sh
```

**Why WebRTC?** WebRTC enables live streaming of the browser UI to your frontend. When `ENABLE_WEBRTC=true`, the browser UI on port 8080 streams video/audio in real-time, allowing you to watch browser automation as it happens in the React frontend. This is essential for live viewing and monitoring automation tasks.

**For Headless Mode** (no UI streaming, automation only):
```bash
# Set ENABLE_WEBRTC=false to disable streaming
export IMAGE=kernel-docker && \
export ENABLE_WEBRTC=false && \
export WITH_KERNEL_IMAGES_API=true && \
./run-docker.sh
```

**Important**: 
- **UKC_TOKEN and UKC_METRO are NOT needed for local development** - they are only required for cloud/production deployments
- **ENABLE_WEBRTC=true is required** if you want to view live browser automation in the frontend

The browser will be available at:
- **CDP Endpoint**: `http://localhost:9222` (for automation via Chrome DevTools Protocol)
- **Browser UI**: `http://localhost:8080` (for viewing in frontend - requires WebRTC)
- **WebRTC Ports**: `56000-56100/udp` (for video/audio streaming when WebRTC enabled)

**Note**: 
- Keep the OnKernal Browser container running while using web-agent
- Use `ENABLE_WEBRTC=true` if you want to view browser automation in the frontend
- Use `ENABLE_WEBRTC=false` for headless automation without UI streaming

### Chrome Browser Setup

**Required when `BROWSER_PROVIDER=chrome`**

For local development, you can use Chrome/Chromium directly without Docker:

```bash
# Chrome/Chromium will be auto-detected, or set explicitly:
# CHROME_EXECUTABLE_PATH=/usr/bin/google-chrome
```

The backend will automatically:
- Launch Chrome with CDP enabled on port 9222
- Stream browser viewport to frontend on port 8080
- Manage Chrome process lifecycle

**Note**: Chrome must be installed on your system. The backend will auto-detect common installation paths.

### Backend Setup

**Prerequisites**: 
- If using OnKernal: OnKernal Browser must be running (see above)
- If using Chrome: Chrome/Chromium must be installed (auto-launched by backend)

```bash
# Clone the repository
git clone https://github.com/hiqbot/web-agent.git
cd web-agent

# Install Python dependencies
pip install -r requirements.txt

# Configure environment
cp env.example .env
# Edit .env and add your OPENAI_API_KEY
# Select browser provider: BROWSER_PROVIDER=onkernal or BROWSER_PROVIDER=chrome
# Configure ports if needed (defaults: CDP_PORT=9222, STREAMING_PORT=8080)

# Run the API server
python run.py
# API available at http://localhost:8000
# Backend connects to OnKernal Browser via CDP on port 9222
```

### Frontend Setup

```bash
# Navigate to frontend directory
cd web-agent-frontend

# Install Node.js dependencies
npm install

# Configure environment (optional - defaults work for local development)
cp .env.example .env
# Edit .env if you need to change API URLs

# Start the development server
npm run dev
# Frontend available at http://localhost:3000
```

**Architecture Overview**:
- **Frontend** (port 3000) → connects to **Backend API** (port 8000)
- **Backend API** (port 8000) → connects to browser via CDP (port 9222)
- **Browser UI** (port 8080) → displayed in frontend for live viewing
  - OnKernal: WebRTC streaming interface
  - Chrome: CDP screencast streaming

**Note**: 
- For OnKernal: Make sure OnKernal Browser is running before starting the backend
- For Chrome: Backend will auto-launch Chrome on startup
- Port conflicts are automatically detected and alternative ports are used if needed

## Project Structure

```
web-agent/
├── api/                 # FastAPI routes (REST + WebSocket)
├── web_agent/
│   ├── agent/          # LangGraph workflow & node orchestration
│   ├── nodes/          # INIT, PLAN, THINK, ACT, REPORT nodes
│   ├── browser/        # OnKernal Browser session management
│   ├── dom/            # DOM serialization & element extraction
│   ├── llm/            # LLM provider integration (OpenAI)
│   ├── tools/          # Action executors (click, type, navigate)
│   ├── filesystem/     # Task workspace & todo.md management
│   └── state.py        # LangGraph state definition
├── web-agent-frontend/  # React frontend application
│   ├── src/
│   │   ├── components/ # UI components
│   │   ├── pages/      # Application pages
│   │   ├── config/     # API configuration
│   │   └── context/    # React context providers
│   ├── public/         # Static assets
│   └── .env.example    # Frontend environment template
├── run.py              # API server entry point
└── env.example         # Backend environment configuration template
```

## Contributing

We welcome contributions from the community! Whether you're fixing bugs, improving documentation, adding new features, or enhancing existing functionality, your help is appreciated.

### Ways to Contribute

- 🐛 **Bug Reports**: Found a bug? Open an issue with detailed reproduction steps
- 💡 **Feature Suggestions**: Have ideas for new capabilities? Share them in discussions
- 🔧 **Code Contributions**: Submit PRs for bug fixes, enhancements, or new features
- 📚 **Documentation**: Help improve docs, add examples, or fix typos
- 🧪 **Testing**: Add test cases or improve test coverage


## Support

- 📧 **Email**: [support@hiqbot.com](mailto:support@hiqbot.com)
- 🐛 **Issues**: [GitHub Issues](https://github.com/hiqbot/web-agent/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/hiqbot/web-agent/discussions)

## License

Open-source project by HiQBot. See LICENSE for details.

---

**🌐 Website**: [hiqbot.com](https://hiqbot.com) | **🏢 Company**: HiQBot | **📦 Project**: web-agent

