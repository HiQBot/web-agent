import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, useLocation, useNavigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from '@/components/ui/toaster';

// Components
import WelcomePage from './components/WelcomePage';
import CollapsibleSidebar from './components/CollapsibleSidebar';
import CompactHeader from './components/CompactHeader';
import Dashboard from './pages/Dashboard';
import TestPlans from './pages/TestPlans';
import TestExecution from './pages/TestExecution';
import Settings from './pages/Settings';
import { WebSocketProvider } from './context/WebSocketContext';

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function AppContent() {
  const [showWelcome, setShowWelcome] = useState(true);
  const location = useLocation();
  const navigate = useNavigate();

  // Enable dark mode by default
  useEffect(() => {
    document.documentElement.classList.add('dark');
  }, []);

  const handleEnterDashboard = () => {
    setShowWelcome(false);
    navigate('/');
  };

  const handlePageChange = (page: string) => {
    const routes: { [key: string]: string } = {
      'dashboard': '/',
      'test-plans': '/test-plans',
      'test-execution': '/test-execution',
      'settings': '/settings'
    };
    
    const route = routes[page];
    if (route) {
      navigate(route);
    }
  };

  const getCurrentPage = () => {
    const path = location.pathname;
    if (path === '/') return 'dashboard';
    if (path === '/test-plans') return 'test-plans';
    if (path === '/test-execution') return 'test-execution';
    if (path === '/settings') return 'settings';
    return 'dashboard';
  };

  if (showWelcome) {
    return <WelcomePage onEnter={handleEnterDashboard} />;
  }

  return (
    <div className="min-h-screen flex">
      <CollapsibleSidebar currentPage={getCurrentPage()} onPageChange={handlePageChange} />

      <div className="flex-1 flex flex-col ml-64 transition-all duration-300">
        <CompactHeader />

        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/test-plans" element={<TestPlans />} />
            <Route path="/test-execution" element={<TestExecution />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>

      <Toaster />
    </div>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <WebSocketProvider>
        <Router>
          <AppContent />
        </Router>
      </WebSocketProvider>
    </QueryClientProvider>
  );
}

export default App;
