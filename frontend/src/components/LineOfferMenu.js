import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import { Loader2, RefreshCw, Store } from 'lucide-react';
import { api, apiError } from '@/lib/api';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

const money = (v) => (v === null || v === undefined ? '\u2014' : `${Number(v).toFixed(2)}`);

// Menu de choix du fournisseur d'une ligne de fourniture (04/10/2026).
// Au survol/clic sur la ligne : la meilleure offre est déjà appliquée par le
// backend (pertinence puis prix, prix figé à la sélection) ; ce menu liste
// les alternatives pour en choisir une autre. Le changement passe par
// POST /quotes/{id}/lines/{n}/offer qui REFIGE le prix et recalcule les
// totaux. L'IA ne choisit pas le fournisseur : la recherche classe,
// l'humain tranche.
export const LineOfferMenu = ({ quoteId, lineIndex, ligne, onChosen, disabled }) => {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [offres, setOffres] = useState([]);
  const [chargement, setChargement] = useState(false);
  const [choix, setChoix] = useState(null);
  const actuelle = ligne.chosen_offer;

  useEffect(() => {
    if (!open) return;
    let vivant = true;
    const charger = async () => {
      setChargement(true);
      try {
        // Recherche FRAÎCHE : le cache de la ligne peut dater d'avant le
        // dernier import de tarif.
        const { data } = await api.get(`/quotes/${quoteId}/lines/${lineIndex}/offers`);
        if (vivant) setOffres(data.offres || []);
      } catch (err) {
        if (vivant) toast.error(apiError(err, 'Failed'));
      } finally {
        if (vivant) setChargement(false);
      }
    };
    charger();
    return () => { vivant = false; };
  }, [open, quoteId, lineIndex]);

  const choisir = async (offre) => {
    setChoix(offre.id);
    try {
      const { data } = await api.post(`/quotes/${quoteId}/lines/${lineIndex}/offer`,
        { offer_id: offre.id });
      onChosen?.(data.quote);
      toast.success(`${offre.fournisseur || ''} \u2014 ${money(offre.prix_net_ht)}`);
      setOpen(false);
    } catch (err) {
      toast.error(apiError(err, 'Failed'));
    } finally {
      setChoix(null);
    }
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          disabled={disabled}
          className={cn(
            'mt-0.5 inline-flex max-w-full items-center gap-1 rounded-full bg-muted px-2 py-0.5',
            'text-[10px] font-medium text-muted-foreground transition-colors hover:bg-primary/10 hover:text-primary',
            actuelle && 'text-emerald-700 hover:bg-emerald-50')}
          data-testid="line-offer-menu"
          title={t('quote.offers_hint')}
        >
          <Store className="h-3 w-3 shrink-0" />
          <span className="truncate">
            {actuelle
              ? `${actuelle.fournisseur || ''} \u00b7 ${money(actuelle.prix_net_ht)}`
              : t('quote.offers_choose')}
          </span>
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-96 p-0" data-testid="line-offer-popover">
        <div className="border-b px-3 py-2">
          <p className="text-xs font-semibold">{t('quote.offers_title')}</p>
          <p className="mt-0.5 text-[11px] text-muted-foreground">{t('quote.offers_hint')}</p>
        </div>
        <div className="max-h-72 overflow-auto">
          {chargement && (
            <div className="flex items-center justify-center gap-2 py-6 text-xs text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />{t('quote.offers_loading')}
            </div>
          )}
          {!chargement && offres.length === 0 && (
            <p className="px-3 py-6 text-center text-xs text-muted-foreground">
              {t('quote.offers_none')}
            </p>
          )}
          {!chargement && offres.map((o) => {
            const estActuelle = actuelle && actuelle.id === o.id;
            return (
              <button
                key={o.id}
                type="button"
                disabled={choix !== null}
                onClick={() => choisir(o)}
                className={cn(
                  'flex w-full flex-col gap-0.5 border-b px-3 py-2 text-left text-xs transition-colors last:border-b-0',
                  estActuelle ? 'bg-emerald-50/70' : 'hover:bg-muted/60')}
                data-testid="line-offer-row"
              >
                <span className="flex w-full items-center justify-between gap-2">
                  <span className="truncate font-semibold">{o.fournisseur || '\u2014'}</span>
                  <span className="shrink-0 font-semibold tabular-nums">{money(o.prix_net_ht)}</span>
                </span>
                <span className="truncate text-muted-foreground">{o.designation}</span>
                <span className="flex items-center gap-2 text-[10px] text-muted-foreground">
                  {o.marque && <span className="font-medium">{o.marque}</span>}
                  {o.reference_fournisseur && <span className="font-mono">{o.reference_fournisseur}</span>}
                  {o.unite_vente && <span>/{o.unite_vente}</span>}
                  {estActuelle && <span className="ml-auto font-semibold text-emerald-700">{t('quote.offers_current')}</span>}
                </span>
              </button>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
};
