import React, { useState, useEffect, useCallback, useRef } from 'react';
import { EyeIcon } from '@heroicons/react/24/outline';

interface BrowserViewProps {
  showByDefault?: boolean;
  height?: string;
  title?: string;
  description?: string;
}

const BrowserView: React.FC<BrowserViewProps> = ({ 
  showByDefault = false, 
  height = "h-[600px]",
  title = "Live Browser View",
  description = "Watch AI testing in real-time"
}) => {
  const [showBrowserView, setShowBrowserView] = useState(showByDefault);
  const [isInitializing, setIsInitializing] = useState(false);
  const hasInitialized = useRef(false);
  const isInitializingRef = useRef(false);

  const initializePersistentSession = useCallback(async () => {
    if (isInitializingRef.current || hasInitialized.current) return;
    
    isInitializingRef.current = true;
    setIsInitializing(true);
    hasInitialized.current = true;
    try {
      const response = await fetch('/api/v1/browser/init-persistent', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      if (response.ok) {
        console.log('✅ Persistent browser session initialized');
      } else {
        console.warn('⚠️ Failed to initialize persistent session');
      }
    } catch (error) {
      console.error('❌ Error initializing persistent session:', error);
    } finally {
      isInitializingRef.current = false;
      setIsInitializing(false);
    }
  }, []); // Empty dependency array - using refs instead of state

  // Initialize persistent session when browser view is shown
  useEffect(() => {
    if (showBrowserView && !isInitializingRef.current && !hasInitialized.current) {
      initializePersistentSession();
    }
  }, [showBrowserView, initializePersistentSession]); // Only showBrowserView and function

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-gray-900">{title}</h2>
        <button
          type="button"
          onClick={() => setShowBrowserView(!showBrowserView)}
          className={`px-4 py-2 rounded-md focus:outline-none focus:ring-2 ${
            showBrowserView
              ? 'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500'
              : 'bg-green-600 text-white hover:bg-green-700 focus:ring-green-500'
          }`}
        >
          {showBrowserView ? (
            <>
              <EyeIcon className="w-4 h-4 inline mr-2" />
              Hide Browser
            </>
          ) : (
            <>
              <EyeIcon className="w-4 h-4 inline mr-2" />
              Show Browser
            </>
          )}
        </button>
      </div>
      
      {showBrowserView && (
        <div className="border-2 border-gray-300 rounded-lg overflow-hidden">
          <div className="bg-gray-100 px-4 py-2 text-sm text-gray-600 border-b flex items-center justify-between">
            <span>🤖 HiQBot Web Agent - {description}</span>
            {isInitializing && (
              <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-1 rounded animate-pulse">
                Initializing...
              </span>
            )}
          </div>
          <iframe
            src="http://localhost:8080"
            className={`w-full ${height} border-0`}
            title="HiQBot Web Agent Browser"
            allow="camera; microphone; fullscreen"
            sandbox="allow-same-origin allow-scripts allow-popups allow-forms"
          />
          <div className="bg-blue-50 px-4 py-2 text-sm text-blue-700">
            💡 Tip: Execute a test plan to see the AI automation in action! Browser session stays alive between tests.
          </div>
        </div>
      )}
      
      {!showBrowserView && (
        <div className="bg-gray-50 rounded-md p-6 text-center">
          <EyeIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600 mb-2">Live browser view is hidden</p>
          <p className="text-sm text-gray-500">
            Click "Show Browser" to watch AI testing in real-time
          </p>
        </div>
      )}
    </div>
  );
};

export default BrowserView;
