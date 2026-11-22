import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { StatCard } from '../components/ui/StatCard';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import {
  Users,
  ShoppingBag,
  Package,
  Warehouse,
  AlertTriangle,
  ArrowUpRight,
  TrendingUp,
  ShieldCheck,
  Truck,
  Sparkles,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import type { ReadinessSummary } from '../types';

export const DashboardPage: React.FC = () => {
  const [readiness, setReadiness] = useState<ReadinessSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      setIsLoading(true);
      const data = await api.getReadiness();
      setReadiness(data);
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const stats = readiness?.stats || {
    total_farmers: 0,
    total_buyers: 0,
    total_listings: 0,
    total_facilities: 0,
    active_incidents: 0,
  };

  return (
    <div className="space-y-6">
      {/* Top Banner: Pilot & Acceptance Gate Status */}
      <div className="bg-gradient-to-r from-emerald-900 to-emerald-800 rounded-3xl p-6 text-white shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-700/80 text-emerald-100 border border-emerald-600">
              Pilot: West Bengal Rural Agri-Corridor
            </span>
            <Badge variant="amber">Audit Gate: Strict Compliance</Badge>
          </div>
          <h1 className="text-2xl font-bold mt-2">GramSetu Supply Chain Command Center</h1>
          <p className="text-emerald-200/90 text-xs mt-1 max-w-2xl leading-relaxed">
            AI-powered rural food supply chain coordination connecting smallholders, FPOs, wholesale buyers, and shared logistics. Blocked datasets remain blank in accordance with Phase 5/6 acceptance criteria.
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => navigate('/voice')}
            leftIcon={<Sparkles className="w-3.5 h-3.5 text-emerald-700" />}
          >
            Voice AI Assistant
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate('/readiness')}
            className="text-slate-900"
            rightIcon={<ArrowUpRight className="w-3.5 h-3.5" />}
          >
            Audit Gates
          </Button>
        </div>
      </div>

      {/* KPI Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard
          title="Registered Farmers"
          value={stats.total_farmers}
          icon={<Users className="w-5 h-5 text-emerald-700" />}
          description="Verified smallholder producers"
        />
        <StatCard
          title="Procurement Buyers"
          value={stats.total_buyers}
          icon={<ShoppingBag className="w-5 h-5 text-emerald-700" />}
          description="Wholesalers & institutions"
        />
        <StatCard
          title="Active Crop Lots"
          value={stats.total_listings}
          icon={<Package className="w-5 h-5 text-emerald-700" />}
          description="Ready for procurement"
        />
        <StatCard
          title="Storage Facilities"
          value={stats.total_facilities}
          icon={<Warehouse className="w-5 h-5 text-emerald-700" />}
          description="Cold & dry warehousing"
        />
        <StatCard
          title="Risk Alerts"
          value={stats.active_incidents}
          isPositive={stats.active_incidents === 0}
          icon={<AlertTriangle className="w-5 h-5 text-amber-600" />}
          description="Active incidents"
        />
      </div>

      {/* Core Workflow Pillars */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Marketplace & CommitGuard */}
        <Card
          title="Marketplace & CommitGuard"
          subtitle="Fair pricing and verified contracts"
          headerAction={
            <Button size="sm" variant="ghost" onClick={() => navigate('/listings')}>
              Explore Lots &rarr;
            </Button>
          }
        >
          <div className="space-y-4">
            <div className="p-3 bg-emerald-50/60 rounded-xl border border-emerald-100 flex items-start space-x-3">
              <ShieldCheck className="w-5 h-5 text-emerald-700 flex-shrink-0 mt-0.5" />
              <div>
                <h4 className="text-xs font-semibold text-emerald-900">Direct Farmer Procurement</h4>
                <p className="text-[11px] text-emerald-800 mt-0.5">
                  Eliminates exploitative intermediaries with transparent pricing in ₹/kg (paise/gram accuracy).
                </p>
              </div>
            </div>

            <div className="flex items-center justify-between text-xs py-2 border-b border-slate-100">
              <span className="text-slate-500">Live Crop Listings:</span>
              <span className="font-semibold text-slate-800">{stats.total_listings} lots</span>
            </div>
            <div className="flex items-center justify-between text-xs py-2 border-b border-slate-100">
              <span className="text-slate-500">Verified Buyer Network:</span>
              <span className="font-semibold text-slate-800">{stats.total_buyers} accounts</span>
            </div>

            <Button
              variant="outline"
              size="sm"
              className="w-full justify-center"
              onClick={() => navigate('/procurement')}
            >
              Review Procurement Offers
            </Button>
          </div>
        </Card>

        {/* Shared Logistics & Route Optimization */}
        <Card
          title="Shared Transportation"
          subtitle="Rural vehicle pooling & route safety"
          headerAction={
            <Button size="sm" variant="ghost" onClick={() => navigate('/logistics')}>
              Logistics &rarr;
            </Button>
          }
        >
          <div className="space-y-4">
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80 flex items-start space-x-3">
              <Truck className="w-5 h-5 text-emerald-700 flex-shrink-0 mt-0.5" />
              <div>
                <h4 className="text-xs font-semibold text-slate-900">Multi-Farmer Cargo Pooling</h4>
                <p className="text-[11px] text-slate-600 mt-0.5">
                  Greedy pooling algorithm aggregates harvest quantities within truck capacity limits.
                </p>
              </div>
            </div>

            <div className="p-3 bg-amber-50/70 border border-amber-200 rounded-xl text-[11px] text-amber-900">
              <span className="font-semibold block">Routing Notice:</span>
              GNSS surveys & road passability datasets are held blank pending ground survey validation.
            </div>

            <Button
              variant="outline"
              size="sm"
              className="w-full justify-center"
              onClick={() => navigate('/logistics')}
            >
              Run Shared Pooling Solver
            </Button>
          </div>
        </Card>

        {/* Storage, Spoilage & Recovery */}
        <Card
          title="Post-Harvest Spoilage Risk"
          subtitle="Agronomic decay curves & recovery"
          headerAction={
            <Button size="sm" variant="ghost" onClick={() => navigate('/storage')}>
              Storage &rarr;
            </Button>
          }
        >
          <div className="space-y-4">
            <div className="p-3 bg-emerald-50/60 rounded-xl border border-emerald-100 flex items-start space-x-3">
              <Warehouse className="w-5 h-5 text-emerald-700 flex-shrink-0 mt-0.5" />
              <div>
                <h4 className="text-xs font-semibold text-emerald-900">Storage Optimization</h4>
                <p className="text-[11px] text-emerald-800 mt-0.5">
                  Monitors perishable crops (potatoes, tomatoes, onions) to prevent post-harvest loss.
                </p>
              </div>
            </div>

            <div className="flex items-center justify-between text-xs py-2 border-b border-slate-100">
              <span className="text-slate-500">Connected Facilities:</span>
              <span className="font-semibold text-slate-800">{stats.total_facilities} facilities</span>
            </div>
            <div className="flex items-center justify-between text-xs py-2 border-b border-slate-100">
              <span className="text-slate-500">Distressed Lot Recovery:</span>
              <span className="font-semibold text-emerald-700">RecoveryOpt Ready</span>
            </div>

            <Button
              variant="outline"
              size="sm"
              className="w-full justify-center"
              onClick={() => navigate('/recovery')}
            >
              Salvage Distressed Produce
            </Button>
          </div>
        </Card>
      </div>

      {/* Dataset Restrictions Banner */}
      <div className="bg-amber-50/80 border border-amber-300/80 rounded-2xl p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-start space-x-3">
          <div className="p-2 bg-amber-100 text-amber-800 rounded-xl flex-shrink-0 mt-0.5">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div>
            <h4 className="text-xs font-bold text-amber-950 uppercase tracking-wider">
              Dataset Restrictions Strictly Enforced
            </h4>
            <p className="text-xs text-amber-800 mt-1 max-w-3xl leading-relaxed">
              Unverified datasets (historical market panels, farm gate GPS, carrier freight quotes, IoT calibrated sensor streams, and IMD weather warnings) are held completely blank. No synthetic or mock data is injected.
            </p>
          </div>
        </div>
        <Button
          size="sm"
          variant="outline"
          className="border-amber-300 text-amber-900 bg-white hover:bg-amber-100"
          onClick={() => navigate('/readiness')}
        >
          View Acceptance Gates
        </Button>
      </div>
    </div>
  );
};
