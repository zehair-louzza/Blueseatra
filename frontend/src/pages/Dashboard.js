import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { api } from '@/lib/api';
import { Card } from '@/components/ui/card';
import { Spinner } from '@/components/Spinner';
import { StatusBadge } from '@/components/StatusBadge';
import { Inbox, FileText, CheckCircle2, BookOpen } from 'lucide-react';
import { motion } from 'framer-motion';

const Kpi = ({ icon: Icon, label, value, i }) => (
  <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
    <Card className="card-shadow border-0 p-5" data-testid={`kpi-card`}>
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">{label}</span>
        <Icon className="h-4 w-4 text-accent" />
      </div>
      <div className="mt-2 font-display text-3xl font-semibold text-foreground">{value}</div>
    </Card>
  </motion.div>
);

export default function Dashboard() {
  const { t } = useTranslation();
  const [data, setData] = useState(null);
  const navigate = useNavigate();
  useEffect(() => { api.get('/dashboard').then((r) => setData(r.data)); }, []);
  if (!data) return <Spinner />;
  const k = data.kpis;
  return (
    <div>
      <h1 className="font-display text-2xl font-semibold tracking-tight">{t('dash.title')}</h1>
      <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi i={0} icon={Inbox} label={t('dash.requests')} value={k.requests} />
        <Kpi i={1} icon={FileText} label={t('dash.drafts')} value={k.drafts} />
        <Kpi i={2} icon={CheckCircle2} label={t('dash.validated')} value={k.validated} />
        <Kpi i={3} icon={BookOpen} label={t('dash.catalog_items')} value={k.active_catalog_items} />
      </div>
      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card className="card-shadow border-0 p-5">
          <h2 className="mb-3 font-display text-base font-semibold">{t('dash.recent_requests')}</h2>
          {data.recent_requests.length === 0 ? <p className="py-6 text-center text-sm text-muted-foreground">{t('dash.empty')}</p> :
            <div className="divide-y">{data.recent_requests.map((r) => (
              <button key={r.id} onClick={() => navigate(`/app/requests/${r.id}`)} className="flex w-full items-center justify-between py-2.5 text-left hover:bg-muted/40" data-testid="recent-request-row">
                <span className="truncate text-sm">{r.title}</span><StatusBadge status={r.status} />
              </button>))}</div>}
        </Card>
        <Card className="card-shadow border-0 p-5">
          <h2 className="mb-3 font-display text-base font-semibold">{t('dash.recent_quotes')}</h2>
          {data.recent_quotes.length === 0 ? <p className="py-6 text-center text-sm text-muted-foreground">{t('dash.empty')}</p> :
            <div className="divide-y">{data.recent_quotes.map((q) => (
              <button key={q.id} onClick={() => navigate(`/app/quotes/${q.id}`)} className="flex w-full items-center justify-between py-2.5 text-left hover:bg-muted/40" data-testid="recent-quote-row">
                <span className="font-mono text-sm">{q.number}</span>
                <span className="flex items-center gap-2"><span className="text-sm text-muted-foreground">{q.total_ttc} {q.currency}</span><StatusBadge status={q.status} /></span>
              </button>))}</div>}
        </Card>
      </div>
    </div>
  );
}
