import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { api } from '@/lib/api';
import { Card } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Spinner, EmptyState } from '@/components/Spinner';
import { StatusBadge } from '@/components/StatusBadge';
import { FileText } from 'lucide-react';

export default function Quotes() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [rows, setRows] = useState(null);
  useEffect(() => { api.get('/quotes').then((r) => setRows(r.data)); }, []);
  return (
    <div>
      <h1 className="font-display text-2xl font-semibold tracking-tight">{t('quote.title')}</h1>
      <div className="mt-5">
        {!rows ? <Spinner /> : rows.length === 0 ? (
          <EmptyState icon={FileText} title={t('quote.no_quotes')} />
        ) : (
          <Card className="card-shadow overflow-hidden border-0">
            <Table data-testid="quotes-table">
              <TableHeader><TableRow>
                <TableHead>{t('quote.number')}</TableHead><TableHead>{t('quote.client')}</TableHead>
                <TableHead className="text-right">{t('quote.total_ttc')}</TableHead><TableHead>{t('common.status')}</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {rows.map((q) => (
                  <TableRow key={q.id} className="cursor-pointer" onClick={() => navigate(`/app/quotes/${q.id}`)} data-testid="quotes-table-row">
                    <TableCell className="font-mono">{q.number}</TableCell>
                    <TableCell>{q.client || '\u2014'}</TableCell>
                    <TableCell className="text-right font-medium">{q.total_ttc} {q.currency}</TableCell>
                    <TableCell><StatusBadge status={q.status} /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        )}
      </div>
    </div>
  );
}
