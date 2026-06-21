import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { api, API, getToken } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Spinner } from '@/components/Spinner';
import { StatusBadge } from '@/components/StatusBadge';
import { toast } from 'sonner';
import { ArrowLeft, Save, CheckCircle2, Download, Send, Info, Loader2 } from 'lucide-react';

export default function QuoteEditor() {
  const { t } = useTranslation();
  const { id } = useParams();
  const navigate = useNavigate();
  const [q, setQ] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = () => api.get(`/quotes/${id}`).then((r) => setQ(r.data));
  useEffect(() => { load(); }, [id]);

  const updateLine = (i, field, val) => {
    const lines = [...q.lines];
    lines[i] = { ...lines[i], [field]: val };
    setQ({ ...q, lines });
  };

  const save = async () => {
    setBusy(true);
    try {
      const lines = q.lines.map((l) => ({ ...l, qty: l.qty === '' ? 0 : Number(l.qty), unit_price_ht: l.unit_price_ht === null || l.unit_price_ht === '' ? null : Number(l.unit_price_ht) }));
      const { data } = await api.patch(`/quotes/${id}`, { lines, client: q.client, site: q.site, object: q.object });
      setQ(data); toast.success(t('quote.save'));
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed'); }
    finally { setBusy(false); }
  };

  const validate = async () => { await api.post(`/quotes/${id}/validate`); toast.success(t('status.validated')); load(); };
  const send = async () => { await api.post(`/quotes/${id}/send`); toast.success(t('status.sent')); load(); };
  const downloadPdf = () => { window.open(`${API}/quotes/${id}/pdf?token=${getToken()}`, '_blank'); };

  if (!q) return <Spinner />;
  const isDraft = q.status === 'draft';

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
          {isDraft && <Button size="sm" className="gap-1" onClick={validate} data-testid="validate-quote-button"><CheckCircle2 className="h-4 w-4" />{t('quote.validate')}</Button>}
          {q.status === 'validated' && <Button size="sm" className="gap-1" onClick={send} data-testid="send-quote-button"><Send className="h-4 w-4" />{t('quote.send')}</Button>}
          <Button variant="outline" size="sm" className="gap-1" onClick={downloadPdf} data-testid="download-pdf-button"><Download className="h-4 w-4" />{t('quote.pdf')}</Button>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <Card className="card-shadow overflow-hidden border-0">
            <div className="overflow-x-auto">
              <Table data-testid="quote-lines-table">
                <TableHeader><TableRow>
                  <TableHead>{t('quote.desc')}</TableHead><TableHead className="w-20">{t('quote.qty')}</TableHead>
                  <TableHead className="w-16">{t('quote.unit')}</TableHead><TableHead className="w-28">{t('quote.unit_price')}</TableHead>
                  <TableHead className="w-16">{t('quote.vat')}</TableHead><TableHead className="w-24 text-right">{t('quote.line_total')}</TableHead>
                  <TableHead className="w-24">{t('quote.match')}</TableHead>
                </TableRow></TableHeader>
                <TableBody>
                  {q.lines.map((l, i) => (
                    <TableRow key={i} data-testid="quote-line-item-row">
                      <TableCell>
                        {isDraft ? <Input value={l.description || ''} onChange={(e) => updateLine(i, 'description', e.target.value)} className="h-8" /> : (l.description || l.request_label)}
                        {l.matched_item_code && <div className="mt-0.5 font-mono text-[10px] text-muted-foreground">{l.matched_item_code}</div>}
                      </TableCell>
                      <TableCell>{isDraft ? <Input type="number" value={l.qty ?? ''} onChange={(e) => updateLine(i, 'qty', e.target.value)} className="h-8" /> : l.qty}</TableCell>
                      <TableCell>{l.unit || '\u2014'}</TableCell>
                      <TableCell>{isDraft ? <Input type="number" value={l.unit_price_ht ?? ''} onChange={(e) => updateLine(i, 'unit_price_ht', e.target.value)} className="h-8" /> : (l.unit_price_ht ?? '\u2014')}</TableCell>
                      <TableCell>{l.vat_rate != null ? `${l.vat_rate}%` : '\u2014'}</TableCell>
                      <TableCell className="text-right font-medium">{l.line_ht ?? '\u2014'}</TableCell>
                      <TableCell>
                        <TooltipProvider><Tooltip><TooltipTrigger asChild>
                          <span className="inline-flex cursor-help items-center gap-1" data-testid="quote-line-match-badge"><StatusBadge status={l.status} /><Info className="h-3 w-3 text-muted-foreground" /></span>
                        </TooltipTrigger><TooltipContent className="max-w-xs">
                          <p className="text-xs">Score: {l.score}</p>
                          <p className="text-xs text-muted-foreground">{(l.reasons || []).join(', ')}</p>
                        </TooltipContent></Tooltip></TooltipProvider>
                      </TableCell>
                    </TableRow>
                  ))}
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
                {isDraft ? <Input value={q.client || ''} onChange={(e) => setQ({ ...q, client: e.target.value })} className="h-8" /> : <div className="font-medium">{q.client || '\u2014'}</div>}
              </div>
              <div className="space-y-1.5">
                <label className="text-xs uppercase text-muted-foreground">{t('quote.site')}</label>
                {isDraft ? <Input value={q.site || ''} onChange={(e) => setQ({ ...q, site: e.target.value })} className="h-8" /> : <div className="font-medium">{q.site || '\u2014'}</div>}
              </div>
              <div className="my-3 h-px bg-border" />
              <Row label={t('quote.total_ht')} value={`${q.total_ht} ${q.currency}`} />
              <Row label={t('quote.total_vat')} value={`${q.total_vat} ${q.currency}`} />
              <div className="flex items-center justify-between border-t pt-2 font-display text-lg font-semibold text-primary"><span>{t('quote.total_ttc')}</span><span>{q.total_ttc} {q.currency}</span></div>
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

const Row = ({ label, value }) => (
  <div className="flex items-center justify-between"><span className="text-muted-foreground">{label}</span><span className="font-medium">{value}</span></div>
);
