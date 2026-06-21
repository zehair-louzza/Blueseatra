import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from '@/lib/api';
import { Card } from '@/components/ui/card';
import { Spinner, EmptyState } from '@/components/Spinner';
import { ScrollText } from 'lucide-react';

export default function Audit() {
  const { t, i18n } = useTranslation();
  const [rows, setRows] = useState(null);
  useEffect(() => { api.get('/audit').then((r) => setRows(r.data)); }, []);
  const fmt = (iso) => { try { return new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(iso)); } catch { return iso; } };
  return (
    <div>
      <h1 className="font-display text-2xl font-semibold tracking-tight">{t('audit.title')}</h1>
      <div className="mt-5">
        {!rows ? <Spinner /> : rows.length === 0 ? <EmptyState icon={ScrollText} title={t('audit.no_logs')} /> : (
          <Card className="card-shadow border-0 p-5">
            <div className="relative pl-4 before:absolute before:bottom-0 before:left-0 before:top-0 before:w-px before:bg-border" data-testid="audit-log-timeline">
              {rows.map((l) => (
                <div key={l.id} className="relative mb-4 pl-4" data-testid="audit-row">
                  <span className="absolute -left-[3px] top-1.5 h-2 w-2 rounded-full bg-accent" />
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs font-medium text-primary">{l.action}</span>
                    <span className="text-xs text-muted-foreground">\u00b7 {l.actor}</span>
                  </div>
                  <div className="text-xs text-muted-foreground">{fmt(l.created_at)}{l.meta && Object.keys(l.meta).length ? ` \u00b7 ${JSON.stringify(l.meta)}` : ''}</div>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
