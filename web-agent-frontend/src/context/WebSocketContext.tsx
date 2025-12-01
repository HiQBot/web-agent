import React, { createContext, useContext, useEffect, useState, ReactNode, useRef } from 'react';
import toast from 'react-hot-toast';
import { buildWsUrl } from '../config/api';

interface WebSocketMessage {
  type: string;
  test_id?: string;
  timestamp: string;
  data?: any;
}

interface WebSocketContextType {
  isConnected: boolean;
  sendMessage: (message: any) => void;
  subscribeToTest: (testId: string) => void;
  lastMessage: WebSocketMessage | null;
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined);

interface WebSocketProviderProps {
  children: ReactNode;
}

export const WebSocketProvider: React.FC<WebSocketProviderProps> = ({ children }) => {
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [shouldReconnect, setShouldReconnect] = useState(true);
  const shouldReconnectRef = useRef(shouldReconnect);
  const socketRef = useRef(socket);

  // Update refs when state changes
  useEffect(() => {
    shouldReconnectRef.current = shouldReconnect;
  }, [shouldReconnect]);

  useEffect(() => {
    socketRef.current = socket;
  }, [socket]);

  useEffect(() => {
    let reconnectTimeout: NodeJS.Timeout;
    
    const connectWebSocket = () => {
      if (!shouldReconnectRef.current) return;
      
      const ws = new WebSocket(buildWsUrl('/ws'));
      
      ws.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        setSocket(ws);
        
        // Send ping to keep connection alive
        ws.send(JSON.stringify({ type: 'ping' }));
        
        toast.success('Connected to real-time updates');
      };
      
      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          setLastMessage(message);
          
          // Handle different message types
          switch (message.type) {
            case 'test_plan_created':
              toast.success('New test plan created!');
              break;
            case 'test_update':
              if (message.data?.status === 'completed') {
                toast.success('✅ Test execution completed successfully!', { duration: 8000 });
              } else if (message.data?.status === 'failed') {
                const errorMsg = message.data?.message || 'Test execution failed';
                toast.error(`❌ ${errorMsg}`, { duration: 12000 });
              } else if (message.data?.status === 'running') {
                const stepMsg = message.data?.message || 'Test running...';
                toast.loading(`🔄 ${stepMsg}`, { duration: 5000 });
              }
              break;
            case 'pong':
              // Connection is alive
              break;
            default:
              console.log('Received message:', message);
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };
      
      ws.onclose = (event) => {
        console.log('WebSocket disconnected', event.code);
        setIsConnected(false);
        setSocket(null);
        
        // Only show error if it wasn't a clean close
        if (event.code !== 1000) {
          toast.error('Disconnected from real-time updates');
        }
        
        // Attempt to reconnect after 5 seconds, but only if shouldReconnect is true
        if (shouldReconnectRef.current) {
          reconnectTimeout = setTimeout(() => {
            connectWebSocket();
          }, 5000);
        }
      };
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        // Don't show toast for every error to avoid spam
      };
    };

    // Only connect if backend is likely running
    connectWebSocket();

    return () => {
      setShouldReconnect(false);
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
      }
      if (socketRef.current) {
        socketRef.current.close(1000, 'Component unmounting');
      }
    };
  }, []); // Empty dependency array

  const sendMessage = (message: any) => {
    if (socket && isConnected) {
      socket.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket not connected');
    }
  };

  const subscribeToTest = (testId: string) => {
    sendMessage({
      type: 'subscribe_test',
      test_id: testId
    });
  };

  const value: WebSocketContextType = {
    isConnected,
    sendMessage,
    subscribeToTest,
    lastMessage
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
};

export const useWebSocket = (): WebSocketContextType => {
  const context = useContext(WebSocketContext);
  if (context === undefined) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
};
