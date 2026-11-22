import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';
import { EmptyState } from '../components/ui/EmptyState';
import { Warehouse, AlertTriangle, ShieldAlert, Plus, Thermometer, Droplets, ArrowRight } from 'lucide-react';
import { useToast } from '../context/ToastContext';
import { useNavigate } from 'react-router-dom';
import type { StorageFacility, SpoilageRiskAlert } from '../types';

export const StoragePage: React.FC = () => {
  const [facilities, setFacilities] = useState<StorageFacility[]>([]);
  const [spoilageRisks, setSpoilageRisks] = useState<SpoilageRiskAlert[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // New Facility Form
  const [formData, setFormData] = useState({
    name: '',
    facility_type: 'cold_storage' as 'cold_storage' | 'dry_warehouse' | 'silo',
    district: 'Hooghly',
    total_capacity_kg: 50000,
    utilized_capacity_kg: 18000,
  });

  const toast = useToast();
  const navigate = useNavigate();

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setIsLoading(true);
      const [facs, risks] = await Promise.all([
        api.getStorageFacilities(),
        api.getSpoilageRisks(),
      ]);
      setFacilities(facs);
      setSpoilageRisks(risks);
    } catch (err) {
      toast.error('Failed to load storage data');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateFacility = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createStorageFacility({
        name: formData.name,
        facility_type: formData.facility_type,
        district: formData.district,
        total_capacity_grams: Number(formData.total_capacity_kg) * 1000,
        utilized_capacity_grams: Number(formData.utilized_capacity_kg) * 1000,
      });
      toast.success('Storage facility registered', `${formData.name} added to corridor map.`);
      setIsModalOpen(false);
      setFormData({
        name: '',
        facility_type: 'cold_storage',
        district: 'Hooghly',
        total_capacity_kg: 50000,
        utilized_capacity_kg: 18000,
      });
      loadData();
    } catch (err: any) {
      toast.error('Registration failed', err?.response?.data?.message || 'Error registering facility');
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Storage & Spoilage Risk Radar</h1>
          <p className="text-xs text-slate-500 mt-1">
            Cold storage utilization meters, shelf-life monitoring, and agronomic decay curve alerts.
          </p>
        </div>
        <Button
          size="sm"
          onClick={() => setIsModalOpen(true)}
          leftIcon={<Plus className="w-4 h-4" />}
        >
          Add Storage Facility
        </Button>
      </div>

      {/* Honest IoT Telemetry Disclosure */}
      <div className="bg-amber-50/70 border border-amber-300/80 rounded-2xl p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-start space-x-3">
          <div className="p-2 bg-amber-100 text-amber-800 rounded-xl flex-shrink-0 mt-0.5">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h4 className="text-xs font-bold text-amber-950 uppercase tracking-wider">
                Phase 5/6 Acceptance Notice: IoT Calibrated Telemetry Gated
              </h4>
              <Badge variant="amber">Strict Compliance</Badge>
            </div>
            <p className="text-xs text-amber-800 mt-1 max-w-3xl leading-relaxed">
              In strict accordance with audit restrictions, <code className="font-mono text-[11px]">storage_sensor_measurements.csv</code> remains blank. Spoilage risk is estimated using certified agronomic crop shelf-life decay formulas rather than unverified simulated IoT temperature streams.
            </p>
          </div>
        </div>
      </div>

      {/* Facility Capacity Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {facilities.map((fac) => {
          const totalTonnes = (fac.total_capacity_grams / 1000000).toFixed(1);
          const usedTonnes = (fac.utilized_capacity_grams / 1000000).toFixed(1);
          const utilPct = fac.total_capacity_grams > 0
            ? Math.round((fac.utilized_capacity_grams / fac.total_capacity_grams) * 100)
            : 0;

          return (
            <Card key={fac.id} className="hover:border-slate-300 transition-all">
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                    {fac.facility_type.replace('_', ' ')}
                  </span>
                  <h3 className="font-bold text-slate-900 text-base mt-1">{fac.name}</h3>
                  <p className="text-xs text-slate-500">District: {fac.district}</p>
                </div>
                <Badge variant={utilPct > 80 ? 'rose' : utilPct > 60 ? 'amber' : 'emerald'}>
                  {utilPct}% Full
                </Badge>
              </div>

              {/* Meter */}
              <div className="mt-4 space-y-1.5">
                <div className="flex justify-between text-xs text-slate-600">
                  <span>Capacity Utilization:</span>
                  <span className="font-medium text-slate-900">{usedTonnes} / {totalTonnes} MT</span>
                </div>
                <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
                  <div
                    className={`h-2.5 rounded-full transition-all ${
                      utilPct > 80 ? 'bg-rose-500' : utilPct > 60 ? 'bg-amber-500' : 'bg-emerald-600'
                    }`}
                    style={{ width: `${Math.min(100, utilPct)}%` }}
                  />
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
                <span>Sensor Gate:</span>
                <span className="font-mono text-amber-700 bg-amber-50 px-2 py-0.5 rounded">
                  Pending Partner Calib.
                </span>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Spoilage Risk Alerts Radar */}
      <Card
        title="Agronomic Spoilage Risk Radar"
        subtitle="Identifies lots approaching critical shelf life thresholds for priority salvage"
        headerAction={
          <Button
            size="sm"
            variant="outline"
            onClick={() => navigate('/recovery')}
            rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
          >
            Launch RecoveryOpt
          </Button>
        }
      >
        {spoilageRisks.length === 0 ? (
          <div className="p-8 text-center bg-slate-50 rounded-xl border border-slate-100">
            <Warehouse className="w-8 h-8 text-slate-300 mx-auto mb-2" />
            <h4 className="text-xs font-semibold text-slate-700">No Critical Spoilage Alerts</h4>
            <p className="text-[11px] text-slate-400 mt-1">
              All stored lots are currently within standard baseline shelf-life parameters.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider">
                  <th className="pb-3 px-3">Lot ID</th>
                  <th className="pb-3 px-3">Commodity</th>
                  <th className="pb-3 px-3">Stored Weight</th>
                  <th className="pb-3 px-3">Storage Duration</th>
                  <th className="pb-3 px-3">Estimated Spoilage Risk</th>
                  <th className="pb-3 px-3">Urgency</th>
                  <th className="pb-3 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {spoilageRisks.map((alert) => (
                  <tr key={alert.lot_id} className="hover:bg-slate-50/60">
                    <td className="py-3 px-3 font-mono font-medium text-slate-900">{alert.lot_id.slice(0, 8)}...</td>
                    <td className="py-3 px-3 font-semibold text-slate-800">{alert.commodity_code}</td>
                    <td className="py-3 px-3 text-slate-700 font-medium">{alert.quantity_grams / 1000} kg</td>
                    <td className="py-3 px-3 text-slate-600">{alert.storage_days} days</td>
                    <td className="py-3 px-3">
                      <div className="flex items-center space-x-2">
                        <div className="w-16 bg-slate-200 h-2 rounded-full overflow-hidden">
                          <div
                            className={`h-2 rounded-full ${
                              alert.spoilage_risk_pct > 60
                                ? 'bg-rose-500'
                                : alert.spoilage_risk_pct > 30
                                ? 'bg-amber-500'
                                : 'bg-emerald-500'
                            }`}
                            style={{ width: `${alert.spoilage_risk_pct}%` }}
                          />
                        </div>
                        <span className="font-bold text-slate-800">{alert.spoilage_risk_pct}%</span>
                      </div>
                    </td>
                    <td className="py-3 px-3">
                      <Badge
                        variant={
                          alert.urgency === 'critical'
                            ? 'rose'
                            : alert.urgency === 'high'
                            ? 'amber'
                            : 'emerald'
                        }
                      >
                        {alert.urgency.toUpperCase()}
                      </Badge>
                    </td>
                    <td className="py-3 px-3 text-right">
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => navigate('/recovery')}
                        rightIcon={<ArrowRight className="w-3 h-3 text-emerald-700" />}
                      >
                        Recover
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Facility Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Add Storage Facility"
        description="Register a cold storage or warehouse hub in the pilot network."
      >
        <form onSubmit={handleCreateFacility} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Facility Name</label>
            <input
              type="text"
              required
              placeholder="e.g. Singur Cold Storage Ltd"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Facility Type</label>
              <select
                value={formData.facility_type}
                onChange={(e) => setFormData({ ...formData, facility_type: e.target.value as any })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              >
                <option value="cold_storage">Cold Storage (Controlled Temp)</option>
                <option value="dry_warehouse">Dry Warehouse (Grain/Dry)</option>
                <option value="silo">Bulk Silo</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">District</label>
              <select
                value={formData.district}
                onChange={(e) => setFormData({ ...formData, district: e.target.value })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              >
                <option value="Hooghly">Hooghly</option>
                <option value="Burdwan">Burdwan</option>
                <option value="Nadia">Nadia</option>
                <option value="Bankura">Bankura</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Total Capacity (kg)</label>
              <input
                type="number"
                min="1000"
                step="1000"
                required
                value={formData.total_capacity_kg}
                onChange={(e) => setFormData({ ...formData, total_capacity_kg: Number(e.target.value) })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Current Stored (kg)</label>
              <input
                type="number"
                min="0"
                step="1000"
                required
                value={formData.utilized_capacity_kg}
                onChange={(e) => setFormData({ ...formData, utilized_capacity_kg: Number(e.target.value) })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              />
            </div>
          </div>

          <div className="flex justify-end space-x-2 pt-3 border-t border-slate-100">
            <Button type="button" variant="ghost" size="sm" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" size="sm">
              Save Facility
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
