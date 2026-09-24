import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { api, apiError, API, getToken } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Plus, Upload, Download, Search, Sparkles, Building2 } from 'lucide-react';
import ClientForm, { TYPES, euro, dfr, selectCls } from '@/components/clients/ClientForm';

export default function Clients() {
  const { t } = useTranslation();
  const { tenant } = useAuth();
  const navigate = useNavigate();
  const peutEcrire = ['owner', 'admin', 'operator'].includes(tenant?.role);
  const peutGerer = ['owner', 'admin'].includes(tenant?.role);
  const [q, setQ] = useState('');
  const [type, setType] = useState('');
  const [attente, setAttente] = useState(false);
  const [archives, setArchives] = useState(false);
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [nouveau, setNouveau] = useState(false);
  const [importer, setImporter] = useState(false);
  const [busy, setBusy] = useState(false);
  const [aValider, setAValider] = useState(0);
  const fichier = useRef(null);

  const charger = useCallback(() => {
    api.get('/clients', { params: { q, type, en_attente: attente, archives, page, taille: 50 } })
      .then((r) => setData(r.data)).catch((e) => { setData({ clients: [], total: 0 }); toast.error(apiError(e)); });
  }, [q, type, attente, archives, page]);

  useEffect(() => { const x = setTimeout(charger, 250); return () => clearTimeout(x); }, [charger]);
  useEffect(() => { api.get('/suggestions-clients').then((r) => setAValider((r.data.a_valider || []).length)).catch(() => {}); }, []);

  const creer = async (body) => {
    setBusy(true);
    try { const { data: c } = await api.post('/clients', body); toast.success(t('cl.saved')); navigate(`/app/clients/${c.id}`); }
    catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };

  const reprise = async () => {
    try { const { data: r } = await api.post('/clients/reprise-devis-existants'); toast.success(t('cl.sg_reprise_done', { n: r.suggestions_creees })); navigate('/app/clients/suggestions'); }
    catch (e) { toast.error(apiError(e)); }
  };

  const envoyerImport = async () => {
    const f = fichier.current?.files?.[0];
    if (!f) return;
    const fd = new FormData(); fd.append('file', f);
    setBusy(true);
    try {
      const { data: r } = await api.post('/clients/import', fd);
      toast.success(t('cl.import_done', { n: r.crees, d: r.doublons.length }));
      setImporter(false); charger();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };

  const exporter = async () => {
    const res = await fetch(`${API}/clients-export.csv`, { headers: { Authorization: `Bearer ${getToken()}` } });
    if (!res.ok) { toast.error('Export impossible'); return; }
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement('a'); a.href = url; a.download = 'clients-blueseatra.csv'; a.click(); URL.revokeObjectURL(url);
  };

  const pages = data ? Math.max(1, Math.ceil(data.total / 50)) : 1;
  return (
    <div className="mx-auto max-w-6xl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-semibold tracking-tight">{t('cl.title')}</h1>
          {data && <p className="text-sm text-muted-foreground">{data.total} {t('cl.title').toLowerCase()}</p>}
        </div>
        <div className="flex flex-wrap gap-2">
          {aValider > 0 && (
            <Link to="/app/clients/suggestions"><Button variant="secondary" className="gap-2"><Sparkles className="h-4 w-4 text-accent" />{t('cl.sg_pending', { n: aValider })}</Button></Link>
          )}
          {peutGerer && <Button variant="ghost" className="gap-2" onClick={reprise}><Sparkles className="h-4 w-4" />{t('cl.sg_reprise')}</Button>}
          {peutGerer && <Button variant="ghost" className="gap-2" onClick={exporter}><Download className="h-4 w-4" />{t('cl.export')}</Button>}
          {peutEcrire && <Button variant="secondary" className="gap-2" onClick={() => setImporter(true)}><Upload className="h-4 w-4" />{t('cl.import')}</Button>}
          {peutEcrire && <Button className="gap-2" onClick={() => setNouveau(true)} data-testid="client-new"><Plus className="h-4 w-4" />{t('cl.new')}</Button>}
        </div>
      </div>

      <Card className="card-shadow mt-5 border-0 p-4">
        <div className="grid gap-3 md:grid-cols-12">
          <div className="relative md:col-span-6">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input className="pl-9" placeholder={t('cl.search')} value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} data-testid="client-search" />
          </div>
          <select className={`${selectCls} md:col-span-3`} value={type} onChange={(e) => { setType(e.target.value); setPage(1); }}>
            <option value="">{t('cl.all_types')}</option>
            {TYPES.map((x) => <option key={x} value={x}>{t(`cl.types.${x}`)}</option>)}
          </select>
          <div className="flex items-center gap-4 text-sm md:col-span-3">
            <label className="flex items-center gap-2"><input type="checkbox" checked={attente} onChange={(e) => { setAttente(e.target.checked); setPage(1); }} />{t('cl.pending_only')}</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={archives} onChange={(e) => { setArchives(e.target.checked); setPage(1); }} />{t('cl.archived')}</label>
          </div>
        </div>
      </Card>

      <Card className="card-shadow mt-4 overflow-hidden border-0">
        {!data ? (
          <div className="space-y-2 p-5">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-10 w-full" />)}</div>
        ) : data.clients.length === 0 ? (
          <div className="flex flex-col items-center gap-3 px-6 py-14 text-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-accent/10 text-accent"><Building2 className="h-5 w-5" /></span>
            <p className="max-w-md text-sm text-muted-foreground">{t('cl.empty')}</p>
            {peutEcrire && <Button onClick={() => setNouveau(true)} className="gap-2"><Plus className="h-4 w-4" />{t('cl.new')}</Button>}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-5 py-3 font-medium">{t('cl.col_client')}</th><th className="px-3 py-3 font-medium">{t('cl.col_type')}</th>
                  <th className="px-3 py-3 font-medium">{t('cl.col_city')}</th><th className="px-3 py-3 text-right font-medium">{t('cl.col_pending')}</th>
                  <th className="px-3 py-3 font-medium">{t('cl.col_last')}</th><th className="px-5 py-3 font-medium">{t('cl.col_next')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.clients.map((c) => {
                  const retard = c.prochaine_relance && new Date(c.prochaine_relance) < new Date(new Date().toDateString());
                  return (
                    <tr key={c.id} className="cursor-pointer transition-colors hover:bg-muted/50" onClick={() => navigate(`/app/clients/${c.id}`)}>
                      <td className="px-5 py-3">
                        <div className="font-medium">{c.raison_sociale}</div>
                        {c.nom_commercial && <div className="text-xs text-muted-foreground">{c.nom_commercial}</div>}
                      </td>
                      <td className="px-3 py-3"><span className="rounded-full bg-muted px-2 py-0.5 text-xs">{t(`cl.types.${c.type}`)}</span></td>
                      <td className="px-3 py-3 text-muted-foreground">{c.ville || '—'}</td>
                      <td className="tabular px-3 py-3 text-right">{c.devis_en_cours ? <>{c.devis_en_cours} · {euro(c.montant_en_cours)}</> : '—'}</td>
                      <td className="px-3 py-3 text-muted-foreground">{dfr(c.dernier_echange)}</td>
                      <td className={`px-5 py-3 ${retard ? 'font-medium text-destructive' : ''}`}>{dfr(c.prochaine_relance)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {data && data.total > 50 && (
          <div className="flex items-center justify-between border-t border-border px-5 py-3 text-sm">
            <span className="text-muted-foreground">{t('cl.page', { p: page, n: pages })}</span>
            <div className="flex gap-2">
              <Button size="sm" variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>{t('cl.prev')}</Button>
              <Button size="sm" variant="secondary" disabled={page >= pages} onClick={() => setPage(page + 1)}>{t('cl.next')}</Button>
            </div>
          </div>
        )}
      </Card>

      <Dialog open={nouveau} onOpenChange={setNouveau}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader><DialogTitle>{t('cl.new')}</DialogTitle></DialogHeader>
          <ClientForm onSubmit={creer} onCancel={() => setNouveau(false)} busy={busy} />
        </DialogContent>
      </Dialog>

      <Dialog open={importer} onOpenChange={setImporter}>
        <DialogContent>
          <DialogHeader><DialogTitle>{t('cl.import_title')}</DialogTitle><DialogDescription>{t('cl.import_hint')}</DialogDescription></DialogHeader>
          <input ref={fichier} type="file" accept=".csv,text/csv" className="text-sm" aria-label={t('cl.import_file')} />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setImporter(false)}>{t('cl.cancel')}</Button>
            <Button onClick={envoyerImport} disabled={busy}>{t('cl.import')}</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
