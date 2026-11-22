import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';
import { EmptyState } from '../components/ui/EmptyState';
import { UserPlus, Search, Phone, MapPin, Globe, Sparkles, Sprout } from 'lucide-react';
import { useToast } from '../context/ToastContext';
import type { Farmer } from '../types';

export const FarmersPage: React.FC = () => {
  const [farmers, setFarmers] = useState<Farmer[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isRegisterOpen, setIsRegisterOpen] = useState(false);
  const [isForecastOpen, setIsForecastOpen] = useState(false);
  const [selectedFarmer, setSelectedFarmer] = useState<Farmer | null>(null);

  // New Farmer Form State
  const [formData, setFormData] = useState({
    name: '',
    phone: '',
    village: '',
    district: 'Hooghly',
    state: 'West Bengal',
    preferred_language: 'bn-IN' as 'bn-IN' | 'hi-IN' | 'en-IN',
    landholding_hectares: 1.5,
  });

  // Forecast Form State
  const [forecastData, setForecastData] = useState({
    commodity_code: 'POTATO',
    expected_quantity_kg: 500,
    forecast_date: new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0],
  });

  const toast = useToast();

  useEffect(() => {
    loadFarmers();
  }, []);

  const loadFarmers = async () => {
    try {
      setIsLoading(true);
      const data = await api.getFarmers();
      setFarmers(data);
    } catch (err) {
      toast.error('Failed to load farmers directory');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createFarmer(formData);
      toast.success('Farmer registered successfully', `${formData.name} is now added.`);
      setIsRegisterOpen(false);
      setFormData({
        name: '',
        phone: '',
        village: '',
        district: 'Hooghly',
        state: 'West Bengal',
        preferred_language: 'bn-IN',
        landholding_hectares: 1.5,
      });
      loadFarmers();
    } catch (err: any) {
      toast.error('Registration failed', err?.response?.data?.message || 'Could not register farmer');
    }
  };

  const handleAddForecast = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFarmer) return;
    try {
      await api.createForecast({
        farmer_id: selectedFarmer.id,
        commodity_code: forecastData.commodity_code,
        expected_quantity_grams: Number(forecastData.expected_quantity_kg) * 1000,
        forecast_date: forecastData.forecast_date,
        confidence_pct: 90,
      });
      toast.success('Harvest forecast recorded', `${forecastData.commodity_code} forecast registered.`);
      setIsForecastOpen(false);
    } catch (err: any) {
      toast.error('Forecast submission failed', err?.response?.data?.message || 'Error creating forecast');
    }
  };

  const filteredFarmers = farmers.filter(
    (f) =>
      f.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      f.village.toLowerCase().includes(searchTerm.toLowerCase()) ||
      f.district.toLowerCase().includes(searchTerm.toLowerCase()) ||
      f.phone.includes(searchTerm)
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Farmer Directory & Profiles</h1>
          <p className="text-xs text-slate-500 mt-1">
            Smallholder producer registration, landholding details, language preferences, and harvest forecasts.
          </p>
        </div>
        <Button
          size="sm"
          onClick={() => setIsRegisterOpen(true)}
          leftIcon={<UserPlus className="w-4 h-4" />}
        >
          Register New Farmer
        </Button>
      </div>

      {/* GNSS Notice */}
      <div className="p-3 bg-amber-50/60 border border-amber-200/80 rounded-xl text-xs text-amber-900 flex items-center justify-between">
        <span>
          <strong className="font-semibold">Farm-gate GNSS Notice:</strong> In compliance with dataset restrictions, GPS coordinates remain unverified until official field surveys are completed.
        </span>
        <Badge variant="amber">Audit Gate Active</Badge>
      </div>

      {/* Directory Card */}
      <Card
        title="Producer Records"
        subtitle={`Showing ${filteredFarmers.length} registered farmers`}
        headerAction={
          <div className="relative w-64">
            <Search className="w-3.5 h-3.5 absolute left-3 top-3 text-slate-400" />
            <input
              type="text"
              placeholder="Search by name, village, district..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full text-xs pl-8 pr-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-emerald-500"
            />
          </div>
        }
      >
        {filteredFarmers.length === 0 ? (
          <EmptyState
            title="No Farmers Found"
            description="No producers match the current filter criteria or none have been enrolled yet."
            actionText="Register Producer"
            onAction={() => setIsRegisterOpen(true)}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider">
                  <th className="pb-3 px-3">Farmer Name</th>
                  <th className="pb-3 px-3">Contact</th>
                  <th className="pb-3 px-3">Village / District</th>
                  <th className="pb-3 px-3">Landholding</th>
                  <th className="pb-3 px-3">Language</th>
                  <th className="pb-3 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredFarmers.map((f) => (
                  <tr key={f.id} className="hover:bg-slate-50/60">
                    <td className="py-3 px-3">
                      <div className="font-semibold text-slate-900">{f.name}</div>
                      <div className="text-[10px] font-mono text-slate-400">{f.id.slice(0, 8)}...</div>
                    </td>
                    <td className="py-3 px-3 text-slate-600">
                      <div className="flex items-center space-x-1">
                        <Phone className="w-3 h-3 text-slate-400" />
                        <span>{f.phone}</span>
                      </div>
                    </td>
                    <td className="py-3 px-3 text-slate-600">
                      <div className="flex items-center space-x-1">
                        <MapPin className="w-3 h-3 text-slate-400" />
                        <span>{f.village}, {f.district}</span>
                      </div>
                    </td>
                    <td className="py-3 px-3 text-slate-800 font-medium">
                      {f.landholding_hectares} ha
                    </td>
                    <td className="py-3 px-3">
                      <Badge variant={f.preferred_language === 'bn-IN' ? 'emerald' : 'blue'}>
                        {f.preferred_language === 'bn-IN' ? 'বাংলা' : f.preferred_language === 'hi-IN' ? 'हिन्दी' : 'English'}
                      </Badge>
                    </td>
                    <td className="py-3 px-3 text-right">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setSelectedFarmer(f);
                          setIsForecastOpen(true);
                        }}
                        leftIcon={<Sprout className="w-3 h-3 text-emerald-600" />}
                      >
                        Add Harvest Forecast
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Registration Modal */}
      <Modal
        isOpen={isRegisterOpen}
        onClose={() => setIsRegisterOpen(false)}
        title="Register New Farmer"
        description="Add a producer to the GramSetu network for direct market access."
      >
        <form onSubmit={handleRegister} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Full Name</label>
            <input
              type="text"
              required
              placeholder="e.g. Subhash Mandal"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Phone Number</label>
              <input
                type="tel"
                required
                placeholder="10-digit mobile"
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Preferred Language</label>
              <select
                value={formData.preferred_language}
                onChange={(e) => setFormData({ ...formData, preferred_language: e.target.value as any })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              >
                <option value="bn-IN">বাংলা (Bengali)</option>
                <option value="hi-IN">हिन्दी (Hindi)</option>
                <option value="en-IN">English</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Village</label>
              <input
                type="text"
                required
                placeholder="e.g. Singur"
                value={formData.village}
                onChange={(e) => setFormData({ ...formData, village: e.target.value })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">District</label>
              <select
                value={formData.district}
                onChange={(e) => setFormData({ ...formData, district: e.target.value })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              >
                <option value="Hooghly">Hooghly</option>
                <option value="Burdwan">Burdwan (Purba Bardhaman)</option>
                <option value="Nadia">Nadia</option>
                <option value="Bankura">Bankura</option>
                <option value="Birbhum">Birbhum</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Landholding (Hectares)</label>
            <input
              type="number"
              step="0.1"
              min="0.1"
              required
              value={formData.landholding_hectares}
              onChange={(e) => setFormData({ ...formData, landholding_hectares: parseFloat(e.target.value) })}
              className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
            />
          </div>

          <div className="flex justify-end space-x-2 pt-3 border-t border-slate-100">
            <Button type="button" variant="ghost" size="sm" onClick={() => setIsRegisterOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" size="sm">
              Save Farmer
            </Button>
          </div>
        </form>
      </Modal>

      {/* Harvest Forecast Modal */}
      <Modal
        isOpen={isForecastOpen}
        onClose={() => setIsForecastOpen(false)}
        title={`Harvest Forecast for ${selectedFarmer?.name || 'Farmer'}`}
        description="Forecast future harvest to synchronize with buyer demand and transport."
      >
        <form onSubmit={handleAddForecast} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Crop Commodity</label>
            <select
              value={forecastData.commodity_code}
              onChange={(e) => setForecastData({ ...forecastData, commodity_code: e.target.value })}
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
            <label className="block text-xs font-semibold text-slate-700 mb-1">Expected Yield (kg)</label>
            <input
              type="number"
              min="10"
              required
              value={forecastData.expected_quantity_kg}
              onChange={(e) => setForecastData({ ...forecastData, expected_quantity_kg: Number(e.target.value) })}
              className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Estimated Harvest Date</label>
            <input
              type="date"
              required
              value={forecastData.forecast_date}
              onChange={(e) => setForecastData({ ...forecastData, forecast_date: e.target.value })}
              className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
            />
          </div>

          <div className="flex justify-end space-x-2 pt-3 border-t border-slate-100">
            <Button type="button" variant="ghost" size="sm" onClick={() => setIsForecastOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" size="sm">
              Save Forecast
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
