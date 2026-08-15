import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { api, apiError } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Spinner, EmptyState } from '@/components/Spinner';
import { StatusBadge } from '@/components/StatusBadge';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog';
import { toast } from 'sonner';
import { FileText, Copy, Trash2 } from 'lucide-react';

export default function Quotes() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [rows, setRows] = useState(null);
  const load = () => api.get('/quotes').then((r) => setRows(r.data));
  useEffect(() => { load(); }, []);

  const duplicate = async (id, e) => {
    e.stopPropagation();
    try {
      const { data } = await api.post(`/quotes/${id}/duplicate`);
      toast.success(t('quote.duplicated'));
      navigate(`/app/quotes/${data.id}`);
    } catch (err) { toast.error(apiError(err, 'Failed')); }
  };
  const remove = async (id) => {
    try {
      await api.delete(`/quotes/${id}`);
      toast.success(t('quote.deleted'));
      load();
    } catch (err) { toast.error(apiError(err, 'Failed')); }
  };

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
                <TableHead className="text-right">{t('common.actions')}</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {rows.map((q) => (
                  <TableRow key={q.id} className="cursor-pointer" onClick={() => navigate(`/app/quotes/${q.id}`)} data-testid="quotes-table-row">
                    <TableCell className="font-mono">{q.number}</TableCell>
                    <TableCell>{q.client || '\u2014'}</TableCell>
                    <TableCell className="text-right font-medium">{q.total_ttc} {q.currency}</TableCell>
                    <TableCell><StatusBadge status={q.status} /></TableCell>
                    <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="sm" onClick={() => navigate(`/app/quotes/${q.id}`)}>{t('common.open')}</Button>
                        <Button variant="ghost" size="sm" className="gap-1" onClick={(e) => duplicate(q.id, e)} data-testid="quote-duplicate-button"><Copy className="h-4 w-4" />{t('quote.duplicate')}</Button>
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button variant="ghost" size="sm" className="gap-1 text-destructive hover:text-destructive" data-testid="quote-delete-button"><Trash2 className="h-4 w-4" />{t('quote.delete')}</Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>{t('quote.delete_title')}</AlertDialogTitle>
                              <AlertDialogDescription>{q.number} — {t('quote.delete_desc')}</AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                              <AlertDialogAction onClick={() => remove(q.id)} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">{t('quote.delete')}</AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </div>
                    </TableCell>
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
