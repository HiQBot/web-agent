import React from 'react';
import {
  HomeIcon,
  DocumentTextIcon,
  PlayIcon,
  Cog6ToothIcon,
  BellIcon,
  MagnifyingGlassIcon,
  UserCircleIcon,
  Squares2X2Icon
} from '@heroicons/react/24/outline';
import { Badge } from '@/components/ui/badge';

interface ModernNavbarProps {
  currentPage: string;
  onPageChange: (page: string) => void;
}

const ModernNavbar: React.FC<ModernNavbarProps> = ({ currentPage, onPageChange }) => {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: HomeIcon },
    { id: 'test-plans', label: 'Test Plans', icon: DocumentTextIcon },
    { id: 'test-execution', label: 'Execution', icon: PlayIcon },
    { id: 'settings', label: 'Settings', icon: Cog6ToothIcon },
  ];

  return (
    <nav className="sticky top-0 z-50 glass-strong border-b border-white/10 backdrop-blur-xl">
      <div className="max-w-[1920px] mx-auto px-6">
        <div className="flex items-center justify-between h-16">
          {/* Left: Logo + Nav Links */}
          <div className="flex items-center gap-8">
            {/* Logo */}
            <div className="flex items-center gap-3 group cursor-pointer">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 via-purple-500 to-cyan-500 flex items-center justify-center shadow-lg glow-blue transition-all duration-300 group-hover:scale-110">
                <Squares2X2Icon className="w-6 h-6 text-white" />
              </div>
              <div className="flex flex-col">
                <span className="text-lg font-bold bg-gradient-to-r from-blue-400 via-purple-400 to-cyan-400 bg-clip-text text-transparent">
                  HiQBot
                </span>
                <span className="text-[10px] text-muted-foreground -mt-1">Web Agent</span>
              </div>
            </div>

            {/* Nav Items */}
            <div className="hidden md:flex items-center gap-2">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = currentPage === item.id;

                return (
                  <button
                    key={item.id}
                    onClick={() => onPageChange(item.id)}
                    className={`
                      relative flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium
                      transition-all duration-300 group
                      ${isActive
                        ? 'glass-strong text-white shadow-lg'
                        : 'text-muted-foreground hover:text-white hover:glass'
                      }
                    `}
                  >
                    <Icon className={`w-5 h-5 transition-all duration-300 ${isActive ? 'text-blue-400' : 'group-hover:text-blue-400'}`} />
                    <span>{item.label}</span>
                    {isActive && (
                      <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-1/2 h-0.5 bg-gradient-to-r from-blue-500 via-purple-500 to-cyan-500 rounded-full"></div>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Right: Search + Actions */}
          <div className="flex items-center gap-3">
            {/* Search Bar */}
            <div className="hidden lg:flex items-center gap-2 glass px-4 py-2 rounded-lg border border-white/10 hover:border-white/20 transition-all duration-300 min-w-[280px]">
              <MagnifyingGlassIcon className="w-5 h-5 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search tests..."
                className="bg-transparent border-none outline-none text-sm text-foreground placeholder:text-muted-foreground flex-1"
              />
              <kbd className="px-2 py-0.5 text-xs bg-white/5 rounded border border-white/10 text-muted-foreground">
                ⌘K
              </kbd>
            </div>

            {/* Notifications */}
            <button className="relative w-10 h-10 flex items-center justify-center glass rounded-lg border border-white/10 hover:border-white/20 transition-all duration-300 hover:scale-105">
              <BellIcon className="w-5 h-5 text-muted-foreground hover:text-white transition-colors" />
              <span className="absolute -top-1 -right-1 w-4 h-4 bg-gradient-to-br from-red-500 to-pink-500 rounded-full text-[10px] text-white flex items-center justify-center font-bold">
                3
              </span>
            </button>

            {/* User Profile */}
            <button className="flex items-center gap-3 glass px-3 py-2 rounded-lg border border-white/10 hover:border-white/20 transition-all duration-300 hover:scale-105">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                <UserCircleIcon className="w-5 h-5 text-white" />
              </div>
              <div className="hidden xl:block text-left">
                <div className="text-sm font-medium text-white">Admin User</div>
                <div className="text-xs text-muted-foreground">admin@hiqbot.com</div>
              </div>
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
};

export default ModernNavbar;
