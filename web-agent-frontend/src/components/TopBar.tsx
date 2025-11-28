import React from 'react';
import { useWebSocket } from '../context/WebSocketContext';

interface TopBarProps {
  currentPage: string;
}

const TopBar: React.FC<TopBarProps> = ({ currentPage }) => {
  const { isConnected } = useWebSocket();

  const getPageTitle = (page: string) => {
    const titles: { [key: string]: string } = {
      dashboard: 'Dashboard',
      'test-plans': 'Test Plans',
      'test-execution': 'Test Execution',
      settings: 'Settings',
    };
    return titles[page] || 'Dashboard';
  };

  return (
    <header className="bg-gray-800 shadow-md sticky top-0 z-20 flex-shrink-0 h-16 flex justify-between items-center px-4 sm:px-6 lg:px-8">
      <h1 className="text-xl font-bold text-white">
        {getPageTitle(currentPage)}
      </h1>
      
      <div className={`flex items-center space-x-2 px-3 py-1 rounded-full text-sm ${
        isConnected 
          ? 'bg-green-900/50 border border-green-600 text-green-300' 
          : 'bg-red-900/50 border border-red-600 text-red-300'
      }`}>
        <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`}></span>
        <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
      </div>
    </header>
  );
};

export default TopBar;
