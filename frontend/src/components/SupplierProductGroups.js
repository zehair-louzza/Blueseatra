import React, { useState } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { TruncatedText } from '@/components/TruncatedText';
import { BadgeCommun } from '@/components/CatalogueCommunPanel';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { useTranslation } from 'react-i18next';
import { Boxes, ChevronDown, ChevronUp, ExternalLink, Link2, Shuffle } from 'lucide-react';
import { prixHT, prixUnitaire, pourcent, quantite, estLot, prixComparable } from '@/lib/fournisseursFormat';

// Produits identiques chez plusieurs fournisseurs (format unique, étape 2).
//
// Le backend regroupe les offres par clé produit : même EAN, ou même marque et
// même référence fabricant. Une offre peut donc apparaître ici alors que sa
// désignation ne contient pas les termes cherchés : c'est tout l'intérêt
// (« Onduleur EASY UPS 500 VA » chez Prolians = « Easy UPS BVS - onduleur… »
// chez Rexel). Les prix sont comparés par unité de base : un câble vendu par
// 100 m est comparé au mètre, et le prix publié reste affiché en dessous.

const GROUPES_VISIBLES = 5;

const Aide = ({ texte, children }) => (
  <TooltipProvider delayDuration={150}>
    <Tooltip>
      <TooltipTrigger asChild>{children}</TooltipTrigger>
      <TooltipContent className="max-w-xs text-xs">{texte}</TooltipContent>
    </Tooltip>
  </TooltipProvider>
);

/** Prix par unité de base, et prix publié du lot s'il diffère. */
export const PrixParUnite = ({ offre, gras = true }) => {
  const { t } = useTranslation();
  const p = prixComparable(offre);
  const unite = offre?.unite_base;
  const avecUnite = unite && (unite !== 'U' || estLot(offre));
  return (
    <span className="inline-flex flex-col items-end leading-tight">
      <span className={`tabular-nums ${gras ? 'font-semibold' : ''}`}>
        {prixUnitaire(p)}
        {avecUnite && (
          <span className="text-xs font-normal text-muted-foreground">/{t(`fo.u_${unite}`)}</span>
        )}
      </span>
      {estLot(offre) && (
        <span className="text-[11px] font-normal tabular-nums text-muted-foreground" data-testid="fournisseurs-prix-lot">
          {prixHT(offre.prix_net_ht)} {t('fo.lot', { q: quantite(offre.qte_par_conditionnement), u: t(`fo.u_${unite || 'U'}`) })}
        </span>
      )}
    </span>
  );
};

/** Pastilles d'anomalies (unité supposée, prix inhabituel…). */
export const BadgesAnomalies = ({ anomalies }) => {
  const { t } = useTranslation();
  if (!anomalies || anomalies.length === 0) return null;
  return (
    <span className="ml-1 inline-flex flex-wrap gap-1 align-middle">
      {anomalies.map((a) => (
        <Aide key={a} texte={t(`fo.a_aide_${a}`)}>
          <span
            className="inline-flex items-center rounded-full bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-800 ring-1 ring-inset ring-amber-200"
            data-testid="fournisseurs-anomalie"
          >
            {t(`fo.a_${a}`)}
          </span>
        </Aide>
      ))}
    </span>
  );
};

const Pastille = ({ icone: Icone, texte, aide, testid }) => (
  <Aide texte={aide}>
    <span
      className="inline-flex items-center gap-1 rounded-full bg-sky-50 px-1.5 py-0.5 text-[10px] font-medium text-sky-800 ring-1 ring-inset ring-sky-200"
      data-testid={testid}
    >
      <Icone className="h-3 w-3" />
      {texte}
    </span>
  </Aide>
);

const Groupe = ({ groupe }) => {
  const { t } = useTranslation();
  const meilleur = groupe.offres[0];
  return (
    <li className="px-4 py-3 sm:px-5" data-testid="fournisseurs-produit">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
        <div className="min-w-0 flex-1">
          <TruncatedText className="text-sm font-medium">{groupe.designation}</TruncatedText>
          <p className="mt-0.5 flex flex-wrap gap-x-3 text-xs text-muted-foreground">
            {groupe.marque && <span>{groupe.marque}</span>}
            {groupe.reference_fabricant && (
              <span className="font-mono">{t('fo.p_ref', { r: groupe.reference_fabricant })}</span>
            )}
            {groupe.gtin && <span className="font-mono">{t('fo.p_ean', { g: groupe.gtin })}</span>}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-xs font-medium text-primary">{t('fo.p_nb', { n: groupe.nb_fournisseurs })}</p>
          <p className="text-xs tabular-nums text-muted-foreground" data-testid="fournisseurs-produit-ecart">
            {groupe.unites_differentes
              ? t('fo.p_unites_diff')
              : groupe.ecart_pct !== null && groupe.ecart_pct !== undefined
                ? t('fo.p_ecart', { e: pourcent(groupe.ecart_pct) })
                : '\u2014'}
          </p>
        </div>
      </div>
      <ul className="mt-2 divide-y rounded-lg border">
        {groupe.offres.map((o, i) => (
          <li
            key={o.id}
            className={`flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 sm:flex-nowrap ${o === meilleur ? 'bg-primary/5' : ''}`}
            data-testid="fournisseurs-produit-offre"
          >
            <span className="w-5 shrink-0 text-xs tabular-nums text-muted-foreground">{i + 1}.</span>
            <span className="w-full min-w-0 shrink-0 text-sm font-medium sm:w-40">
              <TruncatedText className="text-sm font-medium">{o.fournisseur}</TruncatedText>
              {o.catalogue_commun && <BadgeCommun />}
            </span>
            <span className="min-w-0 flex-1 text-xs text-muted-foreground">
              <TruncatedText className="text-xs">{o.designation}</TruncatedText>
              <span className="mt-0.5 flex flex-wrap items-center gap-1">
                {o.designation_differente && (
                  <Pastille icone={Shuffle} texte={t('fo.p_libelle_diff')} aide={t('fo.p_libelle_diff_aide')}
                            testid="fournisseurs-libelle-different" />
                )}
                {o.par_reference && (
                  <Pastille icone={Link2} texte={t('fo.p_par_ref')} aide={t('fo.p_par_ref_aide')}
                            testid="fournisseurs-par-reference" />
                )}
                <BadgesAnomalies anomalies={o.anomalies} />
                {o.autres_offres > 0 && (
                  <span className="text-[10px]">{t('fo.p_autres', { n: o.autres_offres })}</span>
                )}
              </span>
            </span>
            <span className="ml-auto shrink-0 text-right text-sm">
              <PrixParUnite offre={o} />
            </span>
            <span className="w-16 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
              {i === 0 ? t('fo.m_reference') : o.ecart_pct !== null && o.ecart_pct !== undefined ? `+ ${pourcent(o.ecart_pct)}` : '\u2014'}
            </span>
            {o.url_produit ? (
              <a
                href={o.url_produit}
                target="_blank"
                rel="noopener noreferrer"
                className="shrink-0 text-muted-foreground hover:text-foreground"
                aria-label={t('fo.p_fiche')}
                title={t('fo.p_fiche')}
              >
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            ) : (
              <span className="w-3.5 shrink-0" />
            )}
          </li>
        ))}
      </ul>
    </li>
  );
};

export const SupplierProductGroups = ({ produits }) => {
  const { t } = useTranslation();
  const [tout, setTout] = useState(false);
  const liste = produits || [];
  if (liste.length === 0) return null;
  const visibles = tout ? liste : liste.slice(0, GROUPES_VISIBLES);
  const reste = liste.length - GROUPES_VISIBLES;

  return (
    <Card className="card-shadow overflow-hidden border-0" data-testid="fournisseurs-produits-identiques">
      <div className="border-b px-4 py-3 sm:px-5">
        <h2 className="font-display inline-flex items-center gap-2 text-base font-semibold">
          <Boxes className="h-4 w-4 text-primary" />
          {t('fo.p_titre')}
        </h2>
        <p className="mt-0.5 max-w-3xl text-xs text-muted-foreground">{t('fo.p_aide')}</p>
      </div>
      <ul className="divide-y">
        {visibles.map((g) => <Groupe key={g.cle_produit} groupe={g} />)}
      </ul>
      {reste > 0 && (
        <div className="border-t px-4 py-2 sm:px-5">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-8 gap-1.5 px-2 text-xs"
            onClick={() => setTout((v) => !v)}
            data-testid="fournisseurs-produits-voir-plus"
          >
            {tout ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            {tout ? t('fo.p_voir_moins') : t('fo.p_voir_plus', { n: reste })}
          </Button>
        </div>
      )}
    </Card>
  );
};
