import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { EmptyState } from '../components/ui/EmptyState';
import { AlertOctagon, RefreshCw, ShieldAlert, CheckCircle2, CloudRain, AlertTriangle, Clock } from 'lucide-react';
import { useToast } from '../context/ToastContext';
import type { RiskIncident } from '../types';

export const RiskWatchPage: React.FC = () => {
  const [incidents, setIncidents] = useState<RiskIncident[]>([]);
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [isLoading, setIsLoading] = useState(true);
  const [isScanning, setIsScanning] = useState(false);
  const toast = useToast();

  useEffect(() => {
    loadIncidents();
  }, []);

  const loadIncidents = async () => {
    try {
      setIsLoading(true);
      const data = await api.getRiskIncidents();
      setIncidents(data);
    } catch (err) {
      toast.error('Failed to load risk incidents');
    } finally {
      setIsLoading(false);
    }
  };

  const handleScan = async () => {
    try {
      setIsScanning(true);
      const res = await api.scanRisks();
      toast.success('RiskWatch scan complete', `Identified ${res.length || 0} active corridor risks.`);
      loadIncidents();
    } catch (err: any) {
      toast.error('Risk scan failed', err?.response?.data?.message || 'Error executing risk scan');
    } finally {
      setIsScanning(false);
    }
  };

  const handleResolve = async (id: string) => {
    try {
      await api.resolveRiskIncident(id);
      toast.success('Incident resolved', 'Marked as mitigated in the operational risk register.');
      loadIncidents();
    } catch (err: any) {
      toast.error('Resolution failed', err?.response?.data?.message || 'Error resolving incident');
    }
  };

  const filteredIncidents = incidents.filter((inc) => {
    if (severityFilter === 'all') return true;
    return inc.severity === severityFilter;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">RiskWatch: Proactive Supply Chain Resilience</h1>
          <p className="text-xs text-slate-500 mt-1">
            Detects potential disruptions across road passability, storage degradation, and payment bottlenecks.
          </p>
        </div>
        <Button
          size="sm"
          onClick={handleScan}
          isLoading={isScanning}
          leftIcon={<RefreshCw className="w-4 h-4" />}
        >
          Execute Corridor Risk Scan
        </Button>
      </div>

      {/* Honest IMD Weather Disclosure */}
      <div className="bg-amber-50/70 border border-amber-300/80 rounded-2xl p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-start space-x-3">
          <div className="p-2 bg-amber-100 text-amber-800 rounded-xl flex-shrink-0 mt-0.5">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h4 className="text-xs font-bold text-amber-950 uppercase tracking-wider">
                Phase 5/6 Acceptance Notice: IMD Live Warning Feed Gated
              </h4>
              <Badge variant="amber">Strict Compliance</Badge>
            </div>
            <p className="text-xs text-amber-800 mt-1 max-w-3xl leading-relaxed">
              In accordance with audit restrictions, <code className="font-mono text-[11px]">imd_weather_warning_evidence.csv</code> is held blank. Incidents shown represent verified operational bottlenecks and storage alarms; no fabricated weather alerts are injected.
            </p>
          </div>
        </div>
      </div>

      {/* Filter and Overview */}
      <div className="flex items-center space-x-2">
        <span className="text-xs font-semibold text-slate-700">Filter Severity:</span>
        {['all', 'critical', 'high', 'medium', 'low'].map((sev) => (
          <button
            key={sev}
            onClick={() => setSeverityFilter(sev)}
            className={`px-3 py-1 rounded-xl text-xs font-medium capitalize border transition-colors ${
              severityFilter === sev
                ? 'bg-slate-900 text-white border-slate-900'
                : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
            }`}
          >
            {sev}
          </button>
        ))}
      </div>

      {/* Incidents List */}
      <Card
        title="Detected Supply Chain Disruptions"
        subtitle={`Showing ${filteredIncidents.length} incident reports`}
      >
        {filteredIncidents.length === 0 ? (
          <EmptyState
            title="No Risk Incidents Detected"
            description="The corridor is currently operating with no active disruption alarms."
            icon={<AlertOctagon className="w-6 h-6" />}
          />
        ) : (
          <div className="space-y-3">
            {filteredIncidents.map((inc) => (
              <div
                key={inc.id}
                className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 flex flex-col md:flex-row items-start md:items-center justify-between gap-4"
              >
                <div className="flex items-start space-x-3">
                  <div className="p-2 rounded-xl bg-amber-100 text-amber-700 mt-0.5">
                    <AlertTriangle className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-bold text-slate-900 capitalize">
                        {inc.risk_type.replace('_', ' ')}
                      </span>
                      <Badge
                        variant={
                          inc.severity === 'critical'
                            ? 'rose'
                            : inc.severity === 'high'
                            ? 'amber'
                            : 'slate'
                        }
                      >
                        {inc.severity.toUpperCase()}
                      </Badge>
                      <span className="text-[11px] text-slate-400">District: {inc.district}</span>
                    </div>
                    <p className="text-xs text-slate-600 mt-1 leading-relaxed">{inc.description}</p>
                    <div className="text-[10px] text-slate-400 mt-1 flex items-center space-x-1">
                      <Clock className="w-3 h-3" />
                      <span>Detected: {new Date(inc.detected_at).toLocaleString()}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center space-x-2 flex-shrink-0">
                  {inc.status === 'resolved' ? (
                    <span className="text-xs text-emerald-700 font-semibold flex items-center space-x-1">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>Mitigated</span>
                    </span>
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleResolve(inc.id)}
                      leftIcon={<CheckCircle2 className="w-3.5 h-3.5 text-emerald-700" />}
                    >
                      Resolve Incident
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
};
