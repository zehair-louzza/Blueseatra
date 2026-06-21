import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card } from '@/components/ui/card';
import { LanguageToggle } from '@/components/LanguageToggle';
import { toast } from 'sonner';
import { Waves, Loader2 } from 'lucide-react';

const AuthShell = ({ children }) => (
  <div className="flex min-h-screen items-center justify-center bg-background px-4">
    <div className="absolute right-4 top-4"><LanguageToggle /></div>
    <div className="w-full max-w-md">
      <Link to="/" className="mb-6 flex items-center justify-center gap-2">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground"><Waves className="h-5 w-5" /></div>
        <span className="font-display text-xl font-semibold tracking-tight text-primary">Blueseatra</span>
      </Link>
      <Card className="card-shadow border-0 p-6 sm:p-8">{children}</Card>
    </div>
  </div>
);

export function LoginPage() {
  const { t } = useTranslation();
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try { await login(email, password); navigate('/app'); }
    catch (err) { toast.error(err.response?.data?.detail || 'Login failed'); }
    finally { setLoading(false); }
  };

  return (
    <AuthShell>
      <h1 className="font-display text-2xl font-semibold tracking-tight">{t('auth.login_title')}</h1>
      <form onSubmit={submit} className="mt-6 space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="email">{t('auth.email')}</Label>
          <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} data-testid="login-email" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="password">{t('auth.password')}</Label>
          <Input id="password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} data-testid="login-password" />
        </div>
        <Button type="submit" className="w-full" disabled={loading} data-testid="login-submit">
          {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}{t('auth.login_btn')}
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-muted-foreground">
        {t('auth.no_account')} <Link to="/signup" className="font-medium text-accent" data-testid="go-signup">{t('auth.signup_link')}</Link>
      </p>
    </AuthShell>
  );
}

export function SignupPage() {
  const { t } = useTranslation();
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: '', company: '', email: '', password: '' });
  const [loading, setLoading] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try { await signup(form); navigate('/app'); }
    catch (err) { toast.error(err.response?.data?.detail || 'Signup failed'); }
    finally { setLoading(false); }
  };

  return (
    <AuthShell>
      <h1 className="font-display text-2xl font-semibold tracking-tight">{t('auth.signup_title')}</h1>
      <form onSubmit={submit} className="mt-6 space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="name">{t('auth.name')}</Label>
          <Input id="name" required value={form.name} onChange={set('name')} data-testid="signup-name" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="company">{t('auth.company')}</Label>
          <Input id="company" required value={form.company} onChange={set('company')} data-testid="signup-company" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="email">{t('auth.email')}</Label>
          <Input id="email" type="email" required value={form.email} onChange={set('email')} data-testid="signup-email" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="password">{t('auth.password')}</Label>
          <Input id="password" type="password" required minLength={6} value={form.password} onChange={set('password')} data-testid="signup-password" />
        </div>
        <Button type="submit" className="w-full" disabled={loading} data-testid="signup-submit">
          {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}{t('auth.signup_btn')}
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-muted-foreground">
        {t('auth.have_account')} <Link to="/login" className="font-medium text-accent" data-testid="go-login">{t('auth.login_link')}</Link>
      </p>
    </AuthShell>
  );
}
