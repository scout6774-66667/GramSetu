import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';
import { EmptyState } from '../components/ui/EmptyState';
import { Building2, Search, Phone, Mail, MapPin, CheckCircle, PlusCircle, ShieldAlert } from 'lucide-react';
import { useToast } from '../context/ToastContext';
import type { Buyer } from '../types';

export const BuyersPage: React.FC = () => {
  const [buyers, setBuyers] = useState<Buyer[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isRegisterOpen, setIsRegisterOpen] = useState(false);
  const [isRequirementOpen, setIsRequirementOpen] = useState(false);
  const [selectedBuyer, setSelectedBuyer] = useState<Buyer | null>(null);

  // New Buyer Form
  const [formData, setFormData] = useState({
    name: '',
    organization: '',
    phone: '',
    email: '',
    city: 'Kolkata',
    district: 'Kolkata',
    state: 'West Bengal',
    business_type: 'Wholesaler',
    verified_status: true,
  });

  // Requirement Form
  const [reqData, setReqData] = useState({
    commodity_code: 'POTATO',
    target_quantity_kg: 1000,
    max_price_per_kg: 22,
    delivery_district: 'Kolkata',
    required_by: new Date(Date.now() + 10 * 86400000).toISOString().split('T')[0],
  });

  const toast = useToast();

  useEffect(() => {
    loadBuyers();
  }, []);

  const loadBuyers = async () => {
    try {
      setIsLoading(true);
      const data = await api.getBuyers();
      setBuyers(data);
    } catch (err) {
      toast.error('Failed to load buyers network');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createBuyer(formData);
      toast.success('Buyer registered successfully', `${formData.name} (${formData.organization}) enrolled.`);
      setIsRegisterOpen(false);
      setFormData({
        name: '',
        organization: '',
        phone: '',
        email: '',
        city: 'Kolkata',
        district: 'Kolkata',
        state: 'West Bengal',
        business_type: 'Wholesaler',
        verified_status: true,
      });
      loadBuyers();
    } catch (err: any) {
      toast.error('Registration failed', err?.response?.data?.message || 'Error registering buyer');
    }
  };

  const handleAddRequirement = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedBuyer) return;
    try {
      await api.createRequirement({
        buyer_id: selectedBuyer.id,
        commodity_code: reqData.commodity_code,
        target_quantity_grams: Number(reqData.target_quantity_kg) * 1000,
        max_price_paise_per_kg: Math.round(Number(reqData.max_price_per_kg) * 100),
        delivery_district: reqData.delivery_district,
        required_by: reqData.required_by,
      });
      toast.success('Procurement demand registered', `Demand for ${reqData.commodity_code} synchronized.`);
      setIsRequirementOpen(false);
    } catch (err: any) {
      toast.error('Requirement failed', err?.response?.data?.message || 'Error registering demand');
    }
  };

  const filteredBuyers = buyers.filter(
    (b) =>
      b.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      b.organization.toLowerCase().includes(searchTerm.toLowerCase()) ||
      b.city.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Buyer Network & Institutional Demand</h1>
          <p className="text-xs text-slate-500 mt-1">
            Verified wholesale buyers, aggregators, retailers, and food processors with direct procurement demand.
          </p>
        </div>
        <Button
          size="sm"
          onClick={() => setIsRegisterOpen(true)}
          leftIcon={<Building2 className="w-4 h-4" />}
        >
          Register Verified Buyer
        </Button>
      </div>

      {/* Directory Card */}
      <Card
        title="Institutional & Wholesale Accounts"
        subtitle={`Showing ${filteredBuyers.length} verified buyers`}
        headerAction={
          <div className="relative w-64">
            <Search className="w-3.5 h-3.5 absolute left-3 top-3 text-slate-400" />
            <input
              type="text"
              placeholder="Search by buyer, organization, city..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full text-xs pl-8 pr-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-emerald-500"
            />
          </div>
        }
      >
        {filteredBuyers.length === 0 ? (
          <EmptyState
            title="No Buyers Enrolled"
            description="No institutional or wholesale buyer accounts currently listed."
            actionText="Register Buyer"
            onAction={() => setIsRegisterOpen(true)}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider">
                  <th className="pb-3 px-3">Buyer & Org</th>
                  <th className="pb-3 px-3">Business Type</th>
                  <th className="pb-3 px-3">Contact</th>
                  <th className="pb-3 px-3">Location</th>
                  <th className="pb-3 px-3">Verification</th>
                  <th className="pb-3 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredBuyers.map((b) => (
                  <tr key={b.id} className="hover:bg-slate-50/60">
                    <td className="py-3 px-3">
                      <div className="font-semibold text-slate-900">{b.name}</div>
                      <div className="text-[11px] text-slate-500">{b.organization}</div>
                    </td>
                    <td className="py-3 px-3 text-slate-700">
                      <span className="font-medium">{b.business_type}</span>
                    </td>
                    <td className="py-3 px-3 text-slate-600">
                      <div className="flex items-center space-x-1">
                        <Phone className="w-3 h-3 text-slate-400" />
                        <span>{b.phone}</span>
                      </div>
                      {b.email && (
                        <div className="flex items-center space-x-1 text-[11px] text-slate-400 mt-0.5">
                          <Mail className="w-3 h-3" />
                          <span>{b.email}</span>
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-3 text-slate-600">
                      <div className="flex items-center space-x-1">
                        <MapPin className="w-3 h-3 text-slate-400" />
                        <span>{b.city}, {b.district}</span>
                      </div>
                    </td>
                    <td className="py-3 px-3">
                      <Badge variant={b.verified_status ? 'emerald' : 'slate'}>
                        {b.verified_status ? 'Verified KYC' : 'Pending Review'}
                      </Badge>
                    </td>
                    <td className="py-3 px-3 text-right">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setSelectedBuyer(b);
                          setIsRequirementOpen(true);
                        }}
                        leftIcon={<PlusCircle className="w-3 h-3 text-emerald-600" />}
                      >
                        Add Demand Req
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Register Buyer Modal */}
      <Modal
        isOpen={isRegisterOpen}
        onClose={() => setIsRegisterOpen(false)}
        title="Register Buyer Account"
        description="Enroll a food processor, wholesale trader, or retail chain in GramSetu."
      >
        <form onSubmit={handleRegister} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Representative Name</label>
              <input
                type="text"
                required
                placeholder="e.g. Ramesh Ghosh"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Organization / Enterprise</label>
              <input
                type="text"
                required
                placeholder="e.g. Bengal Fresh Wholesale"
                value={formData.organization}
                onChange={(e) => setFormData({ ...formData, organization: e.target.value })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              />
            </div>
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
              <label className="block text-xs font-semibold text-slate-700 mb-1">Business Type</label>
              <select
                value={formData.business_type}
                onChange={(e) => setFormData({ ...formData, business_type: e.target.value })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              >
                <option value="Wholesaler">Wholesaler</option>
                <option value="Food Processor">Food Processor</option>
                <option value="Modern Retail Chain">Modern Retail Chain</option>
                <option value="Exporter">Exporter</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">City</label>
              <input
                type="text"
                required
                placeholder="e.g. Kolkata"
                value={formData.city}
                onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">District</label>
              <input
                type="text"
                required
                value={formData.district}
                onChange={(e) => setFormData({ ...formData, district: e.target.value })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              />
            </div>
          </div>

          <div className="flex justify-end space-x-2 pt-3 border-t border-slate-100">
            <Button type="button" variant="ghost" size="sm" onClick={() => setIsRegisterOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" size="sm">
              Register Buyer
            </Button>
          </div>
        </form>
      </Modal>

      {/* Add Requirement Modal */}
      <Modal
        isOpen={isRequirementOpen}
        onClose={() => setIsRequirementOpen(false)}
        title={`Procurement Requirement for ${selectedBuyer?.organization || 'Buyer'}`}
        description="Add target commodity demand to match against farmer harvest forecasts."
      >
        <form onSubmit={handleAddRequirement} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Crop Commodity</label>
            <select
              value={reqData.commodity_code}
              onChange={(e) => setReqData({ ...reqData, commodity_code: e.target.value })}
              className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
            >
              <option value="POTATO">Potato (আলু / Jyoti)</option>
              <option value="TOMATO">Tomato (টমেটো)</option>
              <option value="PADDY">Paddy / Rice (ধান)</option>
              <option value="ONION">Onion (পেঁয়াজ)</option>
              <option value="JUTE">Jute (পাট)</option>
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Target Quantity (kg)</label>
              <input
                type="number"
                min="50"
                required
                value={reqData.target_quantity_kg}
                onChange={(e) => setReqData({ ...reqData, target_quantity_kg: Number(e.target.value) })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Max Budget Price (₹/kg)</label>
              <input
                type="number"
                min="1"
                step="0.5"
                required
                value={reqData.max_price_per_kg}
                onChange={(e) => setReqData({ ...reqData, max_price_per_kg: Number(e.target.value) })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Delivery Destination District</label>
              <input
                type="text"
                required
                value={reqData.delivery_district}
                onChange={(e) => setReqData({ ...reqData, delivery_district: e.target.value })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Required By Date</label>
              <input
                type="date"
                required
                value={reqData.required_by}
                onChange={(e) => setReqData({ ...reqData, required_by: e.target.value })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              />
            </div>
          </div>

          <div className="flex justify-end space-x-2 pt-3 border-t border-slate-100">
            <Button type="button" variant="ghost" size="sm" onClick={() => setIsRequirementOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" size="sm">
              Save Requirement
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
