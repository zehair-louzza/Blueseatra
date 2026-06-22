import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { api, API } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Spinner, EmptyState } from '@/components/Spinner';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { toast } from 'sonner';
import { BookOpen, Plus, Download, Eye, CheckCircle2, Info, PowerOff, Trash2, Pencil, Check, X } from 'lucide-react';

const verBadge = {
  active: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
  draft: 'bg-slate-100 text-slate-700 ring-slate-200',
  archived: 'bg-slate-50 text-slate-500 ring-slate-200',
};

export default function Catalogs() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [cats, setCats] = useState(null);
  const [viewing, setViewing] = useState(null);
  const [items, setItems] = useState([]);
  const [columns, setColumns] = useState([]);
  const [editingCode, setEditingCode] = useState(null);
  const [codeDraft, setCodeDraft] = useState('');

  const load = () => api.get('/catalogs').then((r) => setCats(r.data));
  useEffect(() => { load(); }, []);

  const startEditCode = (c) => { setEditingCode(c.id); setCodeDraft(c.client_code === 'N/A' ? '' : (c.client_code || '')); };
  const saveCode = async (catId) => {
    try {
      await api.patch(`/catalogs/${catId}`, { client_code: codeDraft });
      toast.success(t('cat.code_updated'));
      setEditingCode(null);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Error'); }
  };

  const activate = async (catId, verId) => { await api.post(`/catalogs/${catId}/activate/${verId}`); toast.success(t('cat.active')); load(); };
  const deactivate = async (catId) => {
    try { await api.post(`/catalogs/${catId}/deactivate`); toast.success(t('cat.deactivated')); load(); }
    catch { toast.error(t('common.loading')); }
  };
  const remove = async (catId) => {
    try { await api.delete(`/catalogs/${catId}`); toast.success(t('cat.deleted')); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || 'Error'); }
  };
  const viewItems = async (cat) => {
    const { data } = await api.get(`/catalogs/${cat.id}/items`);
    setItems(data.items);
    // Prefer the original CSV columns; fall back to union of attribute keys.
    let cols = data.columns || [];
    if (!cols.length) {
      const set = new Set();
      (data.items || []).forEach((it) => Object.keys(it.attributes || {}).forEach((k) => set.add(k)));
      cols = Array.from(set);
    }
    setColumns(cols);
    setViewing(cat);
  };
  const downloadTpl = () => { window.open(`${API}/catalog-template.csv`, '_blank'); };

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-display text-2xl font-semibold tracking-tight">{t('cat.title')}</h1>
        <div className="flex gap-2">
          <Button variant="secondary" className="gap-2" onClick={downloadTpl} data-testid="download-template-button"><Download className="h-4 w-4" />{t('cat.download_tpl')}</Button>
          <Button className="gap-2" onClick={() => navigate('/app/catalogs/import')} data-testid="import-catalog-button"><Plus className="h-4 w-4" />{t('cat.import')}</Button>
        </div>
      </div>

      <div className="mt-5">
        {!cats ? <Spinner /> : cats.length === 0 ? (
          <EmptyState icon={BookOpen} title={t('cat.no_catalogs')} action={<Button onClick={() => navigate('/app/catalogs/import')} className="gap-2"><Plus className="h-4 w-4" />{t('cat.import')}</Button>} />
        ) : (
          <div className="space-y-4">
            {cats.map((c) => (
              <Card key={c.id} className="card-shadow border-0 p-5" data-testid="catalog-card">
                <div className="space-y-3">
                  <div>
                    <h2 className="font-display text-base font-semibold">{c.name}</h2>
                    {editingCode === c.id ? (
                      <div className="mt-1 flex items-center gap-1.5">
                        <span className="text-xs text-muted-foreground">client_code:</span>
                        <Input
                          value={codeDraft}
                          onChange={(e) => setCodeDraft(e.target.value)}
                          onKeyDown={(e) => { if (e.key === 'Enter') saveCode(c.id); if (e.key === 'Escape') setEditingCode(null); }}
                          className="h-7 w-40 font-mono text-xs"
                          placeholder="N/A"
                          autoFocus
                          data-testid="client-code-input"
                        />
                        <Button size="icon" variant="ghost" className="h-7 w-7 text-emerald-600 hover:text-emerald-700" onClick={() => saveCode(c.id)} data-testid="client-code-save"><Check className="h-4 w-4" /></Button>
                        <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => setEditingCode(null)} data-testid="client-code-cancel"><X className="h-4 w-4" /></Button>
                      </div>
                    ) : (
                      <button type="button" className="group mt-1 inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground" onClick={() => startEditCode(c)} data-testid="client-code-edit">
                        client_code: <span className="font-mono">{c.client_code}</span>
                        <Pencil className="h-3 w-3 opacity-0 transition-opacity group-hover:opacity-100" />
                      </button>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Button variant="secondary" size="sm" className="gap-1" onClick={() => viewItems(c)} data-testid="view-items-button"><Eye className="h-4 w-4" />{t('cat.view_items')}</Button>
                    {c.active_version_id && (
                      <Button variant="outline" size="sm" className="gap-1" onClick={() => deactivate(c.id)} data-testid="deactivate-catalog-button"><PowerOff className="h-4 w-4" />{t('cat.deactivate')}</Button>
                    )}
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button variant="ghost" size="sm" className="gap-1 text-destructive hover:text-destructive" data-testid="delete-catalog-button"><Trash2 className="h-4 w-4" />{t('cat.delete')}</Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>{t('cat.delete_title')}</AlertDialogTitle>
                          <AlertDialogDescription>{c.name} — {t('cat.delete_desc')}</AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel data-testid="delete-cancel-button">{t('common.cancel')}</AlertDialogCancel>
                          <AlertDialogAction onClick={() => remove(c.id)} className="bg-destructive text-destructive-foreground hover:bg-destructive/90" data-testid="delete-confirm-button">{t('cat.delete')}</AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </div>
                <div className="mt-3 overflow-x-auto">
                  <Table>
                    <TableHeader><TableRow>
                      <TableHead>{t('cat.version')}</TableHead><TableHead>{t('cat.items')}</TableHead>
                      <TableHead>{t('common.status')}</TableHead><TableHead className="text-right">{t('common.actions')}</TableHead>
                    </TableRow></TableHeader>
                    <TableBody>
                      {c.versions.map((v) => (
                        <TableRow key={v.id}>
                          <TableCell className="font-mono">v{v.version_number}</TableCell>
                          <TableCell>{v.item_count}{v.error_count ? <span className="ml-2 text-xs text-rose-600">({v.error_count} err)</span> : null}</TableCell>
                          <TableCell><span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${verBadge[v.status]}`}>{t(`cat.${v.status === 'active' ? 'active' : v.status === 'draft' ? 'draft' : 'archived'}`)}</span></TableCell>
                          <TableCell className="text-right">
                            {v.status !== 'active' && <Button size="sm" variant="ghost" className="gap-1" onClick={() => activate(c.id, v.id)} data-testid="activate-version-button"><CheckCircle2 className="h-4 w-4" />{t('cat.activate')}</Button>}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      <Dialog open={!!viewing} onOpenChange={(o) => !o && setViewing(null)}>
        <DialogContent className="max-h-[80vh] overflow-auto sm:max-w-5xl">
          <DialogHeader><DialogTitle>{viewing?.name}</DialogTitle></DialogHeader>
          {columns.length === 0 ? (
            <Table>
              <TableHeader><TableRow>
                <TableHead>Code</TableHead><TableHead>Libellé</TableHead><TableHead>Cat.</TableHead>
                <TableHead>Unité</TableHead><TableHead className="text-right">PU HT</TableHead><TableHead className="text-right">TVA</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {items.map((it) => (
                  <TableRow key={it.id} data-testid="catalog-item-row">
                    <TableCell className="font-mono text-xs">{it.item_code}</TableCell>
                    <TableCell>{it.item_label}</TableCell>
                    <TableCell>{it.category}</TableCell>
                    <TableCell>{it.unit}</TableCell>
                    <TableCell className="text-right">{it.unit_price_ht} {it.currency}</TableCell>
                    <TableCell className="text-right">{it.vat_rate}%</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader><TableRow>
                  {columns.map((c) => <TableHead key={c} className="whitespace-nowrap text-xs">{c}</TableHead>)}
                  <TableHead className="text-right text-xs">{t('wiz.details')}</TableHead>
                </TableRow></TableHeader>
                <TableBody>
                  {items.map((it) => (
                    <TableRow key={it.id} data-testid="catalog-item-row">
                      {columns.map((c) => (
                        <TableCell key={c} className="whitespace-nowrap text-xs">{String((it.attributes || {})[c] ?? '')}</TableCell>
                      ))}
                      <TableCell className="text-right">
                        <Popover>
                          <PopoverTrigger asChild>
                            <Button variant="ghost" size="sm" className="h-7 gap-1 px-2" data-testid="item-details-button"><Info className="h-3.5 w-3.5" /></Button>
                          </PopoverTrigger>
                          <PopoverContent align="end" className="max-h-72 w-80 overflow-auto">
                            <p className="mb-2 text-sm font-medium">{it.item_label}</p>
                            <dl className="space-y-1 text-xs">
                              {Object.entries(it.attributes || {}).map(([k, v]) => (
                                <div key={k} className="flex justify-between gap-3">
                                  <dt className="text-muted-foreground">{k}</dt>
                                  <dd className="text-right font-medium">{String(v || '—')}</dd>
                                </div>
                              ))}
                            </dl>
                          </PopoverContent>
                        </Popover>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
