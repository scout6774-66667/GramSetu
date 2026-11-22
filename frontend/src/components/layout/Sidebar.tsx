import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  ShieldAlert,
  Users,
  ShoppingBag,
  Package,
  FileCheck2,
  TrendingUp,
  GitMerge,
  Truck,
  Warehouse,
  QrCode,
  CreditCard,
  AlertOctagon,
  RefreshCw,
  Mic,
} from 'lucide-react';

interface NavItem {
  name: string;
  path: string;
  icon: React.ReactNode;
  badge?: string;
}

export const Sidebar: React.FC = () => {
  const sections: { title: string; items: NavItem[] }[] = [
    {
      title: 'OVERVIEW',
      items: [
        { name: 'Dashboard', path: '/', icon: <LayoutDashboard className="w-4 h-4" /> },
        { name: 'System Readiness', path: '/readiness', icon: <ShieldAlert className="w-4 h-4" /> },
      ],
    },
    {
      title: 'MARKETPLACE & TRADE',
      items: [
        { name: 'Farmers Directory', path: '/farmers', icon: <Users className="w-4 h-4" /> },
        { name: 'Buyer Network', path: '/buyers', icon: <ShoppingBag className="w-4 h-4" /> },
        { name: 'Produce Listings', path: '/listings', icon: <Package className="w-4 h-4" /> },
        { name: 'Procurement Offers', path: '/procurement', icon: <FileCheck2 className="w-4 h-4" /> },
        { name: 'Market Intelligence', path: '/market', icon: <TrendingUp className="w-4 h-4" /> },
        { name: 'DemandSync', path: '/demandsync', icon: <GitMerge className="w-4 h-4" /> },
      ],
    },
    {
      title: 'SUPPLY CHAIN OPERATIONS',
      items: [
        { name: 'Shared Logistics', path: '/logistics', icon: <Truck className="w-4 h-4" /> },
        { name: 'Storage & Spoilage', path: '/storage', icon: <Warehouse className="w-4 h-4" /> },
        { name: 'BatchTrace (Audit)', path: '/traceability', icon: <QrCode className="w-4 h-4" /> },
        { name: 'SettleTrack (Payments)', path: '/settlements', icon: <CreditCard className="w-4 h-4" /> },
      ],
    },
    {
      title: 'RISK & RECOVERY',
      items: [
        { name: 'RiskWatch Alerts', path: '/risks', icon: <AlertOctagon className="w-4 h-4" /> },
        { name: 'RecoveryOpt (Distress)', path: '/recovery', icon: <RefreshCw className="w-4 h-4" /> },
        { name: 'AI Voice Assistant', path: '/voice', icon: <Mic className="w-4 h-4" /> },
      ],
    },
  ];

  return (
    <aside className="w-64 bg-slate-900 text-slate-300 flex flex-col h-[calc(100vh-4rem)] sticky top-16 border-r border-slate-800 flex-shrink-0 select-none overflow-y-auto">
      <div className="p-4 space-y-6">
        {sections.map((section) => (
          <div key={section.title}>
            <div className="text-[10px] font-bold text-slate-400 tracking-wider uppercase px-3 mb-2">
              {section.title}
            </div>
            <nav className="space-y-1">
              {section.items.map((item) => (
                <NavLink
                  key={item.path}
                  to={item.path}
                  end={item.path === '/'}
                  className={({ isActive }) =>
                    `flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-colors ${
                      isActive
                        ? 'bg-emerald-700 text-white shadow-xs font-semibold'
                        : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                    }`
                  }
                >
                  <div className="flex items-center space-x-2.5">
                    <span className="text-emerald-400">{item.icon}</span>
                    <span>{item.name}</span>
                  </div>
                  {item.badge && (
                    <span className="px-1.5 py-0.5 text-[10px] rounded-md bg-emerald-900/60 text-emerald-300 border border-emerald-700/50">
                      {item.badge}
                    </span>
                  )}
                </NavLink>
              ))}
            </nav>
          </div>
        ))}
      </div>

      <div className="mt-auto p-4 border-t border-slate-800 bg-slate-950/40">
        <div className="flex items-center justify-between text-[11px] text-slate-300">
          <span>Target Pilot:</span>
          <span className="font-semibold text-emerald-400">WB Rural Pilot</span>
        </div>
        <div className="flex items-center justify-between text-[11px] text-slate-400 mt-1">
          <span>Data Compliance:</span>
          <span className="text-amber-400 font-mono text-[10px]">Gated Blank</span>
        </div>
      </div>
    </aside>
  );
};
