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
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Mail, Phone, Check, Clock, X, Copy, Settings2, BellRing, ChevronDown } from 'lucide-react';
import { euro, dtfr } from '@/components/clients/ClientForm';

const GROUPES = ['retard', 'aujourdhui', 'a_venir'];

function Carte({ x, onChange, t, peutEcrire }) {
  const agir = async (url, body) => { try { await api.post(url, body); onChange(); } catch (e) { toast.error(apiError(e)); } };
  const tel = x.contact_mobile || x.contact_telephone;
  const mailto = x.contact_email && x.brouillon
    ? `mailto:${x.contact_email}?subject=${encodeURIComponent(`Devis ${x.numero || ''}`)}&body=${encodeURIComponent(x.brouillon)}` : null;
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
      {x.brouillon && (
        <details className="mt-3 rounded-xl bg-muted/50 p-3 text-sm">
          <summary className="cursor-pointer text-xs font-medium">{t('cl.r_draft')}</summary>
          <p className="mt-2 whitespace-pre-wrap">{x.brouillon}</p>
          <button type="button" className="mt-2 inline-flex items-center gap-1 text-xs text-primary"
            onClick={() => { navigator.clipboard?.writeText(x.brouillon); toast.success(t('cl.r_copied')); }}><Copy className="h-3.5 w-3.5" />{t('cl.r_copy')}</button>
        </details>
      )}
      {peutEcrire && (
        <div className="mt-3 flex flex-wrap gap-2">
          {mailto && <a href={mailto}><Button size="sm" variant="secondary" className="gap-1.5"><Mail className="h-3.5 w-3.5" />{t('cl.r_send')}</Button></a>}
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

function Reglages({ onClose }) {
  const { t } = useTranslation();
  const [g, setG] = useState(null);
  useEffect(() => { api.get('/regles-relance').then((r) => setG(r.data)); }, []);
  if (!g) return <Skeleton className="h-40 w-full" />;
  const liste = (v) => v.split(/[,; ]+/).map(Number).filter((n) => n > 0);
  const enregistrer = async () => {
    try { const { data } = await api.put('/regles-relance', g); setG(data); toast.success(t('cl.saved')); } catch (e) { toast.error(apiError(e)); }
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
      {reglages && <Reglages onClose={() => setReglages(false)} />}
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
              <div className="space-y-3">{rows.map((x) => <Carte key={x.id} x={x} onChange={charger} t={t} peutEcrire={peutEcrire} />)}</div>
            </section>
          );
        })}
    </div>
  );
}
