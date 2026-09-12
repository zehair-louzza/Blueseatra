import React from 'react';
import { Card } from '@/components/ui/card';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Info, ScanSearch } from 'lucide-react';
import { entier, prixHT, pourcent } from '@/lib/fournisseursFormat';

// Bandeau de garantie d'inclusion.
// `total` et `comparables` sont TOUJOURS affiches cote a cote : masquer
// l'ecart romprait la promesse du produit (rien n'est cache, les produits
// d'une autre nature sont mis a part, jamais supprimes).
export const SupplierSearchSummary = ({ reponse }) => {
  const total = Number(reponse?.total) || 0;
  const comparables = Number(reponse?.comparables) || 0;
  const misAPart = Math.max(total - comparables, 0);
  const prix = reponse?.prix || {};

  return (
    <Card className="card-shadow border-0 p-4 sm:p-5" data-testid="fournisseurs-summary">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div data-testid="fournisseurs-total">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Résultats trouvés</p>
          <p className="font-display text-2xl font-semibold tabular-nums">{entier(total)}</p>
          <p className="mt-0.5 text-xs text-muted-foreground">Tout produit contenant vos termes</p>
        </div>
        <div data-testid="fournisseurs-comparables">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Dont comparables</p>
          <p className="font-display text-2xl font-semibold tabular-nums text-primary">{entier(comparables)}</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {misAPart > 0
              ? `${entier(misAPart)} mis à part, d’une autre nature`
              : 'Aucun produit mis à part'}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Prix net HT (min / méd. / max)</p>
          <p className="mt-1 text-sm font-medium tabular-nums">
            {prixHT(prix.min)} <span className="text-muted-foreground">/</span> {prixHT(prix.median)}{' '}
            <span className="text-muted-foreground">/</span> {prixHT(prix.max)}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Écart min → max</p>
          <p className="mt-1 text-sm font-medium tabular-nums">{pourcent(prix.ecart_pct)}</p>
          <p className="mt-0.5 text-xs text-muted-foreground">Sur l’ensemble des résultats</p>
        </div>
      </div>
      <p className="mt-3 flex items-start gap-1.5 border-t pt-3 text-xs text-muted-foreground">
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <span>
          La pertinence trie, elle ne filtre jamais : les {entier(total)} lignes trouvées restent
          accessibles, {entier(comparables)} sont comparables sur la spécification demandée.
        </span>
      </p>
    </Card>
  );
};

// Bandeau des termes reconnus : montre au chiffreur que « ph+n » a bien ete
// compris comme « 1P+N », « U+N », « phase neutre ». Sans ce retour, une
// requete sans resultat est indebuggable cote utilisateur.
export const RecognizedTerms = ({ termes, requete }) => {
  const liste = Array.isArray(termes) ? termes : [];
  return (
    <Card className="card-shadow border-0 p-4" data-testid="fournisseurs-termes-reconnus">
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1.5 text-sm font-medium">
          <ScanSearch className="h-4 w-4 text-muted-foreground" />
          Termes reconnus
        </span>
        {liste.length === 0 ? (
          <span className="text-xs text-muted-foreground">
            Aucun terme technique reconnu dans «&nbsp;{requete}&nbsp;» — la recherche a porté sur le
            texte brut. Essayez une abréviation métier (ph+n, courbe, 16a).
          </span>
        ) : (
          <ul className="flex flex-wrap items-center gap-2">
            {liste.map((terme) => (
              <li key={terme.saisi}>
                <TooltipProvider delayDuration={150}>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        className="inline-flex max-w-full cursor-help flex-wrap items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-xs ring-1 ring-inset ring-border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        data-testid="fournisseurs-terme-reconnu"
                      >
                        <span className="font-mono font-medium">{terme.saisi}</span>
                        <span className="text-muted-foreground">compris comme</span>
                        <span className="font-medium">
                          {(terme.equivalences || []).join(' · ')}
                        </span>
                      </button>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs">
                      <p className="text-xs">
                        « {terme.saisi} » recherché aussi sous&nbsp;: {(terme.equivalences || []).join(', ')}
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
};
