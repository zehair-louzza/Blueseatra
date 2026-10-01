import React, { useEffect, useState } from 'react';
import ChoixOffre from '@/components/ChoixOffre';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/context/AuthContext';
import { api, apiError } from '@/lib/api';
import { localeCourante } from '@/lib/locale';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { CreditCard, FileText, ScanText, Users, Info, ArrowRight } from 'lucide-react';

// Nombres et dates dans la langue de l'interface : « 9 octobre 2026 » en
// français, « 9 October 2026 » en anglais.
const nf = { format: (n) => new Intl.NumberFormat(localeCourante()).format(n) };
const eur = (n) => new Intl.NumberFormat(localeCourante(), { style: 'currency', currency: 'EUR', maximumFractionDigits: 2, minimumFractionDigits: 0 }).format(n);
const df = (iso) => (iso ? new Date(iso).toLocaleDateString(localeCourante(), { day: 'numeric', month: 'long', year: 'numeric' }) : '');
const dtf = (iso) => (iso ? new Date(iso).toLocaleString(localeCourante(), { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '');

function Jauge({ icon: Icon, label, inclus, utilise, restant, recharge, t, plein = false, projection = null, epuisement = null }) {
  const illimite = inclus === null || inclus === undefined;
  const total = illimite ? 0 : inclus + (recharge || 0);
  const pct = illimite || !total ? 0 : Math.min(100, Math.round((utilise / Math.max(total, 1)) * 100));
  const ton = plein ? 'bg-primary' : pct >= 100 ? 'bg-destructive' : pct >= 80 ? 'bg-amber-500' : 'bg-accent';
  return (
    <div className="rounded-2xl border border-border bg-card p-5">
      <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
        <Icon className="h-4 w-4 text-accent" /> {label}
      </div>
      <p className="tabular mt-3 font-display text-3xl font-semibold tracking-tight">
        {nf.format(utilise || 0)}
        <span className="ml-1 text-base font-normal text-muted-foreground">
          {illimite ? t('billing.unlimited') : `/ ${nf.format(inclus)}`}
        </span>
      </p>
      {!illimite && (
        <>
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
            <div className={`h-full rounded-full ${ton} transition-all`} style={{ width: `${pct}%` }} />
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            {t('billing.remaining', { n: nf.format(restant ?? 0) })}
            {recharge ? ` · ${t('billing.topup_left', { n: nf.format(recharge) })}` : ''}
          </p>
          {projection != null && utilise > 0 && (
            <p className={`mt-1 text-xs ${epuisement ? 'font-medium text-amber-700' : 'text-muted-foreground'}`} data-testid="billing-projection">
              {epuisement
                ? t('cl.b_epuisement', { d: new Date(epuisement).toLocaleDateString(localeCourante()) })
                : t('cl.b_projection', { n: nf.format(projection) })}
            </p>
          )}
        </>
      )}
    </div>
  );
}

export default function Billing() {
  const { t } = useTranslation();
  const { tenant } = useAuth();
  const [etat, setEtat] = useState(null);
  const [lignes, setLignes] = useState(null);
  const [erreur, setErreur] = useState('');
  const peutVoirHistorique = ['owner', 'admin', 'billing_admin'].includes(tenant?.role);
  const peutPayer = ['owner', 'billing_admin'].includes(tenant?.role);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    if (q.get('paiement') === 'ok') toast.success(t('cl.p_retour_ok'));
    if (q.get('recharge') === 'ok') toast.success(t('cl.p_retour_recharge'));
  }, [t]);

  useEffect(() => {
    api.get('/abonnement/consommation').then((r) => setEtat(r.data)).catch((e) => setErreur(apiError(e, 'Erreur')));
    if (peutVoirHistorique) {
      api.get('/abonnement/historique', { params: { limite: 30 } })
        .then((r) => setLignes(r.data.lignes || [])).catch(() => setLignes([]));
    }
  }, [peutVoirHistorique]);

  if (erreur) {
    return <div className="mx-auto max-w-4xl"><h1 className="font-display text-2xl font-semibold">{t('billing.title')}</h1><p className="mt-4 text-sm text-destructive">{erreur}</p></div>;
  }
  if (!etat) {
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <Skeleton className="h-8 w-48" /><Skeleton className="h-32 w-full rounded-2xl" />
        <div className="grid gap-4 md:grid-cols-3"><Skeleton className="h-36 rounded-2xl" /><Skeleton className="h-36 rounded-2xl" /><Skeleton className="h-36 rounded-2xl" /></div>
      </div>
    );
  }
  if (!etat.disponible) {
    return (
      <div className="mx-auto max-w-4xl">
        <h1 className="font-display text-2xl font-semibold tracking-tight">{t('billing.title')}</h1>
        <Card className="mt-5 border-0 p-6 card-shadow text-sm text-muted-foreground">{t('billing.not_ready')}</Card>
      </div>
    );
  }

  const { offre, statut, jauges, sieges, periode } = etat;
  const essai = statut === 'essai';
  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="font-display text-2xl font-semibold tracking-tight">{t('billing.title')}</h1>

      <Card className="card-shadow mt-5 border-0 p-6">
        <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground"><CreditCard className="h-5 w-5" /></div>
            <div>
              <div className="text-xs uppercase tracking-wide text-muted-foreground">{t('billing.current_plan')}</div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-display text-xl font-semibold">{offre.nom}</span>
                <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${statut === 'actif' || essai ? 'bg-accent/15 text-accent' : 'bg-destructive/10 text-destructive'}`}>
                  {t(`billing.status_${statut}`)}
                </span>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {essai
                  ? t('billing.trial_until', { date: df(etat.essai_fin_le) })
                  : t('billing.period', { debut: df(periode.debut), fin: df(periode.fin) })}
                {offre.prix_mensuel_ht ? ` · ${eur(offre.prix_mensuel_ht)} ${t('cl.p_ht')} / ${t('billing.month')}` : ''}
              </p>
            </div>
          </div>
          <a href="#choix-offre">
            <Button className="gap-2">{essai ? t('billing.choose_plan') : t('billing.change_plan')} <ArrowRight className="h-4 w-4" /></Button>
          </a>
        </div>
      </Card>

      <div className="mt-5 grid gap-4 md:grid-cols-3">
        <Jauge t={t} icon={FileText} label={t('billing.quotes_ai')} inclus={jauges.devis_ia.inclus} utilise={jauges.devis_ia.utilise}
          restant={jauges.devis_ia.restant} recharge={jauges.devis_ia.recharge_restante}
          projection={jauges.devis_ia.projection_fin_periode} epuisement={jauges.devis_ia.epuisement_prevu_le} />
        <Jauge t={t} icon={ScanText} label={t('billing.pages_read')} inclus={jauges.page_lue.inclus} utilise={jauges.page_lue.utilise}
          restant={jauges.page_lue.restant} recharge={jauges.page_lue.recharge_restante}
          projection={jauges.page_lue.projection_fin_periode} epuisement={jauges.page_lue.epuisement_prevu_le} />
        <Jauge t={t} plein icon={Users} label={t('billing.seats')} inclus={sieges.inclus} utilise={sieges.utilises}
          restant={sieges.inclus == null ? null : Math.max(sieges.inclus - (sieges.utilises || 0), 0)} />
      </div>

      <div className="mt-4 flex items-start gap-2 rounded-xl bg-muted/60 p-4 text-sm text-muted-foreground">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
        <span>{t('billing.what_counts')} {!etat.application && t('billing.observation')}</span>
      </div>

      <div id="choix-offre"><ChoixOffre offreActuelle={offre.code} peutPayer={peutPayer} /></div>

      {peutVoirHistorique && (
        <Card className="card-shadow mt-6 border-0 p-0">
          <div className="border-b border-border px-6 py-4 font-semibold">{t('billing.history')}</div>
          {lignes === null ? (
            <div className="p-6"><Skeleton className="h-24 w-full" /></div>
          ) : lignes.length === 0 ? (
            <p className="px-6 py-8 text-sm text-muted-foreground">{t('billing.history_empty')}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <tr><th className="px-6 py-3 font-medium">{t('billing.h_date')}</th><th className="px-3 py-3 font-medium">{t('billing.h_type')}</th>
                    <th className="px-3 py-3 font-medium">{t('billing.h_unit')}</th><th className="px-3 py-3 text-right font-medium">{t('billing.h_qty')}</th>
                    <th className="px-6 py-3 font-medium">{t('billing.h_detail')}</th></tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {lignes.map((l) => (
                    <tr key={l.id}>
                      <td className="whitespace-nowrap px-6 py-2.5 text-muted-foreground">{dtf(l.cree_le)}</td>
                      <td className="px-3 py-2.5">{t(`billing.n_${l.nature}`)}</td>
                      <td className="px-3 py-2.5">{t(`billing.u_${l.unite}`)}{l.reserve === 'recharge' ? ` · ${t('billing.topup')}` : ''}</td>
                      <td className={`tabular px-3 py-2.5 text-right font-medium ${l.quantite > 0 ? 'text-accent' : ''}`}>{l.quantite > 0 ? '+' : ''}{nf.format(l.quantite)}</td>
                      <td className="max-w-[260px] truncate px-6 py-2.5 text-muted-foreground">{l.motif || (l.demande_id ? `${t('billing.request')} ${l.demande_id.slice(0, 8)}` : '')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
