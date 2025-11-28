import React from 'react';
import {
  BellIcon,
  MagnifyingGlassIcon,
  UserCircleIcon,
} from '@heroicons/react/24/outline';
import { Badge } from '@/components/ui/badge';

const CompactHeader: React.FC = () => {
  return (
    <header className="sticky top-0 z-30 h-14 glass-strong border-b border-white/10 backdrop-blur-xl">
      <div className="h-full flex items-center justify-between px-6">
        {/* Search */}
        <div className="flex-1 max-w-md">
          <div className="flex items-center gap-2 glass px-3 py-1.5 rounded-lg border border-white/10 hover:border-white/20 transition-all duration-200">
            <MagnifyingGlassIcon className="w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search tests..."
              className="bg-transparent border-none outline-none text-sm text-foreground placeholder:text-muted-foreground flex-1"
            />
            <kbd className="px-1.5 py-0.5 text-[10px] bg-white/5 rounded border border-white/10 text-muted-foreground">
              ⌘K
            </kbd>
          </div>
        </div>

        {/* Right Actions */}
        <div className="flex items-center gap-2">
          {/* Notifications */}
          <button className="relative w-9 h-9 flex items-center justify-center glass rounded-lg border border-white/10 hover:border-white/20 transition-all duration-200">
            <BellIcon className="w-5 h-5 text-muted-foreground hover:text-white transition-colors" />
            <span className="absolute -top-1 -right-1 w-4 h-4 bg-gradient-to-br from-red-500 to-pink-500 rounded-full text-[9px] text-white flex items-center justify-center font-bold">
              3
            </span>
          </button>

          {/* User Profile */}
          <button className="flex items-center gap-2 glass px-2 py-1.5 rounded-lg border border-white/10 hover:border-white/20 transition-all duration-200">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
              <UserCircleIcon className="w-4 h-4 text-white" />
            </div>
            <div className="hidden lg:block text-left">
              <div className="text-xs font-medium text-white">Admin</div>
            </div>
          </button>
        </div>
      </div>
    </header>
  );
};

export default CompactHeader;
