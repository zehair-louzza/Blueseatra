// Formatage francais partage par l'ecran de comparaison fournisseurs.
// Les prix sont toujours affiches avec deux decimales et le separateur
// francais (espace insecable pour les milliers, virgule decimale), comme sur
// un devis papier : un chiffreur doit pouvoir comparer deux colonnes d'un
// coup d'oeil.

const nfPrix = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const nfEntier = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 });

/** Prix HT en euros, deux decimales, separateur francais. '—' si absent. */
export const prixHT = (valeur) => {
  if (valeur === null || valeur === undefined || valeur === '' || Number.isNaN(Number(valeur))) {
    return '\u2014';
  }
  return nfPrix.format(Number(valeur));
};

/** Nombre entier format francais (12 345). */
export const entier = (valeur) => nfEntier.format(Number(valeur) || 0);

/** Pourcentage entier signe positif : 164 % . */
export const pourcent = (valeur) => {
  if (valeur === null || valeur === undefined || Number.isNaN(Number(valeur))) return '\u2014';
  return `${nfEntier.format(Number(valeur))}\u00a0%`;
};

/** Ecart en % entre le prix le plus bas et le plus haut d'une liste. */
export const ecartPct = (prix) => {
  const valides = (prix || []).map(Number).filter((n) => Number.isFinite(n) && n > 0);
  if (valides.length < 2) return null;
  const min = Math.min(...valides);
  const max = Math.max(...valides);
  return Math.round(((max - min) / min) * 100);
};
