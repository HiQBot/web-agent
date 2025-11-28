import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  PlusIcon, 
  PencilIcon, 
  TrashIcon, 
  PlayIcon,
  EyeIcon,
  DocumentTextIcon,
  CalendarIcon,
  LinkIcon
} from '@heroicons/react/24/outline';
import toast from 'react-hot-toast';

interface TestPlan {
  id: string;
  name: string;
  description: string;
  url: string;
  website_name?: string;
  status: string;
  created_at: string;
  updated_at?: string;
}

const TestPlans: React.FC = () => {
  const [isCreating, setIsCreating] = useState(false);
  // Removed unused editingPlan state
  const [newPlan, setNewPlan] = useState({
    description: '',
    url: '',
    website_name: ''
  });

  const queryClient = useQueryClient();

  // Fetch test plans
  const { data: testPlans, isLoading } = useQuery<TestPlan[]>({
    queryKey: ['testPlans'],
    queryFn: async () => {
      const response = await fetch('/api/v1/tests/test-plans');
      const data = await response.json();
      return data.test_plans || [];
    },
    // Remove automatic polling - we have WebSocket for real-time updates
    // refetchInterval: 5000,
  });

  // Create test plan mutation
  const createPlanMutation = useMutation({
    mutationFn: async (planData: typeof newPlan) => {
      const response = await fetch('/api/v1/tests/test-plans', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(planData),
      });
      if (!response.ok) throw new Error('Failed to create test plan');
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['testPlans'] });
      setIsCreating(false);
      setNewPlan({ description: '', url: '', website_name: '' });
      toast.success('Test plan created successfully!');
    },
    onError: () => {
      toast.error('Failed to create test plan');
    }
  });

  // Note: Delete and Execute mutations removed as backend doesn't support these endpoints

  const handleCreatePlan = () => {
    if (!newPlan.description.trim() || !newPlan.url.trim()) {
      toast.error('Please fill in both description and URL');
      return;
    }
    createPlanMutation.mutate(newPlan);
  };

  const handleDeletePlan = (planId: string) => {
    toast.error('Delete functionality not supported by backend');
  };

  const handleExecuteTest = (planId: string) => {
    toast('Test execution happens automatically when creating test plans. Check the Test Execution page for real-time updates.', {
      icon: 'ℹ️',
      duration: 4000,
    });
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'completed': return 'bg-success-100 text-success-800';
      case 'running': return 'bg-warning-100 text-warning-800';
      case 'failed': return 'bg-error-100 text-error-800';
      case 'pending': return 'bg-gray-100 text-gray-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Test Plans</h1>
            <p className="text-gray-600 mt-2">Manage your test plans and configurations</p>
          </div>
          <button
            onClick={() => setIsCreating(true)}
            className="flex items-center space-x-2 bg-primary-600 text-white px-4 py-2 rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <PlusIcon className="w-5 h-5" />
            <span>New Test Plan</span>
          </button>
        </div>
      </div>

      {/* Create New Plan Modal */}
      {isCreating && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Create New Test Plan</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Test Description
              </label>
              <textarea
                value={newPlan.description}
                onChange={(e) => setNewPlan({ ...newPlan, description: e.target.value })}
                placeholder="Describe what you want to test..."
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                rows={3}
              />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Website URL
                </label>
                <input
                  type="url"
                  value={newPlan.url}
                  onChange={(e) => setNewPlan({ ...newPlan, url: e.target.value })}
                  placeholder="https://www.example.com"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Website Name (Optional)
                </label>
                <input
                  type="text"
                  value={newPlan.website_name}
                  onChange={(e) => setNewPlan({ ...newPlan, website_name: e.target.value })}
                  placeholder="My Website"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
            </div>
            <div className="flex space-x-3">
              <button
                onClick={handleCreatePlan}
                disabled={createPlanMutation.isPending}
                className="bg-primary-600 text-white px-4 py-2 rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:opacity-50"
              >
                {createPlanMutation.isPending ? 'Creating...' : 'Create Plan'}
              </button>
              <button
                onClick={() => setIsCreating(false)}
                className="bg-gray-600 text-white px-4 py-2 rounded-md hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Test Plans List */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">All Test Plans</h2>
        </div>
        
        {isLoading ? (
          <div className="p-6 text-center text-gray-500">
            Loading test plans...
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {testPlans?.map((testPlan) => (
              <div key={testPlan.id} className="p-6">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-3">
                      <DocumentTextIcon className="w-6 h-6 text-primary-600" />
                      <div>
                        <h3 className="text-lg font-medium text-gray-900">{testPlan.name}</h3>
                        <p className="text-gray-600 mt-1">{testPlan.description}</p>
                      </div>
                    </div>
                    
                    <div className="mt-3 flex flex-wrap items-center gap-4 text-sm text-gray-500">
                      <div className="flex items-center space-x-1">
                        <LinkIcon className="w-4 h-4" />
                        <span className="truncate max-w-xs">{testPlan.url}</span>
                      </div>
                      <div className="flex items-center space-x-1">
                        <CalendarIcon className="w-4 h-4" />
                        <span>{new Date(testPlan.created_at).toLocaleDateString()}</span>
                      </div>
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(testPlan.status)}`}>
                        {testPlan.status}
                      </span>
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-2 ml-4">
                    <button
                      onClick={() => handleExecuteTest(testPlan.id)}
                      className="flex items-center space-x-2 bg-success-600 text-white px-3 py-2 rounded-md hover:bg-success-700 focus:outline-none focus:ring-2 focus:ring-success-500 text-sm"
                    >
                      <PlayIcon className="w-4 h-4" />
                      <span>Execute</span>
                    </button>
                    <button className="flex items-center space-x-2 bg-gray-600 text-white px-3 py-2 rounded-md hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500 text-sm">
                      <EyeIcon className="w-4 h-4" />
                      <span>View</span>
                    </button>
                    <button className="flex items-center space-x-2 bg-warning-600 text-white px-3 py-2 rounded-md hover:bg-warning-700 focus:outline-none focus:ring-2 focus:ring-warning-500 text-sm">
                      <PencilIcon className="w-4 h-4" />
                      <span>Edit</span>
                    </button>
                    <button
                      onClick={() => handleDeletePlan(testPlan.id)}
                      className="flex items-center space-x-2 bg-error-600 text-white px-3 py-2 rounded-md hover:bg-error-700 focus:outline-none focus:ring-2 focus:ring-error-500 text-sm"
                    >
                      <TrashIcon className="w-4 h-4" />
                      <span>Delete</span>
                    </button>
                  </div>
                </div>
              </div>
            ))}
            
            {(!testPlans || testPlans.length === 0) && !isLoading && (
              <div className="p-6 text-center text-gray-500">
                <DocumentTextIcon className="w-12 h-12 mx-auto text-gray-300 mb-4" />
                <p className="text-lg font-medium">No test plans yet</p>
                <p className="text-sm">Create your first test plan to get started with automated testing.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default TestPlans;
