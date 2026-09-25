import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { api, apiError } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { toast } from 'sonner';
import { History } from 'lucide-react';

const eur = (v) => (v == null ? '\u2014' : Number(v).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' }));
const val = (k, v) => (v == null || v === '' ? '\u2014' : ['unit_price_ht', 'line_ht'].includes(k) ? eur(v) : ['margin', 'vat_rate'].includes(k) ? `${v} %` : String(v));

export default function QuoteVersions({ quoteId, version }) {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const [data, setData] = useState(null);
  const [de, setDe] = useState(null);
  const [diff, setDiff] = useState(null);

  useEffect(() => {
    if (!open) return;
    api.get(`/quotes/${quoteId}/versions`).then((r) => {
      setData(r.data);
      const figees = r.data.versions.filter((v) => v.figee);
      setDe(figees.length ? figees[figees.length - 1].version : null);
    }).catch((e) => toast.error(apiError(e, 'Failed')));
  }, [open, quoteId, version]);

  useEffect(() => {
    if (!open || de == null) { setDiff(null); return; }
    api.get(`/quotes/${quoteId}/versions/compare`, { params: { de } })
      .then((r) => setDiff(r.data)).catch((e) => toast.error(apiError(e, 'Failed')));
  }, [open, de, quoteId]);

  const dt = (s) => (s ? new Date(s).toLocaleString(i18n.language === 'en' ? 'en-GB' : 'fr-FR', { dateStyle: 'short', timeStyle: 'short' }) : t('cl.v_en_cours'));

  return (
    <>
      <Button variant="outline" size="sm" className="gap-1" onClick={() => setOpen(true)} data-testid="quote-versions-button">
        <History className="h-4 w-4" />{t('cl.v_bouton', { v: version || 1 })}
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>{t('cl.v_titre', { n: data?.numero || '' })}</DialogTitle>
            <DialogDescription>{t('cl.v_aide')}</DialogDescription>
          </DialogHeader>
          {!data ? null : (
            <div className="space-y-5">
              <table className="w-full text-sm">
                <thead className="text-left text-xs uppercase text-muted-foreground">
                  <tr><th className="py-1">{t('cl.v_version')}</th><th>{t('cl.v_date')}</th><th className="text-right">{t('cl.v_lignes')}</th><th className="text-right">HT</th><th className="text-right">TTC</th><th /></tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {data.versions.map((v) => (
                    <tr key={`${v.version}-${v.created_at}`} className={v.version === de && v.figee ? 'bg-muted/50' : ''}>
                      <td className="py-2 font-medium">v{v.version}{v.actuelle && <span className="ml-2 rounded bg-primary/10 px-1.5 py-0.5 text-xs text-primary">{t('cl.v_actuelle')}</span>}</td>
                      <td className="text-muted-foreground">{dt(v.created_at)}</td>
                      <td className="text-right">{v.lignes}</td>
                      <td className="text-right">{eur(v.total_ht)}</td>
                      <td className="text-right">{eur(v.total_ttc)}</td>
                      <td className="text-right">{v.figee && <Button variant="ghost" size="sm" onClick={() => setDe(v.version)}>{t('cl.v_comparer')}</Button>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {de == null && <p className="rounded-lg bg-muted/50 p-3 text-sm text-muted-foreground">{t('cl.v_aucune')}</p>}
              {diff && (
                <div className="space-y-3" data-testid="quote-versions-diff">
                  <h3 className="font-semibold">{t('cl.v_diff', { de: diff.de, a: diff.a })}</h3>
                  {diff.identique ? <p className="text-sm text-muted-foreground">{t('cl.v_identique')}</p> : (
                    <>
                      <div className="grid grid-cols-3 gap-2 text-sm">
                        {['total_ht', 'total_vat', 'total_ttc'].map((k) => (
                          <div key={k} className="rounded-lg border border-border p-2">
                            <div className="text-xs uppercase text-muted-foreground">{t(`cl.v_${k}`)}</div>
                            <div>{eur(diff.totaux[k].avant)} → <b>{eur(diff.totaux[k].apres)}</b></div>
                            <div className={diff.totaux[k].ecart > 0 ? 'text-emerald-700' : diff.totaux[k].ecart < 0 ? 'text-red-700' : 'text-muted-foreground'}>
                              {diff.totaux[k].ecart > 0 ? '+' : ''}{eur(diff.totaux[k].ecart)}
                            </div>
                          </div>
                        ))}
                      </div>
                      {Object.keys(diff.entete).length > 0 && (
                        <ul className="text-sm">{Object.entries(diff.entete).map(([k, c]) => (
                          <li key={k}><span className="text-muted-foreground">{t(`cl.v_champ_${k}`, k)} :</span> {c.avant || '\u2014'} → <b>{c.apres || '\u2014'}</b></li>
                        ))}</ul>
                      )}
                      <Bloc titre={t('cl.v_modifiees')} n={diff.modifiees.length} ton="amber">
                        {diff.modifiees.map((l, i) => (
                          <li key={i}><b>{l.description}</b>{' '}
                            {Object.entries(l.champs).map(([k, c]) => <span key={k} className="mr-2 text-muted-foreground">{t(`cl.v_champ_${k}`, k)} {val(k, c.avant)} → <span className="text-foreground">{val(k, c.apres)}</span></span>)}
                          </li>
                        ))}
                      </Bloc>
                      <Bloc titre={t('cl.v_ajoutees')} n={diff.ajoutees.length} ton="emerald">
                        {diff.ajoutees.map((l, i) => <li key={i}>{l.description} <span className="text-muted-foreground">{l.qty ?? ''} {l.unit || ''} · {eur(l.line_ht)}</span></li>)}
                      </Bloc>
                      <Bloc titre={t('cl.v_supprimees')} n={diff.supprimees.length} ton="red">
                        {diff.supprimees.map((l, i) => <li key={i} className="line-through decoration-red-400">{l.description} <span className="text-muted-foreground">{eur(l.line_ht)}</span></li>)}
                      </Bloc>
                    </>
                  )}
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}

const TONS = { amber: 'border-amber-300 bg-amber-50', emerald: 'border-emerald-300 bg-emerald-50', red: 'border-red-300 bg-red-50' };
const Bloc = ({ titre, n, ton, children }) => (n === 0 ? null : (
  <div className={`rounded-lg border p-3 ${TONS[ton]}`}>
    <div className="mb-1 text-sm font-semibold">{titre} ({n})</div>
    <ul className="space-y-1 text-sm">{children}</ul>
  </div>
));
