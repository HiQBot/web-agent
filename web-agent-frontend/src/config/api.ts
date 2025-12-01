/**
 * API Configuration
 * 
 * Centralized configuration for API endpoints and URLs.
 * Values are read from environment variables with fallback defaults.
 */

// Get API base URL from environment or use default
const getApiUrl = (): string => {
  return process.env.REACT_APP_API_URL || 'http://localhost:8000';
};

// Get WebSocket URL from environment or use default
const getWsUrl = (): string => {
  return process.env.REACT_APP_WS_URL || 'ws://localhost:8000';
};

// Get Browser URL from environment or use default
const getBrowserUrl = (): string => {
  return process.env.REACT_APP_BROWSER_URL || 'http://localhost:8080';
};

// Get API prefix from environment or use default
const getApiPrefix = (): string => {
  return process.env.REACT_APP_API_PREFIX || '/api/v1';
};

// Export configuration object
export const apiConfig = {
  // Base URLs
  apiUrl: getApiUrl(),
  wsUrl: getWsUrl(),
  browserUrl: getBrowserUrl(),
  apiPrefix: getApiPrefix(),
  
  // Full API endpoints
  get apiBaseUrl(): string {
    return `${this.apiUrl}${this.apiPrefix}`;
  },
  
  get wsBaseUrl(): string {
    return `${this.wsUrl}${this.apiPrefix}`;
  },
  
  // Specific endpoints
  endpoints: {
    // Workflow endpoints
    workflow: {
      run: '/workflow/run',
    },
    // Test endpoints
    tests: {
      testPlans: '/tests/test-plans',
      execute: '/tests/execute',
      running: '/tests/running',
      getById: (id: string) => `/tests/${id}`,
    },
    // Browser endpoints
    browser: {
      initPersistent: '/browser/init-persistent',
      stream: '/browser/stream',
    },
    // Health endpoint
    health: '/health',
  },
  
  // WebSocket endpoints
  ws: {
    main: '/ws',
    automation: (clientId: string, task: string, startUrl?: string, maxSteps?: number) => {
      const params = new URLSearchParams({
        client_id: clientId,
        task: task,
      });
      if (startUrl) params.append('start_url', startUrl);
      if (maxSteps) params.append('max_steps', maxSteps.toString());
      return `/ws/automation?${params.toString()}`;
    },
  },
};

// Helper function to build full API URL
export const buildApiUrl = (endpoint: string): string => {
  return `${apiConfig.apiBaseUrl}${endpoint}`;
};

// Helper function to build full WebSocket URL
export const buildWsUrl = (endpoint: string): string => {
  const wsBase = apiConfig.wsUrl.replace('http://', 'ws://').replace('https://', 'wss://');
  return `${wsBase}${apiConfig.apiPrefix}${endpoint}`;
};

export default apiConfig;

