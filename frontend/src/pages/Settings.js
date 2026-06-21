import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { api , apiError } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Spinner } from '@/components/Spinner';
import { toast } from 'sonner';
import { Save, Loader2, KeyRound, CheckCircle2, Building2, Sparkles } from 'lucide-react';

function AiSettings({ canManage }) {
  const { t } = useTranslation();
  const [providerModels, setProviderModels] = useState({});
  const [form, setForm] = useState(null);
  const [keySet, setKeySet] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get('/settings/integrations').then((r) => {
      const s = r.data.settings;
      setProviderModels(r.data.provider_models);
      setForm({ ai_provider: s.ai_provider || 'emergent', ai_model: s.ai_model || '', ai_key: '', n8n_webhook_url: s.n8n_webhook_url || '' });
      setKeySet(!!s.ai_key_set);
    });
  }, []);

  const save = async () => {
    setBusy(true);
    try { await api.put('/settings/integrations', form); toast.success(t('settings.saved')); if (form.ai_key) setKeySet(true); setForm({ ...form, ai_key: '' }); }
    catch (err) { toast.error(apiError(err, 'Failed')); }
    finally { setBusy(false); }
  };

  if (!form) return <Spinner />;
  const models = providerModels[form.ai_provider] || [];
  return (
    <Card className="card-shadow border-0 p-6">
      <div className="space-y-5">
        <div className="space-y-1.5">
          <Label>{t('settings.ai_provider')}</Label>
          <Select value={form.ai_provider} onValueChange={(v) => setForm({ ...form, ai_provider: v, ai_model: (providerModels[v] || [])[0] || '' })} disabled={!canManage}>
            <SelectTrigger data-testid="ai-provider-select"><SelectValue /></SelectTrigger>
            <SelectContent>{Object.keys(providerModels).map((p) => <SelectItem key={p} value={p}>{p === 'emergent' ? 'Built-in (Emergent)' : p}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>{t('settings.ai_model')}</Label>
          <Select value={form.ai_model} onValueChange={(v) => setForm({ ...form, ai_model: v })} disabled={!canManage}>
            <SelectTrigger data-testid="ai-model-select"><SelectValue placeholder="..." /></SelectTrigger>
            <SelectContent>{models.map((m) => <SelectItem key={m} value={m}>{m}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label className="flex items-center gap-1.5"><KeyRound className="h-3.5 w-3.5" />{t('settings.ai_key')}</Label>
          <Input type="password" placeholder={keySet ? '\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022' : ''} value={form.ai_key} onChange={(e) => setForm({ ...form, ai_key: e.target.value })} disabled={!canManage} data-testid="ai-key-input" />
          <p className="text-xs text-muted-foreground">{t('settings.ai_key_hint')}</p>
          {keySet && <p className="flex items-center gap-1 text-xs text-emerald-700"><CheckCircle2 className="h-3.5 w-3.5" />{t('settings.key_set')}</p>}
        </div>
        <div className="space-y-1.5">
          <Label>{t('settings.n8n')}</Label>
          <Input className="font-mono text-xs" placeholder="https://automation.example.com/webhook/..." value={form.n8n_webhook_url || ''} onChange={(e) => setForm({ ...form, n8n_webhook_url: e.target.value })} disabled={!canManage} data-testid="n8n-url-input" />
          <p className="text-xs text-muted-foreground">{t('settings.n8n_hint')}</p>
        </div>
        {canManage && <Button onClick={save} disabled={busy} className="gap-2" data-testid="save-settings-button">{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}{t('settings.save')}</Button>}
      </div>
    </Card>
  );
}

const FIELDS = [
  ['company_name', 'name'], ['subtitle', 'subtitle'], ['address_line1', 'address1'], ['address_line2', 'address2'],
  ['country', 'country'], ['phone', 'phone'], ['email', 'email'], ['siret', 'siret'], ['tva_intra', 'tva'],
  ['capital', 'capital'], ['ape', 'ape'], ['assurance', 'assurance'], ['iban', 'iban'], ['validity', 'validity'],
];

function CompanyProfile({ canManage }) {
  const { t } = useTranslation();
  const [form, setForm] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.get('/company-profile').then((r) => setForm({ payment_terms: '', acceptance_text: '', ...r.data })); }, []);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const save = async () => {
    setBusy(true);
    try { await api.put('/company-profile', form); toast.success(t('settings.company.saved')); }
    catch (err) { toast.error(apiError(err, 'Failed')); }
    finally { setBusy(false); }
  };

  if (!form) return <Spinner />;
  return (
    <Card className="card-shadow border-0 p-6">
      <p className="mb-5 text-sm text-muted-foreground">{t('settings.company.intro')}</p>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {FIELDS.map(([key, label]) => (
          <div key={key} className="space-y-1.5">
            <Label>{t(`settings.company.${label}`)}</Label>
            <Input value={form[key] || ''} onChange={set(key)} disabled={!canManage} data-testid={`company-${key}`} />
          </div>
        ))}
      </div>
      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label>{t('settings.company.payment_terms')}</Label>
          <Textarea rows={4} value={form.payment_terms || ''} onChange={set('payment_terms')} disabled={!canManage} data-testid="company-payment-terms" placeholder={'30% \u00e0 la signature\n40% en cours de travaux\n30% \u00e0 la livraison'} />
        </div>
        <div className="space-y-1.5">
          <Label>{t('settings.company.acceptance')}</Label>
          <Textarea rows={4} value={form.acceptance_text || ''} onChange={set('acceptance_text')} disabled={!canManage} data-testid="company-acceptance" placeholder={'\u00ab Devis re\u00e7u avant l\u2019ex\u00e9cution des travaux. Bon pour accord. \u00bb'} />
        </div>
      </div>
      {canManage && <Button onClick={save} disabled={busy} className="mt-5 gap-2" data-testid="save-company-button">{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}{t('settings.save')}</Button>}
    </Card>
  );
}

export default function Settings() {
  const { t } = useTranslation();
  const { tenant } = useAuth();
  const canManage = ['owner', 'admin'].includes(tenant?.role);
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="font-display text-2xl font-semibold tracking-tight">{t('settings.title')}</h1>
      <Tabs defaultValue="ai" className="mt-5">
        <TabsList>
          <TabsTrigger value="ai" className="gap-1.5" data-testid="tab-ai"><Sparkles className="h-4 w-4" />{t('settings.tab_ai')}</TabsTrigger>
          <TabsTrigger value="company" className="gap-1.5" data-testid="tab-company"><Building2 className="h-4 w-4" />{t('settings.tab_company')}</TabsTrigger>
        </TabsList>
        <TabsContent value="ai" className="mt-4"><AiSettings canManage={canManage} /></TabsContent>
        <TabsContent value="company" className="mt-4"><CompanyProfile canManage={canManage} /></TabsContent>
      </Tabs>
    </div>
  );
}
