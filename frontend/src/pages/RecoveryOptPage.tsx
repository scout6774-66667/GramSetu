import React, { useState } from 'react';
import { api } from '../api/client';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';
import { EmptyState } from '../components/ui/EmptyState';
import { RefreshCw, ShieldCheck, CheckCircle2, Factory, Truck, Sparkles, AlertTriangle } from 'lucide-react';
import { useToast } from '../context/ToastContext';
import type { RecoveryPlan } from '../types';

export const RecoveryOptPage: React.FC = () => {
  const [lotId, setLotId] = useState('LOT-POTATO-2026-001');
  const [commodity, setCommodity] = useState('POTATO');
  const [spoilagePct, setSpoilagePct] = useState(70);
  const [plan, setPlan] = useState<RecoveryPlan | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const toast = useToast();

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setIsGenerating(true);
      const res = await api.generateRecoveryPlan({
        lot_id: lotId,
        commodity_code: commodity,
        spoilage_risk_pct: Number(spoilagePct),
      });
      setPlan(res);
      toast.success('Salvage options ranked', 'Multi-tier buyer recovery plan generated.');
    } catch (err: any) {
      toast.error('Generation failed', err?.response?.data?.message || 'Error generating recovery plan');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleApprove = async () => {
    if (!plan) return;
    try {
      setIsApproving(true);
      const updated = await api.approveRecoveryPlan(plan.id);
      setPlan(updated);
      toast.success('Recovery plan approved', 'Dispatched urgent salvage order to processing partner.');
    } catch (err: any) {
      toast.error('Approval failed', err?.response?.data?.message || 'Error approving recovery plan');
    } finally {
      setIsApproving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">RecoveryOpt: Distressed Lot Salvage Optimization</h1>
          <p className="text-xs text-slate-500 mt-1">
            Dynamic secondary market matching to recover economic value from lots nearing critical spoilage thresholds.
          </p>
        </div>
      </div>

      {/* Generator Card */}
      <Card
        title="Distressed Lot Recovery Solver"
        subtitle="Rank alternative buyers (food processors, bulk dehydrators, feed producers) to salvage up to 80% value"
      >
        <form onSubmit={handleGenerate} className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Distressed Lot ID</label>
            <input
              type="text"
              required
              value={lotId}
              onChange={(e) => setLotId(e.target.value)}
              className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500 font-mono"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Commodity</label>
            <select
              value={commodity}
              onChange={(e) => setCommodity(e.target.value)}
              className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500 font-medium"
            >
              <option value="POTATO">Potato (আলু)</option>
              <option value="TOMATO">Tomato (টমেটো)</option>
              <option value="ONION">Onion (পেঁয়াজ)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Estimated Spoilage Risk ({spoilagePct}%)
            </label>
            <input
              type="range"
              min="40"
              max="95"
              value={spoilagePct}
              onChange={(e) => setSpoilagePct(Number(e.target.value))}
              className="w-full accent-emerald-700 mt-2"
            />
          </div>

          <Button
            type="submit"
            size="md"
            isLoading={isGenerating}
            leftIcon={<RefreshCw className="w-4 h-4" />}
            className="w-full justify-center"
          >
            Solve Recovery Options
          </Button>
        </form>
      </Card>

      {/* Plan Results */}
      {plan ? (
        <div className="space-y-6">
          {/* Recovery Plan Header */}
          <div className="bg-slate-900 text-white rounded-2xl p-6 border border-slate-800 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-xs font-semibold text-slate-400">Plan Ref:</span>
                <span className="font-mono text-emerald-400 text-xs">{plan.id}</span>
                <Badge variant={plan.status === 'fpo_approved' ? 'emerald' : 'amber'}>
                  {plan.status.toUpperCase()}
                </Badge>
              </div>
              <h3 className="text-lg font-bold mt-1">
                Salvage Solution for {plan.commodity_code} ({plan.lot_id})
              </h3>
              <p className="text-xs text-slate-300 mt-0.5">
                Calculated at {plan.spoilage_risk_pct}% spoilage risk. Requires urgent dispatch within 24-36 hours.
              </p>
            </div>

            <div className="flex items-center space-x-3">
              {plan.status !== 'fpo_approved' ? (
                <Button
                  size="md"
                  onClick={handleApprove}
                  isLoading={isApproving}
                  leftIcon={<CheckCircle2 className="w-4 h-4 text-emerald-400" />}
                >
                  Approve Recovery Dispatch
                </Button>
              ) : (
                <div className="flex items-center space-x-1.5 text-xs text-emerald-400 font-semibold bg-emerald-950/60 px-3 py-1.5 rounded-xl border border-emerald-800">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Approved & Dispatched</span>
                </div>
              )}
            </div>
          </div>

          {/* Ranked Buyers Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {/* Candidate 1 (Top Recommended) */}
            <Card
              className="border-2 border-emerald-400 bg-emerald-50/20"
              title="Rank #1: Processing Partner (Recommended)"
              subtitle="Highest economic recovery"
            >
              <div className="space-y-3">
                <div className="flex items-center space-x-2">
                  <Factory className="w-5 h-5 text-emerald-700" />
                  <div>
                    <h4 className="font-bold text-slate-900 text-sm">Bengal Agro Food Processors</h4>
                    <span className="text-[10px] text-slate-500">Tomato Puree & Potato Flakes Unit</span>
                  </div>
                </div>

                <div className="pt-3 border-t border-emerald-200/80 grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-slate-500 block">Offered Price:</span>
                    <span className="font-bold text-emerald-800 text-sm">₹14.50 / kg</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Value Recovery:</span>
                    <span className="font-bold text-emerald-800 text-sm">76% of Baseline</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Facility Distance:</span>
                    <span className="font-medium text-slate-800">18 km</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Max Deadline:</span>
                    <span className="font-medium text-rose-600">36 hours</span>
                  </div>
                </div>
              </div>
            </Card>

            {/* Candidate 2 */}
            <Card title="Rank #2: Discount Wholesaler" subtitle="Quick liquidation">
              <div className="space-y-3">
                <div className="flex items-center space-x-2">
                  <Truck className="w-5 h-5 text-slate-600" />
                  <div>
                    <h4 className="font-bold text-slate-900 text-sm">Kolkata Sub-yard Wholesalers</h4>
                    <span className="text-[10px] text-slate-500">Bulk B2B Wholesale Clearance</span>
                  </div>
                </div>

                <div className="pt-3 border-t border-slate-100 grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-slate-500 block">Offered Price:</span>
                    <span className="font-bold text-slate-800 text-sm">₹11.00 / kg</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Value Recovery:</span>
                    <span className="font-bold text-slate-800 text-sm">58% of Baseline</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Facility Distance:</span>
                    <span className="font-medium text-slate-800">42 km</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Max Deadline:</span>
                    <span className="font-medium text-amber-600">24 hours</span>
                  </div>
                </div>
              </div>
            </Card>

            {/* Candidate 3 */}
            <Card title="Rank #3: Cattle Feed / Bio-Compost" subtitle="Floor recovery">
              <div className="space-y-3">
                <div className="flex items-center space-x-2">
                  <Sparkles className="w-5 h-5 text-slate-500" />
                  <div>
                    <h4 className="font-bold text-slate-900 text-sm">Burdwan Organic Bio-Feed</h4>
                    <span className="text-[10px] text-slate-500">Livestock Mash Production</span>
                  </div>
                </div>

                <div className="pt-3 border-t border-slate-100 grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-slate-500 block">Offered Price:</span>
                    <span className="font-bold text-slate-800 text-sm">₹5.50 / kg</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Value Recovery:</span>
                    <span className="font-bold text-slate-800 text-sm">29% of Baseline</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Facility Distance:</span>
                    <span className="font-medium text-slate-800">12 km</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Max Deadline:</span>
                    <span className="font-medium text-slate-600">48 hours</span>
                  </div>
                </div>
              </div>
            </Card>
          </div>
        </div>
      ) : (
        <EmptyState
          title="No Recovery Plan Generated"
          description="Click 'Solve Recovery Options' above to evaluate multi-tier salvage options for distressed produce."
          icon={<RefreshCw className="w-6 h-6" />}
        />
      )}
    </div>
  );
};
