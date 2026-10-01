import React from 'react';
import { Card } from '@/components/ui/card';
import { useTranslation } from 'react-i18next';
import { FolderTree, SlidersHorizontal, ChevronRight } from 'lucide-react';
import { entier, prixHT } from '@/lib/fournisseursFormat';

// « Isolés car d'une autre nature ».
// Ces produits contiennent bien les termes demandes mais changent la nature de
// l'appareil (differentiel, reconditionne, appareil combine...). Ils ne sont
// jamais supprimes : un clic les reintegre dans la liste principale
// (inclure_qualifiants=true), ce qui relance la recherche.
export const IsolatedQualifiers = ({ qualifiants, inclus, onInclure }) => {
  const { t } = useTranslation();
  const liste = qualifiants || [];
  if (liste.length === 0) return null;

  return (
    <Card className="card-shadow border-0 p-4 sm:p-5" data-testid="fournisseurs-qualifiants">
      <h2 className="font-display inline-flex items-center gap-2 text-base font-semibold">
        <FolderTree className="h-4 w-4 text-muted-foreground" />
        {t('fo.q_titre')}
      </h2>
      <p className="mt-0.5 text-xs text-muted-foreground">
        {inclus
          ? t('fo.q_inclus')
          : t('fo.q_a_part')}
      </p>
      <ul className="mt-3 space-y-1.5">
        {liste.map((q) => (
          <li key={q.libelle}>
            <button
              type="button"
              onClick={() => onInclure(q.libelle)}
              data-testid="fournisseurs-qualifiant-ligne"
              aria-label={t('fo.q_aria', { l: q.libelle })}
              className="flex w-full flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border px-3 py-2 text-left transition-colors hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <span className="min-w-0 flex-1 truncate text-sm font-medium">{q.libelle}</span>
              <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                {entier(q.nombre)} {t('fo.produit', { count: Number(q.nombre) || 0 })}
              </span>
              <span className="shrink-0 text-xs tabular-nums">
                {t('fo.mediane', { p: prixHT(q.prix_median) })}
              </span>
              <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
            </button>
          </li>
        ))}
      </ul>
    </Card>
  );
};

// « Affinez votre recherche » : chaque valeur de criteres_a_affiner est un
// bouton qui ajoute le terme a la requete et relance immediatement. Le bloc
// n'apparait que si le backend juge les resultats heterogenes.
export const RefineCriteria = ({ criteres, onAjouterTerme, requete }) => {
  const { t } = useTranslation();
  const liste = (criteres || []).filter((c) => (c?.valeurs || []).length > 0);
  if (liste.length === 0) return null;

  const dejaDansRequete = (valeur) =>
    (requete || '').toLowerCase().includes(String(valeur).toLowerCase());

  return (
    <Card className="card-shadow border-0 p-4 sm:p-5" data-testid="fournisseurs-affiner">
      <h2 className="font-display inline-flex items-center gap-2 text-base font-semibold">
        <SlidersHorizontal className="h-4 w-4 text-muted-foreground" />
        {t('fo.a_titre')}
      </h2>
      <p className="mt-0.5 text-xs text-muted-foreground">
        {t('fo.a_aide')}
      </p>
      <div className="mt-3 space-y-3">
        {liste.map((c) => (
          <div key={c.critere}>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">{c.critere}</p>
            <ul className="mt-1.5 flex flex-wrap gap-2">
              {c.valeurs.map((v) => (
                <li key={`${c.critere}-${v.valeur}`}>
                  <button
                    type="button"
                    onClick={() => onAjouterTerme(v.valeur)}
                    disabled={dejaDansRequete(v.valeur)}
                    data-testid="fournisseurs-affiner-valeur"
                    aria-label={t('fo.a_aria', { v: v.valeur })}
                    className="inline-flex max-w-full items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <span className="truncate font-medium">{v.valeur}</span>
                    <span className="shrink-0 tabular-nums text-muted-foreground">
                      {entier(v.nombre)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Card>
  );
};
