import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Cloud, Eye, EyeOff, AlertCircle } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { LoadingButton } from '../components/LoadingButton';

export default function Login() {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { login, register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (mode === 'login') {
        await login(email, password);
      } else {
        await register(email, username, password);
      }
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const fillDemo = () => {
    setEmail('demo@cloudforge.io');
    setPassword('demo1234');
    setMode('login');
  };

  return (
    <div className="min-h-screen bg-dark-950 flex">
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-dark-900 via-dark-900 to-dark-950 border-r border-dark-800 flex-col justify-between p-12">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-accent-600 rounded-xl flex items-center justify-center shadow-lg shadow-primary-900/40">
            <Cloud className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="text-xl font-bold text-white tracking-wide">CloudForge</div>
            <div className="text-xs text-dark-500 tracking-widest uppercase">Infrastructure Platform</div>
          </div>
        </div>
        <div className="space-y-8">
          <div>
            <h2 className="text-4xl font-bold text-white leading-tight">Design Cloud<br /><span className="text-gradient">Infrastructure</span><br />Visually</h2>
            <p className="text-dark-400 mt-4 text-base leading-relaxed">Drag and drop AWS resources onto a canvas, connect them visually, and generate production-ready Terraform configurations automatically.</p>
          </div>
          <div className="space-y-4">
            {[
              { icon: '🎨', title: 'Visual Builder', desc: 'Design infrastructure with drag & drop' },
              { icon: '⚡', title: 'Terraform Generation', desc: 'Auto-generate valid IaC from your design' },
              { icon: '✅', title: 'Smart Validation', desc: 'Catch misconfigurations before deployment' },
            ].map((feature) => (
              <div key={feature.title} className="flex items-start gap-3">
                <div className="w-9 h-9 rounded-lg bg-dark-800 flex items-center justify-center text-base flex-shrink-0">{feature.icon}</div>
                <div>
                  <div className="text-sm font-semibold text-dark-100">{feature.title}</div>
                  <div className="text-xs text-dark-500">{feature.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="text-xs text-dark-600">Final Year Project — Cloud Infrastructure Automation Platform</div>
      </div>
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          <div className="flex items-center gap-3 mb-8 lg:hidden">
            <div className="w-9 h-9 bg-gradient-to-br from-primary-500 to-accent-600 rounded-xl flex items-center justify-center">
              <Cloud className="w-4 h-4 text-white" />
            </div>
            <div className="text-xl font-bold text-white">CloudForge</div>
          </div>
          <div className="card">
            <div className="flex rounded-lg bg-dark-800 p-1 mb-6">
              <button className={`flex-1 py-2 text-sm font-medium rounded-md transition-all ${mode === 'login' ? 'bg-dark-900 text-dark-100 shadow' : 'text-dark-500 hover:text-dark-300'}`} onClick={() => { setMode('login'); setError(''); }}>Sign In</button>
              <button className={`flex-1 py-2 text-sm font-medium rounded-md transition-all ${mode === 'register' ? 'bg-dark-900 text-dark-100 shadow' : 'text-dark-500 hover:text-dark-300'}`} onClick={() => { setMode('register'); setError(''); }}>Create Account</button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-4">
              {mode === 'register' && (
                <div>
                  <label className="label">Username</label>
                  <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="johndoe" className="input" required minLength={3} />
                </div>
              )}
              <div>
                <label className="label">Email Address</label>
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" className="input" required />
              </div>
              <div>
                <label className="label">Password</label>
                <div className="relative">
                  <input type={showPassword ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" className="input pr-10" required minLength={6} />
                  <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-500 hover:text-dark-300 transition-colors">
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              {error && (
                <div className="flex items-start gap-2 p-3 rounded-lg bg-red-900/20 border border-red-800/30 text-red-400 text-sm">
                  <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />{error}
                </div>
              )}
              <LoadingButton type="submit" loading={loading} className="w-full justify-center py-2.5">
                {mode === 'login' ? 'Sign In' : 'Create Account'}
              </LoadingButton>
              <button type="button" onClick={fillDemo} className="w-full btn-ghost justify-center text-xs border border-dark-700">
                Use Demo Account (demo@cloudforge.io / demo1234)
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
