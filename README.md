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

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **Workflow Engine** | LangGraph v1.0 (StateGraph) |
| **LLM Provider** | OpenAI API (gpt-4-mini, gpt-4, o1-preview) |
| **Browser Automation** | OnKernal Browser + CDP |
| **API Framework** | FastAPI (async, WebSocket support) |
| **Language** | Python 3.12+ |
| **DOM Serialization** | Custom CDP-based extractor with accessibility tree |

## Coming Soon

- 🔍 **In-Node Scraping**: Enhanced data extraction within workflow nodes
- 👁️ **Multimodal Support**: Vision-based page understanding (screenshot analysis)
- 🔌 **Multi-LLM Integration**: Anthropic (Claude), Google (Gemini), and open-source models
- ⚡ **Performance Optimizations**: Faster DOM processing and action execution

## Quick Start

```bash
# Clone the repository
git clone https://github.com/hiqbot/web-agent.git
cd web-agent

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp env.example .env
# Edit .env and add your OPENAI_API_KEY

# Run the API server
python run.py
# API available at http://localhost:8000
```

### Example Usage

```python
import requests

# Submit a task via REST API
response = requests.post("http://localhost:8000/api/v1/workflow/run", json={
    "task": "Go to example.com, sign up for an account with test@email.com",
    "start_url": "https://example.com",
    "max_steps": 30
})

print(response.json())  # Task completion report
```

Or use WebSocket for real-time streaming:
```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/ws?client_id=123&task=Sign up for account');
ws.onmessage = (event) => {
  console.log('Agent update:', JSON.parse(event.data));
};
```

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
├── run.py              # API server entry point
└── env.example         # Environment configuration template
```

## Contributing

We welcome contributions from the community! Whether you're fixing bugs, improving documentation, adding new features, or enhancing existing functionality, your help is appreciated.

### Ways to Contribute

- 🐛 **Bug Reports**: Found a bug? Open an issue with detailed reproduction steps
- 💡 **Feature Suggestions**: Have ideas for new capabilities? Share them in discussions
- 🔧 **Code Contributions**: Submit PRs for bug fixes, enhancements, or new features
- 📚 **Documentation**: Help improve docs, add examples, or fix typos
- 🧪 **Testing**: Add test cases or improve test coverage

### How to Contribute

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

Please ensure your code follows the existing style and includes appropriate tests.

## Support

- 📧 **Email**: [support@hiqbot.com](mailto:support@hiqbot.com)
- 🐛 **Issues**: [GitHub Issues](https://github.com/hiqbot/web-agent/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/hiqbot/web-agent/discussions)

## License

Open-source project by HiQBot. See LICENSE for details.

---

**🌐 Website**: [hiqbot.com](https://hiqbot.com) | **🏢 Company**: HiQBot | **📦 Project**: web-agent

