import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { api } from '@/lib/api';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/Spinner';
import { StatusBadge } from '@/components/StatusBadge';
import { FileText, Inbox, Plus, Wallet } from 'lucide-react';

const money = (n, lang) =>
  new Intl.NumberFormat(lang === 'fr' ? 'fr-FR' : 'en-GB', {
    style: 'currency', currency: 'EUR', maximumFractionDigits: 0,
  }).format(Number(n) || 0);

const monthLabel = (ym, lang) => {
  if (!ym) return '';
  const [y, m] = ym.split('-').map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString(lang === 'fr' ? 'fr-FR' : 'en-GB', {
    month: 'short', year: '2-digit',
  });
};

function Kpi({ label, value, hint, testid }) {
  return (
    <Card className="border-border/80 p-4" data-testid={testid}>
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-2 font-display text-2xl font-semibold tabular-nums text-foreground">{value}</p>
      {hint ? <p className="mt-1 text-xs text-muted-foreground">{hint}</p> : null}
    </Card>
  );
}

export default function Dashboard() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language?.startsWith('fr') ? 'fr' : 'en';
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [months, setMonths] = useState(6);
  const navigate = useNavigate();

  useEffect(() => {
    api.get('/dashboard')
      .then((r) => setData(r.data))
      .catch(() => setErr(true));
  }, []);

  const chart = useMemo(() => {
    const rows = data?.monthly || [];
    return rows.slice(-months).map((r) => ({
      ...r,
      label: monthLabel(r.month, lang),
    }));
  }, [data, months, lang]);

  if (err) {
    return (
      <div role="alert" className="rounded-lg border border-border bg-card p-8 text-center">
        <p className="font-medium">{t('dash.load_error')}</p>
        <Button className="mt-4" onClick={() => window.location.reload()}>{t('dash.retry')}</Button>
      </div>
    );
  }
  if (!data) return <Spinner />;

  const k = data.kpis || {};
  const funnel = data.funnel || [];
  const maxFunnel = Math.max(1, ...funnel.map((f) => f.count || 0));
  const existingQuotes = (k.drafts || 0) + (k.validated || 0);
  const validatedShare = existingQuotes ? Math.round(((k.validated || 0) / existingQuotes) * 100) : null;

  return (
    <div>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold tracking-tight">{t('dash.title')}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{t('dash.subtitle')}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" className="gap-1.5" onClick={() => navigate('/app/requests')}>
            <Inbox className="h-4 w-4" />{t('dash.cta_request')}
          </Button>
          <Button className="gap-1.5" onClick={() => navigate('/app/quotes')}>
            <Plus className="h-4 w-4" />{t('dash.cta_quotes')}
          </Button>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi testid="kpi-draft-ht" label={t('dash.kpi_draft_ht')} value={money(k.pipeline_draft_ht, lang)} hint={`${k.drafts || 0} ${t('dash.drafts').toLowerCase()}`} />
        <Kpi testid="kpi-won-ht" label={t('dash.kpi_won_ht')} value={money(k.pipeline_won_ht, lang)} hint={`${k.validated || 0} ${t('dash.validated').toLowerCase()}`} />
        <Kpi testid="kpi-action" label={t('dash.kpi_action')} value={(k.requests_review || 0) + (k.requests_failed || 0) + (k.drafts || 0)} hint={t('dash.kpi_action_hint')} />
        <Kpi testid="kpi-catalog" label={t('dash.catalog_items')} value={k.active_catalog_items ?? 0} hint={k.active_catalog_name || t('dash.no_catalog')} />
      </div>

      <div className="mt-5 grid grid-cols-1 gap-4 xl:grid-cols-5">
        <Card className="border-border/80 p-5 xl:col-span-3">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="font-display text-base font-semibold">{t('dash.chart_title')}</h2>
              <p className="text-xs text-muted-foreground">{t('dash.chart_hint')}</p>
            </div>
            <div className="flex rounded-md border border-border p-0.5" role="group" aria-label={t('dash.period')}>
              {[3, 6, 12].map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setMonths(n)}
                  className={`rounded px-2.5 py-1 text-xs font-medium ${months === n ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted'}`}
                >
                  {n} {t('dash.months')}
                </button>
              ))}
            </div>
          </div>
          <div className="h-56" aria-label={t('dash.chart_title')}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chart} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} axisLine={false} tickLine={false} width={56} tickFormatter={(v) => `${Math.round(v / 1000)}k`} />
                <Tooltip
                  formatter={(v, name) => [money(v, lang), name === 'won_ht' ? t('dash.series_won') : t('dash.series_draft')]}
                  contentStyle={{ borderRadius: 8, border: '1px solid hsl(var(--border))', fontSize: 12 }}
                />
                <Area type="monotone" dataKey="won_ht" name="won_ht" stroke="hsl(var(--accent))" fill="hsl(var(--accent))" fillOpacity={0.18} strokeWidth={2} />
                <Area type="monotone" dataKey="draft_ht" name="draft_ht" stroke="hsl(var(--primary))" fill="hsl(var(--primary))" fillOpacity={0.08} strokeWidth={1.5} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-3 flex flex-wrap gap-4 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-accent" />{t('dash.series_won')}</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-primary" />{t('dash.series_draft')}</span>
          </div>
        </Card>

        <Card className="border-border/80 p-5 xl:col-span-2">
          <h2 className="font-display text-base font-semibold">{t('dash.pipeline_title')}</h2>
          <p className="mb-4 text-xs text-muted-foreground">{t('dash.pipeline_hint')}</p>
          <ul className="space-y-3">
            {funnel.map((f) => (
              <li key={f.key}>
                <div className="mb-1 flex justify-between text-sm">
                  <span>{t(`dash.funnel_${f.key}`)}</span>
                  <span className="tabular-nums font-medium">{f.count}</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden>
                  <div className="h-full rounded-full bg-accent" style={{ width: `${Math.round((f.count / maxFunnel) * 100)}%` }} />
                </div>
              </li>
            ))}
          </ul>
          {validatedShare != null && (
            <p className="mt-4 border-t border-border pt-3 text-xs text-muted-foreground">
              {t('dash.validated_share', { pct: validatedShare })}
            </p>
          )}
        </Card>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card className="border-border/80 p-5">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-display text-base font-semibold">{t('dash.awaiting')}</h2>
            <Wallet className="h-4 w-4 text-muted-foreground" />
          </div>
          {(data.awaiting_quotes || []).length === 0 && (data.awaiting_requests || []).length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">{t('dash.empty_action')}</p>
          ) : (
            <div className="divide-y divide-border">
              {(data.awaiting_quotes || []).map((q) => (
                <button key={q.id} type="button" onClick={() => navigate(`/app/quotes/${q.id}`)} className="flex w-full items-center justify-between gap-3 py-2.5 text-left hover:bg-muted/50">
                  <span className="min-w-0">
                    <span className="block font-mono text-sm">{q.number}</span>
                    <span className="block truncate text-xs text-muted-foreground">{q.client_name || '—'}</span>
                  </span>
                  <span className="flex items-center gap-2">
                    <span className="tabular-nums text-sm">{money(q.total_ht, lang)}</span>
                    <StatusBadge status={q.status} />
                  </span>
                </button>
              ))}
              {(data.awaiting_requests || []).map((r) => (
                <button key={r.id} type="button" onClick={() => navigate(`/app/requests/${r.id}`)} className="flex w-full items-center justify-between gap-3 py-2.5 text-left hover:bg-muted/50">
                  <span className="truncate text-sm">{r.title}</span>
                  <StatusBadge status={r.status} />
                </button>
              ))}
            </div>
          )}
        </Card>

        <Card className="border-border/80 p-5">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-display text-base font-semibold">{t('dash.recent_docs')}</h2>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </div>
          {(data.recent_quotes || []).length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">{t('dash.empty')}</p>
          ) : (
            <div className="divide-y divide-border">
              {data.recent_quotes.map((q) => (
                <button key={q.id} type="button" onClick={() => navigate(`/app/quotes/${q.id}`)} className="flex w-full items-center justify-between gap-3 py-2.5 text-left hover:bg-muted/50" data-testid="recent-quote-row">
                  <span className="min-w-0">
                    <span className="block font-mono text-sm">{q.number}</span>
                    <span className="block truncate text-xs text-muted-foreground">{q.client_name || '—'}</span>
                  </span>
                  <span className="flex items-center gap-2">
                    <span className="tabular-nums text-sm text-muted-foreground">{money(q.total_ht, lang)}</span>
                    <StatusBadge status={q.status} />
                  </span>
                </button>
              ))}
            </div>
          )}
        </Card>
      </div>

      {(data.request_status || []).length > 0 && (
        <Card className="mt-5 border-border/80 p-5">
          <h2 className="mb-3 font-display text-base font-semibold">{t('dash.requests_split')}</h2>
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.request_status} layout="vertical" margin={{ left: 8, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" horizontal={false} />
                <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} axisLine={false} />
                <YAxis type="category" dataKey="status" width={110} tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} tickFormatter={(s) => t(`status.${s}`, s)} axisLine={false} tickLine={false} />
                <Tooltip formatter={(v) => [v, t('dash.count')]} />
                <Bar dataKey="count" fill="hsl(var(--primary))" radius={[0, 4, 4, 0]} barSize={14} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      )}
    </div>
  );
}
