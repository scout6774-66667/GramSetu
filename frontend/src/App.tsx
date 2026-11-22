import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import { AppLayout } from './components/layout/AppLayout';

// Auth Pages
import { LoginPage } from './pages/LoginPage';

// Feature Pages
import { DashboardPage } from './pages/DashboardPage';
import { SystemReadinessPage } from './pages/SystemReadinessPage';
import { FarmersPage } from './pages/FarmersPage';
import { BuyersPage } from './pages/BuyersPage';
import { ListingsPage } from './pages/ListingsPage';
import { ProcurementPage } from './pages/ProcurementPage';
import { MarketIntelPage } from './pages/MarketIntelPage';
import { DemandSyncPage } from './pages/DemandSyncPage';
import { LogisticsPage } from './pages/LogisticsPage';
import { StoragePage } from './pages/StoragePage';
import { BatchTracePage } from './pages/BatchTracePage';
import { SettlementsPage } from './pages/SettlementsPage';
import { RiskWatchPage } from './pages/RiskWatchPage';
import { RecoveryOptPage } from './pages/RecoveryOptPage';
import { VoiceAssistantPage } from './pages/VoiceAssistantPage';

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            {/* Standalone Login Route */}
            <Route path="/login" element={<LoginPage />} />

            {/* Application Main Layout */}
            <Route element={<AppLayout />}>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/readiness" element={<SystemReadinessPage />} />
              <Route path="/farmers" element={<FarmersPage />} />
              <Route path="/buyers" element={<BuyersPage />} />
              <Route path="/listings" element={<ListingsPage />} />
              <Route path="/procurement" element={<ProcurementPage />} />
              <Route path="/market" element={<MarketIntelPage />} />
              <Route path="/demandsync" element={<DemandSyncPage />} />
              <Route path="/logistics" element={<LogisticsPage />} />
              <Route path="/storage" element={<StoragePage />} />
              <Route path="/traceability" element={<BatchTracePage />} />
              <Route path="/settlements" element={<SettlementsPage />} />
              <Route path="/risks" element={<RiskWatchPage />} />
              <Route path="/recovery" element={<RecoveryOptPage />} />
              <Route path="/voice" element={<VoiceAssistantPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </AuthProvider>
  );
};

export default App;
