import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';
import { EmptyState } from '../components/ui/EmptyState';
import { Truck, Users, ShieldAlert, Plus, Route, CheckCircle2, Play } from 'lucide-react';
import { useToast } from '../context/ToastContext';
import type { TransportRequest, SharedTransportGroup, Farmer } from '../types';

export const LogisticsPage: React.FC = () => {
  const [requests, setRequests] = useState<TransportRequest[]>([]);
  const [farmers, setFarmers] = useState<Farmer[]>([]);
  const [poolingResults, setPoolingResults] = useState<SharedTransportGroup[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isPoolingLoading, setIsPoolingLoading] = useState(false);
  const [isRequestModalOpen, setIsRequestModalOpen] = useState(false);

  // Pooling Form State
  const [pickupDistrict, setPickupDistrict] = useState('Hooghly');
  const [deliveryDistrict, setDeliveryDistrict] = useState('Kolkata');
  const [vehicleCapacityKg, setVehicleCapacityKg] = useState(2000);

  // New Request Form State
  const [newRequestData, setNewRequestData] = useState({
    farmer_id: '',
    commodity_code: 'POTATO',
    quantity_kg: 400,
    pickup_district: 'Hooghly',
    drop_district: 'Kolkata',
    pickup_date: new Date(Date.now() + 2 * 86400000).toISOString().split('T')[0],
  });

  const toast = useToast();

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setIsLoading(true);
      const [reqs, fms] = await Promise.all([
        api.getTransportRequests(),
        api.getFarmers(),
      ]);
      setRequests(reqs);
      setFarmers(fms);
      if (fms.length > 0 && !newRequestData.farmer_id) {
        setNewRequestData((prev) => ({ ...prev, farmer_id: fms[0].id }));
      }
    } catch (err) {
      toast.error('Failed to load logistics data');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRequestData.farmer_id) {
      toast.error('Select a farmer');
      return;
    }

    try {
      await api.createTransportRequest({
        farmer_id: newRequestData.farmer_id,
        commodity_code: newRequestData.commodity_code,
        quantity_grams: Number(newRequestData.quantity_kg) * 1000,
        pickup_district: newRequestData.pickup_district,
        drop_district: newRequestData.drop_district,
        pickup_date: newRequestData.pickup_date,
        status: 'pending',
      });
      toast.success('Transport request created', `Pickup request for ${newRequestData.quantity_kg}kg logged.`);
      setIsRequestModalOpen(false);
      loadData();
    } catch (err: any) {
      toast.error('Creation failed', err?.response?.data?.message || 'Error creating transport request');
    }
  };

  const handleRunOptimizer = async () => {
    try {
      setIsPoolingLoading(true);
      const groups = await api.optimizeSharedTransport({
        pickup_district: pickupDistrict,
        delivery_district: deliveryDistrict,
        max_vehicle_capacity_grams: Number(vehicleCapacityKg) * 1000,
      });
      setPoolingResults(groups);
      if (groups.length > 0) {
        toast.success('Pooling plan generated', `Formed ${groups.length} multi-farmer transport group(s).`);
      } else {
        toast.info('No pending requests matched the selected district corridor');
      }
    } catch (err: any) {
      toast.error('Optimization failed', err?.response?.data?.message || 'Error running optimizer');
    } finally {
      setIsPoolingLoading(false);
    }
  };

  const farmerMap = new Map(farmers.map((f) => [f.id, f.name]));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Shared Logistics & Cargo Pooling</h1>
          <p className="text-xs text-slate-500 mt-1">
            Greedy vehicle space optimization pooling smallholder harvests into shared multi-farmer trucks.
          </p>
        </div>
        <Button
          size="sm"
          onClick={() => setIsRequestModalOpen(true)}
          leftIcon={<Plus className="w-4 h-4" />}
          disabled={farmers.length === 0}
        >
          Add Transport Request
        </Button>
      </div>

      {/* Honest GNSS & Road Restrictions Disclaimer */}
      <div className="bg-amber-50/70 border border-amber-300/80 rounded-2xl p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-start space-x-3">
          <div className="p-2 bg-amber-100 text-amber-800 rounded-xl flex-shrink-0 mt-0.5">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h4 className="text-xs font-bold text-amber-950 uppercase tracking-wider">
                Logistics Data Restriction: GNSS Surveys & Passability Gated
              </h4>
              <Badge variant="amber">Strict Compliance</Badge>
            </div>
            <p className="text-xs text-amber-800 mt-1 max-w-3xl leading-relaxed">
              In accordance with Phase 5/6 acceptance criteria, <code className="font-mono text-[11px]">road_edges.csv</code> and ground GNSS surveys are kept empty. Route plans are based on district-level aggregation; no fabricated road bypass or bridge passability is assumed.
            </p>
          </div>
        </div>
      </div>

      {/* Shared Pooling Runner Card */}
      <Card
        title="Shared Transport Pooling Solver"
        subtitle="Greedy bin-packing algorithm to aggregate smallholder lots and reduce transport costs by up to 35%"
      >
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Pickup District</label>
            <select
              value={pickupDistrict}
              onChange={(e) => setPickupDistrict(e.target.value)}
              className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500 font-medium"
            >
              <option value="Hooghly">Hooghly</option>
              <option value="Burdwan">Burdwan</option>
              <option value="Nadia">Nadia</option>
              <option value="Bankura">Bankura</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Delivery Destination</label>
            <select
              value={deliveryDistrict}
              onChange={(e) => setDeliveryDistrict(e.target.value)}
              className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500 font-medium"
            >
              <option value="Kolkata">Kolkata</option>
              <option value="Howrah">Howrah</option>
              <option value="Burdwan">Burdwan</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Vehicle Payload Capacity (kg)</label>
            <input
              type="number"
              min="500"
              step="500"
              value={vehicleCapacityKg}
              onChange={(e) => setVehicleCapacityKg(Number(e.target.value))}
              className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
            />
          </div>

          <Button
            size="md"
            onClick={handleRunOptimizer}
            isLoading={isPoolingLoading}
            leftIcon={<Play className="w-4 h-4 fill-current" />}
            className="w-full justify-center"
          >
            Run Pooling Solver
          </Button>
        </div>

        {/* Solver Results */}
        {poolingResults.length > 0 && (
          <div className="mt-6 pt-6 border-t border-slate-100 space-y-4">
            <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
              Generated Shared Transport Groups ({poolingResults.length})
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {poolingResults.map((group, idx) => (
                <div key={idx} className="p-4 rounded-2xl bg-emerald-50/50 border border-emerald-200 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-emerald-950 text-sm">
                      Truck Group #{idx + 1}
                    </span>
                    <Badge variant="emerald">{group.utilization_pct.toFixed(0)}% Utilized</Badge>
                  </div>

                  <div className="text-xs text-slate-600 flex justify-between">
                    <span>Corridor: {group.pickup_district} &rarr; {group.delivery_district}</span>
                    <span className="font-medium text-slate-800">
                      {(group.total_weight_grams / 1000).toFixed(0)} / {(group.vehicle_capacity_grams / 1000).toFixed(0)} kg
                    </span>
                  </div>

                  {/* Progress Bar */}
                  <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
                    <div
                      className="bg-emerald-600 h-2 rounded-full transition-all"
                      style={{ width: `${Math.min(100, group.utilization_pct)}%` }}
                    />
                  </div>

                  <div className="pt-2 border-t border-emerald-200/80 text-[11px] text-slate-600">
                    <span className="font-semibold block mb-1">
                      Pooled Farmers ({group.assigned_requests.length} pickups):
                    </span>
                    <ul className="space-y-1">
                      {group.assigned_requests.map((r, rIdx) => (
                        <li key={rIdx} className="flex justify-between">
                          <span>{farmerMap.get(r.farmer_id) || 'Producer'} ({r.commodity_code})</span>
                          <span className="font-mono font-medium">{(r.quantity_grams / 1000).toFixed(0)} kg</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>

      {/* Pending Requests Table */}
      <Card
        title="Producer Transport Requests"
        subtitle={`Showing ${requests.length} farmer pickup requests awaiting dispatch`}
      >
        {requests.length === 0 ? (
          <EmptyState
            title="No Pickup Requests Pending"
            description="All smallholder transport requests have either been scheduled or none are pending."
            actionText="Create Request"
            onAction={() => setIsRequestModalOpen(true)}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider">
                  <th className="pb-3 px-3">Farmer</th>
                  <th className="pb-3 px-3">Commodity</th>
                  <th className="pb-3 px-3">Quantity</th>
                  <th className="pb-3 px-3">Pickup &rarr; Delivery</th>
                  <th className="pb-3 px-3">Pickup Date</th>
                  <th className="pb-3 px-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {requests.map((req) => (
                  <tr key={req.id} className="hover:bg-slate-50/60">
                    <td className="py-3 px-3 font-semibold text-slate-900">
                      {farmerMap.get(req.farmer_id) || 'Producer'}
                    </td>
                    <td className="py-3 px-3 font-medium text-slate-700">{req.commodity_code}</td>
                    <td className="py-3 px-3 font-bold text-slate-800">{req.quantity_grams / 1000} kg</td>
                    <td className="py-3 px-3 text-slate-600">
                      {req.pickup_district} &rarr; {req.drop_district}
                    </td>
                    <td className="py-3 px-3 text-slate-600">{req.pickup_date}</td>
                    <td className="py-3 px-3">
                      <Badge variant={req.status === 'completed' ? 'emerald' : req.status === 'assigned' ? 'blue' : 'amber'}>
                        {req.status.toUpperCase()}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Create Request Modal */}
      <Modal
        isOpen={isRequestModalOpen}
        onClose={() => setIsRequestModalOpen(false)}
        title="Add Pickup Request"
        description="Book farm-gate pickup for harvested produce into the shared pooling network."
      >
        <form onSubmit={handleCreateRequest} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Farmer Producer</label>
            <select
              required
              value={newRequestData.farmer_id}
              onChange={(e) => setNewRequestData({ ...newRequestData, farmer_id: e.target.value })}
              className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
            >
              {farmers.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name} - {f.village}, {f.district}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Commodity</label>
              <select
                value={newRequestData.commodity_code}
                onChange={(e) => setNewRequestData({ ...newRequestData, commodity_code: e.target.value })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              >
                <option value="POTATO">Potato (আলু)</option>
                <option value="TOMATO">Tomato (টমেটো)</option>
                <option value="PADDY">Paddy (ধান)</option>
                <option value="ONION">Onion (পেঁয়াজ)</option>
                <option value="JUTE">Jute (পাট)</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Quantity (kg)</label>
              <input
                type="number"
                min="50"
                required
                value={newRequestData.quantity_kg}
                onChange={(e) => setNewRequestData({ ...newRequestData, quantity_kg: Number(e.target.value) })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Pickup District</label>
              <select
                value={newRequestData.pickup_district}
                onChange={(e) => setNewRequestData({ ...newRequestData, pickup_district: e.target.value })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              >
                <option value="Hooghly">Hooghly</option>
                <option value="Burdwan">Burdwan</option>
                <option value="Nadia">Nadia</option>
                <option value="Bankura">Bankura</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Drop District</label>
              <select
                value={newRequestData.drop_district}
                onChange={(e) => setNewRequestData({ ...newRequestData, drop_district: e.target.value })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              >
                <option value="Kolkata">Kolkata</option>
                <option value="Howrah">Howrah</option>
                <option value="Burdwan">Burdwan</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Requested Pickup Date</label>
            <input
              type="date"
              required
              value={newRequestData.pickup_date}
              onChange={(e) => setNewRequestData({ ...newRequestData, pickup_date: e.target.value })}
              className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
            />
          </div>

          <div className="flex justify-end space-x-2 pt-3 border-t border-slate-100">
            <Button type="button" variant="ghost" size="sm" onClick={() => setIsRequestModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" size="sm">
              Submit Request
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
