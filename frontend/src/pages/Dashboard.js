import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Area, AreaChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { api } from '@/lib/api';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/Spinner';
import { StatusBadge } from '@/components/StatusBadge';
import { useAuth } from '@/context/AuthContext';
import { FileText, Inbox, Plus } from 'lucide-react';

const money = (n, lang, digits = 0) =>
  new Intl.NumberFormat(lang === 'fr' ? 'fr-FR' : 'en-GB', {
    style: 'currency', currency: 'EUR', maximumFractionDigits: digits,
  }).format(Number(n) || 0);

const monthLabel = (ym, lang) => {
  if (!ym) return '';
  const [y, m] = ym.split('-').map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString(lang === 'fr' ? 'fr-FR' : 'en-GB', {
    month: 'short', year: '2-digit',
  });
};

const firstName = (user, tenant) => {
  const raw = (user?.name || tenant?.name || '').trim();
  if (!raw) return '';
  return raw.split(/\s+/)[0];
};

function DocRow({ title, subtitle, amount, status, onClick, testid }) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={testid}
      className="flex w-full items-start gap-3 py-2.5 text-left hover:bg-muted/40"
    >
      <FileText className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-foreground">{title}</span>
        {subtitle ? <span className="block truncate text-xs text-muted-foreground">{subtitle}</span> : null}
      </span>
      <span className="shrink-0 text-right">
        {amount != null && <span className="block tabular-nums text-sm">{amount}</span>}
        {status ? <StatusBadge status={status} className="mt-0.5" /> : null}
      </span>
    </button>
  );
}

function DonutCard({ title, count, amount, label, slices, accent, items, empty, onItem, lang }) {
  return (
    <div className="border-t border-border pt-4 first:border-t-0 first:pt-0">
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      <div className="mt-2 flex items-center gap-4">
        <div className="h-24 w-24 shrink-0" aria-hidden>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={slices} dataKey="value" innerRadius={28} outerRadius={42} paddingAngle={1} stroke="none">
                {slices.map((s) => <Cell key={s.name} fill={s.color} />)}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div>
          <p className="text-sm text-muted-foreground">{count} {label}</p>
          {amount != null && (
            <p className="font-display text-xl font-semibold tabular-nums" style={{ color: accent }}>{money(amount, lang)}</p>
          )}
        </div>
      </div>
      <div className="mt-2 divide-y divide-border">
        {items.length === 0
          ? <p className="py-4 text-center text-xs text-muted-foreground">{empty}</p>
          : items.slice(0, 3).map((it) => (
            <DocRow
              key={it.id}
              title={it.number || it.title}
              subtitle={it.client_name}
              amount={it.total_ht != null ? money(it.total_ht, lang) : null}
              status={it.status}
              onClick={() => onItem(it)}
            />
          ))}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language?.startsWith('fr') ? 'fr' : 'en';
  const { user, tenant } = useAuth();
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [months, setMonths] = useState(3);
  const navigate = useNavigate();

  useEffect(() => {
    api.get('/dashboard').then((r) => setData(r.data)).catch(() => setErr(true));
  }, []);

  const chart = useMemo(() => {
    const rows = data?.monthly || [];
    return rows.slice(-months).map((r) => ({ ...r, label: monthLabel(r.month, lang) }));
  }, [data, months, lang]);

  const compare = useMemo(() => {
    const rows = data?.monthly || [];
    const cur = rows.slice(-months);
    const prev = rows.slice(-months * 2, -months);
    const sum = (arr, key) => arr.reduce((a, r) => a + (Number(r[key]) || 0), 0);
    const cnt = (arr) => arr.reduce((a, r) => a + (Number(r.count) || 0), 0);
    return {
      current: { ht: sum(cur, 'won_ht') + sum(cur, 'draft_ht'), won: sum(cur, 'won_ht'), docs: cnt(cur) },
      previous: { ht: sum(prev, 'won_ht') + sum(prev, 'draft_ht'), won: sum(prev, 'won_ht'), docs: cnt(prev) },
    };
  }, [data, months]);

  if (err) {
    return (
      <div role="alert" className="rounded-lg border bg-card p-8 text-center">
        <p className="font-medium">{t('dash.load_error')}</p>
        <Button className="mt-4" onClick={() => window.location.reload()}>{t('dash.retry')}</Button>
      </div>
    );
  }
  if (!data) return <Spinner />;

  const k = data.kpis || {};
  const quotes = data.recent_quotes || [];
  const requests = data.recent_requests || [];
  const draftN = k.drafts || 0;
  const wonN = k.validated || 0;
  const reviewN = (k.requests_review || 0) + (k.requests_failed || 0);
  const reqN = k.requests || 0;
  const hello = firstName(user, tenant);

  return (
    <div className="mx-auto max-w-6xl">
      <p className="font-display text-xl font-medium tracking-tight sm:text-2xl">
        {t('dash.hello', { name: hello || tenant?.name || '' })}
      </p>
      <p className="mt-1 text-sm text-muted-foreground">{t('dash.subtitle')}</p>

      <Button
        className="mt-4 h-11 w-full gap-2 text-base font-semibold"
        onClick={() => navigate('/app/requests')}
        data-testid="dash-cta-request"
      >
        <Plus className="h-5 w-5" />
        {t('dash.cta_big')}
      </Button>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <section>
            <h2 className="mb-1 text-sm font-semibold">{t('dash.last_quotes')}</h2>
            <div className="divide-y divide-border border-t border-border">
              {quotes.length === 0
                ? <p className="py-6 text-center text-sm text-muted-foreground">{t('dash.empty')}</p>
                : quotes.slice(0, 5).map((q) => (
                  <DocRow
                    key={q.id}
                    testid="recent-quote-row"
                    title={q.client_name || q.number}
                    subtitle={q.number}
                    amount={money(q.total_ht, lang)}
                    status={q.status}
                    onClick={() => navigate(`/app/quotes/${q.id}`)}
                  />
                ))}
            </div>
          </section>
          <section>
            <h2 className="mb-1 text-sm font-semibold">{t('dash.last_requests')}</h2>
            <div className="divide-y divide-border border-t border-border">
              {requests.length === 0
                ? <p className="py-6 text-center text-sm text-muted-foreground">{t('dash.empty')}</p>
                : requests.slice(0, 5).map((r) => (
                  <DocRow
                    key={r.id}
                    testid="recent-request-row"
                    title={r.title}
                    status={r.status}
                    onClick={() => navigate(`/app/requests/${r.id}`)}
                  />
                ))}
            </div>
          </section>
        </div>

        <Card className="space-y-5 border-border p-5">
          <DonutCard
            title={t('dash.wait_quotes')}
            count={draftN}
            amount={k.pipeline_draft_ht}
            label={t('dash.wait_quotes_n')}
            accent="hsl(var(--accent))"
            slices={[
              { name: 'open', value: draftN || 0.0001, color: 'hsl(var(--accent))' },
              { name: 'rest', value: Math.max(0, wonN), color: 'hsl(var(--muted))' },
            ]}
            items={data.awaiting_quotes || []}
            empty={t('dash.empty_action')}
            onItem={(q) => navigate(`/app/quotes/${q.id}`)}
            lang={lang}
          />
          <DonutCard
            title={t('dash.wait_requests')}
            count={reviewN}
            amount={null}
            label={t('dash.wait_requests_n')}
            accent="hsl(var(--primary))"
            slices={[
              { name: 'open', value: reviewN || 0.0001, color: 'hsl(38 70% 45%)' },
              { name: 'rest', value: Math.max(0, reqN - reviewN), color: 'hsl(var(--muted))' },
            ]}
            items={data.awaiting_requests || []}
            empty={t('dash.empty_action')}
            onItem={(r) => navigate(`/app/requests/${r.id}`)}
            lang={lang}
          />
        </Card>
      </div>

      <section className="mt-8">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold">{t('dash.chart_title')}</h2>
          <div className="flex rounded-md border border-border p-0.5" role="group" aria-label={t('dash.period')}>
            {[3, 6, 12].map((n) => (
              <button
                key={n}
                type="button"
                onClick={() => setMonths(n)}
                className={`rounded px-2.5 py-1 text-xs font-medium ${months === n ? 'bg-foreground text-background' : 'text-muted-foreground hover:bg-muted'}`}
              >
                {n === 12 ? t('dash.one_year') : `${n} ${t('dash.months')}`}
              </button>
            ))}
          </div>
        </div>
        <div className="h-52" aria-label={t('dash.chart_title')}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chart} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} axisLine={false} tickLine={false} width={52} tickFormatter={(v) => `${Math.round(v / 1000)}k`} />
              <Tooltip
                formatter={(v, name) => [money(v, lang), name === 'won_ht' ? t('dash.series_won') : t('dash.series_draft')]}
                contentStyle={{ borderRadius: 8, border: '1px solid hsl(var(--border))', fontSize: 12 }}
              />
              <Area type="monotone" dataKey="won_ht" stroke="hsl(var(--accent))" fill="hsl(var(--accent))" fillOpacity={0.15} strokeWidth={2} />
              <Area type="monotone" dataKey="draft_ht" stroke="hsl(var(--primary))" fill="hsl(var(--primary))" fillOpacity={0.06} strokeWidth={1.5} strokeDasharray="4 3" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-4 grid grid-cols-1 gap-4 border-t border-border pt-4 sm:grid-cols-2">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{t('dash.period_current')}</p>
            <p className="mt-1 font-display text-lg font-semibold tabular-nums">{money(compare.current.ht, lang)}</p>
            <p className="text-xs text-muted-foreground">{t('dash.docs_n', { n: compare.current.docs })} · {t('dash.series_won')} {money(compare.current.won, lang)}</p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{t('dash.period_prev')}</p>
            <p className="mt-1 font-display text-lg font-semibold tabular-nums">{money(compare.previous.ht, lang)}</p>
            <p className="text-xs text-muted-foreground">{t('dash.docs_n', { n: compare.previous.docs })} · {t('dash.series_won')} {money(compare.previous.won, lang)}</p>
          </div>
        </div>
      </section>

      <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <section>
          <h2 className="mb-1 text-sm font-semibold">{t('dash.top_clients')}</h2>
          <div className="divide-y divide-border border-t border-border">
            {(data.top_clients || []).length === 0
              ? <p className="py-6 text-center text-sm text-muted-foreground">{t('dash.empty')}</p>
              : data.top_clients.map((c) => (
                <div key={c.name} className="flex items-center justify-between py-2.5">
                  <span className="truncate text-sm">{c.name}</span>
                  <span className="ml-3 shrink-0 text-right">
                    <span className="block tabular-nums text-sm font-medium">{money(c.ht, lang)}</span>
                    <span className="text-xs text-muted-foreground">{t('dash.docs_n', { n: c.count })}</span>
                  </span>
                </div>
              ))}
          </div>
        </section>
        <section>
          <h2 className="mb-1 text-sm font-semibold">{t('dash.aging')}</h2>
          <div className="divide-y divide-border border-t border-border">
            {(data.aging_drafts || []).length === 0
              ? <p className="py-6 text-center text-sm text-muted-foreground">{t('dash.empty_action')}</p>
              : data.aging_drafts.slice(0, 6).map((q) => (
                <DocRow
                  key={q.id}
                  title={q.number}
                  subtitle={q.client_name}
                  amount={money(q.total_ht, lang)}
                  status="draft"
                  onClick={() => navigate(`/app/quotes/${q.id}`)}
                />
              ))}
          </div>
        </section>
      </div>

      <div className="mt-6 flex flex-wrap gap-2">
        <Button variant="outline" className="gap-1.5" onClick={() => navigate('/app/quotes')}>
          <FileText className="h-4 w-4" />{t('dash.cta_quotes')}
        </Button>
        <Button variant="outline" className="gap-1.5" onClick={() => navigate('/app/catalogs')}>
          <Inbox className="h-4 w-4" />{k.active_catalog_items || 0} {t('dash.catalog_items').toLowerCase()}
        </Button>
      </div>
    </div>
  );
}
