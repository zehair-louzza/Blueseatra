import React from 'react';
import { Card } from '@/components/ui/card';
import { TruncatedText } from '@/components/TruncatedText';
import { useTranslation } from 'react-i18next';
import { Handshake, TrendingUp } from 'lucide-react';
import { pourcent, ecartPct, prixComparable, prixUnitaire } from '@/lib/fournisseursFormat';
import { PrixParUnite } from '@/components/SupplierProductGroups';

// Encart de negociation : le moins cher chez chaque fournisseur.
// C'est la vue qui sert a appeler un commercial ("chez X c'est 6,83 €, vous
// etes a 18,02 €"), donc elle est mise en evidence en tete d'ecran, avec
// l'ecart en pourcentage entre le moins cher et le plus cher des fournisseurs.
// Comparaison au prix par unite de base (format unique) : un lot de 100 m
// n'est plus classe « le plus cher » ; son prix publie reste affiche.
export const SupplierCheapestPanel = ({ offres }) => {
  const { t } = useTranslation();
  const liste = [...(offres || [])].sort((a, b) => (prixComparable(a) ?? 0) - (prixComparable(b) ?? 0));
  if (liste.length === 0) return null;

  const prix = liste.map((o) => prixComparable(o));
  // Mètre chez l'un, pièce chez l'autre : un écart serait faux, on ne le calcule pas.
  const unitesDifferentes = new Set(liste.map((o) => o.unite_base).filter(Boolean)).size > 1;
  const ecart = unitesDifferentes ? null : ecartPct(prix);
  const moinsCher = liste[0];
  const plusCher = liste[liste.length - 1];

  return (
    <Card
      className="card-shadow overflow-hidden border-0 ring-2 ring-inset ring-primary/25"
      data-testid="fournisseurs-moins-cher"
    >
      <div className="flex flex-wrap items-start justify-between gap-3 bg-primary/5 px-4 py-3 sm:px-5">
        <div className="min-w-0">
          <h2 className="font-display inline-flex items-center gap-2 text-base font-semibold">
            <Handshake className="h-4 w-4 text-primary" />
            {t('fo.m_titre')}
          </h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {t('fo.m_aide')}
          </p>
        </div>
        {unitesDifferentes && (
          <p className="text-xs text-muted-foreground sm:text-right" data-testid="fournisseurs-unites-differentes">
            {t('fo.p_unites_diff')}
          </p>
        )}
        {ecart !== null && (
          <div className="text-left sm:text-right" data-testid="fournisseurs-ecart-negociation">
            <p className="inline-flex items-center gap-1.5 text-xs uppercase tracking-wide text-muted-foreground">
              <TrendingUp className="h-3.5 w-3.5" />
              {t('fo.m_ecart')}
            </p>
            <p className="font-display text-2xl font-semibold tabular-nums text-primary">
              {pourcent(ecart)}
            </p>
            <p className="text-xs text-muted-foreground">
              {t('fo.m_contre', {
                p1: prixUnitaire(prixComparable(moinsCher)), f1: moinsCher.fournisseur,
                p2: prixUnitaire(prixComparable(plusCher)), f2: plusCher.fournisseur,
              })}
            </p>
          </div>
        )}
      </div>
      <ul className="divide-y">
        {liste.map((offre, index) => (
          <li
            key={offre.id || `${offre.fournisseur}-${index}`}
            className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2.5 sm:flex-nowrap sm:px-5"
            data-testid="fournisseurs-moins-cher-ligne"
          >
            <span className="w-6 shrink-0 text-xs tabular-nums text-muted-foreground">
              {index + 1}.
            </span>
            <span className="w-full min-w-0 shrink-0 truncate text-sm font-medium sm:w-48">
              {offre.fournisseur}
            </span>
            <span className="min-w-0 flex-1 text-xs text-muted-foreground">
              <TruncatedText className="text-xs">{offre.designation}</TruncatedText>
            </span>
            <span className="ml-auto shrink-0 text-right text-sm">
              <PrixParUnite offre={offre} />
            </span>
            <span className="w-full shrink-0 text-right text-xs tabular-nums text-muted-foreground sm:w-24">
              {index === 0
                ? t('fo.m_reference')
                : unitesDifferentes
                  ? '\u2014'
                  : `+ ${pourcent(
                    Math.round(
                      ((prixComparable(offre) - prixComparable(moinsCher)) / prixComparable(moinsCher)) * 100
                    )
                  )}`}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
};
