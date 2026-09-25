import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { api , apiError } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from '@/components/ui/dialog';
import { Spinner, EmptyState } from '@/components/Spinner';
import { StatusBadge } from '@/components/StatusBadge';
import { toast } from 'sonner';
import { Inbox, Plus, Upload, Loader2, FileText, Trash2, Search, Flame } from 'lucide-react';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog';
import { setFilePreview } from '@/lib/filePreviewCache';

// --- Boîte de réception (ticket #85) : filtres, recherche et priorité -------
const GROUPES = {
  a_relire: ['needs_review'], en_cours: ['received', 'queued', 'processing'],
  terminees: ['done'], echec: ['failed', 'error'],
};
const sansAccent = (s) => String(s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
const client = (r) => r.extracted?.donneur_d_ordre || r.extracted?.client_name || r.extracted?.client_final || '';
const urgence = (r) => sansAccent(r.extracted?.urgency);
const echeance = (r) => {
  const v = r.extracted?.requested_date; if (!v) return null;
  const m = String(v).match(/(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})/);
  const d = m ? new Date(Number(m[3].length === 2 ? `20${m[3]}` : m[3]), Number(m[2]) - 1, Number(m[1])) : new Date(v);
  return Number.isNaN(d.getTime()) ? null : d;
};
// Priorité : à relire ou en échec d'abord, puis urgentes, puis échéance la plus proche.
const score = (r) => {
  let s = 0;
  if (['needs_review', 'failed', 'error'].includes(r.status)) s += 1000;
  if (urgence(r) === 'urgent') s += 500;
  if (!(r.quotes || []).length && r.status === 'done') s += 200;
  const e = echeance(r);
  if (e) s += Math.max(0, 150 - Math.round((e - new Date()) / 86400000) * 10);
  return s;
};

export default function Requests() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [rows, setRows] = useState(null);
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [text, setText] = useState('');
  const [file, setFile] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [recherche, setRecherche] = useState('');
  const [filtre, setFiltre] = useState('tous');
  const [tri, setTri] = useState('priorite');

  const compte = useMemo(() => {
    const c = { tous: 0, a_relire: 0, en_cours: 0, terminees: 0, echec: 0, urgentes: 0, sans_devis: 0 };
    (rows || []).forEach((r) => {
      c.tous += 1;
      Object.entries(GROUPES).forEach(([k, st]) => { if (st.includes(r.status)) c[k] += 1; });
      if (urgence(r) === 'urgent') c.urgentes += 1;
      if (r.status === 'done' && !(r.quotes || []).length) c.sans_devis += 1;
    });
    return c;
  }, [rows]);

  const visibles = useMemo(() => {
    const q = sansAccent(recherche.trim());
    let out = (rows || []).filter((r) => {
      if (filtre === 'urgentes' && urgence(r) !== 'urgent') return false;
      if (filtre === 'sans_devis' && !(r.status === 'done' && !(r.quotes || []).length)) return false;
      if (GROUPES[filtre] && !GROUPES[filtre].includes(r.status)) return false;
      if (!q) return true;
      const x = r.extracted || {};
      return sansAccent([r.title, client(r), x.client_final, x.location, x.di_number, x.request_number, ...(r.quotes || []).map((d) => d.number)].join(' ')).includes(q);
    });
    if (tri === 'priorite') out = [...out].sort((a, b) => score(b) - score(a) || String(b.created_at).localeCompare(String(a.created_at)));
    if (tri === 'echeance') out = [...out].sort((a, b) => (echeance(a) || 8.64e15) - (echeance(b) || 8.64e15));
    return out;
  }, [rows, recherche, filtre, tri]);

  const load = () => api.get('/requests').then((r) => setRows(r.data)).catch((err) => { setRows([]); toast.error(apiError(err, 'Failed')); });
  useEffect(() => { load(); }, []);

  // poll while anything is processing
  useEffect(() => {
    if (!rows) return;
    const pending = rows.some((r) => ['received', 'queued', 'processing'].includes(r.status));
    if (!pending) return;
    const id = setInterval(load, 3000);
    return () => clearInterval(id);
  }, [rows]);

  const submit = async (e) => {
    e.preventDefault();
    if (!title.trim()) { toast.error('Title required'); return; }
    if (!text.trim() && !file) { toast.error('Provide text or a file'); return; }
    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append('title', title);
      if (text.trim()) fd.append('text', text);
      if (file) fd.append('file', file);
      const { data } = await api.post('/requests', fd);
      // Le fichier original n'est jamais envoye pour stockage permanent :
      // on garde juste une reference locale (memoire de l'onglet) pour que
      // l'utilisateur puisse le revoir et le comparer a l'extraction.
      if (file && data?.id) setFilePreview(data.id, file);
      toast.success(t('req.processing'));
      setOpen(false); setTitle(''); setText(''); setFile(null);
      await load();
    } catch (err) { toast.error(apiError(err, 'Failed')); }
    finally { setSubmitting(false); }
  };

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="font-display text-2xl font-semibold tracking-tight">{t('req.title')}</h1>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild><Button className="gap-2" data-testid="new-request-button"><Plus className="h-4 w-4" />{t('req.new')}</Button></DialogTrigger>
          <DialogContent className="sm:max-w-lg">
            <DialogHeader><DialogTitle>{t('req.upload_title')}</DialogTitle></DialogHeader>
            <form onSubmit={submit} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="rtitle">{t('req.name_field')}</Label>
                <Input id="rtitle" value={title} onChange={(e) => setTitle(e.target.value)} data-testid="request-title-input" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="rtext">{t('req.paste_text')}</Label>
                <Textarea id="rtext" rows={5} value={text} onChange={(e) => setText(e.target.value)} data-testid="request-text-input" placeholder="..." />
              </div>
              <div className="space-y-1.5">
                <Label>{t('req.or_upload')}</Label>
                <label className="flex cursor-pointer items-center gap-2 rounded-xl border border-dashed bg-card px-4 py-3 text-sm text-muted-foreground transition-colors hover:bg-muted/40" data-testid="file-dropzone">
                  <Upload className="h-4 w-4" />
                  <span>{file ? file.name : t('req.file_hint')}</span>
                  <input type="file" className="hidden" accept=".pdf,.docx,.xlsx,.xlsm,.csv,.tsv,.txt,.png,.jpg,.jpeg,.webp" onChange={(e) => setFile(e.target.files[0])} data-testid="request-file-input" />
                </label>
                {file && (
                  <button
                    type="button"
                    className="text-xs text-primary underline underline-offset-2"
                    onClick={() => window.open(URL.createObjectURL(file), '_blank', 'noopener')}
                    data-testid="preview-selected-file-button"
                  >
                    {t('req.view_file')}
                  </button>
                )}
              </div>
              <DialogFooter>
                <Button type="submit" disabled={submitting} className="w-full" data-testid="submit-request-button">
                  {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}{t('req.submit')}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {rows && rows.length > 0 && (
        <div className="mt-5 space-y-3" data-testid="requests-filters">
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative min-w-[240px] flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input className="pl-9" value={recherche} onChange={(e) => setRecherche(e.target.value)} placeholder={t('cl.r_rech')} data-testid="requests-search" />
            </div>
            <label className="flex items-center gap-2 text-sm text-muted-foreground">{t('cl.r_tri')}
              <select className="h-9 rounded-md border border-input bg-background px-2 text-sm text-foreground" value={tri} onChange={(e) => setTri(e.target.value)} data-testid="requests-sort">
                <option value="priorite">{t('cl.r_tri_priorite')}</option>
                <option value="recent">{t('cl.r_tri_recent')}</option>
                <option value="echeance">{t('cl.r_tri_echeance')}</option>
              </select>
            </label>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {['tous', 'a_relire', 'en_cours', 'terminees', 'echec', 'urgentes', 'sans_devis'].map((k) => (
              <button key={k} type="button" onClick={() => setFiltre(k)} data-testid={`requests-filter-${k}`}
                className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${filtre === k ? 'border-primary bg-primary text-primary-foreground' : 'border-border bg-card text-muted-foreground hover:text-foreground'}`}>
                {t(k === 'tous' ? 'cl.r_tous' : `cl.r_${k}`)} <span className="opacity-70">{compte[k]}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="mt-4">
        {!rows ? <Spinner /> : rows.length === 0 ? (
          <EmptyState icon={Inbox} title={t('req.no_requests')} action={<Button onClick={() => setOpen(true)} className="gap-2"><Plus className="h-4 w-4" />{t('req.new')}</Button>} />
        ) : visibles.length === 0 ? (
          <p className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">{t('cl.r_aucun_resultat')}</p>
        ) : (
          <Card className="card-shadow overflow-hidden border-0">
            <Table data-testid="requests-table">
              <TableHeader>
                <TableRow>
                  <TableHead>{t('req.name_field')}</TableHead>
                  <TableHead>{t('cl.r_client')}</TableHead>
                  <TableHead>{t('cl.r_echeance')}</TableHead>
                  <TableHead>{t('req.line_items')}</TableHead>
                  <TableHead>{t('cl.r_devis')}</TableHead>
                  <TableHead>{t('common.status')}</TableHead>
                  <TableHead className="text-right">{t('common.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {visibles.map((r) => (
                  <TableRow key={r.id} className="cursor-pointer" onClick={() => navigate(`/app/requests/${r.id}`)} data-testid="requests-table-row">
                    <TableCell className="font-medium"><span className="flex items-center gap-2"><FileText className="h-4 w-4 shrink-0 text-muted-foreground" />{r.title}
                      {urgence(r) === 'urgent' && <span className="inline-flex items-center gap-0.5 rounded-full bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700 ring-1 ring-red-200"><Flame className="h-3 w-3" />{t('cl.r_urgent')}</span>}
                      {r.language && <span className="text-xs uppercase text-muted-foreground">{r.language}</span>}</span></TableCell>
                    <TableCell className="max-w-[220px] truncate">{client(r) || '\u2014'}</TableCell>
                    <TableCell className="whitespace-nowrap">{echeance(r) ? echeance(r).toLocaleDateString('fr-FR') : '\u2014'}</TableCell>
                    <TableCell>{r.extracted?.line_items?.length ?? '\u2014'}</TableCell>
                    <TableCell onClick={(e) => e.stopPropagation()}>{(r.quotes || []).length ? (r.quotes || []).slice(0, 2).map((d) => (
                      <button key={d.id} type="button" className="mr-1 whitespace-nowrap font-mono text-xs text-primary hover:underline" onClick={() => navigate(`/app/quotes/${d.id}`)}>{d.number}</button>
                    )) : <span className="text-xs text-muted-foreground">{'\u2014'}</span>}</TableCell>
                    <TableCell><StatusBadge status={r.status} queuePosition={r.queue_position} /></TableCell>
                    <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="sm" onClick={() => navigate(`/app/requests/${r.id}`)}>{t('common.open')}</Button>
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button variant="ghost" size="sm" className="gap-1 text-destructive hover:text-destructive" data-testid="request-delete-button"><Trash2 className="h-4 w-4" />{t('req.delete')}</Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>{t('req.delete_title')}</AlertDialogTitle>
                              <AlertDialogDescription>{r.title} — {t('req.delete_desc')}</AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                              <AlertDialogAction onClick={async () => {
                                try { await api.delete(`/requests/${r.id}`); toast.success(t('req.deleted')); load(); }
                                catch (err) { toast.error(apiError(err, 'Failed')); }
                              }} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">{t('req.delete')}</AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        )}
      </div>
    </div>
  );
}
