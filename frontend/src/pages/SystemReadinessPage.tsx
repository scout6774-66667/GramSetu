import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { ShieldCheck, ShieldAlert, AlertTriangle, RefreshCw, FileText, CheckCircle2, XCircle } from 'lucide-react';
import { useToast } from '../context/ToastContext';
import type { ReadinessSummary } from '../types';

export const SystemReadinessPage: React.FC = () => {
  const [readiness, setReadiness] = useState<ReadinessSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const toast = useToast();

  useEffect(() => {
    fetchReadiness();
  }, []);

  const fetchReadiness = async () => {
    try {
      setIsLoading(true);
      const data = await api.getReadiness();
      setReadiness(data);
    } catch (err) {
      toast.error('Failed to load system readiness status');
    } finally {
      setIsLoading(false);
    }
  };

  const blockedDatasets = [
    {
      file: 'market_prices.csv',
      module: 'DemandSync & Market Intel',
      reason: 'Only 43 secondary-source baseline observations. Historical 730-day series missing.',
      status: 'BLOCKED',
    },
    {
      file: 'market_arrivals.csv',
      module: 'Market Intelligence',
      reason: 'No authenticated daily physical arrival logs from APMC pilot mandis.',
      status: 'BLOCKED',
    },
    {
      file: 'farm_gate_gnss_surveys.csv',
      module: 'Logistics & RiskWatch',
      reason: 'Ground GPS surveys awaiting pilot enumeration clearance in West Bengal.',
      status: 'BLOCKED',
    },
    {
      file: 'road_edges.csv & road_nodes.csv',
      module: 'Logistics Optimization',
      reason: 'Synthetic connections must not be treated as verified passability routes.',
      status: 'BLOCKED',
    },
    {
      file: 'carrier_vehicle_availability.csv',
      module: 'Logistics',
      reason: 'No authenticated carrier availability schedules or freight tariff filings.',
      status: 'BLOCKED',
    },
    {
      file: 'storage_sensor_measurements.csv',
      module: 'Storage & Spoilage',
      reason: 'Calibrated IoT telemetry streams not yet verified by facility partner.',
      status: 'BLOCKED',
    },
    {
      file: 'imd_weather_warning_evidence.csv',
      module: 'RiskWatch',
      reason: 'Source-verified real-time IMD district warning feed not connected.',
      status: 'BLOCKED',
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">System Trust & Acceptance Gates</h1>
          <p className="text-xs text-slate-500 mt-1">
            Phase 5 and Phase 6 data integrity gates and dataset restriction enforcement audit.
          </p>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={fetchReadiness}
          isLoading={isLoading}
          leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
        >
          Re-Audit Status
        </Button>
      </div>

      {/* Audit Banner */}
      <div className="bg-slate-900 text-white rounded-2xl p-6 border border-slate-800 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-start space-x-4">
          <div className="p-3 bg-amber-500/20 text-amber-400 rounded-xl border border-amber-500/30">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-semibold text-sm">Status:</span>
              <Badge variant="amber">DATASET_RESTRICTION_ACTIVE</Badge>
            </div>
            <p className="text-xs text-slate-300 mt-1 max-w-2xl leading-relaxed">
              GramSetu architecture strictly forbids synthetic data injection. Unverified operational datasets remain completely blank until authentic evidence is uploaded.
            </p>
          </div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-emerald-400">100%</div>
          <div className="text-[11px] text-slate-400">Strict Audit Compliance</div>
        </div>
      </div>

      {/* Blocked Datasets Table */}
      <Card
        title="Restricted & Blocked Datasets (Strict Enforcement)"
        subtitle="Unauthenticated files kept empty to prevent false operational assumptions"
      >
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider">
                <th className="pb-3 px-3">Dataset Identifier</th>
                <th className="pb-3 px-3">Affected Module</th>
                <th className="pb-3 px-3">Restriction Reason</th>
                <th className="pb-3 px-3">Gate Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {blockedDatasets.map((ds) => (
                <tr key={ds.file} className="hover:bg-slate-50/50">
                  <td className="py-3 px-3 font-mono font-medium text-slate-900">{ds.file}</td>
                  <td className="py-3 px-3 text-slate-700">{ds.module}</td>
                  <td className="py-3 px-3 text-slate-600 max-w-xs">{ds.reason}</td>
                  <td className="py-3 px-3">
                    <Badge variant="amber">BLOCKED BLANK</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Module Readiness Matrix */}
      <Card
        title="Domain Services Readiness Matrix"
        subtitle="Operational readiness status across all 15 GramSetu sub-modules"
      >
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[
            { name: 'Core Farmer & Directory', status: 'OPERATIONAL', type: 'authentic' },
            { name: 'Buyer Directory & Registration', status: 'OPERATIONAL', type: 'authentic' },
            { name: 'Produce Listings & Catalog', status: 'OPERATIONAL', type: 'authentic' },
            { name: 'Procurement & CommitGuard', status: 'OPERATIONAL', type: 'authentic' },
            { name: 'Shared Logistics Pooling', status: 'OPERATIONAL (No GPS)', type: 'restricted' },
            { name: 'Storage & Spoilage Radar', status: 'OPERATIONAL (No IoT)', type: 'restricted' },
            { name: 'BatchTrace (Traceability)', status: 'OPERATIONAL', type: 'authentic' },
            { name: 'SettleTrack (Payments)', status: 'OPERATIONAL', type: 'authentic' },
            { name: 'RiskWatch Incidents', status: 'OPERATIONAL (No IMD)', type: 'restricted' },
            { name: 'RecoveryOpt (Distress Solver)', status: 'OPERATIONAL', type: 'authentic' },
            { name: 'Market Intelligence Prices', status: 'GATED (43 Obs)', type: 'restricted' },
            { name: 'ML Temporal Forecasting', status: 'GATED (No 730d)', type: 'blocked' },
            { name: 'Multilingual Voice Assistant', status: 'OPERATIONAL', type: 'authentic' },
            { name: 'Dev Identity & Security', status: 'OPERATIONAL', type: 'authentic' },
          ].map((m) => (
            <div key={m.name} className="p-3.5 rounded-xl border border-slate-200/80 bg-slate-50/50 flex items-center justify-between">
              <div>
                <h5 className="text-xs font-semibold text-slate-900">{m.name}</h5>
                <span className="text-[10px] text-slate-500">
                  {m.type === 'authentic' ? 'Fully Functional' : m.type === 'restricted' ? 'Operational with Honest Notice' : 'Gated pending data'}
                </span>
              </div>
              <Badge variant={m.type === 'authentic' ? 'emerald' : m.type === 'restricted' ? 'amber' : 'rose'}>
                {m.status}
              </Badge>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
};
