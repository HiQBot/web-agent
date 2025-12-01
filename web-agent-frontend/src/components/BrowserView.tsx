import React, { useState, useEffect, useCallback, useRef } from 'react';
import { EyeIcon } from '@heroicons/react/24/outline';
import { apiConfig, buildApiUrl, buildWsUrl } from '../config/api';

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
  const [streamingType, setStreamingType] = useState<'webrtc' | 'screencast' | null>(null);
  const [browserUrl, setBrowserUrl] = useState(apiConfig.browserUrl);
  const [wsConnected, setWsConnected] = useState(false);
  const hasInitialized = useRef(false);
  const isInitializingRef = useRef(false);
  const wsRef = useRef<WebSocket | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const clientIdRef = useRef(`client_${Date.now()}`);

  const initializePersistentSession = useCallback(async () => {
    if (isInitializingRef.current || hasInitialized.current) return;

    isInitializingRef.current = true;
    setIsInitializing(true);
    hasInitialized.current = true;
    try {
      // First, check browser status to get provider info
      console.log('🔍 Checking browser provider...');
      const statusResponse = await fetch(buildApiUrl('/browser/status'));
      if (statusResponse.ok) {
        const statusData = await statusResponse.json();
        console.log('📊 Browser status:', statusData);

        // Set streaming type based on provider
        if (statusData.provider === 'chrome') {
          console.log('🌐 Chrome provider detected - will use WebSocket screencast');
          // Don't set streaming type yet, wait for WebSocket connection message
        } else if (statusData.provider === 'onkernal') {
          console.log('🌐 OnKernal provider detected - will use WebRTC iframe');
          setStreamingType('webrtc');
          if (statusData.browser_url) {
            setBrowserUrl(statusData.browser_url);
          }
          // For OnKernal, we don't need to initialize a session
          isInitializingRef.current = false;
          setIsInitializing(false);
          return;
        }
      }

      // For Chrome: Initialize persistent browser session
      console.log('🔧 Initializing persistent browser session...');
      const response = await fetch(buildApiUrl(apiConfig.endpoints.browser.initPersistent), {
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
    console.log(`🔄 BrowserView useEffect: showBrowserView=${showBrowserView}, isInitializing=${isInitializingRef.current}, hasInitialized=${hasInitialized.current}`);
    if (showBrowserView && !isInitializingRef.current && !hasInitialized.current) {
      console.log('▶️ Calling initializePersistentSession...');
      initializePersistentSession();
    }
  }, [showBrowserView, initializePersistentSession]);

  // Connect to browser stream WebSocket to detect streaming type and handle Chrome screencast
  useEffect(() => {
    console.log(`🔄 WebSocket useEffect: showBrowserView=${showBrowserView}`);
    if (!showBrowserView) {
      // Clean up WebSocket when browser view is hidden
      if (wsRef.current) {
        console.log('🧹 Cleaning up WebSocket');
        wsRef.current.close();
        wsRef.current = null;
        setWsConnected(false);
        setStreamingType(null);
      }
      return;
    }

    const connectWebSocket = () => {
      console.log('🔌 Attempting to connect WebSocket...');
      try {
        const wsUrl = `${buildWsUrl('/ws/browser-stream')}?client_id=${clientIdRef.current}&browser_url=${encodeURIComponent(browserUrl)}`;
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          console.log('✅ Browser stream WebSocket connected');
          setWsConnected(true);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            console.log(`📨 WebSocket message received:`, data.type);

            if (data.type === 'connected') {
              // Server tells us the streaming type
              const detectedType = data.streaming_type || 'webrtc';
              console.log(`📺 Streaming type detected: ${detectedType}`);
              console.log(`🌐 Provider: ${data.provider}`);
              console.log(`🔗 Browser URL: ${data.browser_url}`);
              setStreamingType(detectedType);
              if (data.browser_url) {
                setBrowserUrl(data.browser_url);
              }
            } else if (data.type === 'screencast_frame' && canvasRef.current) {
              console.log(`📸 Screencast frame received (data length: ${data.data?.length || 0})`);

              // Render screencast frame to canvas (Chrome)
              const canvas = canvasRef.current;
              const ctx = canvas.getContext('2d');
              if (ctx && data.data) {
                const img = new Image();
                img.onload = () => {
                  console.log(`🖼️ Image loaded: ${img.width}x${img.height}`);

                  // Maintain aspect ratio
                  const container = canvas.parentElement;
                  if (container) {
                    const containerWidth = container.clientWidth;
                    const containerHeight = container.clientHeight;
                    const imgAspect = img.width / img.height;
                    const containerAspect = containerWidth / containerHeight;
                    
                    let drawWidth, drawHeight;
                    if (imgAspect > containerAspect) {
                      drawWidth = containerWidth;
                      drawHeight = containerWidth / imgAspect;
                    } else {
                      drawHeight = containerHeight;
                      drawWidth = containerHeight * imgAspect;
                    }
                    
                    canvas.width = drawWidth;
                    canvas.height = drawHeight;
                    ctx.drawImage(img, 0, 0, drawWidth, drawHeight);
                    console.log(`✅ Frame rendered to canvas: ${drawWidth}x${drawHeight}`);
                  } else {
                    canvas.width = img.width;
                    canvas.height = img.height;
                    ctx.drawImage(img, 0, 0);
                    console.log(`✅ Frame rendered to canvas: ${img.width}x${img.height}`);
                  }
                };
                img.onerror = (err) => {
                  console.error('❌ Error loading image:', err);
                };
                img.src = `data:image/jpeg;base64,${data.data}`;
              } else {
                console.warn('⚠️ Canvas context or data not available');
              }
            }
          } catch (error) {
            console.error('❌ Error parsing WebSocket message:', error);
          }
        };

        ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          setWsConnected(false);
        };

        ws.onclose = () => {
          console.log('Browser stream WebSocket disconnected');
          setWsConnected(false);
          // Reconnect after 2 seconds if still showing browser view
          if (showBrowserView) {
            setTimeout(connectWebSocket, 2000);
          }
        };
      } catch (error) {
        console.error('Failed to connect browser stream WebSocket:', error);
        setWsConnected(false);
      }
    };

    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
        setWsConnected(false);
      }
    };
  }, [showBrowserView, browserUrl]);

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
            <div className="flex items-center space-x-2">
              {isInitializing && (
                <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-1 rounded animate-pulse">
                  Initializing...
                </span>
              )}
              {!wsConnected && streamingType === null && (
                <span className="text-xs bg-gray-100 text-gray-800 px-2 py-1 rounded">
                  Connecting...
                </span>
              )}
              {streamingType === 'screencast' && (
                <span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded">
                  Chrome Streaming
                </span>
              )}
              {streamingType === 'webrtc' && (
                <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">
                  OnKernal WebRTC
                </span>
              )}
            </div>
          </div>
          {streamingType === 'screencast' ? (
            // Chrome screencast via WebSocket
            <div className={`w-full ${height} bg-gray-900 flex items-center justify-center overflow-hidden`}>
              <canvas
                ref={canvasRef}
                className="max-w-full max-h-full"
                style={{ imageRendering: 'auto' }}
              />
              {!wsConnected && (
                <div className="absolute text-white text-sm">
                  Connecting to Chrome stream...
                </div>
              )}
            </div>
          ) : streamingType === 'webrtc' ? (
            // OnKernal WebRTC iframe
            <iframe
              src={browserUrl}
              className={`w-full ${height} border-0`}
              title="HiQBot Web Agent Browser"
              allow="camera; microphone; fullscreen"
              sandbox="allow-same-origin allow-scripts allow-popups allow-forms"
            />
          ) : (
            // Loading state - waiting for streaming type detection
            <div className={`w-full ${height} bg-gray-100 flex items-center justify-center`}>
              <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900 mx-auto mb-4"></div>
                <p className="text-gray-600">Connecting to browser stream...</p>
              </div>
            </div>
          )}
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
