import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { EmptyState } from '../components/ui/EmptyState';
import { GitMerge, ArrowRight, TrendingUp, TrendingDown, RefreshCw, CheckCircle2 } from 'lucide-react';
import { useToast } from '../context/ToastContext';
import { useNavigate } from 'react-router-dom';

export const DemandSyncPage: React.FC = () => {
  const [commodity, setCommodity] = useState('POTATO');
  const [district, setDistrict] = useState('Hooghly');
  const [gapData, setGapData] = useState<{
    commodity_code: string;
    district?: string;
    total_forecast_grams: number;
    total_required_grams: number;
    gap_grams: number;
    status: 'surplus' | 'deficit' | 'balanced';
  } | null>(null);

  const [isLoading, setIsLoading] = useState(false);
  const toast = useToast();
  const navigate = useNavigate();

  useEffect(() => {
    loadDemandGap();
  }, [commodity, district]);

  const loadDemandGap = async () => {
    try {
      setIsLoading(true);
      const res = await api.getDemandGap(commodity, district);
      setGapData(res);
    } catch (err) {
      toast.error('Failed to compute demand gap');
    } finally {
      setIsLoading(false);
    }
  };

  const forecastKg = gapData ? (gapData.total_forecast_grams / 1000).toFixed(0) : '0';
  const requiredKg = gapData ? (gapData.total_required_grams / 1000).toFixed(0) : '0';
  const gapKg = gapData ? (Math.abs(gapData.gap_grams) / 1000).toFixed(0) : '0';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">DemandSync: Supply-Demand Synchronization</h1>
          <p className="text-xs text-slate-500 mt-1">
            Reconciles forward harvest forecasts against wholesale buyer requirements across target districts.
          </p>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={loadDemandGap}
          isLoading={isLoading}
          leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
        >
          Recalculate Gap
        </Button>
      </div>

      {/* Filter Row */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200/80 flex flex-wrap items-center gap-4">
        <div className="flex items-center space-x-2">
          <span className="text-xs font-semibold text-slate-700">Filter Commodity:</span>
          <select
            value={commodity}
            onChange={(e) => setCommodity(e.target.value)}
            className="text-xs p-2 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500 font-medium"
          >
            <option value="POTATO">Potato (আলু)</option>
            <option value="TOMATO">Tomato (টমেটো)</option>
            <option value="PADDY">Paddy (ধান)</option>
            <option value="ONION">Onion (পেঁয়াজ)</option>
            <option value="JUTE">Jute (পাট)</option>
          </select>
        </div>

        <div className="flex items-center space-x-2">
          <span className="text-xs font-semibold text-slate-700">District:</span>
          <select
            value={district}
            onChange={(e) => setDistrict(e.target.value)}
            className="text-xs p-2 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500 font-medium"
          >
            <option value="Hooghly">Hooghly</option>
            <option value="Burdwan">Burdwan</option>
            <option value="Nadia">Nadia</option>
            <option value="Bankura">Bankura</option>
          </select>
        </div>
      </div>

      {/* Synchronization Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <Card title="Farmer Harvest Supply" subtitle="Forward yield forecasts">
          <div className="flex items-baseline justify-between mt-2">
            <span className="text-2xl font-bold text-slate-900">{forecastKg} kg</span>
            <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full">
              Supply
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-2">
            Aggregated harvest forecasts from verified smallholder farmers in {district}.
          </p>
        </Card>

        <Card title="Buyer Target Demand" subtitle="Institutional requirements">
          <div className="flex items-baseline justify-between mt-2">
            <span className="text-2xl font-bold text-slate-900">{requiredKg} kg</span>
            <span className="text-xs font-semibold text-blue-700 bg-blue-50 px-2 py-0.5 rounded-full">
              Demand
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-2">
            Procurement requirements committed by verified wholesalers and food processors.
          </p>
        </Card>

        <Card title="Net Balance / Gap" subtitle="Supply vs Demand posture">
          <div className="flex items-baseline justify-between mt-2">
            <span className="text-2xl font-bold text-slate-900">
              {gapData?.status === 'surplus' ? `+${gapKg}` : `-${gapKg}`} kg
            </span>
            <Badge
              variant={
                gapData?.status === 'surplus'
                  ? 'emerald'
                  : gapData?.status === 'deficit'
                  ? 'amber'
                  : 'slate'
              }
            >
              {gapData?.status.toUpperCase() || 'BALANCED'}
            </Badge>
          </div>
          <p className="text-xs text-slate-500 mt-2">
            {gapData?.status === 'surplus'
              ? 'Surplus supply available. Pool shared transport or route to cold storage.'
              : gapData?.status === 'deficit'
              ? 'Demand deficit. Procure from neighboring FPO clusters.'
              : 'Supply and demand are currently in equilibrium.'}
          </p>
        </Card>
      </div>

      {/* Action Recommendation */}
      <Card
        title="Recommended Supply Chain Actions"
        subtitle="Automated actions based on current district balance"
      >
        <div className="space-y-3">
          <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200/80 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 rounded-lg bg-emerald-100 text-emerald-800 flex items-center justify-center font-bold text-xs">
                1
              </div>
              <div>
                <h5 className="text-xs font-semibold text-slate-900">Dispatch Shared Transportation</h5>
                <p className="text-[11px] text-slate-500">
                  Pool smallholder lots into high-capacity vehicles for {district} aggregation.
                </p>
              </div>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={() => navigate('/logistics')}
              rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
            >
              Pool Vehicles
            </Button>
          </div>

          <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200/80 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-800 flex items-center justify-center font-bold text-xs">
                2
              </div>
              <div>
                <h5 className="text-xs font-semibold text-slate-900">Direct Buyer Commitment Matching</h5>
                <p className="text-[11px] text-slate-500">
                  Lock purchase contracts with buyers before crop harvest arrives.
                </p>
              </div>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={() => navigate('/procurement')}
              rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
            >
              Review Offers
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
};
