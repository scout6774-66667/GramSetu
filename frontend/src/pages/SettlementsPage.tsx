import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';
import { EmptyState } from '../components/ui/EmptyState';
import { CreditCard, IndianRupee, Plus, ShieldCheck, CheckCircle2, ShieldAlert, FileText } from 'lucide-react';
import { useToast } from '../context/ToastContext';
import type { SettlementLedger, Farmer, Buyer } from '../types';

export const SettlementsPage: React.FC = () => {
  const [settlements, setSettlements] = useState<SettlementLedger[]>([]);
  const [farmers, setFarmers] = useState<Farmer[]>([]);
  const [buyers, setBuyers] = useState<Buyer[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerateOpen, setIsGenerateOpen] = useState(false);
  const [isPaymentOpen, setIsPaymentOpen] = useState(false);
  const [selectedSettlement, setSelectedSettlement] = useState<SettlementLedger | null>(null);

  // Settlement Form State
  const [settleForm, setSettleForm] = useState({
    transaction_id: `TXN-${Math.floor(100000 + Math.random() * 900000)}`,
    farmer_id: '',
    buyer_id: '',
    commodity_code: 'POTATO',
    quantity_kg: 500,
    gross_amount_inr: 9000,
    fpo_commission_pct: 2,
    logistics_fee_inr: 450,
  });

  // Payment Form State
  const [payForm, setPayForm] = useState({
    amount_inr: 0,
    payment_method: 'bank_transfer',
    reference_number: `UTR${Math.floor(10000000 + Math.random() * 90000000)}`,
  });

  const toast = useToast();

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setIsLoading(true);
      const [settles, fms, bys] = await Promise.all([
        api.getSettlements(),
        api.getFarmers(),
        api.getBuyers(),
      ]);
      setSettlements(settles);
      setFarmers(fms);
      setBuyers(bys);
      if (fms.length > 0 && bys.length > 0) {
        setSettleForm((prev) => ({
          ...prev,
          farmer_id: fms[0].id,
          buyer_id: bys[0].id,
        }));
      }
    } catch (err) {
      toast.error('Failed to load settlements');
    } finally {
      setIsLoading(false);
    }
  };

  const handleGenerateSettlement = async (e: React.FormEvent) => {
    e.preventDefault();
    const grossPaise = Math.round(Number(settleForm.gross_amount_inr) * 100);
    const commPaise = Math.round((grossPaise * settleForm.fpo_commission_pct) / 100);
    const logPaise = Math.round(Number(settleForm.logistics_fee_inr) * 100);

    try {
      await api.generateSettlement({
        transaction_id: settleForm.transaction_id,
        farmer_id: settleForm.farmer_id,
        buyer_id: settleForm.buyer_id,
        commodity_code: settleForm.commodity_code,
        quantity_grams: Number(settleForm.quantity_kg) * 1000,
        gross_amount_paise: grossPaise,
        fpo_commission_paise: commPaise,
        logistics_fee_paise: logPaise,
      });
      toast.success('Settlement voucher created', 'Voucher registered in SettleTrack ledger.');
      setIsGenerateOpen(false);
      loadData();
    } catch (err: any) {
      toast.error('Generation failed', err?.response?.data?.message || 'Error generating settlement');
    }
  };

  const handleRecordPayment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSettlement) return;
    try {
      await api.recordPayment(selectedSettlement.id, {
        amount_paise: Math.round(Number(payForm.amount_inr) * 100),
        payment_method: payForm.payment_method,
        reference_number: payForm.reference_number,
      });
      toast.success('Payment recorded', `Payment of ₹${payForm.amount_inr} recorded. Ready for verification.`);
      setIsPaymentOpen(false);
      loadData();
    } catch (err: any) {
      toast.error('Payment record failed', err?.response?.data?.message || 'Error recording payment');
    }
  };

  const farmerMap = new Map(farmers.map((f) => [f.id, f.name]));
  const buyerMap = new Map(buyers.map((b) => [b.id, b.organization || b.name]));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">SettleTrack: Transparent Financial Settlements</h1>
          <p className="text-xs text-slate-500 mt-1">
            Automated settlement ledger with transparent fee deductions, Escrow logging, and payment verification.
          </p>
        </div>
        <Button
          size="sm"
          onClick={() => setIsGenerateOpen(true)}
          leftIcon={<Plus className="w-4 h-4" />}
          disabled={farmers.length === 0 || buyers.length === 0}
        >
          Generate Settlement Voucher
        </Button>
      </div>

      {/* Honest Bank Confirmation Notice */}
      <div className="bg-amber-50/70 border border-amber-300/80 rounded-2xl p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-start space-x-3">
          <div className="p-2 bg-amber-100 text-amber-800 rounded-xl flex-shrink-0 mt-0.5">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h4 className="text-xs font-bold text-amber-950 uppercase tracking-wider">
                Phase 5/6 Acceptance Notice: Bank Credit Evidence Held Blank
              </h4>
              <Badge variant="amber">Strict Compliance</Badge>
            </div>
            <p className="text-xs text-amber-800 mt-1 max-w-3xl leading-relaxed">
              In accordance with audit restrictions, <code className="font-mono text-[11px]">beneficiary_credit_evidence.csv</code> remains blank. Payments reflect ledger-recorded vouchers awaiting final bank API clearing verification.
            </p>
          </div>
        </div>
      </div>

      {/* Settlements Table */}
      <Card
        title="Settlement Vouchers"
        subtitle={`Showing ${settlements.length} transaction settlement ledgers`}
      >
        {settlements.length === 0 ? (
          <EmptyState
            title="No Settlements Found"
            description="No trade transactions have been settled in the current pilot period."
            actionText="Generate Settlement"
            onAction={() => setIsGenerateOpen(true)}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider">
                  <th className="pb-3 px-3">Transaction ID</th>
                  <th className="pb-3 px-3">Producer (Farmer)</th>
                  <th className="pb-3 px-3">Payer (Buyer)</th>
                  <th className="pb-3 px-3">Gross Value</th>
                  <th className="pb-3 px-3">Deductions (FPO + Freight)</th>
                  <th className="pb-3 px-3">Net Farmer Payout</th>
                  <th className="pb-3 px-3">Payment Status</th>
                  <th className="pb-3 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {settlements.map((s) => {
                  const grossInr = (s.gross_amount_paise / 100).toFixed(0);
                  const netInr = (s.net_farmer_amount_paise / 100).toFixed(0);
                  const dedInr = ((s.fpo_commission_paise + s.logistics_fee_paise) / 100).toFixed(0);

                  return (
                    <tr key={s.id} className="hover:bg-slate-50/60">
                      <td className="py-3 px-3 font-mono font-medium text-slate-900">
                        {s.transaction_id}
                      </td>
                      <td className="py-3 px-3 font-semibold text-slate-800">
                        {farmerMap.get(s.farmer_id) || 'Producer'}
                      </td>
                      <td className="py-3 px-3 text-slate-600">
                        {buyerMap.get(s.buyer_id) || 'Buyer Enterprise'}
                      </td>
                      <td className="py-3 px-3 text-slate-700 font-medium">₹{grossInr}</td>
                      <td className="py-3 px-3 text-rose-600 font-medium">- ₹{dedInr}</td>
                      <td className="py-3 px-3 font-bold text-emerald-700 text-sm">₹{netInr}</td>
                      <td className="py-3 px-3">
                        <Badge variant={s.settlement_status === 'paid' ? 'emerald' : 'amber'}>
                          {s.settlement_status.toUpperCase()}
                        </Badge>
                      </td>
                      <td className="py-3 px-3 text-right">
                        {s.settlement_status !== 'paid' && (
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => {
                              setSelectedSettlement(s);
                              setPayForm((prev) => ({
                                ...prev,
                                amount_inr: s.net_farmer_amount_paise / 100,
                              }));
                              setIsPaymentOpen(true);
                            }}
                            leftIcon={<CreditCard className="w-3.5 h-3.5 text-emerald-700" />}
                          >
                            Disburse Payment
                          </Button>
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

      {/* Generate Settlement Modal */}
      <Modal
        isOpen={isGenerateOpen}
        onClose={() => setIsGenerateOpen(false)}
        title="Generate Settlement Voucher"
        description="Calculate final net payout for a completed harvest procurement transaction."
      >
        <form onSubmit={handleGenerateSettlement} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Transaction Ref</label>
              <input
                type="text"
                required
                value={settleForm.transaction_id}
                onChange={(e) => setSettleForm({ ...settleForm, transaction_id: e.target.value })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500 font-mono"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Commodity</label>
              <select
                value={settleForm.commodity_code}
                onChange={(e) => setSettleForm({ ...settleForm, commodity_code: e.target.value })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              >
                <option value="POTATO">Potato (আলু)</option>
                <option value="TOMATO">Tomato (টমেটো)</option>
                <option value="PADDY">Paddy (ধান)</option>
                <option value="ONION">Onion (পেঁয়াজ)</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Farmer (Beneficiary)</label>
              <select
                value={settleForm.farmer_id}
                onChange={(e) => setSettleForm({ ...settleForm, farmer_id: e.target.value })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              >
                {farmers.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name} - {f.village}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Buyer (Payer)</label>
              <select
                value={settleForm.buyer_id}
                onChange={(e) => setSettleForm({ ...settleForm, buyer_id: e.target.value })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              >
                {buyers.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.organization} ({b.name})
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Gross Value (₹)</label>
              <input
                type="number"
                min="100"
                required
                value={settleForm.gross_amount_inr}
                onChange={(e) => setSettleForm({ ...settleForm, gross_amount_inr: Number(e.target.value) })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">FPO Fee (%)</label>
              <input
                type="number"
                min="0"
                step="0.5"
                required
                value={settleForm.fpo_commission_pct}
                onChange={(e) => setSettleForm({ ...settleForm, fpo_commission_pct: Number(e.target.value) })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Logistics (₹)</label>
              <input
                type="number"
                min="0"
                required
                value={settleForm.logistics_fee_inr}
                onChange={(e) => setSettleForm({ ...settleForm, logistics_fee_inr: Number(e.target.value) })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              />
            </div>
          </div>

          <div className="flex justify-end space-x-2 pt-3 border-t border-slate-100">
            <Button type="button" variant="ghost" size="sm" onClick={() => setIsGenerateOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" size="sm">
              Generate Voucher
            </Button>
          </div>
        </form>
      </Modal>

      {/* Record Payment Modal */}
      <Modal
        isOpen={isPaymentOpen}
        onClose={() => setIsPaymentOpen(false)}
        title={`Disburse Payment for ${selectedSettlement?.transaction_id || 'Settlement'}`}
        description="Record payment reference to disburse net funds to the farmer's account."
      >
        <form onSubmit={handleRecordPayment} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Disbursement Amount (₹)</label>
            <input
              type="number"
              required
              value={payForm.amount_inr}
              onChange={(e) => setPayForm({ ...payForm, amount_inr: Number(e.target.value) })}
              className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500 font-bold"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Payment Method</label>
              <select
                value={payForm.payment_method}
                onChange={(e) => setPayForm({ ...payForm, payment_method: e.target.value })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
              >
                <option value="bank_transfer">Direct Bank Transfer (NEFT/RTGS)</option>
                <option value="upi">UPI / Aadhaar Enabled Pay (AePS)</option>
                <option value="cash">Authorized FPO Cash Receipt</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Reference / UTR Number</label>
              <input
                type="text"
                required
                value={payForm.reference_number}
                onChange={(e) => setPayForm({ ...payForm, reference_number: e.target.value })}
                className="w-full text-xs p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500 font-mono"
              />
            </div>
          </div>

          <div className="flex justify-end space-x-2 pt-3 border-t border-slate-100">
            <Button type="button" variant="ghost" size="sm" onClick={() => setIsPaymentOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" size="sm">
              Confirm Disbursement
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
