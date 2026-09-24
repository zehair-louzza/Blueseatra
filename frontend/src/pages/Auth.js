import { apiError } from '@/lib/api';
import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { LanguageToggle } from '@/components/LanguageToggle';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';
import { BrandLogo } from '@/components/BrandLogo';

const AuthShell = ({ children }) => {
  const { t } = useTranslation();
  return (
    <div className="grid min-h-[100dvh] bg-background lg:grid-cols-2">
      <aside className="relative hidden overflow-hidden bg-primary p-12 text-primary-foreground lg:flex lg:flex-col lg:justify-between">
        <div aria-hidden className="pointer-events-none absolute -right-32 -top-32 h-96 w-96 rounded-full bg-[hsl(var(--brand-teal)/0.25)] blur-3xl" />
        <img aria-hidden src="/brand/blueseatra-mark.png" alt="" width={512} height={512} className="pointer-events-none absolute -bottom-20 -right-20 h-[26rem] w-[26rem] object-contain opacity-[0.10]" />
        <div className="relative inline-flex w-fit rounded-xl bg-white px-4 py-2.5">
          <BrandLogo to="/" imgClassName="h-8 max-w-[170px]" />
        </div>
        <div className="relative">
          <p className="max-w-[20ch] font-display text-4xl font-semibold leading-tight">{t('lp.hero_title')}</p>
          <ul className="mt-10 space-y-4 text-[15px] text-primary-foreground/85">
            {['blue', 'sea', 'tra'].map((k) => (
              <li key={k} className="flex gap-4">
                <span className="w-14 shrink-0 font-display font-bold tracking-tight text-[hsl(var(--brand-teal))]">{k.toUpperCase()}</span>
                <span>{t(`lp.${k}_t`)}</span>
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-sm text-primary-foreground/60">© {new Date().getFullYear()} Blueseatra</p>
      </aside>
      <div className="relative flex items-center justify-center px-4 py-12">
        <div className="absolute right-4 top-4"><LanguageToggle /></div>
        <div className="w-full max-w-[400px]">
          <div className="mb-8 lg:hidden">
            <BrandLogo to="/" imgClassName="h-10 max-w-[220px]" />
          </div>
          {children}
        </div>
      </div>
    </div>
  );
};

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
    catch (err) { toast.error(apiError(err, 'Login failed')); }
    finally { setLoading(false); }
  };

  return (
    <AuthShell>
      <h1 className="font-display text-3xl font-semibold">{t('auth.login_title')}</h1>
      <form onSubmit={submit} className="mt-8 space-y-5">
        <div className="space-y-1.5">
          <Label htmlFor="email">{t('auth.email')}</Label>
          <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} data-testid="login-email" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="password">{t('auth.password')}</Label>
          <Input id="password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} data-testid="login-password" />
        </div>
        <Button type="submit" size="lg" className="w-full" disabled={loading} data-testid="login-submit">
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
    catch (err) { toast.error(apiError(err, 'Signup failed')); }
    finally { setLoading(false); }
  };

  return (
    <AuthShell>
      <h1 className="font-display text-3xl font-semibold">{t('auth.signup_title')}</h1>
      <form onSubmit={submit} className="mt-8 space-y-5">
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
        <Button type="submit" size="lg" className="w-full" disabled={loading} data-testid="signup-submit">
          {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}{t('auth.signup_btn')}
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-muted-foreground">
        {t('auth.have_account')} <Link to="/login" className="font-medium text-accent" data-testid="go-login">{t('auth.login_link')}</Link>
      </p>
    </AuthShell>
  );
}
