import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { api , apiError } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import { Upload, ArrowLeft, ArrowRight, CheckCircle2, Loader2, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuth } from '@/context/AuthContext';

const STEPS = ['step_upload', 'step_preview', 'step_validate', 'step_control', 'step_done'];
const TON = { OK: 'border-emerald-300 bg-emerald-50 text-emerald-800', A_VERIFIER: 'border-amber-300 bg-amber-50 text-amber-900', BLOQUANT: 'border-red-300 bg-red-50 text-red-800' };

export default function CatalogImport() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [file, setFile] = useState(null);
  const [catalogName, setCatalogName] = useState('');
  const [preview, setPreview] = useState(null);
  const [mapping, setMapping] = useState({});
  const [result, setResult] = useState(null);
  const [errors, setErrors] = useState([]);
  const [busy, setBusy] = useState(false);
  // Classeur Excel : feuille lue (la premiere qui contient un tableau, sinon celle choisie).
  const [feuille, setFeuille] = useState('');
  const { tenant } = useAuth();
  const peutForcer = ['owner', 'admin'].includes(tenant?.role);

  const doPreview = async (choix = '') => {
    if (!file) { toast.error(t('wiz.choose_file')); return; }
    setBusy(true);
    try {
      const fd = new FormData(); fd.append('file', file);
      if (choix) fd.append('feuille', choix);
      const { data } = await api.post('/catalogs/import/preview', fd);
      setPreview(data);
      setFeuille(data.fichier?.feuille || '');
      setMapping(data.suggested_mapping || {});
      if (!catalogName) setCatalogName(file.name.replace(/\.(csv|xlsx|xls)$/i, ''));
      setStep(1);
    } catch (err) { toast.error(apiError(err, 'Preview failed')); }
    finally { setBusy(false); }
  };

  const doImport = async () => {
    if (!catalogName.trim()) { toast.error(t('wiz.catalog_name')); return; }
    setBusy(true);
    try {
      const fd = new FormData(); fd.append('file', file); fd.append('catalog_name', catalogName); fd.append('activate', 'false');
      fd.append('mapping', JSON.stringify(mapping));
      if (feuille) fd.append('feuille', feuille);
      const { data } = await api.post('/catalogs/import', fd);
      setResult(data);
      if (data.error_rows > 0) { const e = await api.get(`/import-jobs/${data.job_id}/errors`); setErrors(e.data); }
      setStep(3);
      toast.success(t('cl.w_brouillon_ok'));
    } catch (err) { toast.error(apiError(err, 'Import failed')); }
    finally { setBusy(false); }
  };

  const activer = async (force = false) => {
    setBusy(true);
    try {
      await api.post(`/catalogs/${result.catalog_id}/activate/${result.version_id}`, null, { params: force ? { force: true } : {} });
      setResult({ ...result, activated: true });
      setStep(4);
      toast.success(t('wiz.done_msg'));
    } catch (err) { toast.error(apiError(err, 'Activation failed')); }
    finally { setBusy(false); }
  };

  const eur = (v) => (v == null ? '\u2014' : Number(v).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' }));
  const c = result?.comparaison;
  const ctl = result?.controle;

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
              <input type="file" accept=".csv,.xlsx,.xls,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel" className="hidden" onChange={(e) => { setFile(e.target.files[0]); setFeuille(''); }} data-testid="csv-file-input" />
            </label>
            <p className="text-center text-xs text-muted-foreground">{t('wiz.formats')}</p>
            <Button onClick={() => doPreview()} disabled={busy || !file} className="gap-2" data-testid="preview-next-button">
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}{t('wiz.next')}
            </Button>
          </div>
        )}

        {step === 1 && preview && (
          <div className="space-y-4">
            {(preview.fichier?.feuilles || []).length > 1 && (
              <div className="flex flex-wrap items-center gap-2 rounded-lg border bg-muted/30 px-3 py-2 text-sm" data-testid="import-feuille">
                <span>{t('wiz.sheet')}</span>
                <Select value={feuille} onValueChange={(v) => doPreview(v)} disabled={busy}>
                  <SelectTrigger className="h-8 w-56" data-testid="import-feuille-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {preview.fichier.feuilles.map((f) => <SelectItem key={f} value={f}>{f}</SelectItem>)}
                  </SelectContent>
                </Select>
                {preview.fichier.ligne_entete > 1 && (
                  <span className="text-xs text-muted-foreground">{t('wiz.header_row', { n: preview.fichier.ligne_entete })}</span>
                )}
              </div>
            )}
            <div className="flex flex-wrap gap-4 text-sm">
              <span>{t('wiz.total_rows')}: <b>{preview.total_rows}</b></span>
              <span className="text-muted-foreground">{preview.columns.length} colonnes</span>
            </div>
            <div className="overflow-x-auto rounded-lg border">
              <Table>
                <TableHeader><TableRow>{preview.columns.map((c) => <TableHead key={c} className="font-mono text-xs">{c}</TableHead>)}</TableRow></TableHeader>
                <TableBody>{preview.preview.map((row, i) => (
                  <TableRow key={i}>{preview.columns.map((c) => <TableCell key={c} className="text-xs">{String(row[c] ?? '')}</TableCell>)}</TableRow>
                ))}</TableBody>
              </Table>
            </div>

            <div className="space-y-2 rounded-lg border bg-muted/30 p-4" data-testid="column-mapping">
              <div>
                <p className="text-sm font-medium">{t('wiz.mapping_title')}</p>
                <p className="text-xs text-muted-foreground">{t('wiz.mapping_hint')}</p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {(preview.standard_fields || []).map((f) => (
                  <div key={f.key} className="space-y-1">
                    <Label className="text-xs">
                      {f.label}{f.required && <span className="ml-1 text-rose-600">*</span>}
                    </Label>
                    <Select
                      value={mapping[f.key] || '__none__'}
                      onValueChange={(v) => setMapping((m) => ({ ...m, [f.key]: v === '__none__' ? null : v }))}
                    >
                      <SelectTrigger className="h-9" data-testid={`map-${f.key}`}><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__none__">{t('wiz.field_none')}</SelectItem>
                        {preview.columns.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="cname">{t('wiz.catalog_name')}</Label>
              <Input id="cname" value={catalogName} onChange={(e) => setCatalogName(e.target.value)} data-testid="catalog-name-input" />
            </div>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => setStep(0)} className="gap-1"><ArrowLeft className="h-4 w-4" />{t('wiz.back')}</Button>
              <Button onClick={() => { if (!mapping.item_label) { toast.error(t('wiz.map_required_error')); return; } setStep(2); }} className="gap-1" data-testid="validate-next-button">{t('wiz.next')}<ArrowRight className="h-4 w-4" /></Button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">{t('wiz.catalog_name')}: <b>{catalogName}</b> · {preview?.total_rows} {t('cat.items')}</p>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => setStep(1)} className="gap-1"><ArrowLeft className="h-4 w-4" />{t('wiz.back')}</Button>
              <Button onClick={doImport} disabled={busy} className="gap-2" data-testid="import-confirm-button">
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}{t('cl.w_importer')}
              </Button>
            </div>
          </div>
        )}

        {step >= 3 && result && (
          <div className="space-y-4" data-testid="import-control-step">
            <div className="flex flex-wrap gap-6 text-sm">
              <span>{t('wiz.success_rows')}: <b className="text-emerald-700">{result.success_rows}</b></span>
              <span>{t('wiz.error_rows')}: <b className={result.error_rows ? 'text-rose-600' : ''}>{result.error_rows}</b></span>
              <span>{t('cat.version')}: <b className="font-mono">v{result.version_number}</b></span>
              <span>{t('cl.w_statut')}: <b>{result.activated ? t('cl.w_active') : t('cl.w_brouillon')}</b></span>
            </div>
            {ctl && (
              <div className={cn('rounded-lg border p-3 text-sm', TON[ctl.verdict])} data-testid="import-verdict">
                <div className="font-semibold">{t(`cl.w_verdict_${ctl.verdict}`)}</div>
                {ctl.alertes.length > 0 && <ul className="mt-1 list-disc pl-5">{ctl.alertes.map((a) => <li key={a.code}>{a.message}</li>)}</ul>}
              </div>
            )}
            {c ? (
              <div className="space-y-2 text-sm" data-testid="import-comparison">
                <div className="font-medium">{t('cl.w_comparaison', { a: c.articles_avant, n: c.articles_apres })}</div>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
                  {[['ajoutes', 'text-emerald-700'], ['retires', 'text-rose-600'], ['hausses', 'text-amber-700'], ['baisses', 'text-sky-700'], ['inchanges', 'text-muted-foreground']].map(([k, cls]) => (
                    <div key={k} className="rounded-lg border p-2"><div className="text-xs uppercase text-muted-foreground">{t(`cl.w_${k}`)}</div><div className={cn('text-lg font-semibold', cls)}>{c[k]}</div></div>
                  ))}
                </div>
                {(c.plus_fortes_hausses.length > 0 || c.plus_fortes_baisses.length > 0) && (
                  <div className="overflow-x-auto rounded-lg border">
                    <Table>
                      <TableHeader><TableRow><TableHead>{t('cl.w_article')}</TableHead><TableHead className="text-right">{t('cl.w_avant')}</TableHead><TableHead className="text-right">{t('cl.w_apres')}</TableHead><TableHead className="text-right">%</TableHead></TableRow></TableHeader>
                      <TableBody>{[...c.plus_fortes_hausses, ...c.plus_fortes_baisses].slice(0, 12).map((x, i) => (
                        <TableRow key={i}><TableCell>{x.libelle}<span className="ml-1 font-mono text-xs text-muted-foreground">{x.reference}</span></TableCell>
                          <TableCell className="text-right">{eur(x.avant)}</TableCell><TableCell className="text-right">{eur(x.apres)}</TableCell>
                          <TableCell className={cn('text-right font-medium', x.variation_pct > 0 ? 'text-amber-700' : 'text-sky-700')}>{x.variation_pct > 0 ? '+' : ''}{x.variation_pct}</TableCell></TableRow>
                      ))}</TableBody>
                    </Table>
                  </div>
                )}
              </div>
            ) : <p className="text-sm text-muted-foreground">{t('cl.w_premiere')}</p>}
            {errors.length > 0 && (
              <div className="overflow-x-auto rounded-lg border" data-testid="import-errors-table">
                <Table>
                  <TableHeader><TableRow><TableHead>{t('cl.w_ligne')}</TableHead><TableHead>{t('cl.w_erreur')}</TableHead></TableRow></TableHeader>
                  <TableBody>{errors.slice(0, 200).map((e) => <TableRow key={e.id}><TableCell className="font-mono">{e.row_number}</TableCell><TableCell className="text-rose-600">{e.message}</TableCell></TableRow>)}</TableBody>
                </Table>
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              {!result.activated && ctl?.verdict !== 'BLOQUANT' && (
                <Button onClick={() => activer(false)} disabled={busy} className="gap-2" data-testid="import-activate-button">
                  {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}{t('cl.w_activer')}
                </Button>
              )}
              {!result.activated && ctl?.verdict === 'BLOQUANT' && peutForcer && (
                <Button variant="destructive" onClick={() => activer(true)} disabled={busy} className="gap-2" data-testid="import-force-button">
                  <AlertTriangle className="h-4 w-4" />{t('cl.w_forcer')}
                </Button>
              )}
              <Button variant={result.activated ? 'default' : 'secondary'} onClick={() => navigate('/app/catalogs')} data-testid="go-catalogs-button">
                {result.activated ? t('wiz.go_catalogs') : t('cl.w_garder_brouillon')}
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
