import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { api , apiError } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Spinner } from '@/components/Spinner';
import { StatusBadge } from '@/components/StatusBadge';
import { toast } from 'sonner';
import { ArrowLeft, RefreshCw, FileText, Loader2, Trash2, Save } from 'lucide-react';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog';

export default function RequestDetail() {
  const { t } = useTranslation();
  const { id } = useParams();
  const navigate = useNavigate();
  const [req, setReq] = useState(null);
  const [busy, setBusy] = useState(false);
  const [title, setTitle] = useState('');
  const [rawText, setRawText] = useState('');

  const load = () => api.get(`/requests/${id}`).then((r) => {
    setReq(r.data);
    setTitle(r.data.title || '');
    setRawText(r.data.raw_text || '');
  });
  useEffect(() => { load(); }, [id]);
  useEffect(() => {
    if (!req || !['received', 'processing'].includes(req.status)) return;
    const x = setInterval(load, 3000); return () => clearInterval(x);
  }, [req]);

  const reprocess = async () => { await api.post(`/requests/${id}/process`); toast.success(t('req.processing')); load(); };
  const makeQuote = async () => {
    setBusy(true);
    try {
      const { data } = await api.post('/quotes/draft', { request_id: id });
      const n = data.option_count || 1;
      if (n > 1) toast.success(t('req.quotes_created', { n }));
      else toast.success(t('req.quote_created'));
      navigate(`/app/quotes/${data.id}`);
    }
    catch (err) { toast.error(apiError(err, 'Failed')); }
    finally { setBusy(false); }
  };

  if (!req) return <Spinner />;
  const ex = req.extracted;
  return (
    <div>
      <Button variant="ghost" size="sm" className="mb-3 gap-1" onClick={() => navigate('/app/requests')} data-testid="back-button"><ArrowLeft className="h-4 w-4" />{t('common.back')}</Button>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Input value={title} onChange={(e) => setTitle(e.target.value)} className="h-10 max-w-xl font-display text-xl font-semibold" data-testid="request-title-edit" />
          <div className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
            <StatusBadge status={req.status} />
            <span className="uppercase">{req.language || ''}</span>
            {req.confidence != null && <span>\u00b7 {t('req.confidence')}: {Math.round(req.confidence * 100)}%</span>}
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" className="gap-1" onClick={reprocess} data-testid="reprocess-button"><RefreshCw className="h-4 w-4" />{t('req.reprocess')}</Button>
          <Button variant="secondary" size="sm" className="gap-1" onClick={async () => {
            try {
              const { data } = await api.patch(`/requests/${id}`, { title, raw_text: rawText });
              setReq(data); toast.success(t('req.saved'));
            } catch (err) { toast.error(apiError(err, 'Failed')); }
          }} data-testid="save-request-button"><Save className="h-4 w-4" />{t('req.save_edits')}</Button>
          <Button size="sm" className="gap-1" onClick={makeQuote} disabled={busy || !ex} data-testid="make-quote-button">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}{t('req.make_quote')}
          </Button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="ghost" size="sm" className="gap-1 text-destructive hover:text-destructive" data-testid="delete-request-detail-button"><Trash2 className="h-4 w-4" />{t('req.delete')}</Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>{t('req.delete_title')}</AlertDialogTitle>
                <AlertDialogDescription>{t('req.delete_desc')}</AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                <AlertDialogAction onClick={async () => {
                  try { await api.delete(`/requests/${id}`); toast.success(t('req.deleted')); navigate('/app/requests'); }
                  catch (err) { toast.error(apiError(err, 'Failed')); }
                }} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">{t('req.delete')}</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>

      {req.status === 'failed' && <Card className="mt-4 border-0 bg-rose-50 p-4 text-sm text-rose-800">{req.error}</Card>}

      <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card className="card-shadow border-0 p-5">
          <h2 className="mb-3 font-display text-base font-semibold">{t('req.extracted')}</h2>
          {!ex ? <Spinner label={t('req.processing')} /> : (
            <div className="space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <Field label={t('req.donneur')} value={ex.donneur_d_ordre || ex.client_name} />
                <Field label={t('req.client_final')} value={ex.client_final || ex.client_name} />
                <Field label={t('req.request_no')} value={ex.request_number} />
                <Field label={t('req.di')} value={ex.di_number} />
                <Field label={t('req.deadline')} value={ex.response_deadline} />
                <Field label={t('req.lang')} value={(ex.language || '').toUpperCase()} />
                <Field label={t('req.site')} value={ex.intervention_site || ex.location || ex.client_address} />
                <Field label={t('req.urgency')} value={ex.urgency} />
              </div>
              {ex.intervention_address && <Field label={t('req.site')} value={ex.intervention_address} />}
              {ex.description && <p className="text-muted-foreground">{ex.description}</p>}
              {Array.isArray(ex.required_deliverables) && ex.required_deliverables.length > 0 && (
                <div>
                  <h3 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">{t('req.deliverables')}</h3>
                  <ul className="list-disc space-y-0.5 pl-5 text-muted-foreground" data-testid="required-deliverables">
                    {ex.required_deliverables.map((d, i) => <li key={i}>{d}</li>)}
                  </ul>
                </div>
              )}
              <div>
                <h3 className="mb-2 text-xs font-semibold uppercase text-muted-foreground">{t('req.line_items')}</h3>
                <div className="divide-y rounded-lg border">
                  {(ex.line_items || []).map((li, i) => (
                    <div key={i} className="px-3 py-2" data-testid="extracted-line-item">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium">{li.label || li.description}</span>
                        <span className="shrink-0 font-mono text-xs text-muted-foreground">{li.qty ?? li.quantity} {li.unit || ''} {li.category ? `\u00b7 ${li.category}` : ''}</span>
                      </div>
                      {(li.location || li.dimensions || li.specs) && (
                        <div className="mt-0.5 flex flex-wrap gap-x-3 text-xs text-muted-foreground">
                          {li.location && <span>{t('req.location')}: {li.location}</span>}
                          {li.dimensions && <span>{t('req.dimensions')}: {li.dimensions}</span>}
                          {li.specs && <span>{t('req.specs')}: {li.specs}</span>}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </Card>
        <Card className="card-shadow border-0 p-5">
          <h2 className="mb-3 font-display text-base font-semibold">{t('req.raw')}</h2>
          {req.source_type === 'image' ? (
            <p className="text-sm text-muted-foreground">{req.filename} (image)</p>
          ) : (
            <Textarea rows={10} value={rawText} onChange={(e) => setRawText(e.target.value)} className="font-mono text-xs" data-testid="request-raw-edit" />
          )}
        </Card>
      </div>
    </div>
  );
}

const Field = ({ label, value }) => (
  <div><div className="text-xs uppercase text-muted-foreground">{label}</div><div className="font-medium">{value || '\u2014'}</div></div>
);
