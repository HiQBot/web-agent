import React, { useState, useEffect, useRef } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from '@/components/ui/resizable';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  ArrowsPointingOutIcon,
  ArrowsPointingInIcon,
  XMarkIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  ChevronDownIcon,
  ChevronUpIcon,
} from '@heroicons/react/24/outline';
import { cn } from '@/lib/utils';
import { apiConfig, buildApiUrl, buildWsUrl } from '../config/api';

interface BrowserAutomationModalProps {
  isOpen: boolean;
  onClose: () => void;
  testId?: string;
  testName?: string;
  browserUrl?: string;
  task?: string;
  startUrl?: string;
}

interface LogEntry {
  timestamp: string;
  type: 'info' | 'error' | 'warn' | 'debug' | 'success';
  message: string;
}

const BrowserAutomationModal: React.FC<BrowserAutomationModalProps> = ({
  isOpen,
  onClose,
  testId,
  testName = 'Test Automation',
  browserUrl = apiConfig.browserUrl,
  task = 'Automated testing task',
  startUrl,
}) => {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [modalSize, setModalSize] = useState({ width: 1080, height: 800 });
  const [logsExpanded, setLogsExpanded] = useState(false);
  const [testInfoExpanded, setTestInfoExpanded] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([
    { timestamp: new Date().toISOString(), type: 'info', message: 'Initializing browser automation...' },
  ]);
  const [status, setStatus] = useState<'connecting' | 'running' | 'completed' | 'error'>('connecting');
  const [stepCount, setStepCount] = useState(0);
  const [currentNode, setCurrentNode] = useState<string>('');
  const [browserProvider, setBrowserProvider] = useState<'chrome' | 'onkernal' | null>(null);
  const [streamingType, setStreamingType] = useState<'webrtc' | 'screencast' | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const browserWsRef = useRef<WebSocket | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);
  const panelGroupRef = useRef<HTMLDivElement>(null);
  const isResizing = useRef(false);
  const resizeStart = useRef({ x: 0, y: 0, width: 0, height: 0 });

  const addLog = (type: LogEntry['type'], message: string) => {
    setLogs(prev => [
      ...prev,
      { timestamp: new Date().toISOString(), type, message }
    ].slice(-100)); // Keep last 100 logs
  };

  const scrollToBottom = () => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const setupChromeScreencast = () => {
    const clientId = `browser_${Date.now()}`;
    const wsUrl = `${buildWsUrl('/ws/browser-stream')}?client_id=${clientId}&browser_url=${encodeURIComponent(browserUrl)}`;

    console.log('🔌 Connecting to Chrome screencast WebSocket:', wsUrl);
    const ws = new WebSocket(wsUrl);
    browserWsRef.current = ws;

    ws.onopen = () => {
      console.log('✅ Chrome screencast WebSocket connected');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'connected') {
          console.log('📺 Chrome screencast connected:', data.streaming_type);
        } else if (data.type === 'screencast_frame' && canvasRef.current) {
          // Render frame to canvas
          const canvas = canvasRef.current;
          const ctx = canvas.getContext('2d');
          if (ctx && data.data) {
            const img = new Image();
            img.onload = () => {
              canvas.width = img.width;
              canvas.height = img.height;
              ctx.drawImage(img, 0, 0);
            };
            img.src = `data:image/jpeg;base64,${data.data}`;
          }
        }
      } catch (error) {
        console.error('Error parsing Chrome screencast message:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('Chrome screencast WebSocket error:', error);
    };

    ws.onclose = () => {
      console.log('Chrome screencast WebSocket disconnected');
    };
  };

  useEffect(() => {
    scrollToBottom();
  }, [logs]);

  // Calculate responsive modal size on open
  useEffect(() => {
    if (isOpen && !isFullscreen) {
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;
      const maxWidth = Math.min(1080, viewportWidth * 0.95);
      const maxHeight = Math.min(viewportHeight * 0.9, 800);
      setModalSize({ width: maxWidth, height: maxHeight });
    }
  }, [isOpen, isFullscreen]);

  // Use ResizeObserver to detect modal size changes and update browser viewport
  useEffect(() => {
    if (!modalRef.current || !isOpen) return;

    let resizeTimeout: NodeJS.Timeout;
    const resizeObserver = new ResizeObserver((entries) => {
      // Debounce viewport resize calls
      clearTimeout(resizeTimeout);
      resizeTimeout = setTimeout(async () => {
        const entry = entries[0];
        if (entry) {
          const { width, height } = entry.contentRect;
          
          // Calculate actual browser container size (accounting for header, padding, etc.)
          // Header is ~40px, logs panel takes ~15% when expanded, so browser gets ~85%
          const headerHeight = testInfoExpanded ? 60 : 40; // Header + optional test info
          const logsHeight = logsExpanded ? height * 0.15 : 0;
          const browserHeight = Math.max(400, height - headerHeight - logsHeight);
          const browserWidth = Math.max(600, width);
          
          // Force panels to recalculate by triggering a resize event
          const resizeEvent = new Event('resize');
          window.dispatchEvent(resizeEvent);
          
          // Update browser viewport via API
          try {
            const response = await fetch(`${buildApiUrl('/browser/viewport')}?width=${Math.round(browserWidth)}&height=${Math.round(browserHeight)}`, {
              method: 'POST',
            });
            if (response.ok) {
              const data = await response.json();
              console.log('Browser viewport updated:', data);
            }
          } catch (error) {
            console.warn('Failed to update browser viewport:', error);
          }
        }
      }, 300); // Debounce 300ms
    });

    resizeObserver.observe(modalRef.current);

    return () => {
      clearTimeout(resizeTimeout);
      resizeObserver.disconnect();
    };
  }, [isOpen, testInfoExpanded, logsExpanded]);

  // Handle modal resize with mouse
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (isResizing.current) {
        const deltaX = e.clientX - resizeStart.current.x;
        const deltaY = e.clientY - resizeStart.current.y;
        
        const newWidth = Math.max(600, Math.min(window.innerWidth * 0.95, resizeStart.current.width + deltaX));
        const newHeight = Math.max(400, Math.min(window.innerHeight * 0.95, resizeStart.current.height + deltaY));
        
        setModalSize({ width: newWidth, height: newHeight });
      }
    };

    const handleMouseUp = () => {
      isResizing.current = false;
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, []);

  useEffect(() => {
    if (isOpen) {
      // Detect browser provider on modal open
      const detectProvider = async () => {
        try {
          const response = await fetch(buildApiUrl('/browser/status'));
          if (response.ok) {
            const data = await response.json();
            console.log('📊 Browser provider detected:', data.provider);
            setBrowserProvider(data.provider);
            setStreamingType(data.streaming_type);

            // If Chrome, set up WebSocket screencast
            if (data.provider === 'chrome') {
              setupChromeScreencast();
            }
          }
        } catch (error) {
          console.error('Failed to detect browser provider:', error);
          // Default to onkernal if detection fails
          setBrowserProvider('onkernal');
          setStreamingType('webrtc');
        }
      };

      detectProvider();

      // If this is just a live preview (no task), don't connect to automation WebSocket
      if (testId === 'live_preview' || !task || task === 'View live browser window') {
        addLog('info', '🖥️ Live browser preview mode');
        addLog('info', `📺 Viewing: ${browserUrl}`);
        setStatus('running');
        return;
      }

      // Connect to WebSocket for actual test execution
      const clientId = `client_${Date.now()}`;
      const wsUrl = buildWsUrl(apiConfig.ws.automation(clientId, task, startUrl, 50));

      addLog('info', 'Connecting to automation server...');
      setStatus('connecting');

      try {
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          addLog('success', 'Connected to automation server');
          setStatus('running');
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);

            switch (data.type) {
              case 'status':
                addLog('info', `Status: ${data.message}`);
                if (data.status === 'completed') {
                  setStatus('completed');
                }
                break;

              case 'workflow_started':
                addLog('info', `🚀 Starting workflow: ${data.task}`);
                if (data.start_url) {
                  addLog('info', `🌐 Target URL: ${data.start_url}`);
                }
                break;

              case 'node_update':
                setStepCount(data.step);
                setCurrentNode(data.node);
                addLog('debug', `📍 Node: ${data.node} (Step ${data.step})`);
                if (data.data?.current_state) {
                  addLog('info', `State: ${data.data.current_state}`);
                }
                break;

              case 'browser_action':
                addLog('info', `🎬 Action: ${JSON.stringify(data.action)}`);
                if (data.result) {
                  addLog('debug', `Result: ${JSON.stringify(data.result).substring(0, 100)}...`);
                }
                break;

              case 'verification':
                if (data.status === 'passed') {
                  addLog('success', `✅ Verification: ${data.status}`);
                } else {
                  addLog('warn', `⚠️ Verification: ${data.status}`);
                }
                if (data.details) {
                  addLog('debug', data.details);
                }
                break;

              case 'workflow_completed':
                addLog('success', `✅ Workflow completed in ${data.step_count} steps`);
                addLog('info', `Final status: ${data.verification_status}`);
                if (data.report) {
                  addLog('info', `📊 Report generated`);
                }
                setStatus('completed');
                break;

              case 'error':
                addLog('error', `❌ Error: ${data.message || data.error}`);
                setStatus('error');
                break;

              default:
                addLog('debug', `Unknown message type: ${data.type}`);
            }
          } catch (error) {
            addLog('error', `Failed to parse message: ${error}`);
          }
        };

        ws.onerror = (error) => {
          addLog('error', 'WebSocket connection error');
          setStatus('error');
        };

        ws.onclose = () => {
          addLog('info', 'Connection closed');
          if (status === 'running') {
            setStatus('completed');
          }
        };

      } catch (error) {
        addLog('error', `Failed to connect: ${error}`);
        setStatus('error');
      }

      return () => {
        if (wsRef.current) {
          wsRef.current.close();
        }
      };
    }
  }, [isOpen, task, startUrl]);

  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
  };

  const handleResizeMouseDown = (e: React.MouseEvent) => {
    if (isFullscreen) return;
    e.preventDefault();
    e.stopPropagation();
    
    isResizing.current = true;
    resizeStart.current = {
      x: e.clientX,
      y: e.clientY,
      width: modalSize.width,
      height: modalSize.height,
    };
  };

  const getStatusBadge = () => {
    switch (status) {
      case 'connecting':
        return <Badge variant="outline" className="animate-pulse border-blue-400 text-blue-400"><ClockIcon className="w-3 h-3 mr-1" />Connecting</Badge>;
      case 'running':
        return <Badge variant="warning" className="animate-pulse border-yellow-400 text-yellow-400"><ClockIcon className="w-3 h-3 mr-1 animate-spin" />Running</Badge>;
      case 'completed':
        return <Badge variant="success" className="border-green-400 text-green-400"><CheckCircleIcon className="w-3 h-3 mr-1" />Completed</Badge>;
      case 'error':
        return <Badge variant="destructive" className="border-red-400 text-red-400"><XCircleIcon className="w-3 h-3 mr-1" />Error</Badge>;
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        ref={modalRef}
        className={cn(
          "overflow-hidden p-0 glass-strong border-4 border-black/30 shadow-[12px_12px_0px_0px_rgba(0,0,0,0.4)] flex flex-col",
          "[&>button]:!hidden", // Hide the default Dialog close button
          isFullscreen
            ? "max-w-[98vw] h-[98vh] w-[98vw] transition-all duration-300 ease-in-out"
            : "transition-all duration-200 ease-in-out"
        )}
        style={!isFullscreen ? {
          width: `${modalSize.width}px`,
          height: `${modalSize.height}px`,
          maxWidth: '95vw',
          maxHeight: '95vh',
        } : undefined}
        onPointerDownOutside={(e) => e.preventDefault()}
      >
        {/* Resize handle - bottom right corner */}
        {!isFullscreen && (
          <div 
            className="absolute bottom-0 right-0 w-6 h-6 cursor-nwse-resize z-50 bg-transparent hover:bg-blue-500/20 transition-colors"
            style={{ 
              clipPath: 'polygon(100% 0, 100% 100%, 0 100%)',
            }}
            onMouseDown={handleResizeMouseDown}
          >
            <div className="absolute bottom-1 right-1 w-3 h-3 border-r-2 border-b-2 border-white/40"></div>
          </div>
        )}

        {/* Header - Minimal padding, at the very top */}
        <div className="flex items-center justify-between px-2 py-1 border-b border-white/10 glass-strong flex-shrink-0">
          <div className="flex items-center gap-2">
            <ClockIcon className={cn("w-4 h-4", status === 'running' ? 'text-yellow-400 animate-spin' : 'text-blue-400')} />
            <DialogTitle className="text-sm font-bold text-white">
              {testName}
            </DialogTitle>
            {stepCount > 0 && (
              <span className="text-xs text-muted-foreground">• Step {stepCount}</span>
            )}
          </div>
          <div className="flex items-center gap-1.5">
            {getStatusBadge()}

            {/* Test Info Toggle - Only show if not live preview */}
            {testId !== 'live_preview' && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setTestInfoExpanded(!testInfoExpanded)}
                className="h-6 px-2 text-[10px] glass border border-white/20 hover:border-white/40"
              >
                {testInfoExpanded ? <ChevronUpIcon className="h-3 w-3" /> : <ChevronDownIcon className="h-3 w-3" />}
              </Button>
            )}

            <Button
              variant="outline"
              size="icon"
              onClick={toggleFullscreen}
              className="h-6 w-6 glass border border-white/20 hover:border-white/40"
            >
              {isFullscreen ? <ArrowsPointingInIcon className="h-3 w-3" /> : <ArrowsPointingOutIcon className="h-3 w-3" />}
            </Button>
            <Button
              variant="outline"
              size="icon"
              onClick={onClose}
              className="h-6 w-6 glass border border-white/20 hover:border-red-400/50 hover:text-red-400"
            >
              <XMarkIcon className="h-3 w-3" />
            </Button>
          </div>
        </div>

        {/* Test Info - Collapsible */}
        {testInfoExpanded && testId !== 'live_preview' && (
          <div className="px-2 py-1 border-b border-white/10 glass bg-blue-500/5 text-[10px] font-mono flex-shrink-0">
            <div className="grid grid-cols-2 gap-2">
              <div><span className="text-muted-foreground">Task:</span> <span className="text-blue-400">{task}</span></div>
              <div><span className="text-muted-foreground">URL:</span> <span className="text-purple-400">{startUrl}</span></div>
            </div>
          </div>
        )}

        {/* Main Content - Resizable Panels - Takes remaining space */}
        <div className="flex-1 min-h-0 flex flex-col" ref={panelGroupRef}>
          <ResizablePanelGroup 
            direction="vertical" 
            className="flex-1 min-h-0 w-full"
          >
            {/* Browser View Panel - Maximum space */}
            <ResizablePanel defaultSize={85} minSize={60}>
              <div className="h-full w-full bg-black relative m-0 p-0 overflow-hidden flex items-center justify-center" style={{ minHeight: 0 }}>
                {streamingType === 'screencast' ? (
                  // Chrome screencast via WebSocket
                  <canvas
                    ref={canvasRef}
                    className="max-w-full max-h-full"
                    style={{ imageRendering: 'auto' }}
                  />
                ) : streamingType === 'webrtc' ? (
                  // OnKernal WebRTC iframe
                  <iframe
                    src={browserUrl}
                    className="w-full h-full border-0 m-0 p-0 block"
                    title="Live Browser Automation"
                    sandbox="allow-same-origin allow-scripts allow-forms"
                    allow="fullscreen"
                    style={{ minHeight: 0, height: '100%' }}
                  />
                ) : (
                  // Loading state
                  <div className="text-white text-sm">
                    Detecting browser provider...
                  </div>
                )}
              {/* Overlay indicators */}
              <div className="absolute top-2 right-2 flex gap-2 z-10">
                {status === 'running' && (
                  <div className="bg-red-500/95 text-white px-2 py-1 rounded text-[10px] font-bold flex items-center gap-1.5 shadow-lg">
                    <span className="w-1.5 h-1.5 bg-white rounded-full animate-pulse" />
                    LIVE
                  </div>
                )}
                {stepCount > 0 && (
                  <div className="bg-blue-500/95 text-white px-2 py-1 rounded text-[10px] font-bold shadow-lg">
                    Step {stepCount}
                  </div>
                )}
              </div>
            </div>
          </ResizablePanel>

          {/* Resize Handle */}
          <ResizableHandle withHandle className="bg-white/10 hover:bg-white/20 transition-colors" />

          {/* Execution Logs Panel - Collapsible */}
          <ResizablePanel defaultSize={15} minSize={5} maxSize={40}>
            <div className="h-full flex flex-col glass border-t border-white/10">
              <button
                onClick={() => setLogsExpanded(!logsExpanded)}
                className="w-full px-2 py-1 flex items-center justify-between glass-strong bg-gradient-to-r from-cyan-500/10 to-blue-500/10 hover:from-cyan-500/15 hover:to-blue-500/15 transition-all flex-shrink-0"
              >
                <div className="flex items-center gap-2">
                  <h3 className="text-xs font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent uppercase tracking-wider">
                    Execution Logs
                  </h3>
                  <Badge variant="outline" className="text-[9px] border-cyan-400/30 text-cyan-400 px-1.5 py-0">
                    {logs.length}
                  </Badge>
                </div>
                {logsExpanded ? (
                  <ChevronDownIcon className="h-3.5 w-3.5 text-cyan-400" />
                ) : (
                  <ChevronUpIcon className="h-3.5 w-3.5 text-cyan-400" />
                )}
              </button>

              {/* Logs content */}
              {logsExpanded && (
                <div className="flex-1 overflow-y-auto p-2 font-mono text-[10px] space-y-0.5 bg-black/20">
                  {logs.map((log, index) => (
                    <div
                      key={index}
                      className={cn(
                        "transition-all py-0.5 px-1.5 rounded border-l-2",
                        log.type === 'error' && "text-red-400 font-semibold border-red-400 bg-red-500/10",
                        log.type === 'warn' && "text-yellow-400 border-yellow-400 bg-yellow-500/10",
                        log.type === 'info' && "text-blue-400 border-blue-400 bg-blue-500/5",
                        log.type === 'debug' && "text-gray-500 border-gray-500 bg-gray-500/5",
                        log.type === 'success' && "text-green-400 font-semibold border-green-400 bg-green-500/10"
                      )}
                    >
                      <span className="text-gray-600 text-[9px] mr-1.5">
                        {new Date(log.timestamp).toLocaleTimeString()}
                      </span>
                      {log.message}
                    </div>
                  ))}
                  <div ref={logsEndRef} />
                </div>
              )}
            </div>
          </ResizablePanel>
        </ResizablePanelGroup>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default BrowserAutomationModal;
