# HiQBot Web Agent - Frontend

A modern React-based frontend for the HiQBot Web Agent Platform that automates web tasks using AI-powered agents. This platform creates intelligent agents that can browse, click, fill forms, and interact with websites autonomously using natural language instructions.

## 🚀 Features

### Core Functionality
- **AI-Powered Synthetic Users**: Create autonomous agents with natural language instructions
- **Real-time Browser View**: Watch AI testing in action with live browser sessions
- **Intelligent Test Generation**: Self-healing tests that adapt to website changes
- **Human-like Interaction Patterns**: Realistic typing, mouse movements, and behavior
- **Advanced Bug Detection**: Comprehensive error detection and reporting
- **Live Test Execution**: Real-time monitoring and control of test runs

### User Interface
- **Modern Dark Theme**: Sleek, professional interface with smooth animations
- **Responsive Design**: Works seamlessly across desktop and mobile devices
- **Real-time Updates**: WebSocket-powered live updates and notifications
- **Interactive Dashboard**: Comprehensive overview of test plans and execution status
- **Test Management**: Create, edit, delete, and execute test plans with ease

### Technical Features
- **WebSocket Integration**: Real-time communication with backend services
- **Persistent Browser Sessions**: Maintains browser state between test executions
- **Comprehensive Logging**: Detailed execution logs with timestamps and status
- **Progress Tracking**: Visual progress indicators and step-by-step monitoring
- **Error Handling**: Robust error handling with user-friendly notifications

## 🛠️ Tech Stack

- **Frontend Framework**: React 18.2.0 with TypeScript
- **Routing**: React Router DOM 6.20.1
- **State Management**: TanStack React Query 5.8.4
- **Styling**: Tailwind CSS 3.3.6 with custom theme
- **Icons**: Heroicons 2.0.18 & Lucide React 0.294.0
- **Notifications**: React Hot Toast 2.4.1
- **HTTP Client**: Axios 1.6.2
- **Date Handling**: date-fns 2.30.0
- **Utilities**: clsx 2.0.0

## 📁 Project Structure

```
src/
├── components/           # Reusable UI components
│   ├── BrowserView.tsx  # Live browser iframe component
│   ├── Navbar.tsx       # Navigation bar
│   ├── Sidebar.tsx      # Side navigation
│   ├── TopBar.tsx       # Top navigation bar
│   └── WelcomePage.tsx  # Landing page component
├── context/             # React context providers
│   └── WebSocketContext.tsx  # WebSocket connection management
├── pages/               # Main application pages
│   ├── Dashboard.tsx    # Main dashboard with stats and test creation
│   ├── Settings.tsx     # Application settings
│   ├── TestExecution.tsx # Real-time test execution monitoring
│   └── TestPlans.tsx    # Test plan management
├── App.tsx              # Main application component
├── index.tsx            # Application entry point
└── index.css            # Global styles
```

## 🚀 Getting Started

### Prerequisites

- Node.js 16.0 or higher
- npm or yarn package manager
- Backend API running on `http://localhost:8000`
- OnKernal Browser service running on `http://localhost:8080`

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd react_frontend
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Start the development server**
   ```bash
   npm start
   ```

4. **Open your browser**
   Navigate to `http://localhost:3000` to view the application

### Available Scripts

- `npm start` - Start development server
- `npm run dev` - Alias for start command
- `npm run build` - Build for production
- `npm test` - Run tests
- `npm run lint` - Run ESLint
- `npm run lint:fix` - Fix ESLint issues
- `npm run type-check` - Run TypeScript type checking
- `npm run preview` - Preview production build

## 🔧 Configuration

### Environment Variables

The application uses the following default configurations:

- **API Proxy**: `http://localhost:8000` (configured in package.json)
- **WebSocket URL**: `ws://localhost:8000/ws`
- **Browser Service**: `http://localhost:8080`

### Tailwind Configuration

The project includes a custom Tailwind CSS configuration with:
- Extended color palette (primary, success, warning, error)
- Custom animations and keyframes
- Inter font family integration
- Responsive design utilities

## 📱 Pages Overview

### Dashboard
- **Test Statistics**: Overview of total, passed, and failed tests
- **Create Test Plans**: Form to create new test plans with natural language descriptions
- **Test Plans List**: Display and manage existing test plans
- **Live Browser View**: Real-time browser session monitoring
- **Real-time Updates**: WebSocket message display

### Test Plans
- **Test Plan Management**: Create, edit, delete test plans
- **Bulk Operations**: Execute multiple tests
- **Status Tracking**: Visual status indicators for each test plan
- **Detailed Information**: URL, creation date, and execution history

### Test Execution
- **Real-time Monitoring**: Live test execution status
- **Progress Tracking**: Step-by-step progress with visual indicators
- **Test Controls**: Start, pause, resume, and stop test execution
- **Execution Logs**: Detailed logs with timestamps and error information
- **Live Browser View**: Watch tests execute in real-time

### Settings
- **Application Configuration**: User preferences and settings
- **API Configuration**: Backend service settings
- **Browser Settings**: OnKernal Browser configuration

## 🔌 API Integration

### REST API Endpoints

- `GET /api/v1/tests/test-plans` - Fetch all test plans
- `POST /api/v1/tests/test-plans` - Create new test plan
- `DELETE /api/v1/tests/test-plans/{id}` - Delete test plan
- `POST /api/v1/tests/execute` - Execute test plan
- `GET /api/v1/tests/running` - Get running tests
- `GET /api/v1/tests/{id}` - Get test details
- `POST /api/v1/browser/init-persistent` - Initialize browser session

### WebSocket Events

- `test_plan_created` - New test plan created
- `test_update` - Test execution status updates
- `ping/pong` - Connection keep-alive

## 🎨 UI Components

### BrowserView Component
- **Persistent Sessions**: Maintains browser state between tests
- **Real-time Display**: Live iframe showing browser activity
- **Toggle Controls**: Show/hide browser view
- **Status Indicators**: Connection and initialization status

### WebSocket Context
- **Auto-reconnection**: Automatic reconnection on connection loss
- **Message Handling**: Structured message processing
- **Toast Notifications**: User-friendly status updates
- **Connection Management**: Robust connection state management

## 🚀 Deployment

### Production Build

1. **Build the application**
   ```bash
   npm run build
   ```

2. **Serve the build**
   ```bash
   npm run preview
   ```

3. **Deploy to your hosting platform**
   - Upload the `build/` directory to your web server
   - Configure your web server to serve the React app
   - Ensure API endpoints are accessible

### Docker Deployment

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "run", "preview"]
```

## 🔧 Development

### Code Style

- **TypeScript**: Strict type checking enabled
- **ESLint**: Configured with React and TypeScript rules
- **Prettier**: Code formatting (if configured)
- **Conventional Commits**: Follow conventional commit messages

### Testing

- **Jest**: Testing framework
- **React Testing Library**: Component testing utilities
- **User Event**: User interaction testing

### Performance

- **React Query**: Efficient data fetching and caching
- **Code Splitting**: Automatic code splitting with React Router
- **Lazy Loading**: Component lazy loading for better performance
- **Memoization**: Optimized re-renders with React.memo

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Create an issue in the repository
- Check the documentation
- Review the API documentation

## 🔮 Roadmap

- [ ] Enhanced test result visualization
- [ ] Advanced reporting and analytics
- [ ] Team collaboration features
- [ ] Enterprise SSO integration
- [ ] Mobile app development
- [ ] Advanced AI agent customization
- [ ] Performance optimization tools
- [ ] Multi-browser support

---

**Built with ❤️ for the future of automated testing**
