import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { api, apiError } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Users, Check, X, MinusCircle } from 'lucide-react';
import { dtfr } from '@/components/clients/ClientForm';

function ChoixClient({ label, valeur, nom, onChange, disabled }) {
  const { t } = useTranslation();
  const [q, setQ] = useState('');
  const [opts, setOpts] = useState([]);
  const [ouvert, setOuvert] = useState(false);
  useEffect(() => {
    if (!ouvert) return undefined;
    const x = setTimeout(() => api.get('/clients', { params: { q, taille: 8 } }).then((r) => setOpts(r.data.clients)).catch(() => {}), 200);
    return () => clearTimeout(x);
  }, [q, ouvert]);
  return (
    <div className="relative space-y-1">
      <div className="text-xs uppercase text-muted-foreground">{label}</div>
      {valeur && !ouvert ? (
        <div className="flex items-center justify-between gap-2 rounded-md border border-border px-3 py-1.5 text-sm">
          <Link to={`/app/clients/${valeur}`} className="truncate font-medium hover:underline">{nom}</Link>
          {!disabled && <button type="button" className="text-xs text-muted-foreground hover:text-foreground" onClick={() => onChange(null, null)}>{t('cl.q_none')}</button>}
        </div>
      ) : (
        <Input className="h-8" placeholder={t('cl.q_pick')} value={q} disabled={disabled}
          onFocus={() => setOuvert(true)} onBlur={() => setTimeout(() => setOuvert(false), 150)} onChange={(e) => setQ(e.target.value)} />
      )}
      {ouvert && opts.length > 0 && (
        <div className="absolute z-20 mt-1 max-h-56 w-full overflow-y-auto rounded-md border border-border bg-popover p-1 shadow-soft">
          {opts.map((o) => (
            <button key={o.id} type="button" className="block w-full truncate rounded px-2 py-1.5 text-left text-sm hover:bg-muted"
              onMouseDown={() => { onChange(o.id, o.raison_sociale); setOuvert(false); setQ(''); }}>
              {o.raison_sociale}<span className="text-xs text-muted-foreground"> {o.ville || ''}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function QuoteClientPanel({ quoteId, status }) {
  const { t } = useTranslation();
  const { tenant } = useAuth();
  const peutEcrire = ['owner', 'admin', 'operator'].includes(tenant?.role);
  const [s, setS] = useState(null);
  const [motif, setMotif] = useState('');
  const charger = useCallback(() => api.get(`/quotes/${quoteId}/suivi`).then((r) => setS(r.data)).catch(() => setS(false)), [quoteId]);
  useEffect(() => { charger(); }, [charger, status]);
  if (s === false || s === null) return null;

  const lier = async (patch) => {
    const body = { client_id: s.client_id, client_final_id: s.client_final_id, chantier_id: s.chantier_id,
      contact_id: s.contact_id, valable_jusqu_au: s.valable_jusqu_au, ...patch };
    try { const { data } = await api.post(`/quotes/${quoteId}/client`, body); setS(data); toast.success(t('cl.q_link_saved')); }
    catch (e) { toast.error(apiError(e)); }
  };
  const issue = async (v) => {
    try { const { data } = await api.post(`/quotes/${quoteId}/issue`, { issue: v, motif: motif || null }); setS(data); setMotif(''); }
    catch (e) { toast.error(apiError(e)); }
  };
  const actives = (s.relances || []).filter((x) => ['prevue', 'reportee'].includes(x.statut));
  return (
    <Card className="card-shadow mt-4 border-0 p-5" data-testid="quote-client-panel">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold"><Users className="h-4 w-4 text-accent" />{t('cl.q_panel')}</h3>
      <div className="space-y-3 text-sm">
        <ChoixClient label={t('cl.q_client')} valeur={s.client_id} nom={s.client_nom} disabled={!peutEcrire}
          onChange={(id, nom) => { setS({ ...s, client_id: id, client_nom: nom }); lier({ client_id: id }); }} />
        <ChoixClient label={t('cl.q_final')} valeur={s.client_final_id} nom={s.client_final_nom} disabled={!peutEcrire}
          onChange={(id, nom) => { setS({ ...s, client_final_id: id, client_final_nom: nom }); lier({ client_final_id: id }); }} />
        <label className="block space-y-1"><span className="text-xs uppercase text-muted-foreground">{t('cl.q_validity')}</span>
          <Input type="date" className="h-8" value={s.valable_jusqu_au || ''} disabled={!peutEcrire}
            onChange={(e) => lier({ valable_jusqu_au: e.target.value || null })} /></label>

        {status === 'sent' && (
          <div className="rounded-xl bg-muted/50 p-3">
            <div className="mb-2 flex items-center justify-between text-xs uppercase text-muted-foreground">
              <span>{t('cl.q_issue')}</span>
              <span className="rounded-full bg-background px-2 py-0.5 normal-case text-foreground">{t(`cl.issue.${s.issue || 'en_attente'}`)}</span>
            </div>
            {peutEcrire && (!s.issue || s.issue === 'en_attente') && (
              <>
                <Input className="mb-2 h-8" placeholder={t('cl.q_reason')} value={motif} onChange={(e) => setMotif(e.target.value)} />
                <div className="grid grid-cols-3 gap-1.5">
                  <Button size="sm" className="gap-1" onClick={() => issue('accepte')}><Check className="h-3.5 w-3.5" />{t('cl.q_accepted')}</Button>
                  <Button size="sm" variant="secondary" className="gap-1" onClick={() => issue('refuse')}><X className="h-3.5 w-3.5" />{t('cl.q_refused')}</Button>
                  <Button size="sm" variant="ghost" className="gap-1" onClick={() => issue('sans_suite')}><MinusCircle className="h-3.5 w-3.5" />{t('cl.q_nofollow')}</Button>
                </div>
              </>
            )}
            {peutEcrire && s.issue && s.issue !== 'en_attente' && (
              <button type="button" className="text-xs text-muted-foreground underline" onClick={() => issue('en_attente')}>{t('cl.issue.en_attente')}</button>
            )}
          </div>
        )}

        <div>
          <div className="mb-1 text-xs uppercase text-muted-foreground">{t('cl.q_followups')}</div>
          {status !== 'sent' && !(s.relances || []).length ? <p className="text-xs text-muted-foreground">{t('cl.q_send_first')}</p> : (
            <ul className="space-y-1.5 text-xs">
              {(s.relances || []).map((x) => (
                <li key={x.id} className={actives.includes(x) ? '' : 'text-muted-foreground line-through decoration-muted-foreground/40'}>
                  {dtfr(x.echeance)} · {t(`cl.canal.${x.canal}`)} · {t(`cl.statut.${x.statut}`)}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </Card>
  );
}
