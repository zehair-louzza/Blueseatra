import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { api, apiError } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Skeleton } from '@/components/ui/skeleton';
import { Loader2, Mail, Send } from 'lucide-react';
import { dtfr } from '@/components/clients/ClientForm';

// Boîte d'envoi des relances (backend/relances_email.py). Le mot de passe
// n'est jamais renvoyé par l'API : champ vide = mot de passe inchangé.
const PRESETS = [
  { nom: 'Zoho Mail (Europe)', hote: 'smtp.zoho.eu', port: 465 },
  { nom: 'OVHcloud', hote: 'ssl0.ovh.net', port: 465 },
  { nom: 'Hostinger', hote: 'smtp.hostinger.com', port: 465 },
  { nom: 'Gmail', hote: 'smtp.gmail.com', port: 465 },
  { nom: 'Microsoft 365', hote: 'smtp.office365.com', port: 587 },
];

export default function MessagerieEnvoi({ onChange }) {
  const { t } = useTranslation();
  const [m, setM] = useState(null);
  const [mdp, setMdp] = useState('');
  const [busy, setBusy] = useState('');

  useEffect(() => {
    api.get('/messagerie').then((r) => setM({ hote: '', identifiant: '', expediteur_email: '', expediteur_nom: '', signature: '', actif: true, ...r.data }))
      .catch((e) => toast.error(apiError(e)));
  }, []);
  if (!m) return <Skeleton className="mt-5 h-40 w-full" />;

  const maj = (k) => (e) => setM({ ...m, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value });
  const enregistrer = async () => {
    setBusy('save');
    try {
      const { data } = await api.put('/messagerie', {
        hote: m.hote, port: Number(m.port), identifiant: m.identifiant, mot_de_passe: mdp || null,
        expediteur_email: m.expediteur_email, expediteur_nom: m.expediteur_nom, signature: m.signature,
        copie_cachee: m.copie_cachee, actif: m.actif,
      });
      setM({ ...m, ...data }); setMdp(''); toast.success(t('cl.mb_saved')); onChange?.();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(''); }
  };
  const tester = async () => {
    setBusy('test');
    try {
      const { data } = await api.post('/messagerie/test', null, { timeout: 60000 });
      setM({ ...m, ...data }); toast.success(t('cl.mb_test_ok', { e: data.expediteur_email })); onChange?.();
    } catch (e) {
      toast.error(apiError(e));
      api.get('/messagerie').then((r) => setM((x) => ({ ...x, ...r.data }))).catch(() => {});
    } finally { setBusy(''); }
  };
  const champ = (k, label, props = {}) => (
    <label className="text-sm"><span className="mb-1 block text-xs text-muted-foreground">{label}</span>
      <Input value={m[k] ?? ''} onChange={maj(k)} {...props} /></label>
  );

  return (
    <Card className="card-shadow mt-5 border-0 p-5" data-testid="messagerie-envoi">
      <h2 className="flex items-center gap-2 font-display text-base font-semibold"><Mail className="h-4 w-4" />{t('cl.mb_title')}</h2>
      <p className="mt-1 text-xs text-muted-foreground">{t('cl.mb_aide')}</p>
      <div className="mt-3 flex flex-wrap items-center gap-1.5 text-xs">
        <span className="text-muted-foreground">{t('cl.mb_presets')} :</span>
        {PRESETS.map((p) => (
          <button key={p.nom} type="button" className="rounded-full border border-input px-2 py-0.5 hover:bg-muted/40"
            onClick={() => setM({ ...m, hote: p.hote, port: p.port })}>{p.nom}</button>
        ))}
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        {champ('hote', t('cl.mb_hote'), { placeholder: 'smtp.zoho.eu', autoComplete: 'off' })}
        <label className="text-sm"><span className="mb-1 block text-xs text-muted-foreground">{t('cl.mb_port')}</span>
          <select className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm" value={m.port} onChange={maj('port')}>
            <option value={465}>465 (SSL)</option><option value={587}>587 (STARTTLS)</option>
          </select></label>
        {champ('identifiant', t('cl.mb_identifiant'), { autoComplete: 'off' })}
        <label className="text-sm"><span className="mb-1 block text-xs text-muted-foreground">{t('cl.mb_mdp')}</span>
          <Input type="password" value={mdp} onChange={(e) => setMdp(e.target.value)} autoComplete="new-password"
            placeholder={m.mot_de_passe_defini ? t('cl.mb_mdp_garde') : ''} data-testid="messagerie-mdp" /></label>
        {champ('expediteur_email', t('cl.mb_exp_email'), { type: 'email' })}
        {champ('expediteur_nom', t('cl.mb_exp_nom'))}
        <label className="text-sm md:col-span-3"><span className="mb-1 block text-xs text-muted-foreground">{t('cl.mb_signature')}</span>
          <Textarea rows={3} value={m.signature ?? ''} onChange={maj('signature')} /></label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!m.copie_cachee} onChange={maj('copie_cachee')} />{t('cl.mb_copie')}</label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!m.actif} onChange={maj('actif')} />{t('cl.mb_actif')}</label>
      </div>
      {m.configuree && (
        <p className={`mt-3 text-xs ${m.verifie_le ? 'text-emerald-700' : 'text-amber-700'}`} data-testid="messagerie-etat">
          {m.verifie_le ? t('cl.mb_verifiee', { d: dtfr(m.verifie_le) }) : t('cl.mb_non_verifiee')}
          {m.derniere_erreur && <span className="block text-destructive">{t('cl.mb_erreur', { e: m.derniere_erreur })}</span>}
        </p>
      )}
      <div className="mt-4 flex flex-wrap justify-end gap-2">
        {m.configuree && (
          <Button variant="secondary" className="gap-1.5" onClick={tester} disabled={!!busy || !m.actif} data-testid="messagerie-test">
            {busy === 'test' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}{t('cl.mb_test')}
          </Button>
        )}
        <Button onClick={enregistrer} disabled={!!busy} data-testid="messagerie-save">
          {busy === 'save' && <Loader2 className="h-4 w-4 animate-spin" />}{t('cl.mb_save')}
        </Button>
      </div>
    </Card>
  );
}
