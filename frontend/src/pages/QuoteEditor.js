import React, { useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { api, API, getToken , apiError } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Spinner } from '@/components/Spinner';
import { StatusBadge } from '@/components/StatusBadge';
import { toast } from 'sonner';
import {
  ArrowLeft, Save, CheckCircle2, Download, Send, Info, Loader2, Plus, Trash2,
  ChevronUp, ChevronDown, BookOpen, Search,
} from 'lucide-react';

const VAT_RATES = [20, 10, 5.5, 2.1, 0];
const UNITS = ['u', 'hr', 'm2', 'ml', 'ens', 'j', 'forfait'];

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
  const [search, setSearch] = useState('');

  const load = () => api.get(`/quotes/${id}`).then((r) => setQ(r.data));
  useEffect(() => { load(); }, [id]);
  useEffect(() => { api.get('/catalog/active').then((r) => setCatalog(r.data.items || [])).catch(() => {}); }, []);

  const cur = q?.currency || 'EUR';
  const isDraft = q?.status === 'draft';

  const setLines = (lines) => setQ({ ...q, lines });
  const updateLine = (i, field, val) => {
    const lines = [...q.lines];
    lines[i] = { ...lines[i], [field]: val };
    setLines(lines);
  };
  const removeLine = (i) => setLines(q.lines.filter((_, idx) => idx !== i));
  const moveLine = (i, dir) => {
    const j = i + dir;
    if (j < 0 || j >= q.lines.length) return;
    const lines = [...q.lines];
    [lines[i], lines[j]] = [lines[j], lines[i]];
    setLines(lines);
  };
  const addBlank = () => setLines([...(q.lines || []), {
    description: '', category: null, matched_item_code: null, qty: 1, unit: 'u',
    unit_price_ht: '', vat_rate: 20, status: 'to_confirm', score: 0, reasons: [],
  }]);
  const addFromCatalog = (item) => {
    setLines([...(q.lines || []), {
      description: item.item_label, category: item.category, matched_item_code: item.item_code,
      matched_label: item.item_label, qty: item.min_qty || 1, unit: item.unit,
      unit_price_ht: item.unit_price_ht, vat_rate: item.vat_rate, status: 'confirmed',
      score: 100, reasons: ['from_catalog'],
    }]);
    toast.success(item.item_label);
  };

  // live totals
  const totals = useMemo(() => {
    let ht = 0; const byRate = {};
    (q?.lines || []).forEach((l) => {
      const qty = num(l.qty); const price = num(l.unit_price_ht); const vat = num(l.vat_rate) || 0;
      if (qty !== null && price !== null) {
        const lt = qty * price; ht += lt;
        byRate[vat] = (byRate[vat] || 0) + lt * vat / 100;
      }
    });
    const vatSum = Object.values(byRate).reduce((a, b) => a + b, 0);
    return { ht: +ht.toFixed(2), vat: +vatSum.toFixed(2), ttc: +(ht + vatSum).toFixed(2), byRate };
  }, [q]);

  const save = async () => {
    setBusy(true);
    try {
      const lines = q.lines.map((l) => ({ ...l, qty: num(l.qty), unit_price_ht: num(l.unit_price_ht), vat_rate: num(l.vat_rate) }));
      const { data } = await api.patch(`/quotes/${id}`, { lines, client: q.client, site: q.site, object: q.object, client_final: q.client_final });
      setQ(data); toast.success(t('quote.save'));
    } catch (err) { toast.error(apiError(err, 'Failed')); }
    finally { setBusy(false); }
  };
  const validate = async () => {
    setBusy(true);
    try {
      const lines = q.lines.map((l) => ({ ...l, qty: num(l.qty), unit_price_ht: num(l.unit_price_ht), vat_rate: num(l.vat_rate) }));
      await api.patch(`/quotes/${id}`, { lines, client: q.client, site: q.site, object: q.object });
      await api.post(`/quotes/${id}/validate`); toast.success(t('status.validated')); await load();
    } catch (err) { toast.error(apiError(err, 'Failed')); }
    finally { setBusy(false); }
  };
  const send = async () => { await api.post(`/quotes/${id}/send`); toast.success(t('status.sent')); load(); };
  const downloadPdf = () => window.open(`${API}/quotes/${id}/pdf?token=${getToken()}`, '_blank');

  const filtered = catalog.filter((it) =>
    !search || `${it.item_code} ${it.item_label} ${it.category}`.toLowerCase().includes(search.toLowerCase()));

  if (!q) return <Spinner />;

  const vatOptions = Array.from(new Set([...VAT_RATES, ...(q.lines || []).map((l) => num(l.vat_rate)).filter((v) => v !== null)]))
    .sort((a, b) => b - a);

  return (
    <div>
      <Button variant="ghost" size="sm" className="mb-3 gap-1" onClick={() => navigate('/app/quotes')}><ArrowLeft className="h-4 w-4" />{t('common.back')}</Button>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-semibold tracking-tight">{t('quote.editor')}</h1>
          <div className="mt-1 flex items-center gap-2"><span className="font-mono text-sm text-muted-foreground">{q.number}</span><StatusBadge status={q.status} /></div>
        </div>
        <div className="flex flex-wrap gap-2">
          {isDraft && <Button variant="secondary" size="sm" className="gap-1" onClick={save} disabled={busy} data-testid="save-quote-button">{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}{t('quote.save')}</Button>}
          {isDraft && <Button size="sm" className="gap-1" onClick={validate} disabled={busy} data-testid="validate-quote-button"><CheckCircle2 className="h-4 w-4" />{t('quote.validate')}</Button>}
          {q.status === 'validated' && <Button size="sm" className="gap-1" onClick={send} data-testid="send-quote-button"><Send className="h-4 w-4" />{t('quote.send')}</Button>}
          <Button variant="outline" size="sm" className="gap-1" onClick={downloadPdf} data-testid="download-pdf-button"><Download className="h-4 w-4" />{t('quote.pdf')}</Button>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <Card className="card-shadow overflow-hidden border-0">
            {isDraft && (
              <div className="flex flex-wrap items-center justify-between gap-2 border-b bg-muted/30 px-3 py-2">
                <span className="text-xs text-muted-foreground">{(q.lines || []).length} {t('quote.lines_count')}</span>
                <div className="flex gap-2">
                  <Dialog open={pickerOpen} onOpenChange={setPickerOpen}>
                    <DialogTrigger asChild>
                      <Button variant="outline" size="sm" className="gap-1.5" data-testid="add-from-catalog-button"><BookOpen className="h-4 w-4" />{t('quote.add_from_catalog')}</Button>
                    </DialogTrigger>
                    <DialogContent className="max-h-[80vh] overflow-hidden sm:max-w-2xl">
                      <DialogHeader><DialogTitle>{t('quote.add_from_catalog')}</DialogTitle></DialogHeader>
                      {catalog.length === 0 ? (
                        <p className="py-8 text-center text-sm text-muted-foreground">{t('quote.catalog_empty')}</p>
                      ) : (
                        <div className="space-y-3">
                          <div className="relative">
                            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                            <Input className="pl-8" placeholder={t('quote.pick_item')} value={search} onChange={(e) => setSearch(e.target.value)} data-testid="catalog-search-input" autoFocus />
                          </div>
                          <div className="max-h-[50vh] divide-y overflow-auto rounded-lg border">
                            {filtered.map((it) => (
                              <button key={it.id} onClick={() => { addFromCatalog(it); setPickerOpen(false); setSearch(''); }}
                                className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left text-sm hover:bg-muted/50" data-testid="catalog-pick-row">
                                <span>
                                  <span className="font-medium">{it.item_label}</span>
                                  <span className="ml-2 font-mono text-xs text-muted-foreground">{it.item_code}</span>
                                  <span className="ml-2 text-xs text-muted-foreground">{it.category}</span>
                                </span>
                                <span className="shrink-0 font-medium">{money(it.unit_price_ht, it.currency)}/{it.unit}</span>
                              </button>
                            ))}
                            {filtered.length === 0 && <p className="px-3 py-6 text-center text-sm text-muted-foreground">\u2014</p>}
                          </div>
                        </div>
                      )}
                    </DialogContent>
                  </Dialog>
                  <Button size="sm" className="gap-1.5" onClick={addBlank} data-testid="add-line-button"><Plus className="h-4 w-4" />{t('quote.add_line')}</Button>
                </div>
              </div>
            )}
            <div className="overflow-x-auto">
              <Table data-testid="quote-lines-table">
                <TableHeader>
                  <TableRow>
                    <TableHead className="min-w-[200px]">{t('quote.desc')}</TableHead>
                    <TableHead className="w-20">{t('quote.qty')}</TableHead>
                    <TableHead className="w-24">{t('quote.unit')}</TableHead>
                    <TableHead className="w-28">{t('quote.unit_price')}</TableHead>
                    <TableHead className="w-24">{t('quote.vat')}</TableHead>
                    <TableHead className="w-28 text-right">{t('quote.line_total')}</TableHead>
                    <TableHead className="w-24">{t('quote.match')}</TableHead>
                    {isDraft && <TableHead className="w-24"></TableHead>}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(q.lines || []).length === 0 && (
                    <TableRow><TableCell colSpan={isDraft ? 8 : 7} className="py-10 text-center text-sm text-muted-foreground">{t('quote.no_lines')}</TableCell></TableRow>
                  )}
                  {(q.lines || []).map((l, i) => {
                    const lt = (num(l.qty) !== null && num(l.unit_price_ht) !== null) ? (num(l.qty) * num(l.unit_price_ht)) : null;
                    return (
                      <TableRow key={i} data-testid="quote-line-item-row">
                        <TableCell>
                          {isDraft ? <Input value={l.description || ''} onChange={(e) => updateLine(i, 'description', e.target.value)} className="h-8" data-testid="line-description-input" /> : (l.description || l.request_label)}
                          {l.matched_item_code && <div className="mt-0.5 font-mono text-[10px] text-muted-foreground">{l.matched_item_code}</div>}
                        </TableCell>
                        <TableCell>{isDraft ? <Input type="number" step="any" value={l.qty ?? ''} onChange={(e) => updateLine(i, 'qty', e.target.value)} className="h-8" data-testid="line-qty-input" /> : (l.qty ?? '\u2014')}</TableCell>
                        <TableCell>
                          {isDraft ? (
                            <Select value={l.unit || ''} onValueChange={(v) => updateLine(i, 'unit', v)}>
                              <SelectTrigger className="h-8" data-testid="line-unit-select"><SelectValue placeholder="u" /></SelectTrigger>
                              <SelectContent>{Array.from(new Set([...(l.unit ? [l.unit] : []), ...UNITS])).map((u) => <SelectItem key={u} value={u}>{u}</SelectItem>)}</SelectContent>
                            </Select>
                          ) : (l.unit || '\u2014')}
                        </TableCell>
                        <TableCell>{isDraft ? <Input type="number" step="any" value={l.unit_price_ht ?? ''} onChange={(e) => updateLine(i, 'unit_price_ht', e.target.value)} className="h-8" data-testid="line-price-input" placeholder="0.00" /> : money(l.unit_price_ht, cur)}</TableCell>
                        <TableCell>
                          {isDraft ? (
                            <Select value={l.vat_rate != null ? String(l.vat_rate) : ''} onValueChange={(v) => updateLine(i, 'vat_rate', v)}>
                              <SelectTrigger className="h-8" data-testid="line-vat-select"><SelectValue placeholder="%" /></SelectTrigger>
                              <SelectContent>{vatOptions.map((r) => <SelectItem key={r} value={String(r)}>{r} %</SelectItem>)}</SelectContent>
                            </Select>
                          ) : (l.vat_rate != null ? `${l.vat_rate} %` : '\u2014')}
                        </TableCell>
                        <TableCell className="text-right font-medium">{lt !== null ? lt.toFixed(2) : '\u2014'}</TableCell>
                        <TableCell>
                          <TooltipProvider><Tooltip><TooltipTrigger asChild>
                            <span className="inline-flex cursor-help items-center gap-1" data-testid="quote-line-match-badge"><StatusBadge status={l.status} /><Info className="h-3 w-3 text-muted-foreground" /></span>
                          </TooltipTrigger><TooltipContent className="max-w-xs">
                            <p className="text-xs">Score: {l.score ?? 0}</p>
                            <p className="text-xs text-muted-foreground">{(l.reasons || []).join(', ') || '\u2014'}</p>
                          </TooltipContent></Tooltip></TooltipProvider>
                        </TableCell>
                        {isDraft && (
                          <TableCell>
                            <div className="flex items-center gap-0.5">
                              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => moveLine(i, -1)} disabled={i === 0} title={t('quote.move_up')} data-testid="line-move-up"><ChevronUp className="h-4 w-4" /></Button>
                              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => moveLine(i, 1)} disabled={i === q.lines.length - 1} title={t('quote.move_down')} data-testid="line-move-down"><ChevronDown className="h-4 w-4" /></Button>
                              <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive" onClick={() => removeLine(i)} title={t('quote.remove')} data-testid="line-remove-button"><Trash2 className="h-4 w-4" /></Button>
                            </div>
                          </TableCell>
                        )}
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
                  {q.meta.request_number && <div className="flex justify-between"><span className="text-muted-foreground">{t('req.request_no')}</span><span className="font-mono">{q.meta.request_number}</span></div>}
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
              {q.pricing_snapshot?.catalog_name} \u00b7 v{q.pricing_snapshot?.version_number}
              <p className="mt-1">{t('quote.pricing_note')}</p>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

const Row = ({ label, value, muted }) => (
  <div className="flex items-center justify-between"><span className={muted ? 'text-muted-foreground' : 'text-muted-foreground'}>{label}</span><span className={muted ? 'text-sm' : 'font-medium'}>{value}</span></div>
);
