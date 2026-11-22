import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';
import { EmptyState } from '../components/ui/EmptyState';
import { FileCheck2, ShieldCheck, CheckCircle2, XCircle, Plus, ArrowRight } from 'lucide-react';
import { useToast } from '../context/ToastContext';
import { useNavigate } from 'react-router-dom';
import type { ProcurementOffer, Buyer, ProduceListing, Farmer } from '../types';

export const ProcurementPage: React.FC = () => {
  const [offers, setOffers] = useState<ProcurementOffer[]>([]);
  const [buyers, setBuyers] = useState<Buyer[]>([]);
  const [listings, setListings] = useState<ProduceListing[]>([]);
  const [farmers, setFarmers] = useState<Farmer[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreateOpen, setIsCreateOpen] = useState(false);

  // Form State
  const [formData, setFormData] = useState({
    buyer_id: '',
    listing_id: '',
    offered_price_per_kg: 19,
    quantity_kg: 500,
  });

  const toast = useToast();
  const navigate = useNavigate();

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setIsLoading(true);
      const [offersData, buyersData, listingsData, farmersData] = await Promise.all([
        api.getProcurementOffers(),
        api.getBuyers(),
        api.getListings(),
        api.getFarmers(),
      ]);
      setOffers(offersData);
      setBuyers(buyersData);
      setListings(listingsData);
      setFarmers(farmersData);

      if (buyersData.length > 0 && listingsData.length > 0) {
        setFormData((prev) => ({
          ...prev,
          buyer_id: buyersData[0].id,
          listing_id: listingsData[0].id,
        }));
      }
    } catch (err) {
      toast.error('Failed to load procurement offers');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateOffer = async (e: React.FormEvent) => {
    e.preventDefault();
    const listing = listings.find((l) => l.id === formData.listing_id);
    if (!listing) {
      toast.error('Listing not found');
      return;
    }

    try {
      await api.createProcurementOffer({
        buyer_id: formData.buyer_id,
        farmer_id: listing.farmer_id,
        listing_id: listing.id,
        offered_price_paise_per_kg: Math.round(Number(formData.offered_price_per_kg) * 100),
        quantity_grams: Number(formData.quantity_kg) * 1000,
      });
      toast.success('Procurement offer submitted', 'Offer sent to producer/FPO for review.');
      setIsCreateOpen(false);
      loadData();
    } catch (err: any) {
      toast.error('Offer submission failed', err?.response?.data?.message || 'Error creating offer');
    }
  };

  const handleAccept = async (offerId: string) => {
    try {
      await api.acceptProcurementOffer(offerId);
      toast.success('Procurement offer accepted!', 'Commitment contract locked. Ready for settlement.');
      loadData();
    } catch (err: any) {
      toast.error('Acceptance failed', err?.response?.data?.message || 'Error accepting offer');
    }
  };

  const handleReject = async (offerId: string) => {
    try {
      await api.rejectProcurementOffer(offerId);
      toast.info('Procurement offer rejected');
      loadData();
    } catch (err: any) {
      toast.error('Rejection failed', err?.response?.data?.message || 'Error rejecting offer');
    }
  };

  const buyerMap = new Map(buyers.map((b) => [b.id, b.organization || b.name]));
  const farmerMap = new Map(farmers.map((f) => [f.id, f.name]));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Procurement & CommitGuard Contracts</h1>
          <p className="text-xs text-slate-500 mt-1">
            Bilateral purchase offers, digital commitment verification, and transparent price locking.
          </p>
        </div>
        <Button
          size="sm"
          onClick={() => setIsCreateOpen(true)}
          leftIcon={<Plus className="w-4 h-4" />}
          disabled={listings.length === 0 || buyers.length === 0}
        >
          Create Buyer Offer
        </Button>
      </div>

      {/* CommitGuard Banner */}
      <div className="p-4 bg-emerald-50/70 border border-emerald-200/90 rounded-2xl flex items-start space-x-3 text-xs text-emerald-950">
        <ShieldCheck className="w-5 h-5 text-emerald-700 flex-shrink-0 mt-0.5" />
        <div>
          <span className="font-bold text-emerald-900">CommitGuard Protocol Active:</span>
          <p className="text-emerald-800 text-[11px] mt-0.5">
            Every accepted offer establishes an immutable commitment with fixed unit pricing in ₹/kg. Once accepted, proceeds automatically link into SettleTrack for escrow recording and disbursement.
          </p>
        </div>
      </div>

      {/* Offers Table */}
      <Card
        title="Procurement Offers & Bids"
        subtitle={`Showing ${offers.length} recorded bilateral purchase offers`}
      >
        {offers.length === 0 ? (
          <EmptyState
            title="No Active Procurement Offers"
            description="There are currently no outstanding purchase offers between buyers and farmers."
            actionText="Submit First Offer"
            onAction={() => setIsCreateOpen(true)}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider">
                  <th className="pb-3 px-3">Offer ID</th>
                  <th className="pb-3 px-3">Buyer Enterprise</th>
                  <th className="pb-3 px-3">Producer</th>
                  <th className="pb-3 px-3">Quantity</th>
                  <th className="pb-3 px-3">Offered Price</th>
                  <th className="pb-3 px-3">Total Value</th>
                  <th className="pb-3 px-3">Commitment Status</th>
                  <th className="pb-3 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {offers.map((offer) => {
                  const pricePerKg = (offer.offered_price_paise_per_kg / 100).toFixed(2);
                  const kg = offer.quantity_grams / 1000;
                  const totalVal = ((offer.quantity_grams / 1000) * (offer.offered_price_paise_per_kg / 100)).toFixed(0);

                  return (
                    <tr key={offer.id} className="hover:bg-slate-50/60">
                      <td className="py-3 px-3 font-mono text-[11px] text-slate-600">
                        {offer.id.slice(0, 8)}...
                      </td>
                      <td className="py-3 px-3 font-semibold text-slate-900">
                        {buyerMap.get(offer.buyer_id) || 'Buyer Enterprise'}
                      </td>
                      <td className="py-3 px-3 text-slate-700">
                        {farmerMap.get(offer.farmer_id) || 'Smallholder Producer'}
                      </td>
                      <td className="py-3 px-3 font-medium text-slate-800">
                        {kg} kg
                      </td>
                      <td className="py-3 px-3 font-semibold text-emerald-700">
                        ₹{pricePerKg} / kg
                      </td>
                      <td className="py-3 px-3 font-bold text-slate-900">
                        ₹{totalVal}
                      </td>
                      <td className="py-3 px-3">
                        <Badge
                          variant={
                            offer.status === 'accepted'
                              ? 'emerald'
                              : offer.status === 'rejected'
                              ? 'rose'
                              : 'amber'
                          }
                        >
                          {offer.status.toUpperCase()}
                        </Badge>
                      </td>
                      <td className="py-3 px-3 text-right">
                        {offer.status === 'pending' ? (
                          <div className="flex items-center justify-end space-x-1.5">
                            <Button
                              size="sm"
                              variant="secondary"
                              onClick={() => handleAccept(offer.id)}
                              leftIcon={<CheckCircle2 className="w-3.5 h-3.5 text-emerald-700" />}
                            >
                              Accept
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleReject(offer.id)}
                              className="text-rose-600 hover:text-rose-700"
                            >
                              Reject
                            </Button>
                          </div>
                        ) : offer.status === 'accepted' ? (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => navigate('/settlements')}
                            rightIcon={<ArrowRight className="w-3 h-3" />}
                          >
                            Go to Settlement
                          </Button>
                        ) : (
                          <span className="text-slate-400 text-xs italic">Closed</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Create Offer Modal */}
      <Modal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title="Submit Procurement Offer"
        description="Place a verified procurement bid on an available crop listing."
      >
        <form onSubmit={handleCreateOffer} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Purchaser Account</label>
            <select
              required
              value={formData.buyer_id}
              onChange={(e) => setFormData({ ...formData, buyer_id: e.target.value })}
              className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
            >
              {buyers.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.organization} ({b.name}) - {b.city}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Target Crop Listing</label>
            <select
              required
              value={formData.listing_id}
              onChange={(e) => setFormData({ ...formData, listing_id: e.target.value })}
              className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
            >
              {listings.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.commodity_code} - {l.quantity_grams / 1000}kg (Asking: ₹{l.asking_price_paise_per_kg / 100}/kg)
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Offered Price (₹/kg)</label>
              <input
                type="number"
                min="1"
                step="0.5"
                required
                value={formData.offered_price_per_kg}
                onChange={(e) => setFormData({ ...formData, offered_price_per_kg: Number(e.target.value) })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Procurement Quantity (kg)</label>
              <input
                type="number"
                min="10"
                required
                value={formData.quantity_kg}
                onChange={(e) => setFormData({ ...formData, quantity_kg: Number(e.target.value) })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              />
            </div>
          </div>

          <div className="flex justify-end space-x-2 pt-3 border-t border-slate-100">
            <Button type="button" variant="ghost" size="sm" onClick={() => setIsCreateOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" size="sm">
              Submit Offer
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
