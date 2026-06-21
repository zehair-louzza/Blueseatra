import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { api , apiError } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { toast } from 'sonner';
import { Upload, ArrowLeft, ArrowRight, CheckCircle2, Loader2, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';

const STEPS = ['step_upload', 'step_preview', 'step_validate', 'step_done'];

export default function CatalogImport() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [file, setFile] = useState(null);
  const [catalogName, setCatalogName] = useState('');
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [errors, setErrors] = useState([]);
  const [busy, setBusy] = useState(false);

  const doPreview = async () => {
    if (!file) { toast.error(t('wiz.choose_file')); return; }
    setBusy(true);
    try {
      const fd = new FormData(); fd.append('file', file);
      const { data } = await api.post('/catalogs/import/preview', fd);
      setPreview(data);
      if (!catalogName) setCatalogName(file.name.replace(/\.csv$/i, ''));
      setStep(1);
    } catch (err) { toast.error(apiError(err, 'Preview failed')); }
    finally { setBusy(false); }
  };

  const doImport = async () => {
    if (!catalogName.trim()) { toast.error(t('wiz.catalog_name')); return; }
    setBusy(true);
    try {
      const fd = new FormData(); fd.append('file', file); fd.append('catalog_name', catalogName); fd.append('activate', 'true');
      const { data } = await api.post('/catalogs/import', fd);
      setResult(data);
      if (data.error_rows > 0) { const e = await api.get(`/import-jobs/${data.job_id}/errors`); setErrors(e.data); }
      setStep(3);
      toast.success(t('wiz.done_msg'));
    } catch (err) { toast.error(apiError(err, 'Import failed')); }
    finally { setBusy(false); }
  };

  return (
    <div className="mx-auto max-w-3xl">
      <Button variant="ghost" size="sm" className="mb-3 gap-1" onClick={() => navigate('/app/catalogs')}><ArrowLeft className="h-4 w-4" />{t('common.back')}</Button>
      <h1 className="font-display text-2xl font-semibold tracking-tight">{t('wiz.title')}</h1>

      <div className="mt-5 flex items-center gap-2" data-testid="catalog-import-stepper">
        {STEPS.map((s, i) => (
          <React.Fragment key={s}>
            <div className={cn('flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium', i <= step ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground')}>
              <span>{i + 1}</span>{t(`wiz.${s}`)}
            </div>
            {i < STEPS.length - 1 && <div className={cn('h-px flex-1', i < step ? 'bg-primary' : 'bg-border')} />}
          </React.Fragment>
        ))}
      </div>

      <Card className="card-shadow mt-5 border-0 p-6">
        {step === 0 && (
          <div className="space-y-4">
            <label className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border border-dashed bg-card py-10 text-sm text-muted-foreground transition-colors hover:bg-muted/40" data-testid="csv-dropzone">
              <Upload className="h-6 w-6" />
              <span>{file ? file.name : t('wiz.choose_file')}</span>
              <input type="file" accept=".csv" className="hidden" onChange={(e) => setFile(e.target.files[0])} data-testid="csv-file-input" />
            </label>
            <Button onClick={doPreview} disabled={busy || !file} className="gap-2" data-testid="preview-next-button">
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}{t('wiz.next')}
            </Button>
          </div>
        )}

        {step === 1 && preview && (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-4 text-sm">
              <span>{t('wiz.total_rows')}: <b>{preview.total_rows}</b></span>
              {preview.missing_required.length > 0 && (
                <span className="flex items-center gap-1 text-rose-600"><AlertTriangle className="h-4 w-4" />{t('wiz.missing')}: {preview.missing_required.join(', ')}</span>
              )}
            </div>
            <div className="overflow-x-auto rounded-lg border">
              <Table>
                <TableHeader><TableRow>{preview.columns.map((c) => <TableHead key={c} className="font-mono text-xs">{c}</TableHead>)}</TableRow></TableHeader>
                <TableBody>{preview.preview.map((row, i) => (
                  <TableRow key={i}>{preview.columns.map((c) => <TableCell key={c} className="text-xs">{String(row[c] ?? '')}</TableCell>)}</TableRow>
                ))}</TableBody>
              </Table>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="cname">{t('wiz.catalog_name')}</Label>
              <Input id="cname" value={catalogName} onChange={(e) => setCatalogName(e.target.value)} data-testid="catalog-name-input" />
            </div>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => setStep(0)} className="gap-1"><ArrowLeft className="h-4 w-4" />{t('wiz.back')}</Button>
              <Button onClick={() => setStep(2)} disabled={preview.missing_required.length > 0} className="gap-1" data-testid="validate-next-button">{t('wiz.next')}<ArrowRight className="h-4 w-4" /></Button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">{t('wiz.catalog_name')}: <b>{catalogName}</b> \u00b7 {preview?.total_rows} {t('cat.items')}</p>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => setStep(1)} className="gap-1"><ArrowLeft className="h-4 w-4" />{t('wiz.back')}</Button>
              <Button onClick={doImport} disabled={busy} className="gap-2" data-testid="import-confirm-button">
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}{t('wiz.import_btn')}
              </Button>
            </div>
          </div>
        )}

        {step === 3 && result && (
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-emerald-700"><CheckCircle2 className="h-6 w-6" /><span className="font-medium">{t('wiz.done_msg')}</span></div>
            <div className="flex gap-6 text-sm">
              <span>{t('wiz.success_rows')}: <b className="text-emerald-700">{result.success_rows}</b></span>
              <span>{t('wiz.error_rows')}: <b className={result.error_rows ? 'text-rose-600' : ''}>{result.error_rows}</b></span>
              <span>{t('cat.version')}: <b className="font-mono">v{result.version_number}</b></span>
            </div>
            {errors.length > 0 && (
              <div className="overflow-x-auto rounded-lg border" data-testid="import-errors-table">
                <Table>
                  <TableHeader><TableRow><TableHead>Row</TableHead><TableHead>Error</TableHead></TableRow></TableHeader>
                  <TableBody>{errors.map((e) => <TableRow key={e.id}><TableCell className="font-mono">{e.row_number}</TableCell><TableCell className="text-rose-600">{e.message}</TableCell></TableRow>)}</TableBody>
                </Table>
              </div>
            )}
            <Button onClick={() => navigate('/app/catalogs')} data-testid="go-catalogs-button">{t('wiz.go_catalogs')}</Button>
          </div>
        )}
      </Card>
    </div>
  );
}
