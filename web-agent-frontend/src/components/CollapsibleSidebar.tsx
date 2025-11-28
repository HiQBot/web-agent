import React, { useState } from 'react';
import {
  HomeIcon,
  DocumentTextIcon,
  PlayIcon,
  Cog6ToothIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  Squares2X2Icon,
  SparklesIcon
} from '@heroicons/react/24/outline';

interface CollapsibleSidebarProps {
  currentPage: string;
  onPageChange: (page: string) => void;
}

const CollapsibleSidebar: React.FC<CollapsibleSidebarProps> = ({ currentPage, onPageChange }) => {
  const [isCollapsed, setIsCollapsed] = useState(false);

  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: HomeIcon, color: 'blue' },
    { id: 'test-plans', label: 'Test Plans', icon: DocumentTextIcon, color: 'purple' },
    { id: 'test-execution', label: 'Execution', icon: PlayIcon, color: 'green' },
    { id: 'settings', label: 'Settings', icon: Cog6ToothIcon, color: 'orange' },
  ];

  const getColorClasses = (color: string, isActive: boolean) => {
    const colors = {
      blue: isActive
        ? 'bg-blue-500/20 border-blue-400/50 text-blue-300 shadow-lg shadow-blue-500/20'
        : 'hover:bg-blue-500/10 hover:border-blue-400/30 hover:text-blue-300',
      purple: isActive
        ? 'bg-purple-500/20 border-purple-400/50 text-purple-300 shadow-lg shadow-purple-500/20'
        : 'hover:bg-purple-500/10 hover:border-purple-400/30 hover:text-purple-300',
      green: isActive
        ? 'bg-green-500/20 border-green-400/50 text-green-300 shadow-lg shadow-green-500/20'
        : 'hover:bg-green-500/10 hover:border-green-400/30 hover:text-green-300',
      orange: isActive
        ? 'bg-orange-500/20 border-orange-400/50 text-orange-300 shadow-lg shadow-orange-500/20'
        : 'hover:bg-orange-500/10 hover:border-orange-400/30 hover:text-orange-300',
    };
    return colors[color as keyof typeof colors] || colors.blue;
  };

  return (
    <aside
      className={`fixed left-0 top-0 h-full glass-strong border-r-4 border-black/20 backdrop-blur-xl transition-all duration-300 z-40 shadow-[8px_0px_0px_0px_rgba(0,0,0,0.3)] ${
        isCollapsed ? 'w-20' : 'w-64'
      }`}
    >
      <div className="flex flex-col h-full">
        {/* Logo Section - Enhanced */}
        <div className="h-16 flex items-center justify-between px-4 border-b-2 border-white/20 relative overflow-hidden">
          {/* Animated background gradient */}
          <div className="absolute inset-0 bg-gradient-to-r from-blue-500/10 via-purple-500/10 to-cyan-500/10"></div>
          <div className="absolute top-0 left-0 w-32 h-32 bg-gradient-to-br from-cyan-400/20 to-blue-500/20 rounded-full blur-3xl animate-pulse"></div>

          {!isCollapsed && (
            <div className="flex items-center gap-3 relative z-10">
              <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-blue-500 via-purple-500 to-cyan-500 flex items-center justify-center shadow-lg border-2 border-white/20 transform hover:scale-110 hover:rotate-12 transition-all duration-300">
                <Squares2X2Icon className="w-6 h-6 text-white" />
              </div>
              <div className="flex flex-col">
                <span className="text-base font-black bg-gradient-to-r from-blue-400 via-purple-400 to-cyan-400 bg-clip-text text-transparent">
                  HiQBot
                </span>
                <span className="text-[9px] text-cyan-400 font-bold uppercase tracking-wider -mt-0.5">Web Agent</span>
              </div>
            </div>
          )}
          {isCollapsed && (
            <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-blue-500 via-purple-500 to-cyan-500 flex items-center justify-center shadow-lg border-2 border-white/20 mx-auto transform hover:scale-110 hover:rotate-12 transition-all duration-300 relative z-10">
              <Squares2X2Icon className="w-6 h-6 text-white" />
            </div>
          )}
        </div>

        {/* AI Status Badge */}
        {!isCollapsed && (
          <div className="mx-3 mt-3 mb-2 glass border-2 border-green-400/40 rounded-xl p-2.5 bg-gradient-to-r from-green-500/10 to-emerald-500/10 shadow-lg">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse shadow-lg shadow-green-400/50"></div>
              <div className="flex-1">
                <div className="text-[10px] font-bold text-green-300 uppercase tracking-wider">AI Agent Active</div>
                <div className="text-[9px] text-muted-foreground">Ready to test</div>
              </div>
              <SparklesIcon className="w-4 h-4 text-green-400 animate-pulse" />
            </div>
          </div>
        )}

        {/* Navigation Items - Enhanced */}
        <nav className="flex-1 py-4 px-3">
          <div className="space-y-2">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = currentPage === item.id;

              return (
                <button
                  key={item.id}
                  onClick={() => onPageChange(item.id)}
                  className={`
                    w-full flex items-center gap-3 px-3 py-3 rounded-xl text-sm font-bold
                    transition-all duration-300 group relative border-2
                    ${isActive
                      ? `${getColorClasses(item.color, true)} shadow-[4px_4px_0px_0px_rgba(0,0,0,0.2)] translate-x-1`
                      : `text-muted-foreground border-transparent ${getColorClasses(item.color, false)} hover:shadow-[3px_3px_0px_0px_rgba(0,0,0,0.15)] hover:translate-x-0.5`
                    }
                  `}
                  title={isCollapsed ? item.label : undefined}
                >
                  <Icon className={`w-5 h-5 flex-shrink-0 transition-all duration-300 ${isActive ? 'scale-110' : 'group-hover:scale-110'}`} />
                  {!isCollapsed && (
                    <span className="transition-all duration-200">{item.label}</span>
                  )}
                  {isActive && !isCollapsed && (
                    <div className="ml-auto w-1.5 h-1.5 rounded-full bg-current animate-pulse"></div>
                  )}
                </button>
              );
            })}
          </div>
        </nav>

        {/* Quick Stats - Only when expanded */}
        {!isCollapsed && (
          <div className="mx-3 mb-3 glass border-2 border-white/20 rounded-xl p-3 bg-gradient-to-br from-blue-500/5 to-purple-500/5">
            <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider mb-2">Quick Stats</div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="glass border border-white/10 rounded-lg p-2 text-center">
                <div className="text-lg font-black text-blue-400">12</div>
                <div className="text-[9px] text-muted-foreground">Tests</div>
              </div>
              <div className="glass border border-white/10 rounded-lg p-2 text-center">
                <div className="text-lg font-black text-green-400">95%</div>
                <div className="text-[9px] text-muted-foreground">Pass</div>
              </div>
            </div>
          </div>
        )}

        {/* Collapse Toggle - Enhanced */}
        <div className="p-3 border-t-2 border-white/20">
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="w-full glass px-3 py-2.5 rounded-xl border-2 border-white/20 hover:border-white/40 transition-all duration-300 flex items-center justify-center gap-2 text-muted-foreground hover:text-white shadow-[4px_4px_0px_0px_rgba(0,0,0,0.2)] hover:shadow-[5px_5px_0px_0px_rgba(0,0,0,0.3)] hover:-translate-y-0.5 font-bold"
          >
            {isCollapsed ? (
              <ChevronRightIcon className="w-5 h-5" />
            ) : (
              <>
                <ChevronLeftIcon className="w-5 h-5" />
                <span className="text-xs uppercase tracking-wider">Collapse</span>
              </>
            )}
          </button>
        </div>
      </div>
    </aside>
  );
};

export default CollapsibleSidebar;
