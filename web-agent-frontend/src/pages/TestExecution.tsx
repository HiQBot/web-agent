import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useWebSocket } from '../context/WebSocketContext';
import { 
  PlayIcon, 
  StopIcon, 
  PauseIcon,
  EyeIcon,
  ChartBarIcon,
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  ArrowPathIcon
} from '@heroicons/react/24/outline';
import toast from 'react-hot-toast';
import BrowserView from '../components/BrowserView';

interface TestExecutionData {
  test_id: string;
  test_plan_id: string;
  test_plan_name: string;
  status: string;
  started_at: string;
  ended_at?: string;
  progress?: {
    current_step: number;
    total_steps: number;
    current_action?: string;
  };
  logs?: Array<{
    timestamp: string;
    level: string;
    message: string;
    step?: number;
  }>;
  screenshots?: Array<{
    timestamp: string;
    step: number;
    url: string;
  }>;
  recording?: {
    url: string;
    status: string;
  };
}

const TestExecution: React.FC = () => {
  const { isConnected, lastMessage } = useWebSocket();
  const [selectedTest, setSelectedTest] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  // Fetch running tests
  const { data: runningTests, refetch } = useQuery<TestExecutionData[]>({
    queryKey: ['runningTests'],
    queryFn: async () => {
      try {
        const response = await fetch(buildApiUrl(apiConfig.endpoints.tests.testPlans));
        if (!response.ok) {
          throw new Error('Failed to fetch running tests');
        }
        const data = await response.json();
        return data.test_plans || [];
      } catch (error) {
        console.error('Error fetching running tests:', error);
        return [];
      }
    },
    refetchInterval: autoRefresh ? 2000 : false,
  });

  // Fetch test details
  const { data: testDetails } = useQuery<TestExecutionData>({
    queryKey: ['testDetails', selectedTest],
    queryFn: async () => {
      if (!selectedTest) return null;
      try {
        const response = await fetch(buildApiUrl(apiConfig.endpoints.tests.getById(selectedTest)));
        if (!response.ok) {
          throw new Error('Failed to fetch test details');
        }
        const data = await response.json();
        return data.test_plan;
      } catch (error) {
        console.error('Error fetching test details:', error);
        return null;
      }
    },
    enabled: !!selectedTest,
    refetchInterval: autoRefresh ? 1000 : false,
  });

  // Handle WebSocket messages with live updates
  useEffect(() => {
    if (lastMessage && lastMessage.type === 'test_update') {
      const testId = lastMessage.test_id;
      const updateData = lastMessage.data;

      // Refetch running tests list
      refetch();

      // If this is the selected test, we'll see it in the refetch
      // Show toast notifications for important events
      if (updateData?.status === 'completed') {
        toast.success(`Test ${testId?.slice(0, 8) || 'Unknown'} completed!`);
      } else if (updateData?.status === 'failed') {
        toast.error(`Test ${testId?.slice(0, 8) || 'Unknown'} failed!`);
      }

      // Log the update message for debugging
      if (updateData?.message) {
        console.log(`Test ${testId}: ${updateData.message}`);
      }
    }
  }, [lastMessage, selectedTest, refetch]);

  // Note: Stop/Pause/Resume functionality removed as these endpoints don't exist in backend
  // Tests run to completion automatically

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'running': return 'bg-success-100 text-success-800';
      case 'paused': return 'bg-warning-100 text-warning-800';
      case 'completed': return 'bg-primary-100 text-primary-800';
      case 'failed': return 'bg-error-100 text-error-800';
      case 'stopped': return 'bg-gray-100 text-gray-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status.toLowerCase()) {
      case 'running': return <PlayIcon className="w-4 h-4" />;
      case 'paused': return <PauseIcon className="w-4 h-4" />;
      case 'completed': return <CheckCircleIcon className="w-4 h-4" />;
      case 'failed': return <XCircleIcon className="w-4 h-4" />;
      case 'stopped': return <StopIcon className="w-4 h-4" />;
      default: return <ExclamationTriangleIcon className="w-4 h-4" />;
    }
  };

  const formatDuration = (startTime: string, endTime?: string) => {
    const start = new Date(startTime);
    const end = endTime ? new Date(endTime) : new Date();
    const diff = end.getTime() - start.getTime();
    
    const minutes = Math.floor(diff / 60000);
    const seconds = Math.floor((diff % 60000) / 1000);
    
    return `${minutes}m ${seconds}s`;
  };

  const getProgressPercentage = (current: number | undefined, total: number | undefined) => {
    const currentStep = current || 0;
    const totalSteps = total || 0;
    return totalSteps > 0 ? Math.round((currentStep / totalSteps) * 100) : 0;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gray-800 rounded-lg shadow p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white">Test Execution</h1>
            <p className="text-gray-300 mt-2">Monitor and control test execution in real-time</p>
          </div>
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-success-500' : 'bg-error-500'}`}></div>
              <span className="text-sm text-gray-300">
                {isConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              />
              <span className="text-sm text-gray-300">Auto-refresh</span>
            </label>
            <button
              onClick={() => refetch()}
              className="flex items-center space-x-2 bg-cyan-600 text-white px-3 py-2 rounded-md hover:bg-cyan-700 focus:outline-none focus:ring-2 focus:ring-cyan-500"
            >
              <ArrowPathIcon className="w-4 h-4" />
              <span>Refresh</span>
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Running Tests List */}
        <div className="lg:col-span-1">
          <div className="bg-gray-800 rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-600">
              <h2 className="text-xl font-semibold text-white">Running Tests</h2>
            </div>
            <div className="divide-y divide-gray-600 max-h-96 overflow-y-auto">
              {runningTests?.map((test) => (
                <div
                  key={test.test_id}
                  className={`p-4 cursor-pointer hover:bg-gray-700 ${
                    selectedTest === test.test_id ? 'bg-cyan-900/50 border-r-4 border-cyan-500' : ''
                  }`}
                  onClick={() => setSelectedTest(test.test_id)}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <h3 className="text-sm font-medium text-white truncate">
                        {test.test_plan_name}
                      </h3>
                      <p className="text-xs text-gray-400 mt-1">ID: {test.test_id?.slice(0, 8) || 'N/A'}...</p>
                      <div className="mt-2 flex items-center space-x-2">
                        <span className={`px-2 py-1 rounded-full text-xs font-medium flex items-center space-x-1 ${getStatusColor(test.status)}`}>
                          {getStatusIcon(test.status)}
                          <span>{test.status}</span>
                        </span>
                      </div>
                    </div>
                    <div className="flex flex-col items-end space-y-1">
                      <span className="text-xs text-gray-400">
                        {formatDuration(test.started_at, test.ended_at)}
                      </span>
                      <div className="text-xs text-gray-400">
                        Step {test.progress?.current_step || 0}/{test.progress?.total_steps || 0}
                      </div>
                    </div>
                  </div>
                  <div className="mt-2">
                    <div className="w-full bg-gray-600 rounded-full h-2">
                      <div
                        className="bg-cyan-600 h-2 rounded-full transition-all duration-300"
                        style={{ width: `${getProgressPercentage(test.progress?.current_step || 0, test.progress?.total_steps || 0)}%` }}
                      ></div>
                    </div>
                  </div>
                </div>
              ))}
              {(!runningTests || runningTests.length === 0) && (
                <div className="p-6 text-center text-gray-400">
                  <ChartBarIcon className="w-12 h-12 mx-auto text-gray-500 mb-4" />
                  <p className="text-sm">No running tests</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Test Details */}
        <div className="lg:col-span-2">
          {selectedTest && testDetails ? (
            <div className="space-y-6">
              {/* Test Info */}
              <div className="bg-gray-800 rounded-lg shadow p-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xl font-semibold text-white">Test Details</h2>
                  <span className={`px-3 py-1 rounded-full text-sm font-medium flex items-center space-x-2 ${getStatusColor(testDetails.status)}`}>
                    {getStatusIcon(testDetails.status)}
                    <span>{testDetails.status}</span>
                  </span>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-300">Test Plan</label>
                    <p className="text-sm text-white">{testDetails.test_plan_name}</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-300">Duration</label>
                    <p className="text-sm text-white">{formatDuration(testDetails.started_at, testDetails.ended_at)}</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-300">Progress</label>
                    <p className="text-sm text-white">
                      {testDetails.progress?.current_step || 0} / {testDetails.progress?.total_steps || 0} steps
                      ({getProgressPercentage(testDetails.progress?.current_step || 0, testDetails.progress?.total_steps || 0)}%)
                    </p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-300">Current Action</label>
                    <p className="text-sm text-white">{testDetails.progress?.current_action || 'N/A'}</p>
                  </div>
                </div>

                {/* Progress Bar */}
                <div className="mb-4">
                  <div className="w-full bg-gray-600 rounded-full h-3">
                    <div
                      className="bg-cyan-600 h-3 rounded-full transition-all duration-500"
                      style={{ width: `${getProgressPercentage(testDetails.progress?.current_step || 0, testDetails.progress?.total_steps || 0)}%` }}
                    ></div>
                  </div>
                </div>

                {/* Control Buttons - Removed as backend doesn't support stop/pause/resume */}
                <div className="flex space-x-3">
                  <button className="flex items-center space-x-2 bg-gray-600 text-white px-4 py-2 rounded-md hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500">
                    <EyeIcon className="w-4 h-4" />
                    <span>View Recording</span>
                  </button>
                </div>
              </div>

              {/* Logs */}
              <div className="bg-gray-800 rounded-lg shadow">
                <div className="px-6 py-4 border-b border-gray-600">
                  <h3 className="text-lg font-semibold text-white">Execution Logs</h3>
                </div>
                <div className="max-h-96 overflow-y-auto">
                  {testDetails.logs?.map((log, index) => (
                    <div key={index} className="px-6 py-3 border-b border-gray-700 text-sm">
                      <div className="flex items-start space-x-3">
                        <span className="text-gray-400 text-xs mt-1">
                          {new Date(log.timestamp).toLocaleTimeString()}
                        </span>
                        <span className={`px-2 py-1 rounded text-xs font-medium ${
                          log.level === 'ERROR' ? 'bg-red-900/50 text-red-300' :
                          log.level === 'WARNING' ? 'bg-yellow-900/50 text-yellow-300' :
                          log.level === 'INFO' ? 'bg-cyan-900/50 text-cyan-300' :
                          'bg-gray-700 text-gray-300'
                        }`}>
                          {log.level}
                        </span>
                        {log.step && (
                          <span className="text-gray-400 text-xs">Step {log.step}</span>
                        )}
                      </div>
                      <p className="mt-1 text-white">{log.message}</p>
                    </div>
                  ))}
                  {(!testDetails.logs || testDetails.logs.length === 0) && (
                    <div className="p-6 text-center text-gray-400">
                      <p>No logs available yet</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-gray-800 rounded-lg shadow p-6 text-center text-gray-400">
              <ChartBarIcon className="w-16 h-16 mx-auto text-gray-500 mb-4" />
              <p className="text-lg font-medium">Select a test to view details</p>
              <p className="text-sm">Choose a running test from the list to see real-time execution details.</p>
            </div>
          )}
        </div>

        {/* Live Browser View */}
        <BrowserView 
          showByDefault={true}
          height="h-[600px]"
          title="Live Browser View"
          description="Watch AI testing in real-time"
        />
      </div>
    </div>
  );
};

export default TestExecution;
