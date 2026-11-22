import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import {
  Sprout,
  Lock,
  User,
  Eye,
  EyeOff,
  ArrowRight,
  ShieldCheck,
  Truck,
  Sparkles,
  Info,
  Building2,
  Users,
} from 'lucide-react';
import { Button } from '../components/ui/Button';

export const LoginPage: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showForgotModal, setShowForgotModal] = useState(false);

  const { login } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const location = useLocation();

  const from = (location.state as any)?.from?.pathname || '/';

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setErrorMessage('Please enter both username and password.');
      return;
    }

    try {
      setIsLoading(true);
      setErrorMessage(null);
      await login(username.trim(), password);
      toast.success('Welcome back to GramSetu!', `Logged in successfully.`);
      navigate(from, { replace: true });
    } catch (err: any) {
      const msg =
        err?.response?.data?.message ||
        (err?.response?.status === 401
          ? 'Invalid username or password. Please verify your credentials.'
          : 'Unable to connect to the authentication server.');
      setErrorMessage(msg);
      toast.error('Authentication failed', msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleQuickFill = (demoUser: string, demoPass: string) => {
    setUsername(demoUser);
    setPassword(demoPass);
    setErrorMessage(null);
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        {/* Brand Logo */}
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-emerald-700 text-white shadow-md shadow-emerald-700/20 mb-4">
          <Sprout className="w-8 h-8 text-emerald-100" />
        </div>
        <h2 className="text-3xl font-bold tracking-tight text-slate-900">GramSetu</h2>
        <p className="mt-1 text-xs text-slate-600 font-medium">
          AI-Powered Smart Rural Food Supply Chain Management
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-lg">
        <div className="bg-white py-8 px-6 shadow-sm border border-slate-200/80 sm:rounded-3xl sm:px-10">
          <div className="mb-6 pb-5 border-b border-slate-100 text-center sm:text-left">
            <h3 className="text-lg font-bold text-slate-900">Sign in to your account</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Enter your credentials to access the producer and supply chain portal.
            </p>
          </div>

          {/* Error Banner */}
          {errorMessage && (
            <div className="mb-5 p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-start space-x-2">
              <span className="font-semibold block">{errorMessage}</span>
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-4">
            {/* Username field */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Username or Account ID
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <User className="w-4 h-4" />
                </div>
                <input
                  type="text"
                  required
                  placeholder="e.g. fpo_admin or farmer_subhash"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="block w-full text-xs pl-9 pr-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-600 focus:bg-white transition-all text-slate-900"
                />
              </div>
            </div>

            {/* Password field */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="block text-xs font-semibold text-slate-700">
                  Password
                </label>
                <button
                  type="button"
                  onClick={() => setShowForgotModal(true)}
                  className="text-[11px] font-medium text-emerald-700 hover:text-emerald-800 transition-colors"
                >
                  Forgot password?
                </button>
              </div>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="block w-full text-xs pl-9 pr-10 py-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-600 focus:bg-white transition-all text-slate-900"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Remember Me */}
            <div className="flex items-center justify-between pt-1">
              <label className="flex items-center space-x-2 text-xs text-slate-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  className="w-4 h-4 text-emerald-700 rounded border-slate-300 focus:ring-emerald-500"
                />
                <span>Remember this workstation</span>
              </label>
            </div>

            {/* Submit Button */}
            <Button
              type="submit"
              size="lg"
              isLoading={isLoading}
              className="w-full justify-center mt-2 shadow-sm"
              rightIcon={<ArrowRight className="w-4 h-4" />}
            >
              Sign In to Command Center
            </Button>
          </form>

          {/* Quick Demo Credentials for Evaluation & Pilot */}
          <div className="mt-6 pt-5 border-t border-slate-100">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-2.5 text-center">
              Quick Role Sign-In (Pilot & Audit Accounts)
            </span>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => handleQuickFill('fpo_admin', 'fpo_admin')}
                className="p-2 rounded-xl bg-slate-50 hover:bg-emerald-50 border border-slate-200 hover:border-emerald-300 text-left transition-all group"
              >
                <div className="font-semibold text-xs text-slate-900 group-hover:text-emerald-800">
                  FPO Executive
                </div>
                <div className="text-[10px] text-slate-400 font-mono">fpo_admin</div>
              </button>

              <button
                type="button"
                onClick={() => handleQuickFill('farmer_subhash', 'farmer_subhash')}
                className="p-2 rounded-xl bg-slate-50 hover:bg-emerald-50 border border-slate-200 hover:border-emerald-300 text-left transition-all group"
              >
                <div className="font-semibold text-xs text-slate-900 group-hover:text-emerald-800">
                  Producer (Farmer)
                </div>
                <div className="text-[10px] text-slate-400 font-mono">farmer_subhash</div>
              </button>

              <button
                type="button"
                onClick={() => handleQuickFill('buyer_apex', 'buyer_apex')}
                className="p-2 rounded-xl bg-slate-50 hover:bg-emerald-50 border border-slate-200 hover:border-emerald-300 text-left transition-all group"
              >
                <div className="font-semibold text-xs text-slate-900 group-hover:text-emerald-800">
                  Institutional Buyer
                </div>
                <div className="text-[10px] text-slate-400 font-mono">buyer_apex</div>
              </button>

              <button
                type="button"
                onClick={() => handleQuickFill('driver_mandal', 'driver_mandal')}
                className="p-2 rounded-xl bg-slate-50 hover:bg-emerald-50 border border-slate-200 hover:border-emerald-300 text-left transition-all group"
              >
                <div className="font-semibold text-xs text-slate-900 group-hover:text-emerald-800">
                  Transporter Fleet
                </div>
                <div className="text-[10px] text-slate-400 font-mono">driver_mandal</div>
              </button>
            </div>
          </div>
        </div>

        {/* Security & Pilot Notice */}
        <div className="mt-6 text-center text-xs text-slate-500 space-y-1">
          <div className="flex items-center justify-center space-x-1">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
            <span>PBKDF2-HMAC-SHA256 Salted Credentials & Signed JWT Tokens</span>
          </div>
          <p className="text-[11px] text-slate-400">
            Pilot Corridor: West Bengal Rural Agri-Distribution Network
          </p>
        </div>
      </div>

      {/* Forgot Password Modal */}
      {showForgotModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div
            className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs"
            onClick={() => setShowForgotModal(false)}
          />
          <div className="flex min-h-full items-center justify-center p-4">
            <div className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl border border-slate-100 z-10 text-left">
              <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-700 flex items-center justify-center mb-3">
                <Info className="w-5 h-5" />
              </div>
              <h3 className="font-bold text-slate-900 text-base">Credential Reset</h3>
              <p className="text-xs text-slate-600 mt-2 leading-relaxed">
                For security in the rural pilot deployment, smallholder and buyer credentials are authenticated via FPO administrative oversight. Please contact your FPO coordinator or system administrator to reset your account password.
              </p>
              <div className="mt-5 flex justify-end">
                <Button size="sm" onClick={() => setShowForgotModal(false)}>
                  Understood
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
