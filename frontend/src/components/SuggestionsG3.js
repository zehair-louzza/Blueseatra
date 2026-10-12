import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { api, apiError } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Loader2, ListChecks, ArrowRight, Check } from 'lucide-react';

// Chaîne G3 (backend/recherche_g3.py) : fournitures extraites de la demande,
// articles du catalogue actif choisis parmi des candidats. Toujours « à valider ».
// « Reporter dans le devis » (backend/devis_sync.py) : les articles proposés
// sont écrits sur les lignes à confirmer du brouillon, puis prixés au prix
// catalogue sur confirmation — la validation humaine du devis est inchangée.
const SOURCE_TON = {
  ia: 'bg-primary/10 text-primary',
  repli: 'bg-amber-100 text-amber-800',
  aucun: 'bg-muted text-muted-foreground',
};

const prix = (v) => (typeof v === 'number' ? `${v.toFixed(2).replace('.', ',')} € HT` : '');

export default function SuggestionsG3({ demandeId }) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const [syncBusy, setSyncBusy] = useState(false);
  const [syncRes, setSyncRes] = useState(null);

  const lancer = async () => {
    setBusy(true);
    setRes(null);
    try {
      // Plusieurs appels IA à la suite : délai propre de 10 minutes.
      const { data } = await api.post(`/requests/${demandeId}/suggestions-g3`, null, { timeout: 600000 });
      setRes(data);
    } catch (err) {
      setRes({ statut: 'erreur', erreur: apiError(err, t('req.g3_error')), lignes: [] });
    } finally {
      setBusy(false);
    }
  };

  // Synchronisation déterministe (aucune IA) : quelques secondes suffisent,
  // mais la recherche fournisseurs peut enchaîner des requêtes par ligne.
  const reporter = async (appliquer = false) => {
    setSyncBusy(true);
    setSyncRes(null);
    try {
      const suffixe = appliquer ? '?appliquer=true' : '';
      const { data } = await api.post(`/requests/${demandeId}/sync-articles-devis${suffixe}`, null, { timeout: 300000 });
      setSyncRes(data);
    } catch (err) {
      setSyncRes({ erreur: apiError(err, t('req.g3_sync_error', 'Le report dans le devis a échoué')) });
    } finally {
      setSyncBusy(false);
    }
  };

  return (
    <Card className="card-shadow mt-4 border-0 p-5" data-testid="g3-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-base font-semibold">{t('req.g3_title')}</h2>
          <p className="text-xs text-muted-foreground">{t('req.g3_hint')}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" className="gap-1" onClick={lancer} disabled={busy || syncBusy} data-testid="g3-button">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ListChecks className="h-4 w-4" />}
            {busy ? t('req.g3_running') : t('req.g3_button')}
          </Button>
          <Button size="sm" className="gap-1" onClick={() => reporter(false)} disabled={busy || syncBusy} data-testid="g3-sync-button">
            {syncBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
            {syncBusy
              ? t('req.g3_sync_running', 'Report en cours…')
              : t('req.g3_sync_button', 'Reporter dans le devis')}
          </Button>
        </div>
      </div>

      {syncRes?.erreur && (
        <p className="mt-3 text-sm text-destructive" data-testid="g3-sync-error">{syncRes.erreur}</p>
      )}
      {syncRes && !syncRes.erreur && (
        <div className="mt-3 rounded-lg border bg-muted/40 px-3 py-2 text-sm" data-testid="g3-sync-result">
          <p>
            {t('req.g3_sync_done', {
              suggestions: syncRes.suggestions,
              total: syncRes.lignes_a_confirmer + syncRes.suggestions,
              defaultValue: '{{suggestions}} suggestion(s) d’article reportée(s) dans le brouillon.',
            })}
            {syncRes.appliquees > 0 && (
              <span className="ml-1 font-medium text-primary">
                {t('req.g3_sync_applied', {
                  count: syncRes.appliquees,
                  defaultValue: '{{count}} ligne(s) prixée(s) au tarif catalogue.',
                })}
              </span>
            )}
          </p>
          {syncRes.suggestions === 0 && syncRes.appliquees === 0 && (
            <p className="mt-1 text-xs text-muted-foreground" data-testid="g3-sync-none">
              {t('req.g3_sync_none', 'Aucune suggestion trouvée : vérifiez le catalogue actif ou activez un catalogue fournisseur (page Catalogues).')}
            </p>
          )}
          {syncRes.suggestions > 0 && syncRes.appliquees === 0 && (
            <Button variant="outline" size="sm" className="mt-2 gap-1" onClick={() => reporter(true)} disabled={syncBusy} data-testid="g3-sync-apply">
              <Check className="h-4 w-4" />
              {t('req.g3_sync_apply', 'Appliquer les prix du catalogue')}
            </Button>
          )}
          {syncRes.appliquees > 0 && (
            <p className="mt-1 text-xs text-muted-foreground">
              {t('req.g3_sync_review', 'Ouvrez le brouillon pour vérifier les lignes avant validation — le devis reste à valider.')}
            </p>
          )}
        </div>
      )}

      {res?.statut === 'erreur' && (
        <p className="mt-3 text-sm text-destructive" data-testid="g3-error">{res.erreur}</p>
      )}
      {res && res.statut !== 'erreur' && res.lignes.length === 0 && (
        <p className="mt-3 text-sm text-muted-foreground" data-testid="g3-empty">{res.remarque || t('req.g3_empty')}</p>
      )}
      {res && res.lignes.length > 0 && (
        <div className="mt-4">
          <p className="mb-2 text-xs text-amber-700" data-testid="g3-validate-note">{t('req.g3_validate_note')}</p>
          <div className="divide-y rounded-lg border">
            {res.lignes.map((l, i) => (
              <div key={i} className="px-3 py-2 text-sm" data-testid="g3-line">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium">{l.produit}{l.quantite ? <span className="font-normal text-muted-foreground"> · {l.quantite}</span> : null}</span>
                  <span className={`rounded-full px-2 py-0.5 text-xs ${SOURCE_TON[l.source] || ''}`}>{t(`req.g3_source_${l.source}`)}</span>
                </div>
                {l.articles.length > 0 ? (
                  <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
                    {l.articles.map((a, j) => (
                      <li key={`${a.item_code}-${j}`} className="flex flex-wrap gap-x-2">
                        <span className="font-mono">{a.item_code}</span>
                        <span className="text-foreground">{a.item_label}</span>
                        <span className="rounded bg-muted px-1.5">{a.origine === 'fournisseur' ? (a.fournisseur || t('req.g3_fournisseur')) : t('req.g3_catalogue_interne')}</span>
                        {a.unit && <span>· {a.unit}</span>}
                        {prix(a.unit_price_ht) && <span>· {prix(a.unit_price_ht)}</span>}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-1 text-xs text-muted-foreground">{t('req.g3_no_article')}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
