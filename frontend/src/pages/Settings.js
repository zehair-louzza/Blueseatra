import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Spinner } from '@/components/Spinner';
import { toast } from 'sonner';
import { Save, Loader2, KeyRound, CheckCircle2 } from 'lucide-react';

export default function Settings() {
  const { t } = useTranslation();
  const { tenant } = useAuth();
  const [data, setData] = useState(null);
  const [providerModels, setProviderModels] = useState({});
  const [form, setForm] = useState({ ai_provider: 'emergent', ai_model: '', ai_key: '', n8n_webhook_url: '' });
  const [keySet, setKeySet] = useState(false);
  const [busy, setBusy] = useState(false);
  const canManage = ['owner', 'admin'].includes(tenant?.role);

  useEffect(() => {
    api.get('/settings/integrations').then((r) => {
      const s = r.data.settings;
      setProviderModels(r.data.provider_models);
      setForm({ ai_provider: s.ai_provider || 'emergent', ai_model: s.ai_model || '', ai_key: '', n8n_webhook_url: s.n8n_webhook_url || '' });
      setKeySet(!!s.ai_key_set);
      setData(s);
    });
  }, []);

  const save = async () => {
    setBusy(true);
    try { await api.put('/settings/integrations', form); toast.success(t('settings.saved')); if (form.ai_key) setKeySet(true); setForm({ ...form, ai_key: '' }); }
    catch (err) { toast.error(err.response?.data?.detail || 'Failed'); }
    finally { setBusy(false); }
  };

  if (!data) return <Spinner />;
  const models = providerModels[form.ai_provider] || [];

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="font-display text-2xl font-semibold tracking-tight">{t('settings.title')}</h1>
      <Card className="card-shadow mt-5 border-0 p-6">
        <div className="space-y-5">
          <div className="space-y-1.5">
            <Label>{t('settings.ai_provider')}</Label>
            <Select value={form.ai_provider} onValueChange={(v) => setForm({ ...form, ai_provider: v, ai_model: (providerModels[v] || [])[0] || '' })} disabled={!canManage}>
              <SelectTrigger data-testid="ai-provider-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                {Object.keys(providerModels).map((p) => <SelectItem key={p} value={p}>{p === 'emergent' ? 'Built-in (Emergent)' : p}</SelectItem>)}
              </SelectContent>
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
          {canManage && (
            <Button onClick={save} disabled={busy} className="gap-2" data-testid="save-settings-button">
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}{t('settings.save')}
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}
