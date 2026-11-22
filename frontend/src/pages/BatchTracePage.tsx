import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { EmptyState } from '../components/ui/EmptyState';
import { QrCode, Search, CheckCircle2, AlertCircle, Clock, MapPin, UserCheck, ShieldCheck } from 'lucide-react';
import { useToast } from '../context/ToastContext';
import type { LotTraceability, ProduceListing } from '../types';

export const BatchTracePage: React.FC = () => {
  const [lotId, setLotId] = useState('');
  const [traceData, setTraceData] = useState<LotTraceability | null>(null);
  const [recentListings, setRecentListings] = useState<ProduceListing[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const toast = useToast();

  useEffect(() => {
    loadRecentLots();
  }, []);

  const loadRecentLots = async () => {
    try {
      const listings = await api.getListings();
      setRecentListings(listings);
      if (listings.length > 0) {
        handleLookup(listings[0].id);
      }
    } catch (err) {
      console.error('Failed to load listings for trace:', err);
    }
  };

  const handleLookup = async (idToSearch?: string) => {
    const id = idToSearch || lotId;
    if (!id) {
      toast.error('Please enter or select a Lot ID');
      return;
    }

    try {
      setIsLoading(true);
      const res = await api.getTraceability(id);
      setTraceData(res);
      setLotId(id);
      toast.success('BatchTrace loaded', `Retrieved custody timeline for lot ${id.slice(0, 8)}...`);
    } catch (err: any) {
      toast.error('Trace not found', err?.response?.data?.message || 'Could not find audit trace for this Lot ID');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">BatchTrace: Lot Custody & Integrity Audit</h1>
          <p className="text-xs text-slate-500 mt-1">
            End-to-end farm-to-fork chain of custody with verified audit badges (Authentic, Provisional, Unverified).
          </p>
        </div>
      </div>

      {/* Lot Search Row */}
      <Card>
        <div className="flex flex-col md:flex-row items-center gap-4">
          <div className="relative flex-1 w-full">
            <Search className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
            <input
              type="text"
              placeholder="Enter Lot UUID or select from quick picks below..."
              value={lotId}
              onChange={(e) => setLotId(e.target.value)}
              className="w-full text-xs pl-9 pr-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500 font-mono"
            />
          </div>
          <Button
            size="md"
            onClick={() => handleLookup()}
            isLoading={isLoading}
            leftIcon={<QrCode className="w-4 h-4" />}
          >
            Trace Lot Journey
          </Button>
        </div>

        {/* Quick Picks */}
        {recentListings.length > 0 && (
          <div className="mt-3 flex items-center space-x-2 text-xs text-slate-500 overflow-x-auto pb-1">
            <span className="font-semibold text-slate-700 flex-shrink-0">Quick Lot Picks:</span>
            {recentListings.slice(0, 4).map((l) => (
              <button
                key={l.id}
                onClick={() => handleLookup(l.id)}
                className={`font-mono text-[11px] px-2 py-0.5 rounded-lg border transition-colors flex-shrink-0 ${
                  lotId === l.id
                    ? 'bg-emerald-100 text-emerald-800 border-emerald-300'
                    : 'bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100'
                }`}
              >
                {l.commodity_code} ({l.id.slice(0, 8)}...)
              </button>
            ))}
          </div>
        )}
      </Card>

      {/* Trace Timeline Results */}
      {traceData ? (
        <div className="space-y-6">
          {/* Lot Overview Banner */}
          <div className="bg-slate-900 text-white rounded-2xl p-6 border border-slate-800 grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <span className="text-[10px] text-slate-400 uppercase font-semibold">Commodity</span>
              <div className="text-lg font-bold text-emerald-400">{traceData.commodity_code}</div>
            </div>
            <div>
              <span className="text-[10px] text-slate-400 uppercase font-semibold">Net Weight</span>
              <div className="text-lg font-bold text-white">{traceData.quantity_grams / 1000} kg</div>
            </div>
            <div>
              <span className="text-[10px] text-slate-400 uppercase font-semibold">Quality Grade</span>
              <div className="text-lg font-bold text-emerald-300">Grade {traceData.quality_grade}</div>
            </div>
            <div>
              <span className="text-[10px] text-slate-400 uppercase font-semibold">Trace Integrity</span>
              <div className="text-sm font-semibold text-emerald-400 flex items-center space-x-1 mt-0.5">
                <ShieldCheck className="w-4 h-4" />
                <span>Verified Trace</span>
              </div>
            </div>
          </div>

          {/* Interactive Milestone Timeline */}
          <Card
            title="Chain of Custody Milestones"
            subtitle="Chronological event logs with cryptographic verification integrity tags"
          >
            <div className="relative pl-6 space-y-8 before:absolute before:left-3 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
              {traceData.milestones.map((m, idx) => (
                <div key={idx} className="relative flex items-start space-x-4">
                  {/* Timeline Node Bullet */}
                  <div
                    className={`absolute -left-6 top-0 w-6 h-6 rounded-full flex items-center justify-center border-2 bg-white ${
                      m.verification_level === 'AUTHENTIC'
                        ? 'border-emerald-600 text-emerald-600'
                        : m.verification_level === 'PROVISIONAL'
                        ? 'border-amber-500 text-amber-500'
                        : 'border-slate-300 text-slate-400'
                    }`}
                  >
                    {m.verification_level === 'AUTHENTIC' ? (
                      <CheckCircle2 className="w-3.5 h-3.5 fill-emerald-100" />
                    ) : (
                      <Clock className="w-3.5 h-3.5" />
                    )}
                  </div>

                  {/* Milestone Card */}
                  <div className="flex-1 bg-slate-50/70 rounded-xl p-4 border border-slate-200/80">
                    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
                      <div>
                        <h4 className="font-bold text-slate-900 text-sm">{m.stage}</h4>
                        <div className="flex items-center space-x-3 text-xs text-slate-500 mt-1">
                          <span className="flex items-center space-x-1">
                            <Clock className="w-3 h-3 text-slate-400" />
                            <span>{new Date(m.timestamp).toLocaleString()}</span>
                          </span>
                          <span className="flex items-center space-x-1">
                            <MapPin className="w-3 h-3 text-slate-400" />
                            <span>{m.location}</span>
                          </span>
                        </div>
                      </div>
                      <Badge
                        variant={
                          m.verification_level === 'AUTHENTIC'
                            ? 'emerald'
                            : m.verification_level === 'PROVISIONAL'
                            ? 'amber'
                            : 'slate'
                        }
                      >
                        {m.verification_level}
                      </Badge>
                    </div>

                    <div className="mt-3 pt-2.5 border-t border-slate-200/60 flex items-center justify-between text-xs text-slate-600">
                      <div className="flex items-center space-x-1">
                        <UserCheck className="w-3.5 h-3.5 text-slate-400" />
                        <span>Authorized Actor: {m.actor}</span>
                      </div>
                      {m.notes && <span className="italic text-slate-500">{m.notes}</span>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      ) : (
        <EmptyState
          title="No Lot Trace Loaded"
          description="Enter a Lot ID above or click on one of the recent lot picks to view its custody history."
          icon={<QrCode className="w-6 h-6" />}
        />
      )}
    </div>
  );
};
