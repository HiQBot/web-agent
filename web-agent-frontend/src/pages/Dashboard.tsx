import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { PlayIcon, ClockIcon, CheckCircleIcon, XCircleIcon, RocketLaunchIcon, ChartBarIcon, BeakerIcon, SparklesIcon, TvIcon } from '@heroicons/react/24/outline';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/components/ui/use-toast';
import BrowserAutomationModal from '../components/BrowserAutomationModal';

interface TestPlan {
  id: string;
  name: string;
  description: string;
  url: string;
  website_name?: string;
  status: string;
  created_at: string;
}

const Dashboard: React.FC = () => {
  const { toast } = useToast();
  const [newTestDescription, setNewTestDescription] = useState('');
  const [newTestUrl, setNewTestUrl] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedTest, setSelectedTest] = useState<TestPlan | null>(null);

  const { data: testPlans, refetch: refetchTestPlans } = useQuery<TestPlan[]>({
    queryKey: ['testPlans'],
    queryFn: async () => {
      // For now, return mock data - in production this would fetch from a database
      const mockTests: TestPlan[] = [];
      return mockTests;
    },
  });

  const totalTests = testPlans?.length || 0;
  const passedTests = testPlans?.filter(p => p.status === 'completed').length || 0;
  const failedTests = testPlans?.filter(p => p.status === 'failed').length || 0;
  const runningTests = testPlans?.filter(p => p.status === 'running').length || 0;
  const passRate = totalTests > 0 ? Math.round((passedTests / totalTests) * 100) : 0;

  const createTestPlan = async () => {
    if (!newTestDescription.trim() || !newTestUrl.trim()) {
      toast({ title: "Missing information", description: "Please fill in both fields", variant: "destructive" });
      return;
    }

    setIsCreating(true);
    let normalizedUrl = newTestUrl.trim();
    if (!normalizedUrl.startsWith('http')) normalizedUrl = `https://${normalizedUrl}`;

    try {
      // Create a test object for the modal
      const testPlan: TestPlan = {
        id: `test_${Date.now()}`,
        name: `Test: ${newTestDescription.substring(0, 50)}`,
        description: newTestDescription,
        url: normalizedUrl,
        status: 'pending',
        created_at: new Date().toISOString(),
      };

      // Open modal immediately to show live execution
      setSelectedTest(testPlan);
      setModalOpen(true);

      setNewTestDescription('');
      setNewTestUrl('');
      toast({ title: "Test started", description: "Watch live automation in the modal" });

    } catch (error) {
      toast({ title: "Failed", description: error instanceof Error ? error.message : 'Error', variant: "destructive" });
    } finally {
      setIsCreating(false);
    }
  };

  const executeTest = (testPlan: TestPlan) => {
    setSelectedTest(testPlan);
    setModalOpen(true);
    toast({ title: "Test started", description: "Watch live automation in the modal" });
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed': return <Badge variant="success" className="text-xs"><CheckCircleIcon className="w-3 h-3 mr-1" />Passed</Badge>;
      case 'failed': return <Badge variant="destructive" className="text-xs"><XCircleIcon className="w-3 h-3 mr-1" />Failed</Badge>;
      case 'running': return <Badge variant="warning" className="text-xs animate-pulse"><ClockIcon className="w-3 h-3 mr-1" />Running</Badge>;
      default: return <Badge variant="outline" className="text-xs">{status}</Badge>;
    }
  };

  return (
    <div className="p-6 space-y-5">
      {/* BENTO GRID LAYOUT - Asymmetric Modern Design */}
      <div className="grid grid-cols-12 gap-4 auto-rows-[140px]">

        {/* MAIN HERO CARD - Circular Radial Progress (spans 8 cols, 2 rows) */}
        <div className="col-span-8 row-span-2 glass-strong rounded-2xl p-6 border-4 border-black/20 shadow-[8px_8px_0px_0px_rgba(0,0,0,0.3)] hover:shadow-[12px_12px_0px_0px_rgba(0,0,0,0.4)] transition-all duration-300 relative overflow-hidden group bg-gradient-to-br from-blue-500/10 via-purple-500/10 to-pink-500/10">
          {/* Animated orbs */}
          <div className="absolute -top-20 -right-20 w-48 h-48 bg-gradient-to-br from-cyan-400/30 to-blue-500/30 rounded-full blur-3xl animate-pulse"></div>
          <div className="absolute -bottom-20 -left-20 w-48 h-48 bg-gradient-to-tr from-purple-400/30 to-pink-500/30 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1.5s' }}></div>

          <div className="relative z-10 h-full flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-2xl font-black text-white tracking-tight">Test Analytics</h2>
                <p className="text-xs text-cyan-400 font-medium mt-0.5">Real-time Quality Metrics</p>
              </div>
              <div className="flex items-center gap-2 px-3 py-1.5 bg-gradient-to-r from-green-500/20 to-emerald-500/20 border-2 border-green-400/40 rounded-lg shadow-lg">
                <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse shadow-lg shadow-green-400/50"></div>
                <span className="text-xs font-bold text-green-300">Live</span>
              </div>
            </div>

            {/* Circular Progress Rings - Side by side */}
            <div className="flex-1 flex items-center justify-around px-8">

              {/* Total Tests Circle */}
              <div className="relative group/circle">
                <svg className="w-28 h-28 transform -rotate-90 group-hover/circle:scale-110 transition-transform duration-300">
                  <circle cx="56" cy="56" r="50" stroke="rgba(59, 130, 246, 0.2)" strokeWidth="8" fill="none" />
                  <circle
                    cx="56" cy="56" r="50"
                    stroke="url(#blueGradient)"
                    strokeWidth="8"
                    fill="none"
                    strokeLinecap="round"
                    strokeDasharray={`${2 * Math.PI * 50}`}
                    strokeDashoffset={0}
                    className="transition-all duration-1000"
                  />
                  <defs>
                    <linearGradient id="blueGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" stopColor="#3b82f6" />
                      <stop offset="100%" stopColor="#06b6d4" />
                    </linearGradient>
                  </defs>
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <ChartBarIcon className="w-6 h-6 text-blue-400 mb-1" />
                  <div className="text-2xl font-black text-white">{totalTests}</div>
                  <div className="text-[9px] text-muted-foreground uppercase tracking-wider">Total</div>
                </div>
              </div>

              {/* Passed Tests Circle */}
              <div className="relative group/circle">
                <svg className="w-28 h-28 transform -rotate-90 group-hover/circle:scale-110 transition-transform duration-300">
                  <circle cx="56" cy="56" r="50" stroke="rgba(34, 197, 94, 0.2)" strokeWidth="8" fill="none" />
                  <circle
                    cx="56" cy="56" r="50"
                    stroke="url(#greenGradient)"
                    strokeWidth="8"
                    fill="none"
                    strokeLinecap="round"
                    strokeDasharray={`${2 * Math.PI * 50}`}
                    strokeDashoffset={totalTests > 0 ? (2 * Math.PI * 50) * (1 - passedTests / totalTests) : (2 * Math.PI * 50)}
                    className="transition-all duration-1000"
                  />
                  <defs>
                    <linearGradient id="greenGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" stopColor="#22c55e" />
                      <stop offset="100%" stopColor="#10b981" />
                    </linearGradient>
                  </defs>
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <CheckCircleIcon className="w-6 h-6 text-green-400 mb-1" />
                  <div className="text-2xl font-black text-white">{passedTests}</div>
                  <div className="text-[9px] text-muted-foreground uppercase tracking-wider">Passed</div>
                </div>
              </div>

              {/* Failed Tests Circle */}
              <div className="relative group/circle">
                <svg className="w-28 h-28 transform -rotate-90 group-hover/circle:scale-110 transition-transform duration-300">
                  <circle cx="56" cy="56" r="50" stroke="rgba(239, 68, 68, 0.2)" strokeWidth="8" fill="none" />
                  <circle
                    cx="56" cy="56" r="50"
                    stroke="url(#redGradient)"
                    strokeWidth="8"
                    fill="none"
                    strokeLinecap="round"
                    strokeDasharray={`${2 * Math.PI * 50}`}
                    strokeDashoffset={totalTests > 0 ? (2 * Math.PI * 50) * (1 - failedTests / totalTests) : (2 * Math.PI * 50)}
                    className="transition-all duration-1000"
                  />
                  <defs>
                    <linearGradient id="redGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" stopColor="#ef4444" />
                      <stop offset="100%" stopColor="#f43f5e" />
                    </linearGradient>
                  </defs>
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <XCircleIcon className="w-6 h-6 text-red-400 mb-1" />
                  <div className="text-2xl font-black text-white">{failedTests}</div>
                  <div className="text-[9px] text-muted-foreground uppercase tracking-wider">Failed</div>
                </div>
              </div>

              {/* Running Tests Circle - Animated */}
              <div className="relative group/circle">
                <svg className="w-28 h-28 transform -rotate-90 group-hover/circle:scale-110 transition-transform duration-300">
                  <circle cx="56" cy="56" r="50" stroke="rgba(234, 179, 8, 0.2)" strokeWidth="8" fill="none" />
                  <circle
                    cx="56" cy="56" r="50"
                    stroke="url(#yellowGradient)"
                    strokeWidth="8"
                    fill="none"
                    strokeLinecap="round"
                    strokeDasharray={`${2 * Math.PI * 50}`}
                    strokeDashoffset={totalTests > 0 ? (2 * Math.PI * 50) * (1 - runningTests / totalTests) : (2 * Math.PI * 50)}
                    className="transition-all duration-1000 animate-pulse"
                  />
                  <defs>
                    <linearGradient id="yellowGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" stopColor="#eab308" />
                      <stop offset="100%" stopColor="#f97316" />
                    </linearGradient>
                  </defs>
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <ClockIcon className="w-6 h-6 text-yellow-400 mb-1 animate-pulse" />
                  <div className="text-2xl font-black text-white">{runningTests}</div>
                  <div className="text-[9px] text-muted-foreground uppercase tracking-wider">Running</div>
                </div>
              </div>

            </div>

            {/* Bottom Stats Bar */}
            <div className="mt-auto pt-3 border-t-2 border-white/10 flex items-center justify-between text-xs">
              <div className="flex items-center gap-4">
                <span className="text-muted-foreground">Success Rate:</span>
                <span className={`text-lg font-black ${passRate >= 70 ? 'text-green-400' : passRate >= 40 ? 'text-yellow-400' : 'text-red-400'}`}>
                  {passRate}%
                </span>
              </div>
              <div className="text-muted-foreground">Updated: <span className="text-cyan-400 font-semibold">Now</span></div>
            </div>
          </div>
        </div>

        {/* PASS RATE CARD - Vertical (spans 4 cols, 2 rows) */}
        <div className="col-span-4 row-span-2 glass-strong rounded-2xl p-5 border-4 border-black/20 shadow-[8px_8px_0px_0px_rgba(0,0,0,0.3)] hover:shadow-[12px_12px_0px_0px_rgba(0,0,0,0.4)] transition-all duration-300 bg-gradient-to-br from-emerald-500/10 to-green-500/10 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center shadow-lg border-2 border-green-300/30">
                <SparklesIcon className="w-5 h-5 text-white" />
              </div>
              <div>
                <div className="text-xs text-muted-foreground uppercase tracking-wider">Pass Rate</div>
              </div>
            </div>
            <div className="text-5xl font-black text-white mb-2 leading-none">
              {passRate}<span className="text-2xl text-green-400">%</span>
            </div>
            <div className="text-xs text-green-300 font-semibold">
              {passedTests} of {totalTests} tests passed
            </div>
          </div>

          {/* Visual Progress Bar */}
          <div className="space-y-2">
            <div className="h-3 bg-white/10 rounded-full overflow-hidden border-2 border-black/20 shadow-inner">
              <div
                className="h-full bg-gradient-to-r from-green-500 to-emerald-400 transition-all duration-1000 rounded-full shadow-lg"
                style={{ width: `${passRate}%` }}
              ></div>
            </div>
            <div className="flex justify-between text-[10px] text-muted-foreground font-medium">
              <span>0%</span>
              <span>50%</span>
              <span>100%</span>
            </div>
          </div>
        </div>

      </div>

      {/* CREATE TEST - Bento Card with Visual Flow (spans full width) */}
      <div className="glass-strong rounded-2xl p-6 border-4 border-black/20 shadow-[8px_8px_0px_0px_rgba(0,0,0,0.3)] hover:shadow-[10px_10px_0px_0px_rgba(0,0,0,0.4)] transition-all duration-300 bg-gradient-to-br from-purple-500/10 via-pink-500/10 to-orange-500/10 relative overflow-hidden">
        {/* Background accent */}
        <div className="absolute top-0 right-0 w-64 h-64 bg-gradient-to-bl from-pink-400/20 to-purple-500/20 rounded-full blur-3xl"></div>

        <div className="relative z-10">
          {/* Header with icon */}
          <div className="flex items-center gap-3 mb-5">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500 to-pink-600 flex items-center justify-center shadow-lg border-2 border-purple-300/30 transform hover:rotate-12 hover:scale-110 transition-all duration-300">
              <RocketLaunchIcon className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-black text-white tracking-tight">Create New Test</h2>
              <p className="text-xs text-purple-300 font-medium">Launch automated QA workflow</p>
            </div>
          </div>

          <form onSubmit={(e) => { e.preventDefault(); createTestPlan(); }} className="space-y-4">
            <div className="grid md:grid-cols-12 gap-4">
              {/* Test Description - 7 cols */}
              <div className="md:col-span-7 space-y-2">
                <label className="text-xs font-bold text-blue-400 uppercase tracking-wider flex items-center gap-1">
                  <BeakerIcon className="w-3 h-3" />
                  Test Description
                </label>
                <textarea
                  value={newTestDescription}
                  onChange={(e) => setNewTestDescription(e.target.value)}
                  rows={3}
                  className="w-full px-4 py-3 text-sm glass border-2 border-white/20 rounded-xl text-foreground focus:ring-2 focus:ring-blue-500 focus:border-blue-400 resize-none font-medium transition-all duration-200 hover:border-white/30"
                  placeholder="E.g., Navigate to GitHub and search for React repositories..."
                />
              </div>

              {/* Target URL + Quick Tips - 5 cols */}
              <div className="md:col-span-5 space-y-3">
                <div className="space-y-2">
                  <label className="text-xs font-bold text-purple-400 uppercase tracking-wider flex items-center gap-1">
                    <SparklesIcon className="w-3 h-3" />
                    Target URL
                  </label>
                  <input
                    type="url"
                    value={newTestUrl}
                    onChange={(e) => setNewTestUrl(e.target.value)}
                    placeholder="https://example.com"
                    className="w-full px-4 py-3 text-sm glass border-2 border-white/20 rounded-xl text-foreground focus:ring-2 focus:ring-purple-500 focus:border-purple-400 font-medium transition-all duration-200 hover:border-white/30"
                  />
                </div>

                {/* Quick tips box */}
                <div className="glass border-2 border-cyan-400/30 rounded-xl p-3 bg-cyan-500/5">
                  <div className="text-xs font-bold text-cyan-300 flex items-center gap-1 mb-2">
                    <SparklesIcon className="w-3 h-3" />
                    Quick Tips
                  </div>
                  <div className="text-[11px] text-muted-foreground space-y-1">
                    <div className="flex items-center gap-1">
                      <div className="w-1 h-1 rounded-full bg-cyan-400"></div>
                      Auto-executes after creation
                    </div>
                    <div className="flex items-center gap-1">
                      <div className="w-1 h-1 rounded-full bg-cyan-400"></div>
                      Live browser preview available
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex justify-between items-center pt-2">
              {/* Live Preview Button */}
              <Button
                type="button"
                onClick={() => {
                  setSelectedTest({
                    id: 'live_preview',
                    name: 'Live Browser Preview',
                    description: 'View live browser window',
                    url: 'http://localhost:8080',
                    status: 'running',
                    created_at: new Date().toISOString(),
                  });
                  setModalOpen(true);
                }}
                className="px-6 py-3 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-bold rounded-xl shadow-[6px_6px_0px_0px_rgba(0,0,0,0.3)] hover:shadow-[8px_8px_0px_0px_rgba(0,0,0,0.4)] transition-all duration-300 border-2 border-white/20 transform hover:-translate-y-1"
              >
                <span className="flex items-center gap-2">
                  <TvIcon className="w-5 h-5" />
                  Live Preview
                </span>
              </Button>

              {/* Launch Test Button */}
              <Button
                type="submit"
                disabled={isCreating}
                className="px-8 py-3 bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 hover:from-blue-500 hover:via-purple-500 hover:to-pink-500 text-white font-bold rounded-xl shadow-[6px_6px_0px_0px_rgba(0,0,0,0.3)] hover:shadow-[8px_8px_0px_0px_rgba(0,0,0,0.4)] transition-all duration-300 border-2 border-white/20 transform hover:-translate-y-1"
              >
                {isCreating ? (
                  <span className="flex items-center gap-2">
                    <ClockIcon className="w-5 h-5 animate-spin" />
                    Creating...
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    <RocketLaunchIcon className="w-5 h-5" />
                    Launch Test
                  </span>
                )}
              </Button>
            </div>
          </form>
        </div>
      </div>

      {/* RECENT TESTS - Kanban/Timeline Style with Bento Grid */}
      <div className="glass-strong rounded-2xl p-6 border-4 border-black/20 shadow-[8px_8px_0px_0px_rgba(0,0,0,0.3)] bg-gradient-to-br from-slate-500/5 via-blue-500/5 to-purple-500/5">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-600 flex items-center justify-center shadow-lg border-2 border-blue-300/30">
              <BeakerIcon className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-black text-white tracking-tight">Recent Tests</h2>
              <p className="text-xs text-blue-300 font-medium">Latest automation runs</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="glass border-2 border-white/30 text-xs font-bold px-3 py-1">
              {totalTests} Total
            </Badge>
          </div>
        </div>

        {testPlans && testPlans.length > 0 ? (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
            {testPlans.slice(0, 6).map((testPlan, index) => (
              <div
                key={testPlan.id}
                className="glass border-2 border-white/20 rounded-xl p-4 hover:border-white/40 transition-all duration-300 group hover:shadow-[6px_6px_0px_0px_rgba(0,0,0,0.2)] hover:-translate-y-1 bg-gradient-to-br from-white/5 to-transparent"
                style={{ animationDelay: `${index * 50}ms` }}
              >
                <div className="flex flex-col h-full gap-3">
                  {/* Header with status */}
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="font-bold text-sm text-white truncate group-hover:text-blue-300 transition-colors">
                        {testPlan.name}
                      </p>
                      <div className="text-[10px] text-muted-foreground mt-0.5 truncate">
                        {new Date(testPlan.created_at).toLocaleDateString('en-US', {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit'
                        })}
                      </div>
                    </div>
                    {getStatusBadge(testPlan.status)}
                  </div>

                  {/* URL Display */}
                  <a
                    href={testPlan.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[11px] text-blue-400 hover:text-cyan-300 hover:underline truncate block glass border border-white/10 px-2 py-1.5 rounded-lg font-medium transition-all"
                  >
                    🌐 {testPlan.url}
                  </a>

                  {/* Action Button */}
                  <Button
                    size="sm"
                    onClick={() => executeTest(testPlan)}
                    className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white border-2 border-white/20 shadow-[4px_4px_0px_0px_rgba(0,0,0,0.3)] hover:shadow-[5px_5px_0px_0px_rgba(0,0,0,0.4)] transition-all font-bold mt-auto"
                  >
                    <PlayIcon className="w-4 h-4 mr-1" />
                    Run Test
                  </Button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-16 glass border-2 border-dashed border-white/20 rounded-xl">
            <div className="w-20 h-20 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-blue-500/20 to-purple-500/20 flex items-center justify-center border-2 border-white/10">
              <BeakerIcon className="w-10 h-10 text-blue-400/40" />
            </div>
            <p className="text-sm font-bold text-white mb-1">No tests yet</p>
            <p className="text-xs text-muted-foreground">Create your first test above to get started!</p>
          </div>
        )}
      </div>

      <BrowserAutomationModal
        isOpen={modalOpen}
        onClose={() => { setModalOpen(false); setSelectedTest(null); }}
        testId={selectedTest?.id}
        testName={selectedTest?.name || 'Test Automation'}
        task={selectedTest?.description || 'Automated testing task'}
        startUrl={selectedTest?.url}
        browserUrl="http://localhost:8080"
      />
    </div>
  );
};

export default Dashboard;
