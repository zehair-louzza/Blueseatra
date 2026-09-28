import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { api , apiError } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import DonneesPersonnelles from '@/components/DonneesPersonnelles';
import { ShieldCheck } from 'lucide-react';
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

// « mistral:<id> » sous le moteur intégré = API Mistral interrogée par l'agent Hermès (#88).
function nomModele(m) {
  if (!m.startsWith('mistral:')) return m;
  const id = m.slice(8).replace(/-latest$/, '').replace(/^mistral-/, '');
  return `Mistral ${id.charAt(0).toUpperCase()}${id.slice(1)} (via Hermès)`;
}

function AiSettings({ canManage }) {
  const { t } = useTranslation();
  const [providerModels, setProviderModels] = useState({});
  const [ocrModelChoices, setOcrModelChoices] = useState({});
  const [form, setForm] = useState(null);
  const [keySet, setKeySet] = useState(false);
  const [apercu, setApercu] = useState(null);
  const [labels, setLabels] = useState({});
  const [clePlateforme, setClePlateforme] = useState(false);
  const [test, setTest] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get('/settings/integrations').then((r) => {
      const s = r.data.settings;
      setProviderModels(r.data.provider_models);
      setLabels(r.data.provider_labels || {});
      setClePlateforme(!!r.data.mistral_cle_plateforme);
      setApercu(s.ai_key_apercu || null);
      setOcrModelChoices(r.data.ocr_model_choices || {});
      setForm({
        ai_provider: s.ai_provider || 'hermes', ai_model: s.ai_model || '', ai_key: '',
        n8n_webhook_url: s.n8n_webhook_url || '', ocr_model_preference: s.ocr_model_preference || 'auto',
      });
      setKeySet(!!s.ai_key_set);
    });
  }, []);

  const save = async () => {
    setBusy(true);
    try {
      await api.put('/settings/integrations', form); toast.success(t('settings.saved'));
      const r = await api.get('/settings/integrations');
      setKeySet(!!r.data.settings.ai_key_set); setApercu(r.data.settings.ai_key_apercu || null);
      setForm({ ...form, ai_key: '', effacer_cle: false }); setTest(null);
    }
    catch (err) { toast.error(apiError(err, 'Failed')); }
    finally { setBusy(false); }
  };

  const tester = async () => {
    setTest({ enCours: true });
    try { const { data } = await api.post('/settings/integrations/tester'); setTest(data); }
    catch (err) { setTest({ ok: false, message: apiError(err, 'Échec du test') }); }
  };

  if (!form) return <Spinner />;
  const mistralHermes = form.ai_provider === 'hermes' && (form.ai_model || '').startsWith('mistral:');
  const mistral = form.ai_provider === 'mistral';
  const models = providerModels[form.ai_provider] || [];
  return (
    <Card className="card-shadow border-0 p-6">
      <div className="space-y-5">
        <div className="space-y-1.5">
          <Label>{t('settings.ai_provider')}</Label>
          <Select value={form.ai_provider} onValueChange={(v) => setForm({ ...form, ai_provider: v, ai_model: (providerModels[v] || [])[0] || '' })} disabled={!canManage}>
            <SelectTrigger data-testid="ai-provider-select"><SelectValue /></SelectTrigger>
            <SelectContent>{Object.keys(providerModels).map((p) => <SelectItem key={p} value={p}>{labels[p] || p}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>{t('settings.ai_model')}</Label>
          <Select value={form.ai_model} onValueChange={(v) => setForm({ ...form, ai_model: v })} disabled={!canManage}>
            <SelectTrigger data-testid="ai-model-select"><SelectValue placeholder="..." /></SelectTrigger>
            <SelectContent>{models.map((m) => <SelectItem key={m} value={m}>{nomModele(m)}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label className="flex items-center gap-1.5"><KeyRound className="h-3.5 w-3.5" />{t('settings.ai_key')}</Label>
          {!mistralHermes && <Input type="password" autoComplete="off" placeholder={keySet ? (apercu || '\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022') : (mistral ? t('settings.mistral_placeholder') : '')} value={form.ai_key} onChange={(e) => setForm({ ...form, ai_key: e.target.value })} disabled={!canManage} data-testid="ai-key-input" />}
          {!mistralHermes && <p className="text-xs text-muted-foreground">{mistral ? t('settings.mistral_hint') : t('settings.ai_key_hint')}</p>}
          {keySet && (
            <div className="flex flex-wrap items-center gap-3 text-xs">
              <span className="flex items-center gap-1 text-emerald-700"><CheckCircle2 className="h-3.5 w-3.5" />{t('settings.key_set')}{apercu ? ` (${apercu})` : ''}</span>
              {canManage && <button type="button" className="text-muted-foreground underline" onClick={() => setForm({ ...form, ai_key: '', effacer_cle: true })}>{t('settings.key_remove')}</button>}
              {form.effacer_cle && <span className="text-amber-700">{t('settings.key_remove_pending')}</span>}
            </div>
          )}
          {mistral && !keySet && clePlateforme && <p className="text-xs text-muted-foreground">{t('settings.mistral_platform')}</p>}
          {mistralHermes && <p className="text-xs text-muted-foreground">{t('settings.mistral_hermes_hint')}</p>}
          {(mistral || mistralHermes) && canManage && (
            <div className="flex flex-wrap items-center gap-3 pt-1">
              <Button type="button" variant="outline" size="sm" onClick={tester} disabled={test?.enCours} data-testid="ai-test-button">
                {test?.enCours ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <ShieldCheck className="mr-1 h-4 w-4" />}{t('settings.test_connection')}
              </Button>
              {test && !test.enCours && <span className={`text-xs ${test.ok ? 'text-emerald-700' : 'text-destructive'}`} data-testid="ai-test-result">{test.message}</span>}
            </div>
          )}
        </div>
        <div className="space-y-1.5">
          <Label>{t('settings.n8n')}</Label>
          <Input className="font-mono text-xs" placeholder="https://automation.example.com/webhook/..." value={form.n8n_webhook_url || ''} onChange={(e) => setForm({ ...form, n8n_webhook_url: e.target.value })} disabled={!canManage} data-testid="n8n-url-input" />
          <p className="text-xs text-muted-foreground">{t('settings.n8n_hint')}</p>
        </div>
        <div className="space-y-1.5">
          <Label>{t('settings.ocr_model_preference')}</Label>
          <Select value={form.ocr_model_preference} onValueChange={(v) => setForm({ ...form, ocr_model_preference: v })} disabled={!canManage}>
            <SelectTrigger data-testid="ocr-model-preference-select"><SelectValue /></SelectTrigger>
            <SelectContent>{Object.entries(ocrModelChoices).map(([key, label]) => <SelectItem key={key} value={key}>{label}</SelectItem>)}</SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">{t('settings.ocr_model_preference_hint')}</p>
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
      <div className="mb-5 flex items-start gap-4">
        <div className="flex h-20 w-36 items-center justify-center overflow-hidden rounded-md border border-dashed bg-muted/30">
          {(form.logo_b64 || form.logo_url) ? (
            <img src={form.logo_b64 || form.logo_url} alt="Logo" className="max-h-20 max-w-36 object-contain" />
          ) : (
            <span className="text-xs text-muted-foreground">{t('settings.company.logo_slot')}</span>
          )}
        </div>
        <div className="space-y-2">
          <Label>{t('settings.company.logo')}</Label>
          <Input type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" disabled={!canManage} data-testid="company-logo-file" onChange={(e) => {
            const f = e.target.files && e.target.files[0];
            if (!f) return;
            if (f.size > 800000) { toast.error(t('settings.company.logo_heavy')); return; }
            const reader = new FileReader();
            reader.onload = () => setForm({ ...form, logo_b64: reader.result, logo_url: '' });
            reader.readAsDataURL(f);
          }} />
          <Input placeholder={t('settings.company.logo_url')} value={form.logo_url || ''} disabled={!canManage} data-testid="company-logo-url" onChange={(e) => setForm({ ...form, logo_url: e.target.value })} />
        </div>
      </div>
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
          <TabsTrigger value="rgpd" className="gap-1.5" data-testid="tab-rgpd"><ShieldCheck className="h-4 w-4" />{t('cl.g_onglet')}</TabsTrigger>
        </TabsList>
        <TabsContent value="ai" className="mt-4"><AiSettings canManage={canManage} /></TabsContent>
        <TabsContent value="company" className="mt-4"><CompanyProfile canManage={canManage} /></TabsContent>
        <TabsContent value="rgpd" className="mt-4"><DonneesPersonnelles canManage={canManage} /></TabsContent>
      </Tabs>
    </div>
  );
}
