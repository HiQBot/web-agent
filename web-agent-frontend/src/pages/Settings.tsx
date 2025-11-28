import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  CogIcon,
  GlobeAltIcon,
  WifiIcon,
  BellIcon,
  EyeIcon,
  EyeSlashIcon,
  CheckIcon,
  XMarkIcon
} from '@heroicons/react/24/outline';
import toast from 'react-hot-toast';

interface AppSettings {
  api_url: string;
  websocket_url: string;
  browser_timeout: number;
  screenshot_interval: number;
  recording_enabled: boolean;
  auto_retry_failed_tests: boolean;
  max_retry_attempts: number;
  notification_enabled: boolean;
  email_notifications: boolean;
  webhook_url?: string;
}

const Settings: React.FC = () => {
  const [settings, setSettings] = useState<AppSettings>({
    api_url: 'http://localhost:8000',
    websocket_url: 'ws://localhost:8000/ws',
    browser_timeout: 30,
    screenshot_interval: 5,
    recording_enabled: true,
    auto_retry_failed_tests: true,
    max_retry_attempts: 3,
    notification_enabled: true,
    email_notifications: false,
    webhook_url: ''
  });
  
  const [showApiKey, setShowApiKey] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [isTestingConnection, setIsTestingConnection] = useState(false);

  const queryClient = useQueryClient();

  // Fetch current settings
  const { data: currentSettings, isLoading } = useQuery<AppSettings>({
    queryKey: ['settings'],
    queryFn: async () => {
      const response = await fetch('/api/v1/settings');
      const data = await response.json();
      return data.settings;
    }
  });

  // Update settings when data is loaded
  React.useEffect(() => {
    if (currentSettings) {
      setSettings(currentSettings);
    }
  }, [currentSettings]);

  // Save settings mutation
  const saveSettingsMutation = useMutation({
    mutationFn: async (newSettings: AppSettings) => {
      const response = await fetch('/api/v1/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newSettings),
      });
      if (!response.ok) throw new Error('Failed to save settings');
      return response.json();
    },
    onSuccess: () => {
      toast.success('Settings saved successfully!');
      queryClient.invalidateQueries({ queryKey: ['settings'] });
    },
    onError: () => {
      toast.error('Failed to save settings');
    }
  });

  // Test connection mutation
  const testConnectionMutation = useMutation({
    mutationFn: async () => {
      const response = await fetch('/api/v1/health');
      if (!response.ok) throw new Error('Connection failed');
      return response.json();
    },
    onSuccess: () => {
      toast.success('Connection test successful!');
    },
    onError: () => {
      toast.error('Connection test failed');
    }
  });

  const handleSaveSettings = () => {
    saveSettingsMutation.mutate(settings);
  };

  const handleTestConnection = async () => {
    setIsTestingConnection(true);
    try {
      await testConnectionMutation.mutateAsync();
    } finally {
      setIsTestingConnection(false);
    }
  };

  const handleResetSettings = () => {
    if (window.confirm('Are you sure you want to reset all settings to default values?')) {
      setSettings({
        api_url: 'http://localhost:8000',
        websocket_url: 'ws://localhost:8000/ws',
        browser_timeout: 30,
        screenshot_interval: 5,
        recording_enabled: true,
        auto_retry_failed_tests: true,
        max_retry_attempts: 3,
        notification_enabled: true,
        email_notifications: false,
        webhook_url: ''
      });
      toast.success('Settings reset to defaults');
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="bg-gray-800 rounded-lg shadow p-6">
          <div className="animate-pulse">
            <div className="h-8 bg-gray-700 rounded w-1/4 mb-2"></div>
            <div className="h-4 bg-gray-700 rounded w-1/2"></div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gray-800 rounded-lg shadow p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white">Settings</h1>
            <p className="text-gray-300 mt-2">Configure your testing environment and preferences</p>
          </div>
          <div className="flex space-x-3">
            <button
              onClick={handleTestConnection}
              disabled={isTestingConnection}
              className="flex items-center space-x-2 bg-cyan-600 text-white px-4 py-2 rounded-md hover:bg-cyan-700 focus:outline-none focus:ring-2 focus:ring-cyan-500 disabled:opacity-50"
            >
              <WifiIcon className="w-4 h-4" />
              <span>{isTestingConnection ? 'Testing...' : 'Test Connection'}</span>
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* API Configuration */}
        <div className="bg-gray-800 rounded-lg shadow p-6">
          <div className="flex items-center space-x-2 mb-4">
            <GlobeAltIcon className="w-6 h-6 text-cyan-400" />
            <h2 className="text-xl font-semibold text-white">API Configuration</h2>
          </div>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                API Base URL
              </label>
              <input
                type="url"
                value={settings.api_url}
                onChange={(e) => setSettings({ ...settings, api_url: e.target.value })}
                className="w-full px-3 py-2 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-gray-700 text-white placeholder-gray-400"
                placeholder="http://localhost:8000"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                WebSocket URL
              </label>
              <input
                type="url"
                value={settings.websocket_url}
                onChange={(e) => setSettings({ ...settings, websocket_url: e.target.value })}
                className="w-full px-3 py-2 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-gray-700 text-white placeholder-gray-400"
                placeholder="ws://localhost:8000/ws"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                API Key (Optional)
              </label>
              <div className="relative">
                <input
                  type={showApiKey ? 'text' : 'password'}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  className="w-full px-3 py-2 pr-10 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-gray-700 text-white placeholder-gray-400"
                  placeholder="Enter your API key"
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center"
                >
                  {showApiKey ? (
                    <EyeSlashIcon className="w-4 h-4 text-gray-400" />
                  ) : (
                    <EyeIcon className="w-4 h-4 text-gray-400" />
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Browser Settings */}
        <div className="bg-gray-800 rounded-lg shadow p-6">
          <div className="flex items-center space-x-2 mb-4">
            <CogIcon className="w-6 h-6 text-cyan-400" />
            <h2 className="text-xl font-semibold text-white">Browser Settings</h2>
          </div>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Browser Timeout (seconds)
              </label>
              <input
                type="number"
                min="5"
                max="300"
                value={settings.browser_timeout}
                onChange={(e) => setSettings({ ...settings, browser_timeout: parseInt(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-gray-700 text-white placeholder-gray-400"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Screenshot Interval (seconds)
              </label>
              <input
                type="number"
                min="1"
                max="60"
                value={settings.screenshot_interval}
                onChange={(e) => setSettings({ ...settings, screenshot_interval: parseInt(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-gray-700 text-white placeholder-gray-400"
              />
            </div>

            <div className="flex items-center space-x-3">
              <input
                type="checkbox"
                id="recording_enabled"
                checked={settings.recording_enabled}
                onChange={(e) => setSettings({ ...settings, recording_enabled: e.target.checked })}
                className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              />
              <label htmlFor="recording_enabled" className="text-sm font-medium text-gray-300">
                Enable test recording
              </label>
            </div>
          </div>
        </div>

        {/* Test Execution Settings */}
        <div className="bg-gray-800 rounded-lg shadow p-6">
          <div className="flex items-center space-x-2 mb-4">
            <CogIcon className="w-6 h-6 text-cyan-400" />
            <h2 className="text-xl font-semibold text-white">Test Execution</h2>
          </div>
          
          <div className="space-y-4">
            <div className="flex items-center space-x-3">
              <input
                type="checkbox"
                id="auto_retry"
                checked={settings.auto_retry_failed_tests}
                onChange={(e) => setSettings({ ...settings, auto_retry_failed_tests: e.target.checked })}
                className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              />
              <label htmlFor="auto_retry" className="text-sm font-medium text-gray-300">
                Auto-retry failed tests
              </label>
            </div>

            {settings.auto_retry_failed_tests && (
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Max Retry Attempts
                </label>
                <input
                  type="number"
                  min="1"
                  max="10"
                  value={settings.max_retry_attempts}
                  onChange={(e) => setSettings({ ...settings, max_retry_attempts: parseInt(e.target.value) })}
                  className="w-full px-3 py-2 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-gray-700 text-white placeholder-gray-400"
                />
              </div>
            )}
          </div>
        </div>

        {/* Notifications */}
        <div className="bg-gray-800 rounded-lg shadow p-6">
          <div className="flex items-center space-x-2 mb-4">
            <BellIcon className="w-6 h-6 text-cyan-400" />
            <h2 className="text-xl font-semibold text-white">Notifications</h2>
          </div>
          
          <div className="space-y-4">
            <div className="flex items-center space-x-3">
              <input
                type="checkbox"
                id="notifications_enabled"
                checked={settings.notification_enabled}
                onChange={(e) => setSettings({ ...settings, notification_enabled: e.target.checked })}
                className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              />
              <label htmlFor="notifications_enabled" className="text-sm font-medium text-gray-300">
                Enable notifications
              </label>
            </div>

            <div className="flex items-center space-x-3">
              <input
                type="checkbox"
                id="email_notifications"
                checked={settings.email_notifications}
                onChange={(e) => setSettings({ ...settings, email_notifications: e.target.checked })}
                className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                disabled={!settings.notification_enabled}
              />
              <label htmlFor="email_notifications" className="text-sm font-medium text-gray-300">
                Email notifications
              </label>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Webhook URL (Optional)
              </label>
              <input
                type="url"
                value={settings.webhook_url || ''}
                onChange={(e) => setSettings({ ...settings, webhook_url: e.target.value })}
                className="w-full px-3 py-2 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-cyan-500 bg-gray-700 text-white placeholder-gray-400"
                placeholder="https://hooks.slack.com/services/..."
                disabled={!settings.notification_enabled}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="bg-gray-800 rounded-lg shadow p-6">
        <div className="flex items-center justify-between">
          <button
            onClick={handleResetSettings}
            className="flex items-center space-x-2 bg-gray-600 text-white px-4 py-2 rounded-md hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500"
          >
            <XMarkIcon className="w-4 h-4" />
            <span>Reset to Defaults</span>
          </button>
          
          <div className="flex space-x-3">
            <button
              onClick={() => window.location.reload()}
              className="flex items-center space-x-2 bg-gray-600 text-white px-4 py-2 rounded-md hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500"
            >
              <span>Cancel</span>
            </button>
            <button
              onClick={handleSaveSettings}
              disabled={saveSettingsMutation.isPending}
              className="flex items-center space-x-2 bg-cyan-600 text-white px-4 py-2 rounded-md hover:bg-cyan-700 focus:outline-none focus:ring-2 focus:ring-cyan-500 disabled:opacity-50"
            >
              <CheckIcon className="w-4 h-4" />
              <span>{saveSettingsMutation.isPending ? 'Saving...' : 'Save Settings'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Settings;
