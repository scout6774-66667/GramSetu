import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';
import { EmptyState } from '../components/ui/EmptyState';
import { Package, Plus, Calendar, ShieldCheck, Tag, ShoppingCart } from 'lucide-react';
import { useToast } from '../context/ToastContext';
import { useNavigate } from 'react-router-dom';
import type { ProduceListing, Farmer } from '../types';

export const ListingsPage: React.FC = () => {
  const [listings, setListings] = useState<ProduceListing[]>([]);
  const [farmers, setFarmers] = useState<Farmer[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [selectedListing, setSelectedListing] = useState<ProduceListing | null>(null);

  // Listing Form State
  const [formData, setFormData] = useState({
    farmer_id: '',
    commodity_code: 'POTATO',
    quantity_kg: 500,
    asking_price_per_kg: 18,
    harvest_date: new Date().toISOString().split('T')[0],
    available_from: new Date().toISOString().split('T')[0],
    quality_grade: 'A' as 'A' | 'B' | 'C',
    notes: 'Grade-A fresh harvest from Hooghly cold storage belt',
  });

  const toast = useToast();
  const navigate = useNavigate();

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setIsLoading(true);
      const [listingsData, farmersData] = await Promise.all([
        api.getListings(),
        api.getFarmers(),
      ]);
      setListings(listingsData);
      setFarmers(farmersData);
      if (farmersData.length > 0 && !formData.farmer_id) {
        setFormData((prev) => ({ ...prev, farmer_id: farmersData[0].id }));
      }
    } catch (err) {
      toast.error('Failed to load listings');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateListing = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.farmer_id) {
      toast.error('Please select a farmer producer first');
      return;
    }
    try {
      await api.createListing({
        farmer_id: formData.farmer_id,
        commodity_code: formData.commodity_code,
        quantity_grams: Number(formData.quantity_kg) * 1000,
        asking_price_paise_per_kg: Math.round(Number(formData.asking_price_per_kg) * 100),
        harvest_date: formData.harvest_date,
        available_from: formData.available_from,
        quality_grade: formData.quality_grade,
        notes: formData.notes,
        status: 'active',
      });
      toast.success('Crop listing published', `Published ${formData.quantity_kg}kg of ${formData.commodity_code}.`);
      setIsCreateOpen(false);
      loadData();
    } catch (err: any) {
      toast.error('Failed to publish listing', err?.response?.data?.message || 'Error creating listing');
    }
  };

  const farmerMap = new Map(farmers.map((f) => [f.id, f.name]));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Produce Marketplace & Catalog</h1>
          <p className="text-xs text-slate-500 mt-1">
            Real farm-gate produce listings with transparent pricing in ₹/kg (paise precision) and verified lot custody.
          </p>
        </div>
        <Button
          size="sm"
          onClick={() => setIsCreateOpen(true)}
          leftIcon={<Plus className="w-4 h-4" />}
        >
          Create Crop Listing
        </Button>
      </div>

      {/* Produce Grid */}
      {listings.length === 0 ? (
        <EmptyState
          title="No Crop Listings Available"
          description="There are currently no active crop lots listed by farmers or FPOs."
          actionText="Create First Listing"
          onAction={() => setIsCreateOpen(true)}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {listings.map((item) => {
            const pricePerKg = (item.asking_price_paise_per_kg / 100).toFixed(2);
            const totalKg = item.quantity_grams / 1000;
            const totalVal = ((item.quantity_grams / 1000) * (item.asking_price_paise_per_kg / 100)).toFixed(0);
            const farmerName = farmerMap.get(item.farmer_id) || 'Enrolled Producer';

            return (
              <Card key={item.id} className="hover:border-slate-300 transition-all">
                <div className="flex items-start justify-between">
                  <div>
                    <span className="text-[10px] font-bold text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded-md uppercase tracking-wider">
                      {item.commodity_code}
                    </span>
                    <h3 className="font-bold text-slate-900 text-lg mt-1.5">{item.commodity_code}</h3>
                    <p className="text-xs text-slate-500">Producer: {farmerName}</p>
                  </div>
                  <Badge variant={item.quality_grade === 'A' ? 'emerald' : item.quality_grade === 'B' ? 'blue' : 'amber'}>
                    Grade {item.quality_grade}
                  </Badge>
                </div>

                <div className="mt-4 pt-4 border-t border-slate-100 grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <span className="text-slate-400 block">Available Quantity:</span>
                    <span className="font-bold text-slate-900 text-sm">{totalKg} kg</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block">Asking Price:</span>
                    <span className="font-bold text-emerald-700 text-sm">₹{pricePerKg} / kg</span>
                  </div>
                </div>

                <div className="mt-3 flex items-center justify-between text-xs bg-slate-50 p-2.5 rounded-xl border border-slate-100">
                  <div className="flex items-center space-x-1 text-slate-600">
                    <Calendar className="w-3.5 h-3.5 text-slate-400" />
                    <span>Harvest: {item.harvest_date}</span>
                  </div>
                  <span className="font-semibold text-slate-900">Lot: ₹{totalVal}</span>
                </div>

                <div className="mt-4 flex space-x-2">
                  <Button
                    size="sm"
                    variant="outline"
                    className="flex-1 text-xs"
                    onClick={() => navigate(`/traceability`)}
                  >
                    View BatchTrace
                  </Button>
                  <Button
                    size="sm"
                    className="flex-1 text-xs"
                    onClick={() => navigate(`/procurement`)}
                    leftIcon={<ShoppingCart className="w-3.5 h-3.5" />}
                  >
                    Make Offer
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Create Listing Modal */}
      <Modal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title="Create New Crop Listing"
        description="Publish available harvest to wholesale buyers across the corridor."
      >
        <form onSubmit={handleCreateListing} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Farmer Producer</label>
            <select
              required
              value={formData.farmer_id}
              onChange={(e) => setFormData({ ...formData, farmer_id: e.target.value })}
              className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
            >
              {farmers.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name} ({f.village}, {f.district})
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Commodity</label>
              <select
                value={formData.commodity_code}
                onChange={(e) => setFormData({ ...formData, commodity_code: e.target.value })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              >
                <option value="POTATO">Potato (আলু / Jyoti)</option>
                <option value="TOMATO">Tomato (টমেটো)</option>
                <option value="PADDY">Paddy / Rice (ধান)</option>
                <option value="ONION">Onion (পেঁয়াজ)</option>
                <option value="JUTE">Jute (পাট)</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Quality Grade</label>
              <select
                value={formData.quality_grade}
                onChange={(e) => setFormData({ ...formData, quality_grade: e.target.value as any })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              >
                <option value="A">Grade A (Premium)</option>
                <option value="B">Grade B (Standard)</option>
                <option value="C">Grade C (Processing / Utility)</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Available Quantity (kg)</label>
              <input
                type="number"
                min="10"
                required
                value={formData.quantity_kg}
                onChange={(e) => setFormData({ ...formData, quantity_kg: Number(e.target.value) })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Asking Price (₹/kg)</label>
              <input
                type="number"
                min="1"
                step="0.5"
                required
                value={formData.asking_price_per_kg}
                onChange={(e) => setFormData({ ...formData, asking_price_per_kg: Number(e.target.value) })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Harvest Date</label>
              <input
                type="date"
                required
                value={formData.harvest_date}
                onChange={(e) => setFormData({ ...formData, harvest_date: e.target.value })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Available From</label>
              <input
                type="date"
                required
                value={formData.available_from}
                onChange={(e) => setFormData({ ...formData, available_from: e.target.value })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Lot Notes / Description</label>
            <textarea
              rows={2}
              value={formData.notes}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
            />
          </div>

          <div className="flex justify-end space-x-2 pt-3 border-t border-slate-100">
            <Button type="button" variant="ghost" size="sm" onClick={() => setIsCreateOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" size="sm">
              Publish Listing
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
