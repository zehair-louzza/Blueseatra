import React, { useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { api, API, getToken, apiError } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Spinner } from '@/components/Spinner';
import { StatusBadge } from '@/components/StatusBadge';
import { toast } from 'sonner';
import {
  ArrowLeft, Save, CheckCircle2, Download, Send, Info, Loader2, Plus, Trash2,
  ChevronUp, ChevronDown, BookOpen, Search, Wrench, Package, StickyNote, SeparatorHorizontal,
  Copy, RotateCcw, RefreshCw, Truck, Layers, FolderTree,
} from 'lucide-react';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog';

const VAT_RATES = [20, 10, 5.5, 2.1, 0];
const UNITS = ['u', 'hr', 'm2', 'm3', 'ml', 'ens', 'sac', 'tonne', 'j', 'forfait'];
const NOSPIN = '[appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none';

const num = (v) => {
  if (v === '' || v === null || v === undefined) return null;
  const n = parseFloat(String(v).replace(',', '.'));
  return Number.isNaN(n) ? null : n;
};
const money = (v, cur = 'EUR') => (v === null || v === undefined ? '\u2014' : `${Number(v).toFixed(2)} ${cur}`);

export default function QuoteEditor() {
  const { t } = useTranslation();
  const { id } = useParams();
  const navigate = useNavigate();
  const [q, setQ] = useState(null);
  const [busy, setBusy] = useState(false);
  const [catalog, setCatalog] = useState([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [catalogError, setCatalogError] = useState(false);
  const [search, setSearch] = useState('');
  const [family, setFamily] = useState('__all__');
  const [supplierBy, setSupplierBy] = useState({});

  const load = () => api.get(`/quotes/${id}`).then((r) => setQ(r.data));
  useEffect(() => { load(); }, [id]);
  const loadCatalog = (q = '') => {
    setCatalogLoading(true);
    setCatalogError(false);
    api.get('/catalog/search', { params: { q, limit: 40 } })
      .then((r) => { setCatalog(r.data.items || []); })
      .catch(() => { setCatalog([]); setCatalogError(true); })
      .finally(() => setCatalogLoading(false));
  };
  useEffect(() => { if (pickerOpen) loadCatalog(search); }, [pickerOpen]);
  useEffect(() => {
    if (!pickerOpen) return undefined;
    const t = setTimeout(() => loadCatalog(search), 200);
    return () => clearTimeout(t);
  }, [search, pickerOpen]);

  const cur = q?.currency || 'EUR';
  const isDraft = q?.status === 'draft';
  const colSpan = isDraft ? 9 : 8;

  const setLines = (lines) => setQ({ ...q, lines });
  const updateLine = (i, field, val) => { const lines = [...q.lines]; lines[i] = { ...lines[i], [field]: val }; setLines(lines); };
  const removeLine = (i) => setLines(q.lines.filter((_, idx) => idx !== i));
  const moveLine = (i, dir) => {
    const j = i + dir; if (j < 0 || j >= q.lines.length) return;
    const lines = [...q.lines]; [lines[i], lines[j]] = [lines[j], lines[i]]; setLines(lines);
  };
  const append = (line) => setLines([...(q.lines || []), line]);
  const addPriced = (type) => append({
    line_type: type,
    description: type === 'labor'
      ? "Main d'oeuvre — heures normales 7h-18h"
      : type === 'travel'
        ? 'Deplacement en Ile-de-France — heures normales 8h-18h'
        : '',
    category: type === 'labor' ? 'main_oeuvre' : type === 'travel' ? 'deplacement' : null,
    matched_item_code: type === 'labor' ? 'MO-001' : type === 'travel' ? 'DEP-001' : null,
    qty: 1, unit: type === 'labor' ? 'hr' : 'u',
    unit_price_ht: type === 'labor' ? 42 : type === 'travel' ? 40 : '',
    vat_rate: '', margin: '', status: 'to_confirm', score: 0, reasons: [],
  });
  const addNote = () => append({ line_type: 'note', description: '', status: 'note' });
  const addPageBreak = () => append({ line_type: 'page_break', status: 'page_break' });
  const addLot = () => {
    const n = (q.lines || []).filter((l) => l.line_type === 'lot').length + 1;
    append({ line_type: 'lot', description: 'Nouveau lot', lot_number: String(n), status: 'lot' });
  };
  const addSublot = () => {
    let lot = 0; let sub = 0;
    (q.lines || []).forEach((l) => {
      if (l.line_type === 'lot') { lot += 1; sub = 0; }
      if (l.line_type === 'sublot') sub += 1;
    });
    if (!lot) lot = 1;
    append({ line_type: 'sublot', description: 'Nouveau sous-lot', lot_number: `${lot}.${sub + 1}`, status: 'sublot' });
  };
  const groupSubtotal = (idx, stops) => {
    let ht = 0;
    for (let j = idx + 1; j < (q.lines || []).length; j += 1) {
      const x = q.lines[j];
      if (stops.includes(x.line_type)) break;
      if (['note', 'page_break', 'lot', 'sublot'].includes(x.line_type)) continue;
      const qty = num(x.qty); const price = num(x.unit_price_ht);
      if (qty !== null && price !== null) ht += qty * price * (1 + (num(x.margin) || 0) / 100);
    }
    return ht;
  };
  const addFromCatalog = (item, supplier) => {
    append({
      line_type: 'material', description: item.item_label || item.item_code || 'Article',
      category: item.category || '', matched_item_code: item.item_code || '',
      matched_label: item.item_label || '', brand: item.brand || '',
      supplier: supplier || item.supplier_main || (item.suppliers || [])[0] || '',
      qty: item.min_qty || 1, unit: item.unit || 'u',
      unit_price_ht: item.unit_price_ht || 0, vat_rate: '',
      margin: item.margin || 0, status: 'confirmed', score: 100, reasons: ['from_catalog'],
    });
    toast.success(item.item_label || item.item_code || 'Article');
  };

  const totals = useMemo(() => {
    let ht = 0; const byRate = {};
    (q?.lines || []).forEach((l) => {
      if (['note', 'page_break', 'lot', 'sublot'].includes(l.line_type)) return;
      const qty = num(l.qty); const price = num(l.unit_price_ht); const vat = num(l.vat_rate) || 0;
      if (qty !== null && price !== null) {
        const m = num(l.margin) || 0;
        const lt = qty * price * (1 + m / 100);
        ht += lt;
        byRate[vat] = (byRate[vat] || 0) + lt * vat / 100;
      }
    });
    const vatSum = Object.values(byRate).reduce((a, b) => a + b, 0);
    return { ht: +ht.toFixed(2), vat: +vatSum.toFixed(2), ttc: +(ht + vatSum).toFixed(2), byRate };
  }, [q]);

  const persist = async (validate = false) => {
    setBusy(true);
    try {
      const lines = q.lines.map((l) => ({ ...l, qty: num(l.qty), unit_price_ht: num(l.unit_price_ht), vat_rate: num(l.vat_rate), margin: num(l.margin) }));
      const { data } = await api.patch(`/quotes/${id}`, {
        lines, client: q.client, site: q.site, object: q.object, client_final: q.client_final,
        works_description: (q.meta && q.meta.works_description) || q.works_description || '',
      });
      setQ(data);
      if (validate) { await api.post(`/quotes/${id}/validate`); toast.success(t('status.validated')); await load(); }
      else toast.success(t('quote.save'));
    } catch (err) { toast.error(apiError(err, 'Failed')); }
    finally { setBusy(false); }
  };
  const send = async () => { await api.post(`/quotes/${id}/send`); toast.success(t('status.sent')); load(); };
  const downloadPdf = () => window.open(`${API}/quotes/${id}/pdf?token=${getToken()}`, '_blank');

  const families = useMemo(() => Array.from(new Set(catalog.map((i) => i.family).filter(Boolean))).sort(), [catalog]);
  const filtered = catalog.filter((it) =>
    (family === '__all__' || it.family === family) &&
    (!search || `${it.item_code} ${it.item_label} ${it.brand} ${it.family} ${Object.values(it.attributes || {}).join(' ')}`.toLowerCase().includes(search.toLowerCase())));

  if (!q) return <Spinner />;
  const vatOptions = Array.from(new Set([...VAT_RATES, ...(q.lines || []).map((l) => num(l.vat_rate)).filter((v) => v !== null)])).sort((a, b) => b - a);

  return (
    <div>
      <Button variant="ghost" size="sm" className="mb-3 gap-1" onClick={() => navigate('/app/quotes')}><ArrowLeft className="h-4 w-4" />{t('common.back')}</Button>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-semibold tracking-tight">{t('quote.editor')}</h1>
          <div className="mt-1 flex items-center gap-2"><span className="font-mono text-sm text-muted-foreground">{q.number}</span><StatusBadge status={q.status} /></div>
        </div>
        <div className="flex flex-wrap gap-2">
          {isDraft && <Button variant="secondary" size="sm" className="gap-1" onClick={() => persist(false)} disabled={busy} data-testid="save-quote-button">{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}{t('quote.save')}</Button>}
          {isDraft && <Button size="sm" className="gap-1" onClick={() => persist(true)} disabled={busy} data-testid="validate-quote-button"><CheckCircle2 className="h-4 w-4" />{t('quote.validate')}</Button>}
          {isDraft && <Button variant="outline" size="sm" className="gap-1" disabled={busy} onClick={async () => {
            try { const { data } = await api.post(`/quotes/${id}/rematch`); setQ(data); toast.success(t('quote.rematch')); }
            catch (err) { toast.error(apiError(err, 'Failed')); }
          }} data-testid="rematch-quote-button"><RefreshCw className="h-4 w-4" />{t('quote.rematch')}</Button>}
          {q.status === 'validated' && <Button size="sm" className="gap-1" onClick={send} data-testid="send-quote-button"><Send className="h-4 w-4" />{t('quote.send')}</Button>}
          {(q.status === 'validated' || q.status === 'sent') && <Button variant="secondary" size="sm" className="gap-1" onClick={async () => {
            try { const { data } = await api.post(`/quotes/${id}/reopen`); setQ(data); toast.success(t('quote.reopened')); }
            catch (err) { toast.error(apiError(err, 'Failed')); }
          }} data-testid="reopen-quote-button"><RotateCcw className="h-4 w-4" />{t('quote.reopen')}</Button>}
          <Button variant="outline" size="sm" className="gap-1" onClick={async () => {
            try { const { data } = await api.post(`/quotes/${id}/duplicate`); toast.success(t('quote.duplicated')); navigate(`/app/quotes/${data.id}`); }
            catch (err) { toast.error(apiError(err, 'Failed')); }
          }} data-testid="duplicate-quote-button"><Copy className="h-4 w-4" />{t('quote.duplicate')}</Button>}
          <Button variant="outline" size="sm" className="gap-1" onClick={downloadPdf} data-testid="download-pdf-button"><Download className="h-4 w-4" />{t('quote.pdf')}</Button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="ghost" size="sm" className="gap-1 text-destructive hover:text-destructive" data-testid="delete-quote-editor-button"><Trash2 className="h-4 w-4" />{t('quote.delete')}</Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>{t('quote.delete_title')}</AlertDialogTitle>
                <AlertDialogDescription>{q.number} — {t('quote.delete_desc')}</AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                <AlertDialogAction onClick={async () => {
                  try { await api.delete(`/quotes/${id}`); toast.success(t('quote.deleted')); navigate('/app/quotes'); }
                  catch (err) { toast.error(apiError(err, 'Failed')); }
                }} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">{t('quote.delete')}</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <Card className="card-shadow overflow-hidden border-0">
            {isDraft && (
              <div className="flex flex-wrap items-center gap-2 border-b bg-muted/30 px-3 py-2">
                <Button variant="outline" size="sm" className="gap-1.5" data-testid="add-from-catalog-button" onClick={() => setPickerOpen(true)}><BookOpen className="h-4 w-4" />{t('quote.add_from_catalog')}</Button>
                <Dialog open={pickerOpen} onOpenChange={setPickerOpen}>
                  <DialogContent className="z-[100] max-h-[82vh] overflow-hidden sm:max-w-3xl">
                    <DialogHeader>
                      <DialogTitle>{t('quote.add_from_catalog')}</DialogTitle>
                      <DialogDescription className="sr-only">{t('quote.pick_item')}</DialogDescription>
                    </DialogHeader>
                    {catalogLoading ? (
                      <div className="flex justify-center py-10"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
                    ) : catalogError ? (
                      <p className="py-8 text-center text-sm text-muted-foreground">{t('quote.catalog_empty')}</p>
                    ) : catalog.length === 0 ? (
                      <p className="py-8 text-center text-sm text-muted-foreground">{t('quote.catalog_empty')}</p>
                    ) : (
                      <div className="space-y-3">
                        <div className="flex flex-col gap-2 sm:flex-row">
                          <Select value={family} onValueChange={setFamily}>
                            <SelectTrigger className="sm:w-64" data-testid="family-filter"><SelectValue /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="__all__">{t('quote.all_families')}</SelectItem>
                              {families.map((f) => <SelectItem key={f} value={f}>{f}</SelectItem>)}
                            </SelectContent>
                          </Select>
                          <div className="relative flex-1">
                            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                            <Input className="pl-8" placeholder={t('quote.pick_item')} value={search} onChange={(e) => setSearch(e.target.value)} data-testid="catalog-search-input" autoFocus />
                          </div>
                        </div>
                        <div className="max-h-[55vh] divide-y overflow-auto rounded-lg border">
                          {filtered.map((it) => {
                            const sup = supplierBy[it.id] || it.supplier_main || (it.suppliers || [])[0] || '';
                            return (
                              <div key={it.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2.5 text-sm hover:bg-muted/40" data-testid="catalog-pick-row">
                                <div className="min-w-[180px] flex-1">
                                  <div className="font-medium">{it.item_label}</div>
                                  <div className="text-xs text-muted-foreground">
                                    {it.family && <span className="rounded bg-muted px-1.5 py-0.5 font-medium text-foreground">{it.family}</span>}
                                    {it.brand && <span className="ml-1.5">{it.brand}</span>}
                                    {it.item_code && <span className="ml-1.5 font-mono">{it.item_code}</span>}
                                  </div>
                                </div>
                                <div className="flex items-center gap-2">
                                  <span className="whitespace-nowrap font-medium">{money(it.unit_price_ht, it.currency)}/{it.unit}</span>
                                  {(it.suppliers || []).length > 0 && (
                                    <Select value={sup} onValueChange={(v) => setSupplierBy({ ...supplierBy, [it.id]: v })}>
                                      <SelectTrigger className="h-8 w-44" data-testid="supplier-select"><SelectValue /></SelectTrigger>
                                      <SelectContent>{(it.suppliers || []).map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
                                    </Select>
                                  )}
                                  <Button size="sm" className="gap-1" onClick={() => { addFromCatalog(it, sup); }} data-testid="catalog-add-row"><Plus className="h-4 w-4" /></Button>
                                </div>
                              </div>
                            );
                          })}
                          {filtered.length === 0 && <p className="px-3 py-6 text-center text-sm text-muted-foreground">\u2014</p>}
                        </div>
                      </div>
                    )}
                  </DialogContent>
                </Dialog>
                <div className="mx-1 h-5 w-px bg-border" />
                <Button size="sm" className="gap-1.5" onClick={() => addPriced('generic')} data-testid="add-line-button"><Plus className="h-4 w-4" />{t('quote.add_line')}</Button>
                <Button variant="secondary" size="sm" className="gap-1.5" onClick={() => addPriced('labor')} data-testid="add-labor-button"><Wrench className="h-4 w-4" />{t('quote.add_labor')}</Button>
                <Button variant="secondary" size="sm" className="gap-1.5" onClick={() => addPriced('travel')} data-testid="add-travel-button"><Truck className="h-4 w-4" />{t('quote.add_travel')}</Button>
                <Button variant="secondary" size="sm" className="gap-1.5" onClick={() => addPriced('material')} data-testid="add-material-button"><Package className="h-4 w-4" />{t('quote.add_material')}</Button>
                <Button variant="secondary" size="sm" className="gap-1.5" onClick={addLot} data-testid="add-lot-button"><Layers className="h-4 w-4" />{t('quote.add_lot')}</Button>
                <Button variant="secondary" size="sm" className="gap-1.5" onClick={addSublot} data-testid="add-sublot-button"><FolderTree className="h-4 w-4" />{t('quote.add_sublot')}</Button>
                <Button variant="secondary" size="sm" className="gap-1.5" onClick={addNote} data-testid="add-note-button"><StickyNote className="h-4 w-4" />{t('quote.add_note')}</Button>
                <Button variant="secondary" size="sm" className="gap-1.5" onClick={addPageBreak} data-testid="add-page-break-button"><SeparatorHorizontal className="h-4 w-4" />{t('quote.add_page_break')}</Button>
              </div>
            )}
            <div className="overflow-x-auto">
              <Table data-testid="quote-lines-table">
                <TableHeader>
                  <TableRow>
                    <TableHead className="min-w-[180px]">{t('quote.desc')}</TableHead>
                    <TableHead className="w-20">{t('quote.qty')}</TableHead>
                    <TableHead className="w-24">{t('quote.unit')}</TableHead>
                    <TableHead className="w-28">{t('quote.unit_price')}</TableHead>
                    <TableHead className="w-20">
                      <span className="inline-flex items-center gap-1">{t('quote.margin')}
                        <TooltipProvider><Tooltip><TooltipTrigger asChild><Info className="h-3 w-3 text-muted-foreground" /></TooltipTrigger><TooltipContent><p className="max-w-[180px] text-xs">{t('quote.margin_hint')}</p></TooltipContent></Tooltip></TooltipProvider>
                      </span>
                    </TableHead>
                    <TableHead className="w-24">{t('quote.vat')}</TableHead>
                    <TableHead className="w-24 text-right">{t('quote.line_total')}</TableHead>
                    <TableHead className="w-20">{t('quote.match')}</TableHead>
                    {isDraft && <TableHead className="w-20"></TableHead>}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(q.lines || []).length === 0 && (
                    <TableRow><TableCell colSpan={colSpan} className="py-10 text-center text-sm text-muted-foreground">{t('quote.no_lines')}</TableCell></TableRow>
                  )}
                  {(q.lines || []).map((l, i) => {
                    const actions = isDraft ? (
                      <div className="flex items-center gap-0.5">
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => moveLine(i, -1)} disabled={i === 0} data-testid="line-move-up"><ChevronUp className="h-4 w-4" /></Button>
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => moveLine(i, 1)} disabled={i === q.lines.length - 1} data-testid="line-move-down"><ChevronDown className="h-4 w-4" /></Button>
                        <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive" onClick={() => removeLine(i)} data-testid="line-remove-button"><Trash2 className="h-4 w-4" /></Button>
                      </div>
                    ) : null;

                    if (l.line_type === 'lot' || l.line_type === 'sublot') {
                      const isLot = l.line_type === 'lot';
                      const sub = groupSubtotal(i, isLot ? ['lot'] : ['lot', 'sublot']);
                      return (
                        <TableRow key={i} className={isLot ? 'bg-emerald-50/80' : 'bg-slate-50'} data-testid={isLot ? 'quote-line-lot-row' : 'quote-line-sublot-row'}>
                          <TableCell colSpan={isDraft ? colSpan - 1 : colSpan}>
                            <div className="flex items-center gap-2">
                              {isDraft ? (
                                <Input value={l.lot_number || ''} onChange={(e) => updateLine(i, 'lot_number', e.target.value)} className="h-8 w-16 font-mono" data-testid="lot-number-input" />
                              ) : (
                                <span className="font-mono text-sm font-semibold">{l.lot_number}</span>
                              )}
                              {isDraft ? (
                                <Input value={l.description || ''} onChange={(e) => updateLine(i, 'description', e.target.value)} className="h-8 flex-1 font-semibold" data-testid="lot-title-input" />
                              ) : (
                                <span className="font-semibold">{l.description}</span>
                              )}
                              <span className="ml-auto text-sm font-semibold tabular-nums">{money(sub, cur)}</span>
                            </div>
                          </TableCell>
                          {isDraft && <TableCell>{actions}</TableCell>}
                        </TableRow>
                      );
                    }
                    if (l.line_type === 'note') {
                      return (
                        <TableRow key={i} className="bg-amber-50/40" data-testid="quote-line-note-row">
                          <TableCell colSpan={isDraft ? colSpan - 1 : colSpan}>
                            <span className="mr-2 inline-flex items-center gap-1 align-middle text-xs font-medium text-amber-700"><StickyNote className="h-3.5 w-3.5" />{t('quote.add_note')}</span>
                            {isDraft ? <Input value={l.description || ''} onChange={(e) => updateLine(i, 'description', e.target.value)} className="inline-block h-8 w-[80%] align-middle" placeholder={t('quote.note_ph')} data-testid="note-input" /> : <span className="italic text-muted-foreground">{l.description}</span>}
                          </TableCell>
                          {isDraft && <TableCell>{actions}</TableCell>}
                        </TableRow>
                      );
                    }
                    if (l.line_type === 'page_break') {
                      return (
                        <TableRow key={i} className="bg-muted/40" data-testid="quote-line-pagebreak-row">
                          <TableCell colSpan={isDraft ? colSpan - 1 : colSpan} className="text-center text-xs font-medium uppercase tracking-wide text-muted-foreground">
                            <span className="inline-flex items-center gap-1"><SeparatorHorizontal className="h-3.5 w-3.5" />{t('quote.page_break_label')}</span>
                          </TableCell>
                          {isDraft && <TableCell>{actions}</TableCell>}
                        </TableRow>
                      );
                    }

                    const lt = (num(l.qty) !== null && num(l.unit_price_ht) !== null)
                      ? (num(l.qty) * num(l.unit_price_ht) * (1 + (num(l.margin) || 0) / 100))
                      : null;
                    return (
                      <TableRow key={i} data-testid="quote-line-item-row">
                        <TableCell>
                          {l.line_type === 'labor' && <span className="mr-1 inline-flex items-center rounded bg-sky-50 px-1.5 py-0.5 text-[10px] font-medium text-sky-700">M.O.</span>}
                          {l.line_type === 'travel' && <span className="mr-1 inline-flex items-center rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-800">Dép.</span>}
                          {l.line_type === 'material' && <span className="mr-1 inline-flex items-center rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">Mat.</span>}
                          {isDraft ? <Input value={l.description || ''} onChange={(e) => updateLine(i, 'description', e.target.value)} className="h-8" data-testid="line-description-input" /> : (l.description || l.request_label)}
                          {(l.matched_item_code || l.supplier) && <div className="mt-0.5 font-mono text-[10px] text-muted-foreground">{l.matched_item_code}{l.supplier ? ` \u00b7 ${l.supplier}` : ''}</div>}
                        </TableCell>
                        <TableCell>{isDraft ? <Input type="number" step="any" value={l.qty ?? ''} onChange={(e) => updateLine(i, 'qty', e.target.value)} className={`h-8 w-full min-w-0 px-2 ${NOSPIN}`} data-testid="line-qty-input" /> : (l.qty ?? '\u2014')}</TableCell>
                        <TableCell>
                          {isDraft ? (
                            <Select value={l.unit || ''} onValueChange={(v) => updateLine(i, 'unit', v)}>
                              <SelectTrigger className="h-8" data-testid="line-unit-select"><SelectValue placeholder="u" /></SelectTrigger>
                              <SelectContent>{Array.from(new Set([...(l.unit ? [l.unit] : []), ...UNITS])).map((u) => <SelectItem key={u} value={u}>{u}</SelectItem>)}</SelectContent>
                            </Select>
                          ) : (l.unit || '\u2014')}
                        </TableCell>
                        <TableCell>{isDraft ? <Input type="number" step="any" value={l.unit_price_ht ?? ''} onChange={(e) => updateLine(i, 'unit_price_ht', e.target.value)} className={`h-8 w-full min-w-0 px-2 ${NOSPIN}`} data-testid="line-price-input" placeholder="0.00" /> : money(l.unit_price_ht, cur)}</TableCell>
                        <TableCell>{isDraft ? <Input type="number" step="any" value={l.margin ?? ''} onChange={(e) => updateLine(i, 'margin', e.target.value)} className={`h-8 w-full min-w-0 px-2 ${NOSPIN}`} data-testid="line-margin-input" placeholder="%" /> : (l.margin != null ? `${l.margin} %` : '\u2014')}</TableCell>
                        <TableCell>
                          {isDraft ? (
                            <Select value={l.vat_rate != null && l.vat_rate !== '' ? String(l.vat_rate) : ''} onValueChange={(v) => updateLine(i, 'vat_rate', v)}>
                              <SelectTrigger className="h-8" data-testid="line-vat-select"><SelectValue placeholder="%" /></SelectTrigger>
                              <SelectContent>{vatOptions.map((r) => <SelectItem key={r} value={String(r)}>{r} %</SelectItem>)}</SelectContent>
                            </Select>
                          ) : (l.vat_rate != null ? `${l.vat_rate} %` : '\u2014')}
                        </TableCell>
                        <TableCell className="text-right font-medium">{lt !== null ? lt.toFixed(2) : '\u2014'}</TableCell>
                        <TableCell>
                          <TooltipProvider><Tooltip><TooltipTrigger asChild>
                            <span className="inline-flex cursor-help items-center gap-1" data-testid="quote-line-match-badge"><StatusBadge status={l.status} /></span>
                          </TooltipTrigger><TooltipContent className="max-w-xs">
                            <p className="text-xs">Score: {l.score ?? 0}</p>
                            <p className="text-xs text-muted-foreground">{(l.reasons || []).join(', ') || '\u2014'}</p>
                          </TooltipContent></Tooltip></TooltipProvider>
                        </TableCell>
                        {isDraft && <TableCell>{actions}</TableCell>}
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          </Card>
        </div>

        <div className="lg:col-span-4">
          <Card className="card-shadow sticky top-20 border-0 p-5" data-testid="quote-totals-panel">
            <div className="space-y-2 text-sm">
              <div className="space-y-1.5">
                <label className="text-xs uppercase text-muted-foreground">{t('quote.object')}</label>
                {isDraft ? <Input value={q.object || ''} onChange={(e) => setQ({ ...q, object: e.target.value })} className="h-8" data-testid="quote-object-input" /> : <div className="font-medium">{q.object || '\u2014'}</div>}
              </div>
              <div className="space-y-1.5">
                <label className="text-xs uppercase text-muted-foreground">{t('quote.works_desc')}</label>
                {isDraft ? (
                  <textarea
                    value={(q.meta && q.meta.works_description) || ''}
                    onChange={(e) => setQ({ ...q, meta: { ...(q.meta || {}), works_description: e.target.value } })}
                    rows={6}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    data-testid="quote-works-desc"
                  />
                ) : (
                  <div className="whitespace-pre-wrap text-sm">{(q.meta && q.meta.works_description) || '\u2014'}</div>
                )}
              </div>
              <div className="space-y-1.5">
                <label className="text-xs uppercase text-muted-foreground">{t('quote.client')}</label>
                {isDraft ? <Input value={q.client || ''} onChange={(e) => setQ({ ...q, client: e.target.value })} className="h-8" data-testid="quote-client-input" /> : <div className="font-medium">{q.client || '\u2014'}</div>}
              </div>
              <div className="space-y-1.5">
                <label className="text-xs uppercase text-muted-foreground">{t('quote.site')}</label>
                {isDraft ? <Input value={q.site || ''} onChange={(e) => setQ({ ...q, site: e.target.value })} className="h-8" /> : <div className="font-medium">{q.site || '\u2014'}</div>}
              </div>
              {q.meta && (q.meta.di_number || q.meta.response_deadline || q.meta.client_final) && (
                <div className="rounded-lg bg-muted/40 p-2.5 text-xs" data-testid="quote-meta-refs">
                  {q.meta.client_final && <div className="flex justify-between"><span className="text-muted-foreground">{t('req.client_final')}</span><span className="font-medium">{q.meta.client_final}</span></div>}
                  {q.meta.di_number && <div className="flex justify-between"><span className="text-muted-foreground">{t('req.di')}</span><span className="font-mono">{q.meta.di_number}</span></div>}
                  {q.meta.response_deadline && <div className="flex justify-between"><span className="text-muted-foreground">{t('req.deadline')}</span><span className="font-medium">{q.meta.response_deadline}</span></div>}
                </div>
              )}
              <div className="my-3 h-px bg-border" />
              <Row label={t('quote.total_ht')} value={money(totals.ht, cur)} />
              {Object.entries(totals.byRate).sort((a, b) => b[0] - a[0]).map(([rate, amt]) => (
                <Row key={rate} label={`${t('quote.vat')} ${rate} %`} value={money(+amt.toFixed(2), cur)} muted />
              ))}
              {Object.keys(totals.byRate).length === 0 && <Row label={t('quote.total_vat')} value={money(totals.vat, cur)} muted />}
              <div className="flex items-center justify-between border-t pt-2 font-display text-lg font-semibold text-primary"><span>{t('quote.total_ttc')}</span><span>{money(totals.ttc, cur)}</span></div>
            </div>
            <div className="mt-4 rounded-lg bg-muted/50 p-3 text-xs text-muted-foreground">
              <div className="font-medium text-foreground">{t('quote.source')}</div>
              {q.pricing_snapshot?.catalog_name} · v{q.pricing_snapshot?.version_number}
              <p className="mt-1">{t('quote.pricing_note')}</p>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

const Row = ({ label, value, muted }) => (
  <div className="flex items-center justify-between"><span className="text-muted-foreground">{label}</span><span className={muted ? 'text-sm' : 'font-medium'}>{value}</span></div>
);
