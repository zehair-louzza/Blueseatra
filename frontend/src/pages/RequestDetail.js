import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { api , apiError } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Spinner } from '@/components/Spinner';
import { StatusBadge } from '@/components/StatusBadge';
import { toast } from 'sonner';
import { ArrowLeft, RefreshCw, FileText, Loader2 } from 'lucide-react';

export default function RequestDetail() {
  const { t } = useTranslation();
  const { id } = useParams();
  const navigate = useNavigate();
  const [req, setReq] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = () => api.get(`/requests/${id}`).then((r) => setReq(r.data));
  useEffect(() => { load(); }, [id]);
  useEffect(() => {
    if (!req || !['received', 'processing'].includes(req.status)) return;
    const x = setInterval(load, 3000); return () => clearInterval(x);
  }, [req]);

  const reprocess = async () => { await api.post(`/requests/${id}/process`); toast.success(t('req.processing')); load(); };
  const makeQuote = async () => {
    setBusy(true);
    try { const { data } = await api.post('/quotes/draft', { request_id: id }); navigate(`/app/quotes/${data.id}`); }
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
          <h1 className="font-display text-2xl font-semibold tracking-tight">{req.title}</h1>
          <div className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
            <StatusBadge status={req.status} />
            <span className="uppercase">{req.language || ''}</span>
            {req.confidence != null && <span>\u00b7 {t('req.confidence')}: {Math.round(req.confidence * 100)}%</span>}
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" className="gap-1" onClick={reprocess} data-testid="reprocess-button"><RefreshCw className="h-4 w-4" />{t('req.reprocess')}</Button>
          <Button size="sm" className="gap-1" onClick={makeQuote} disabled={busy || !ex} data-testid="make-quote-button">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}{t('req.make_quote')}
          </Button>
        </div>
      </div>

      {req.status === 'failed' && <Card className="mt-4 border-0 bg-rose-50 p-4 text-sm text-rose-800">{req.error}</Card>}

      <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card className="card-shadow border-0 p-5">
          <h2 className="mb-3 font-display text-base font-semibold">{t('req.extracted')}</h2>
          {!ex ? <Spinner label={t('req.processing')} /> : (
            <div className="space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <Field label={t('req.donneur')} value={ex.donneur_d_ordre} />
                <Field label={t('req.client_final')} value={ex.client_final} />
                <Field label={t('req.request_no')} value={ex.request_number} />
                <Field label={t('req.di')} value={ex.di_number} />
                <Field label={t('req.deadline')} value={ex.response_deadline} />
                <Field label={t('req.lang')} value={(ex.language || '').toUpperCase()} />
                <Field label={t('req.site')} value={ex.intervention_site} />
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
                        <span className="font-medium">{li.label}</span>
                        <span className="shrink-0 font-mono text-xs text-muted-foreground">{li.qty} {li.unit || ''} {li.category ? `\u00b7 ${li.category}` : ''}</span>
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
            <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-muted/50 p-3 font-mono text-xs text-muted-foreground">{req.raw_text || '\u2014'}</pre>
          )}
        </Card>
      </div>
    </div>
  );
}

const Field = ({ label, value }) => (
  <div><div className="text-xs uppercase text-muted-foreground">{label}</div><div className="font-medium">{value || '\u2014'}</div></div>
);
