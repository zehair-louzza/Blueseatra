import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from '@/components/ui/dialog';
import { Spinner, EmptyState } from '@/components/Spinner';
import { StatusBadge } from '@/components/StatusBadge';
import { toast } from 'sonner';
import { Inbox, Plus, Upload, Loader2, FileText } from 'lucide-react';

export default function Requests() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [rows, setRows] = useState(null);
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [text, setText] = useState('');
  const [file, setFile] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const load = () => api.get('/requests').then((r) => setRows(r.data));
  useEffect(() => { load(); }, []);

  // poll while anything is processing
  useEffect(() => {
    if (!rows) return;
    const pending = rows.some((r) => ['received', 'processing'].includes(r.status));
    if (!pending) return;
    const id = setInterval(load, 3000);
    return () => clearInterval(id);
  }, [rows]);

  const submit = async (e) => {
    e.preventDefault();
    if (!title.trim()) { toast.error('Title required'); return; }
    if (!text.trim() && !file) { toast.error('Provide text or a file'); return; }
    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append('title', title);
      if (text.trim()) fd.append('text', text);
      if (file) fd.append('file', file);
      await api.post('/requests', fd);
      toast.success(t('req.processing'));
      setOpen(false); setTitle(''); setText(''); setFile(null);
      await load();
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed'); }
    finally { setSubmitting(false); }
  };

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="font-display text-2xl font-semibold tracking-tight">{t('req.title')}</h1>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild><Button className="gap-2" data-testid="new-request-button"><Plus className="h-4 w-4" />{t('req.new')}</Button></DialogTrigger>
          <DialogContent className="sm:max-w-lg">
            <DialogHeader><DialogTitle>{t('req.upload_title')}</DialogTitle></DialogHeader>
            <form onSubmit={submit} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="rtitle">{t('req.name_field')}</Label>
                <Input id="rtitle" value={title} onChange={(e) => setTitle(e.target.value)} data-testid="request-title-input" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="rtext">{t('req.paste_text')}</Label>
                <Textarea id="rtext" rows={5} value={text} onChange={(e) => setText(e.target.value)} data-testid="request-text-input" placeholder="..." />
              </div>
              <div className="space-y-1.5">
                <Label>{t('req.or_upload')}</Label>
                <label className="flex cursor-pointer items-center gap-2 rounded-xl border border-dashed bg-card px-4 py-3 text-sm text-muted-foreground transition-colors hover:bg-muted/40" data-testid="file-dropzone">
                  <Upload className="h-4 w-4" />
                  <span>{file ? file.name : t('req.file_hint')}</span>
                  <input type="file" className="hidden" accept=".pdf,.docx,.png,.jpg,.jpeg,.webp" onChange={(e) => setFile(e.target.files[0])} data-testid="request-file-input" />
                </label>
              </div>
              <DialogFooter>
                <Button type="submit" disabled={submitting} className="w-full" data-testid="submit-request-button">
                  {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}{t('req.submit')}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="mt-5">
        {!rows ? <Spinner /> : rows.length === 0 ? (
          <EmptyState icon={Inbox} title={t('req.no_requests')} action={<Button onClick={() => setOpen(true)} className="gap-2"><Plus className="h-4 w-4" />{t('req.new')}</Button>} />
        ) : (
          <Card className="card-shadow overflow-hidden border-0">
            <Table data-testid="requests-table">
              <TableHeader>
                <TableRow>
                  <TableHead>{t('req.name_field')}</TableHead>
                  <TableHead>{t('req.lang')}</TableHead>
                  <TableHead>{t('req.line_items')}</TableHead>
                  <TableHead>{t('common.status')}</TableHead>
                  <TableHead className="text-right">{t('common.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r) => (
                  <TableRow key={r.id} className="cursor-pointer" onClick={() => navigate(`/app/requests/${r.id}`)} data-testid="requests-table-row">
                    <TableCell className="font-medium"><span className="flex items-center gap-2"><FileText className="h-4 w-4 text-muted-foreground" />{r.title}</span></TableCell>
                    <TableCell className="uppercase">{r.language || '\u2014'}</TableCell>
                    <TableCell>{r.extracted?.line_items?.length ?? '\u2014'}</TableCell>
                    <TableCell><StatusBadge status={r.status} /></TableCell>
                    <TableCell className="text-right"><Button variant="ghost" size="sm">{t('common.open')}</Button></TableCell>
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
