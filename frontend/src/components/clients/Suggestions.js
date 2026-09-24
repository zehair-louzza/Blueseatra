import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { api, apiError } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Sparkles, Check, Link2, X, Undo2 } from 'lucide-react';

const ton = { exacte: 'bg-accent/15 text-accent', probable: 'bg-primary/10 text-primary', faible: 'bg-amber-100 text-amber-800' };

function Carte({ s, onDone, t, peutEcrire }) {
  const v = s.valeurs || {};
  const [busy, setBusy] = useState(false);
  const agir = async (url) => {
    setBusy(true);
    try { await api.post(url); onDone(); } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };
  const lien = s.type === 'rattachement';
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="font-semibold">{lien ? t('cl.sg_link') : t('cl.sg_new')}</span>
        {s.role && <span className="rounded-full bg-muted px-2 py-0.5">{t(`cl.sg_roles.${s.role}`)}</span>}
        <span className={`rounded-full px-2 py-0.5 ${ton[s.force] || ''}`}>{t(`cl.sg_force.${s.force}`)}</span>
      </div>
      <p className="mt-2 font-medium">
        {v.raison_sociale}
        {lien && v.nom_lu && v.nom_lu !== v.raison_sociale && <span className="font-normal text-muted-foreground"> ← « {v.nom_lu} »</span>}
        {v.email && <span className="font-normal text-muted-foreground"> · {v.email}</span>}
      </p>
      <p className="mt-1 text-xs text-muted-foreground"><span className="font-medium text-foreground">{t('cl.sg_proof')} :</span> {s.preuve}</p>
      {peutEcrire && (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button size="sm" className="gap-1.5" disabled={busy} onClick={() => agir(`/suggestions-clients/${s.id}/accepter`)}>
            {lien ? <Link2 className="h-3.5 w-3.5" /> : <Check className="h-3.5 w-3.5" />}{lien ? t('cl.sg_accept') : t('cl.sg_create')}
          </Button>
          <Button size="sm" variant="ghost" className="gap-1.5" disabled={busy} onClick={() => agir(`/suggestions-clients/${s.id}/rejeter`)}>
            <X className="h-3.5 w-3.5" />{t('cl.sg_ignore')}
          </Button>
        </div>
      )}
    </div>
  );
}

export function SuggestionsList({ demandeId, compact = false, enCarte = false }) {
  const { t } = useTranslation();
  const { tenant } = useAuth();
  const peutEcrire = ['owner', 'admin', 'operator'].includes(tenant?.role);
  const [data, setData] = useState(null);
  const charger = useCallback(() => {
    api.get('/suggestions-clients', { params: demandeId ? { demande_id: demandeId } : {} })
      .then((r) => setData(r.data)).catch(() => setData({ a_valider: [], rattachements_auto: [] }));
  }, [demandeId]);
  useEffect(() => { charger(); }, [charger]);
  if (!data || (compact && !data.a_valider.length && !data.rattachements_auto.length)) return null;
  if (!data.a_valider.length && !data.rattachements_auto.length) {
    return <p className="text-sm text-muted-foreground">{t('cl.sg_empty')}</p>;
  }
  const liste = (
    <div className="space-y-3">
      {data.rattachements_auto.map((s) => (
        <div key={s.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-accent/10 px-4 py-3 text-sm">
          <span><Check className="mr-1.5 inline h-4 w-4 text-accent" />{t('cl.sg_auto')} : <b>{s.valeurs?.raison_sociale}</b>
            {s.role && ` · ${t(`cl.sg_roles.${s.role}`)}`} <span className="text-muted-foreground">({s.valeurs?.motif})</span></span>
          <span className="flex gap-2">
            {s.cible_id && <Link to={`/app/clients/${s.cible_id}`} className="text-xs font-medium text-primary underline-offset-2 hover:underline">{t('cl.col_client')}</Link>}
            {peutEcrire && <button type="button" className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
              onClick={async () => { try { await api.post(`/suggestions-clients/${s.id}/annuler-rattachement`); charger(); } catch (e) { toast.error(apiError(e)); } }}>
              <Undo2 className="h-3.5 w-3.5" />{t('cl.sg_undo')}</button>}
          </span>
        </div>
      ))}
      {data.a_valider.map((s) => <Carte key={s.id} s={s} onDone={charger} t={t} peutEcrire={peutEcrire} />)}
    </div>
  );
  if (!enCarte) return liste;
  return (
    <Card className="card-shadow mt-4 border-0 p-5" data-testid="client-suggestions">
      <h2 className="mb-3 flex items-center gap-2 font-display text-base font-semibold"><Sparkles className="h-4 w-4 text-accent" />{t('cl.sg_title')}</h2>
      {liste}
    </Card>
  );
}

export function SuggestionsPanel({ demandeId }) {
  return <SuggestionsList demandeId={demandeId} compact enCarte />;
}

export default function SuggestionsPage() {
  const { t } = useTranslation();
  return (
    <div className="mx-auto max-w-3xl">
      <Link to="/app/clients" className="text-sm text-muted-foreground hover:text-foreground">← {t('cl.title')}</Link>
      <h1 className="mt-2 font-display text-2xl font-semibold tracking-tight">{t('cl.sg_page')}</h1>
      <div className="mt-5"><SuggestionsList /></div>
    </div>
  );
}
