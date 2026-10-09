import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { api, apiError } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import MessagerieEnvoi from '@/components/clients/MessagerieEnvoi';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Mail, Phone, Check, Clock, X, Copy, Settings2, BellRing, ChevronDown, Send, Save, Loader2 } from 'lucide-react';
import { euro, dtfr } from '@/components/clients/ClientForm';

const GROUPES = ['retard', 'aujourdhui', 'a_venir'];

function Carte({ x, onChange, t, peutEcrire, envoi }) {
  const agir = async (url, body) => { try { await api.post(url, body); onChange(); } catch (e) { toast.error(apiError(e)); } };
  const tel = x.contact_mobile || x.contact_telephone;
  const parEmail = x.canal === 'email' && !!x.brouillon;
  const [objet, setObjet] = useState(x.objet || `Devis ${x.numero || ''}`.trim());
  const [texte, setTexte] = useState(x.brouillon || '');
  const [busy, setBusy] = useState('');
  const modifie = objet !== (x.objet || `Devis ${x.numero || ''}`.trim()) || texte !== (x.brouillon || '');
  const mailto = x.contact_email && texte
    ? `mailto:${x.contact_email}?subject=${encodeURIComponent(objet)}&body=${encodeURIComponent(texte)}` : null;
  const serveur = envoi?.messagerie_active && x.contact_email;
  const auto = envoi?.envoi_auto && serveur && envoi.envoi_auto_depuis && new Date(x.echeance) >= new Date(envoi.envoi_auto_depuis)
    && new Date(x.echeance) > new Date();
  const enregistrer = async () => {
    setBusy('save');
    try { await api.patch(`/relances/${x.id}/texte`, { objet, brouillon: texte }); toast.success(t('cl.r_text_saved')); onChange(); }
    catch (e) { toast.error(apiError(e)); } finally { setBusy(''); }
  };
  const envoyer = async () => {
    setBusy('send');
    try {
      const { data } = await api.post(`/relances/${x.id}/envoyer`, { objet, brouillon: texte }, { timeout: 60000 });
      toast.success(t('cl.r_sent', { e: data.envoye_a })); onChange();
    } catch (e) { toast.error(apiError(e)); onChange(); } finally { setBusy(''); }
  };
  return (
    <div className="rounded-2xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="text-sm">
          <Link to={`/app/quotes/${x.devis_id}`} className="font-semibold hover:underline">{x.numero || x.devis_id.slice(0, 8)}</Link>
          {x.client && <> · <Link to={`/app/clients/${x.client_id}`} className="hover:underline">{x.client}</Link></>}
          {x.total_ht != null && <span className="tabular text-muted-foreground"> · {euro(x.total_ht)}</span>}
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {x.canal === 'appel' ? <Phone className="h-3.5 w-3.5" /> : x.canal === 'email' ? <Mail className="h-3.5 w-3.5" /> : <BellRing className="h-3.5 w-3.5" />}
          {t(`cl.canal.${x.canal}`)}{x.contact_nom ? ` · ${[x.prenom, x.contact_nom].filter(Boolean).join(' ')}` : ''} · {dtfr(x.echeance)}
        </div>
      </div>
      <p className="mt-1.5 text-sm text-muted-foreground">« {x.raison} »</p>
      {auto && <p className="mt-1.5 text-xs font-medium text-primary" data-testid="relance-auto">{t('cl.r_auto_le', { d: dtfr(x.echeance) })}</p>}
      {x.envoi_statut === 'echec' && x.envoi_erreur && (
        <p className="mt-1.5 text-xs text-destructive" data-testid="relance-echec">{t('cl.r_envoi_echec', { e: x.envoi_erreur })}</p>
      )}
      {x.brouillon && (
        <details className="mt-3 rounded-xl bg-muted/50 p-3 text-sm" open={parEmail && x.groupe !== 'a_venir'}>
          <summary className="cursor-pointer text-xs font-medium">{t('cl.r_draft')}</summary>
          {parEmail && peutEcrire ? (
            <div className="mt-2 space-y-2" data-testid="relance-editeur">
              <label className="block text-xs text-muted-foreground">{t('cl.r_subject')}
                <Input value={objet} maxLength={200} onChange={(e) => setObjet(e.target.value)} className="mt-1 bg-card" /></label>
              <Textarea rows={7} value={texte} onChange={(e) => setTexte(e.target.value)} className="bg-card" />
              {!envoi?.messagerie_active && <p className="text-xs text-muted-foreground">{t('cl.r_no_mailbox')}</p>}
            </div>
          ) : <p className="mt-2 whitespace-pre-wrap">{x.brouillon}</p>}
          <div className="mt-2 flex flex-wrap gap-3">
            <button type="button" className="inline-flex items-center gap-1 text-xs text-primary"
              onClick={() => { navigator.clipboard?.writeText(texte); toast.success(t('cl.r_copied')); }}><Copy className="h-3.5 w-3.5" />{t('cl.r_copy')}</button>
            {parEmail && peutEcrire && modifie && (
              <button type="button" className="inline-flex items-center gap-1 text-xs text-primary" onClick={enregistrer} disabled={!!busy}>
                {busy === 'save' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}{t('cl.r_save_text')}</button>
            )}
          </div>
        </details>
      )}
      {peutEcrire && (
        <div className="mt-3 flex flex-wrap gap-2">
          {parEmail && serveur && (
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button size="sm" className="gap-1.5" disabled={!!busy || !texte.trim() || !objet.trim()} data-testid="relance-envoyer">
                  {busy === 'send' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}{t('cl.r_send_now')}
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>{t('cl.r_send_confirm', { e: x.contact_email })}</AlertDialogTitle>
                  <AlertDialogDescription>{t('cl.r_send_confirm_aide')}</AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                  <AlertDialogAction onClick={envoyer}>{t('cl.r_send_now')}</AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          )}
          {mailto && !serveur && <a href={mailto}><Button size="sm" variant="secondary" className="gap-1.5"><Mail className="h-3.5 w-3.5" />{t('cl.r_send')}</Button></a>}
          {tel && x.canal !== 'email' && <a href={`tel:${tel}`}><Button size="sm" variant="secondary" className="gap-1.5"><Phone className="h-3.5 w-3.5" />{t('cl.r_call')} {tel}</Button></a>}
          <DropdownMenu>
            <DropdownMenuTrigger asChild><Button size="sm" className="gap-1.5"><Check className="h-3.5 w-3.5" />{t('cl.r_done')}<ChevronDown className="h-3.5 w-3.5" /></Button></DropdownMenuTrigger>
            <DropdownMenuContent>
              {['sans_reponse', 'a_rappeler', 'en_reflexion', 'accepte', 'refuse'].map((r) => (
                <DropdownMenuItem key={r} onClick={() => agir(`/relances/${x.id}/faite`, { resultat: r })}>{t(`cl.results.${r}`)}</DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
          <DropdownMenu>
            <DropdownMenuTrigger asChild><Button size="sm" variant="ghost" className="gap-1.5"><Clock className="h-3.5 w-3.5" />{t('cl.r_postpone')}</Button></DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuItem onClick={() => agir(`/relances/${x.id}/reporter`, { jours_ouvres: 1 })}>{t('cl.r_tomorrow')}</DropdownMenuItem>
              <DropdownMenuItem onClick={() => agir(`/relances/${x.id}/reporter`, { jours_ouvres: 3 })}>{t('cl.r_3days')}</DropdownMenuItem>
              <DropdownMenuItem onClick={() => agir(`/relances/${x.id}/reporter`, { jours_ouvres: 5 })}>{t('cl.r_week_later')}</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <Button size="sm" variant="ghost" className="gap-1.5 text-muted-foreground" onClick={() => agir(`/relances/${x.id}/annuler`, {})}><X className="h-3.5 w-3.5" />{t('cl.r_cancel')}</Button>
        </div>
      )}
    </div>
  );
}

function Reglages({ onClose, onChange }) {
  const { t } = useTranslation();
  const [g, setG] = useState(null);
  const relire = useCallback(() => api.get('/regles-relance').then((r) => setG(r.data)), []);
  useEffect(() => { relire(); }, [relire]);
  if (!g) return <Skeleton className="h-40 w-full" />;
  const liste = (v) => v.split(/[,; ]+/).map(Number).filter((n) => n > 0);
  const enregistrer = async () => {
    try { const { data } = await api.put('/regles-relance', g); setG(data); toast.success(t('cl.saved')); onChange?.(); } catch (e) { toast.error(apiError(e)); }
  };
  const champ = (k, label, type = 'number') => (
    <label className="text-sm"><span className="mb-1 block text-xs text-muted-foreground">{label}</span>
      <Input type={type} value={g[k]} onChange={(e) => setG({ ...g, [k]: type === 'number' ? Number(e.target.value) : e.target.value })} /></label>
  );
  return (
    <Card className="card-shadow mt-5 border-0 p-5">
      <div className="flex items-center justify-between"><h2 className="font-display text-base font-semibold">{t('cl.rules')}</h2><Button size="sm" variant="ghost" onClick={onClose}><X className="h-4 w-4" /></Button></div>
      <p className="mt-1 text-xs text-muted-foreground">{t('cl.rules_note')}</p>
      <div className="mt-4 grid gap-3 md:grid-cols-4">
        <label className="flex items-center gap-2 text-sm md:col-span-4"><input type="checkbox" checked={g.actif} onChange={(e) => setG({ ...g, actif: e.target.checked })} />{t('cl.rules_active')}</label>
        <div className="md:col-span-4">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={!!g.envoi_auto} disabled={!g.envoi_auto && !(g.messagerie_active && g.messagerie_verifiee)}
              onChange={(e) => setG({ ...g, envoi_auto: e.target.checked })} data-testid="regles-envoi-auto" />{t('cl.rules_auto')}
          </label>
          <p className="ml-6 text-xs text-muted-foreground">
            {g.messagerie_active && g.messagerie_verifiee ? t('cl.rules_auto_aide') : t('cl.rules_auto_bloque')}
          </p>
        </div>
        <label className="text-sm"><span className="mb-1 block text-xs text-muted-foreground">{t('cl.rules_delays')}</span>
          <Input value={g.delais_jours_ouvres.join(', ')} onChange={(e) => setG({ ...g, delais_jours_ouvres: liste(e.target.value) })} /></label>
        <label className="text-sm"><span className="mb-1 block text-xs text-muted-foreground">{t('cl.rules_urgent')}</span>
          <Input value={g.delais_urgent.join(', ')} onChange={(e) => setG({ ...g, delais_urgent: liste(e.target.value) })} /></label>
        {champ('max_relances', t('cl.rules_max'))}
        {champ('validite_devis_jours', t('cl.rules_validity'))}
        {champ('rappel_avant_expiration_j', t('cl.rules_expiry'))}
        {champ('seuil_appel_ht', t('cl.rules_threshold'))}
        {champ('heure_relance', t('cl.rules_hour'), 'time')}
      </div>
      <div className="mt-4 rounded-xl bg-muted/50 p-3 text-sm">
        <div className="mb-1 text-xs font-medium">{t('cl.rules_preview')}</div>
        {g.apercu.length === 0 ? '—' : g.apercu.map((p) => <div key={p.rang} className="text-muted-foreground">{dtfr(p.echeance)} · {t(`cl.canal.${p.canal}`)} · {p.raison}</div>)}
      </div>
      <div className="mt-4 flex justify-end"><Button onClick={enregistrer}>{t('cl.save')}</Button></div>
    </Card>
  );
}

function ReglagesEtMessagerie({ onClose, onChange }) {
  const [cle, setCle] = useState(0);   // relit les règles après un test de la messagerie
  return (
    <>
      <Reglages key={cle} onClose={onClose} onChange={onChange} />
      <MessagerieEnvoi onChange={() => { setCle((k) => k + 1); onChange?.(); }} />
    </>
  );
}

export default function Relances() {
  const { t } = useTranslation();
  const { tenant } = useAuth();
  const peutEcrire = ['owner', 'admin', 'operator'].includes(tenant?.role);
  const peutGerer = ['owner', 'admin'].includes(tenant?.role);
  const [data, setData] = useState(null);
  const [reglages, setReglages] = useState(false);
  const charger = useCallback(() => api.get('/relances', { params: { periode: 'semaine' } }).then((r) => setData(r.data)).catch((e) => toast.error(apiError(e))), []);
  useEffect(() => { charger(); }, [charger]);
  const titres = { retard: t('cl.r_late'), aujourdhui: t('cl.r_today'), a_venir: t('cl.r_week') };
  return (
    <div className="mx-auto max-w-4xl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-semibold tracking-tight">{t('cl.r_title')}</h1>
          {data && <p className="text-sm text-muted-foreground">{t('cl.r_late')} : {data.compte.retard} · {t('cl.r_today')} : {data.compte.aujourdhui} · {t('cl.r_week')} : {data.compte.semaine}</p>}
        </div>
        {peutGerer && <Button variant="secondary" className="gap-1.5" onClick={() => setReglages(!reglages)}><Settings2 className="h-4 w-4" />{t('cl.rules')}</Button>}
      </div>
      {reglages && <ReglagesEtMessagerie onClose={() => setReglages(false)} onChange={charger} />}
      {!data ? <div className="mt-5 space-y-3"><Skeleton className="h-28 w-full rounded-2xl" /><Skeleton className="h-28 w-full rounded-2xl" /></div>
        : data.relances.length === 0 ? (
          <Card className="card-shadow mt-5 border-0 p-10 text-center text-sm text-muted-foreground">{t('cl.r_empty')}</Card>
        ) : GROUPES.map((gp) => {
          const rows = data.relances.filter((x) => x.groupe === gp);
          if (!rows.length) return null;
          return (
            <section key={gp} className="mt-6">
              <h2 className={`mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide ${gp === 'retard' ? 'text-destructive' : 'text-muted-foreground'}`}>
                <span className={`h-2 w-2 rounded-full ${gp === 'retard' ? 'bg-destructive' : gp === 'aujourdhui' ? 'bg-accent' : 'bg-muted-foreground/40'}`} />{titres[gp]} ({rows.length})
              </h2>
              <div className="space-y-3">{rows.map((x) => <Carte key={`${x.id}-${x.objet || ''}-${x.envoi_statut || ''}`} x={x} onChange={charger} t={t} peutEcrire={peutEcrire} envoi={data} />)}</div>
            </section>
          );
        })}
    </div>
  );
}
