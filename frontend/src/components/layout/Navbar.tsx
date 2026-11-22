import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { Sprout, Globe, ShieldCheck, UserCircle2, Mic, LogOut, LogIn } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import type { UserRole } from '../../types';

export const Navbar: React.FC = () => {
  const {
    activeActor,
    setActiveActor,
    language,
    setLanguage,
    devMode,
    setDevMode,
    isAuthenticated,
    currentUser,
    logout,
  } = useAuth();
  const navigate = useNavigate();

  const handleSignOut = () => {
    logout();
    navigate('/login');
  };

  return (
    <header className="h-16 bg-white border-b border-slate-200/80 px-6 flex items-center justify-between sticky top-0 z-30 shadow-2xs">
      <div className="flex items-center space-x-3 cursor-pointer" onClick={() => navigate('/')}>
        <div className="w-9 h-9 rounded-xl bg-emerald-700 text-white flex items-center justify-center shadow-xs">
          <Sprout className="w-5 h-5 text-emerald-100" />
        </div>
        <div>
          <span className="font-bold text-slate-900 text-lg tracking-tight">GramSetu</span>
          <span className="ml-2 text-[10px] font-semibold uppercase px-2 py-0.5 rounded-md bg-emerald-100 text-emerald-800">
            Smart Rural Supply Chain
          </span>
        </div>
      </div>

      <div className="flex items-center space-x-3 sm:space-x-4">
        {/* Quick Voice Assistant shortcut */}
        <button
          onClick={() => navigate('/voice')}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-emerald-50 text-emerald-800 text-xs font-medium border border-emerald-200/80 hover:bg-emerald-100 transition-colors"
          title="Open AI Multilingual Voice Assistant"
        >
          <Mic className="w-3.5 h-3.5 text-emerald-600" />
          <span className="hidden sm:inline">Voice AI</span>
        </button>

        {/* Language Selector */}
        <div className="flex items-center space-x-1 bg-slate-50 border border-slate-200/80 rounded-xl px-2.5 py-1">
          <Globe className="w-3.5 h-3.5 text-slate-400 mr-1" />
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value as any)}
            className="bg-transparent text-xs font-medium text-slate-700 focus:outline-none cursor-pointer"
          >
            <option value="en-IN">English</option>
            <option value="bn-IN">বাংলা (Bengali)</option>
            <option value="hi-IN">हिन्दी (Hindi)</option>
          </select>
        </div>

        {/* Active Role Switcher */}
        <div className="flex items-center space-x-2 bg-slate-50 border border-slate-200/80 rounded-xl px-3 py-1">
          <UserCircle2 className="w-4 h-4 text-emerald-700" />
          <div className="flex flex-col text-left">
            <span className="text-[10px] text-slate-400 uppercase font-semibold leading-none">Role Context</span>
            <select
              value={activeActor}
              onChange={(e) => setActiveActor(e.target.value as UserRole)}
              className="bg-transparent text-xs font-semibold text-slate-800 focus:outline-none cursor-pointer pt-0.5"
            >
              <option value="fpo_admin">FPO Executive</option>
              <option value="farmer">Farmer</option>
              <option value="buyer">Buyer</option>
              <option value="transporter">Transporter</option>
              <option value="storage_operator">Storage Operator</option>
              <option value="system_auditor">System Auditor</option>
            </select>
          </div>
        </div>

        {/* Dev Mode Badge */}
        <button
          onClick={() => setDevMode(!devMode)}
          className={`hidden md:flex items-center space-x-1 px-2.5 py-1 rounded-xl text-xs font-medium border transition-colors ${devMode
              ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
              : 'bg-slate-100 text-slate-600 border-slate-200'
            }`}
          title="Toggle dev authorization bypass header"
        >
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
          <span>{devMode ? 'Dev Auth' : 'Prod Mode'}</span>
        </button>

        {/* Auth / Logout Button */}
        {isAuthenticated ? (
          <div className="flex items-center space-x-2 pl-2 border-l border-slate-200">
            {currentUser && (
              <span className="hidden xl:inline text-xs font-medium text-slate-700">
                {currentUser.name}
              </span>
            )}
            <button
              onClick={handleSignOut}
              className="flex items-center space-x-1 px-2.5 py-1.5 rounded-xl bg-slate-100 hover:bg-rose-50 text-slate-600 hover:text-rose-700 text-xs font-medium border border-slate-200 hover:border-rose-200 transition-colors"
              title="Sign Out"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Sign Out</span>
            </button>
          </div>
        ) : (
          <button
            onClick={() => navigate('/login')}
            className="flex items-center space-x-1 px-3 py-1.5 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-medium transition-colors shadow-xs"
          >
            <LogIn className="w-3.5 h-3.5" />
            <span>Sign In</span>
          </button>
        )}
      </div>
    </header>
  );
};
