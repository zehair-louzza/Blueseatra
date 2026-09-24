import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { api, apiError } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Skeleton } from '@/components/ui/skeleton';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { ArrowLeft, Pencil, Archive, RotateCcw, Plus, Star, Phone, Mail, MapPin, BellOff, UserX } from 'lucide-react';
import ClientForm, { euro, dfr, dtfr, selectCls } from '@/components/clients/ClientForm';

const ONGLETS = ['overview', 'contacts', 'sites', 'quotes', 'log', 'followups'];

function Kpi({ label, value, sub }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-4">
      <div className="text-xs font-medium text-muted-foreground">{label}</div>
      <div className="tabular mt-1.5 font-display text-2xl font-semibold tracking-tight">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

function Confirmer({ titre, texte, onOk, children }) {
  const { t } = useTranslation();
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>{children}</AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader><AlertDialogTitle>{titre}</AlertDialogTitle><AlertDialogDescription>{texte}</AlertDialogDescription></AlertDialogHeader>
        <AlertDialogFooter><AlertDialogCancel>{t('cl.cancel')}</AlertDialogCancel><AlertDialogAction onClick={onOk}>{titre}</AlertDialogAction></AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

function Contacts({ clientId, peutEcrire, peutGerer }) {
  const { t } = useTranslation();
  const [rows, setRows] = useState(null);
  const [f, setF] = useState(null);
  const charger = useCallback(() => api.get(`/clients/${clientId}/contacts`).then((r) => setRows(r.data)), [clientId]);
  useEffect(() => { charger(); }, [charger]);
  const enregistrer = async (e) => {
    e.preventDefault();
    try {
      if (f.id) await api.patch(`/contacts/${f.id}`, f); else await api.post(`/clients/${clientId}/contacts`, f);
      setF(null); charger(); toast.success(t('cl.saved'));
    } catch (err) { toast.error(apiError(err)); }
  };
  if (!rows) return <Skeleton className="h-24 w-full" />;
  return (
    <div>
      {peutEcrire && <Button size="sm" className="mb-4 gap-1.5" onClick={() => setF({ prenom: '', nom: '', fonction: '', email: '', telephone: '', mobile: '', langue: 'fr', principal: rows.length === 0, accepte_relances: true })}><Plus className="h-4 w-4" />{t('cl.contact_new')}</Button>}
      <div className="grid gap-3 md:grid-cols-2">
        {rows.map((c) => (
          <div key={c.id} className="rounded-xl border border-border p-4 text-sm">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="font-medium">{[c.prenom, c.nom].filter(Boolean).join(' ') || '—'} {c.principal && <Star className="ml-1 inline h-3.5 w-3.5 fill-accent text-accent" aria-label={t('cl.c_main')} />}</div>
                {c.fonction && <div className="text-xs text-muted-foreground">{c.fonction}</div>}
              </div>
              {!c.accepte_relances && <span className="flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800"><BellOff className="h-3 w-3" />{t('cl.c_refuses')}</span>}
            </div>
            <div className="mt-2 space-y-1 text-muted-foreground">
              {c.email && <div className="flex items-center gap-2"><Mail className="h-3.5 w-3.5" /><a className="hover:text-foreground" href={`mailto:${c.email}`}>{c.email}</a></div>}
              {(c.telephone || c.mobile) && <div className="flex items-center gap-2"><Phone className="h-3.5 w-3.5" />{[c.telephone, c.mobile].filter(Boolean).join(' · ')}</div>}
            </div>
            <div className="mt-3 flex gap-2">
              {peutEcrire && <Button size="sm" variant="ghost" onClick={() => setF(c)}><Pencil className="mr-1 h-3.5 w-3.5" />{t('cl.edit')}</Button>}
              {peutGerer && (
                <Confirmer titre={t('cl.anonymize')} texte={t('cl.anonymize_confirm')}
                  onOk={async () => { try { await api.post(`/contacts/${c.id}/anonymiser`); charger(); } catch (e) { toast.error(apiError(e)); } }}>
                  <Button size="sm" variant="ghost" className="text-muted-foreground"><UserX className="mr-1 h-3.5 w-3.5" />{t('cl.anonymize')}</Button>
                </Confirmer>
              )}
            </div>
          </div>
        ))}
      </div>
      <Dialog open={!!f} onOpenChange={(o) => !o && setF(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>{f?.id ? t('cl.edit') : t('cl.contact_new')}</DialogTitle></DialogHeader>
          {f && (
            <form onSubmit={enregistrer} className="grid gap-3 sm:grid-cols-2">
              {[['prenom', 'c_first'], ['nom', 'c_last'], ['fonction', 'c_role'], ['email', 'f_email'], ['telephone', 'f_phone'], ['mobile', 'c_mobile']].map(([k, l]) => (
                <label key={k} className="text-sm"><span className="mb-1 block text-xs text-muted-foreground">{t(`cl.${l}`)}</span>
                  <Input value={f[k] || ''} type={k === 'email' ? 'email' : 'text'} onChange={(e) => setF({ ...f, [k]: e.target.value })} /></label>
              ))}
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!f.principal} onChange={(e) => setF({ ...f, principal: e.target.checked })} />{t('cl.c_main')}</label>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!f.accepte_relances} onChange={(e) => setF({ ...f, accepte_relances: e.target.checked })} />{t('cl.c_consent')}</label>
              <div className="flex justify-end gap-2 sm:col-span-2"><Button type="button" variant="ghost" onClick={() => setF(null)}>{t('cl.cancel')}</Button><Button type="submit">{t('cl.save')}</Button></div>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Chantiers({ clientId, peutEcrire }) {
  const { t } = useTranslation();
  const [rows, setRows] = useState(null);
  const [f, setF] = useState(null);
  const charger = useCallback(() => api.get(`/clients/${clientId}/chantiers`).then((r) => setRows(r.data)), [clientId]);
  useEffect(() => { charger(); }, [charger]);
  const enregistrer = async (e) => {
    e.preventDefault();
    try {
      if (f.id) await api.patch(`/chantiers/${f.id}`, f); else await api.post(`/clients/${clientId}/chantiers`, f);
      setF(null); charger(); toast.success(t('cl.saved'));
    } catch (err) { toast.error(apiError(err)); }
  };
  if (!rows) return <Skeleton className="h-24 w-full" />;
  return (
    <div>
      {peutEcrire && <Button size="sm" className="mb-4 gap-1.5" onClick={() => setF({ nom: '', code_site: '', adresse: { ligne1: '', code_postal: '', ville: '' }, acces: '' })}><Plus className="h-4 w-4" />{t('cl.site_new')}</Button>}
      <div className="divide-y divide-border rounded-xl border border-border">
        {rows.length === 0 && <p className="p-4 text-sm text-muted-foreground">—</p>}
        {rows.map((c) => (
          <div key={c.id} className="flex items-start justify-between gap-3 p-4 text-sm">
            <div>
              <div className="font-medium">{c.nom} {c.code_site && <span className="ml-1 rounded bg-muted px-1.5 py-0.5 font-mono text-xs">{c.code_site}</span>}</div>
              <div className="mt-1 flex items-center gap-1.5 text-muted-foreground"><MapPin className="h-3.5 w-3.5" />{[c.adresse?.ligne1, c.adresse?.code_postal, c.adresse?.ville].filter(Boolean).join(', ') || '—'}</div>
              {c.acces && <div className="mt-1 text-xs text-muted-foreground">{c.acces}</div>}
            </div>
            {peutEcrire && <Button size="sm" variant="ghost" onClick={() => setF(c)}><Pencil className="h-3.5 w-3.5" /></Button>}
          </div>
        ))}
      </div>
      <Dialog open={!!f} onOpenChange={(o) => !o && setF(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>{f?.id ? t('cl.edit') : t('cl.site_new')}</DialogTitle></DialogHeader>
          {f && (
            <form onSubmit={enregistrer} className="grid gap-3 sm:grid-cols-2">
              <label className="text-sm sm:col-span-2"><span className="mb-1 block text-xs text-muted-foreground">{t('cl.s_name')}</span><Input required value={f.nom} onChange={(e) => setF({ ...f, nom: e.target.value })} /></label>
              <label className="text-sm"><span className="mb-1 block text-xs text-muted-foreground">{t('cl.s_code')}</span><Input value={f.code_site || ''} onChange={(e) => setF({ ...f, code_site: e.target.value })} /></label>
              <label className="text-sm"><span className="mb-1 block text-xs text-muted-foreground">{t('cl.f_city')}</span><Input value={f.adresse?.ville || ''} onChange={(e) => setF({ ...f, adresse: { ...f.adresse, ville: e.target.value } })} /></label>
              <label className="text-sm sm:col-span-2"><span className="mb-1 block text-xs text-muted-foreground">{t('cl.f_address')}</span><Input value={f.adresse?.ligne1 || ''} onChange={(e) => setF({ ...f, adresse: { ...f.adresse, ligne1: e.target.value } })} /></label>
              <label className="text-sm sm:col-span-2"><span className="mb-1 block text-xs text-muted-foreground">{t('cl.s_access')}</span><Textarea rows={2} value={f.acces || ''} onChange={(e) => setF({ ...f, acces: e.target.value })} /></label>
              <div className="flex justify-end gap-2 sm:col-span-2"><Button type="button" variant="ghost" onClick={() => setF(null)}>{t('cl.cancel')}</Button><Button type="submit">{t('cl.save')}</Button></div>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Journal({ clientId, peutEcrire }) {
  const { t } = useTranslation();
  const [rows, setRows] = useState(null);
  const [type, setType] = useState('note');
  const [texte, setTexte] = useState('');
  const charger = useCallback(() => api.get(`/clients/${clientId}/echanges`).then((r) => setRows(r.data)), [clientId]);
  useEffect(() => { charger(); }, [charger]);
  const ajouter = async () => {
    if (!texte.trim()) return;
    try { await api.post(`/clients/${clientId}/echanges`, { type, resume: texte }); setTexte(''); charger(); } catch (e) { toast.error(apiError(e)); }
  };
  return (
    <div>
      {peutEcrire && (
        <div className="mb-5 flex flex-col gap-2 sm:flex-row">
          <select className={`${selectCls} sm:w-40`} value={type} onChange={(e) => setType(e.target.value)}>
            {['note', 'appel', 'email', 'visite'].map((x) => <option key={x} value={x}>{t(`cl.log_types.${x}`)}</option>)}
          </select>
          <Input value={texte} onChange={(e) => setTexte(e.target.value)} placeholder={t('cl.log_placeholder')} onKeyDown={(e) => e.key === 'Enter' && ajouter()} />
          <Button onClick={ajouter}>{t('cl.log_add')}</Button>
        </div>
      )}
      {!rows ? <Skeleton className="h-24 w-full" /> : (
        <ol className="relative space-y-4 border-l border-border pl-5">
          {rows.length === 0 && <li className="text-sm text-muted-foreground">—</li>}
          {rows.map((e) => (
            <li key={e.id} className="text-sm">
              <span className="absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full bg-accent" />
              <div className="text-xs text-muted-foreground">{dtfr(e.survenu_le)} · {t(`cl.log_types.${e.type}`)}{e.auteur ? ` · ${e.auteur}` : ''}</div>
              <div className="mt-0.5">{e.resume}</div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function DevisDemandes({ clientId }) {
  const { t } = useTranslation();
  const [d, setD] = useState(null);
  useEffect(() => { api.get(`/clients/${clientId}/devis`).then((r) => setD(r.data)); }, [clientId]);
  if (!d) return <Skeleton className="h-24 w-full" />;
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div>
        <h3 className="mb-2 text-sm font-semibold">{t('cl.quotes')}</h3>
        <div className="divide-y divide-border rounded-xl border border-border">
          {d.devis.length === 0 && <p className="p-4 text-sm text-muted-foreground">—</p>}
          {d.devis.map((q) => (
            <Link key={q.id} to={`/app/quotes/${q.id}`} className="flex items-center justify-between gap-3 p-3 text-sm hover:bg-muted/50">
              <span><span className="font-medium">{q.number || q.id.slice(0, 8)}</span> <span className="text-muted-foreground">{q.object || ''}</span></span>
              <span className="flex items-center gap-2 whitespace-nowrap"><span className="tabular">{euro(q.total_ht)}</span>
                {q.issue && <span className={`rounded-full px-2 py-0.5 text-xs ${q.issue === 'accepte' ? 'bg-accent/15 text-accent' : q.issue === 'refuse' ? 'bg-destructive/10 text-destructive' : 'bg-muted'}`}>{t(`cl.issue.${q.issue}`)}</span>}</span>
            </Link>
          ))}
        </div>
      </div>
      <div>
        <h3 className="mb-2 text-sm font-semibold">{t('cl.requests')}</h3>
        <div className="divide-y divide-border rounded-xl border border-border">
          {d.demandes.length === 0 && <p className="p-4 text-sm text-muted-foreground">—</p>}
          {d.demandes.map((r) => (
            <Link key={r.id} to={`/app/requests/${r.id}`} className="flex items-center justify-between p-3 text-sm hover:bg-muted/50">
              <span className="font-medium">{r.title}</span><span className="text-muted-foreground">{dfr(r.created_at)}</span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function ClientDetail() {
  const { id } = useParams();
  const { t } = useTranslation();
  const { tenant } = useAuth();
  const peutEcrire = ['owner', 'admin', 'operator'].includes(tenant?.role);
  const peutGerer = ['owner', 'admin'].includes(tenant?.role);
  const [c, setC] = useState(null);
  const [k, setK] = useState(null);
  const [onglet, setOnglet] = useState('overview');
  const [edition, setEdition] = useState(false);
  const charger = useCallback(() => {
    api.get(`/clients/${id}`).then((r) => setC(r.data)).catch((e) => toast.error(apiError(e)));
    api.get(`/clients/${id}/resume`).then((r) => setK(r.data)).catch(() => {});
  }, [id]);
  useEffect(() => { charger(); }, [charger]);

  if (!c) return <div className="mx-auto max-w-6xl space-y-3"><Skeleton className="h-8 w-64" /><Skeleton className="h-40 w-full rounded-2xl" /></div>;
  const adr = [c.adresse?.ligne1, [c.adresse?.code_postal, c.adresse?.ville].filter(Boolean).join(' ')].filter(Boolean).join(', ');
  return (
    <div className="mx-auto max-w-6xl">
      <Link to="/app/clients" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="h-4 w-4" />{t('cl.title')}</Link>
      <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex flex-wrap items-center gap-2 font-display text-2xl font-semibold tracking-tight">
            {c.raison_sociale}
            <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium">{t(`cl.types.${c.type}`)}</span>
            {c.archive_le && <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800">{t('cl.archived')}</span>}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {[c.siret && `SIRET ${c.siret.replace(/(\d{3})(\d{3})(\d{3})(\d{5})/, '$1 $2 $3 $4')}`, adr, c.telephone, c.email].filter(Boolean).join(' · ') || '—'}
          </p>
          {c.etiquettes?.length > 0 && <div className="mt-2 flex flex-wrap gap-1.5">{c.etiquettes.map((x) => <span key={x} className="rounded-full border border-border px-2 py-0.5 text-xs">{x}</span>)}</div>}
        </div>
        <div className="flex gap-2">
          {peutEcrire && <Button variant="secondary" className="gap-1.5" onClick={() => setEdition(true)}><Pencil className="h-4 w-4" />{t('cl.edit')}</Button>}
          {peutGerer && !c.archive_le && (
            <Confirmer titre={t('cl.archive')} texte={t('cl.archive_confirm')} onOk={async () => { await api.post(`/clients/${id}/archiver`); charger(); }}>
              <Button variant="ghost" className="gap-1.5"><Archive className="h-4 w-4" />{t('cl.archive')}</Button>
            </Confirmer>
          )}
          {peutGerer && c.archive_le && <Button variant="ghost" className="gap-1.5" onClick={async () => { await api.post(`/clients/${id}/restaurer`); charger(); }}><RotateCcw className="h-4 w-4" />{t('cl.restore')}</Button>}
        </div>
      </div>

      <div className="mt-5 flex gap-1 overflow-x-auto border-b border-border" role="tablist">
        {ONGLETS.map((o) => (
          <button key={o} type="button" role="tab" aria-selected={onglet === o} onClick={() => setOnglet(o)}
            className={`whitespace-nowrap border-b-2 px-3.5 py-2.5 text-sm font-medium transition-colors ${onglet === o ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'}`}>
            {t(`cl.tab_${o}`)}
          </button>
        ))}
      </div>

      <Card className="card-shadow mt-4 border-0 p-5">
        {onglet === 'overview' && (
          !k ? <Skeleton className="h-24 w-full" /> : (
            <div>
              <div className="grid gap-3 md:grid-cols-4">
                <Kpi label={t('cl.k_signed')} value={euro(k.signe_ht)} />
                <Kpi label={t('cl.k_pending')} value={k.en_attente} sub={euro(k.en_attente_ht)} />
                <Kpi label={t('cl.k_rate')} value={k.taux_transformation === null ? '—' : `${Math.round(k.taux_transformation * 100)} %`} sub={k.conclus ? `${k.acceptes} / ${k.conclus}` : t('cl.k_none')} />
                <Kpi label={t('cl.k_delay')} value={k.delai_reponse_j === null ? '—' : t('cl.k_days', { n: k.delai_reponse_j })} />
              </div>
              <div className="mt-4 rounded-xl bg-muted/50 p-4 text-sm">
                <span className="font-medium">{t('cl.next_followup')} : </span>
                {k.prochaine_relance
                  ? <>{k.prochaine_relance.numero} · {dtfr(k.prochaine_relance.echeance)} · {t(`cl.canal.${k.prochaine_relance.canal}`)} — <span className="text-muted-foreground">{k.prochaine_relance.raison}</span></>
                  : <span className="text-muted-foreground">{t('cl.no_followup')}</span>}
              </div>
              {c.notes && <p className="mt-4 whitespace-pre-wrap text-sm text-muted-foreground">{c.notes}</p>}
            </div>
          )
        )}
        {onglet === 'contacts' && <Contacts clientId={id} peutEcrire={peutEcrire} peutGerer={peutGerer} />}
        {onglet === 'sites' && <Chantiers clientId={id} peutEcrire={peutEcrire} />}
        {onglet === 'quotes' && <DevisDemandes clientId={id} />}
        {onglet === 'log' && <Journal clientId={id} peutEcrire={peutEcrire} />}
        {onglet === 'followups' && <RelancesClient clientId={id} />}
      </Card>

      <Dialog open={edition} onOpenChange={setEdition}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader><DialogTitle>{t('cl.edit')}</DialogTitle></DialogHeader>
          <ClientForm initial={c} busy={false} onCancel={() => setEdition(false)}
            onSubmit={async (b) => { try { const { data } = await api.patch(`/clients/${id}`, b); setC(data); setEdition(false); toast.success(t('cl.saved')); } catch (e) { toast.error(apiError(e)); } }} />
        </DialogContent>
      </Dialog>
    </div>
  );
}

function RelancesClient({ clientId }) {
  const { t } = useTranslation();
  const [rows, setRows] = useState(null);
  useEffect(() => {
    api.get(`/clients/${clientId}/devis`).then(async (r) => {
      const suivis = await Promise.all(r.data.devis.slice(0, 30).map((q) => api.get(`/quotes/${q.id}/suivi`).then((s) => s.data.relances.map((x) => ({ ...x, numero: q.number })))));
      setRows(suivis.flat().sort((a, b) => new Date(b.echeance) - new Date(a.echeance)));
    });
  }, [clientId]);
  if (!rows) return <Skeleton className="h-24 w-full" />;
  if (!rows.length) return <p className="text-sm text-muted-foreground">{t('cl.no_followup')}</p>;
  return (
    <div className="divide-y divide-border rounded-xl border border-border text-sm">
      {rows.map((x) => (
        <div key={x.id} className="flex flex-wrap items-center justify-between gap-2 p-3">
          <span><span className="font-medium">{x.numero}</span> · {dtfr(x.echeance)} · {t(`cl.canal.${x.canal}`)}<br /><span className="text-xs text-muted-foreground">{x.raison}{x.motif_annulation ? ` — ${x.motif_annulation}` : ''}</span></span>
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs">{t(`cl.statut.${x.statut}`)}{x.resultat ? ` · ${t(`cl.results.${x.resultat}`)}` : ''}</span>
        </div>
      ))}
    </div>
  );
}
