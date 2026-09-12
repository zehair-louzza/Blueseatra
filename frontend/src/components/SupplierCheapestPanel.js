import React from 'react';
import { Card } from '@/components/ui/card';
import { TruncatedText } from '@/components/TruncatedText';
import { Handshake, TrendingUp } from 'lucide-react';
import { prixHT, pourcent, ecartPct } from '@/lib/fournisseursFormat';

// Encart de negociation : le moins cher chez chaque fournisseur.
// C'est la vue qui sert a appeler un commercial ("chez X c'est 6,83 €, vous
// etes a 18,02 €"), donc elle est mise en evidence en tete d'ecran, avec
// l'ecart en pourcentage entre le moins cher et le plus cher des fournisseurs.
export const SupplierCheapestPanel = ({ offres }) => {
  const liste = [...(offres || [])].sort((a, b) => (a.prix_net_ht ?? 0) - (b.prix_net_ht ?? 0));
  if (liste.length === 0) return null;

  const prix = liste.map((o) => o.prix_net_ht);
  const ecart = ecartPct(prix);
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
            Le moins cher chez chaque fournisseur
          </h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Vue de négociation : une ligne par fournisseur, sur la spécification demandée.
          </p>
        </div>
        {ecart !== null && (
          <div className="text-left sm:text-right" data-testid="fournisseurs-ecart-negociation">
            <p className="inline-flex items-center gap-1.5 text-xs uppercase tracking-wide text-muted-foreground">
              <TrendingUp className="h-3.5 w-3.5" />
              Écart moins cher → plus cher
            </p>
            <p className="font-display text-2xl font-semibold tabular-nums text-primary">
              {pourcent(ecart)}
            </p>
            <p className="text-xs text-muted-foreground">
              {prixHT(moinsCher.prix_net_ht)} chez {moinsCher.fournisseur} contre{' '}
              {prixHT(plusCher.prix_net_ht)} chez {plusCher.fournisseur}
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
            <span className="ml-auto shrink-0 text-right text-sm font-semibold tabular-nums">
              {prixHT(offre.prix_net_ht)}
              <span className="ml-1 text-xs font-normal text-muted-foreground">HT</span>
            </span>
            <span className="w-full shrink-0 text-right text-xs tabular-nums text-muted-foreground sm:w-24">
              {index === 0
                ? 'référence'
                : `+ ${pourcent(
                    Math.round(
                      ((offre.prix_net_ht - moinsCher.prix_net_ht) / moinsCher.prix_net_ht) * 100
                    )
                  )}`}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
};
