// Formatage partagé par les écrans fournisseurs.
// Les prix sont toujours affichés avec deux décimales, dans la langue de
// l'interface : 3,20 € (espace insécable pour les milliers, virgule décimale)
// en français, €3.20 en anglais. Un chiffreur doit pouvoir comparer deux
// colonnes d'un coup d'oeil.
import { localeCourante } from '@/lib/locale';

const formats = {};
const format = (cle, options) => {
  const locale = localeCourante();
  const k = `${locale}|${cle}`;
  if (!formats[k]) formats[k] = new Intl.NumberFormat(locale, options);
  return formats[k];
};

const prix = () => format('prix', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const ent = () => format('entier', { maximumFractionDigits: 0 });

/** Prix HT en euros, deux décimales. '—' si absent. */
export const prixHT = (valeur) => {
  if (valeur === null || valeur === undefined || valeur === '' || Number.isNaN(Number(valeur))) {
    return '\u2014';
  }
  return prix().format(Number(valeur));
};

/** Nombre entier (12 345 en français, 12,345 en anglais). */
export const entier = (valeur) => ent().format(Number(valeur) || 0);

/** Pourcentage entier : 164 % en français, 164% en anglais. */
export const pourcent = (valeur) => {
  if (valeur === null || valeur === undefined || Number.isNaN(Number(valeur))) return '\u2014';
  const n = ent().format(Number(valeur));
  return localeCourante() === 'fr-FR' ? `${n}\u00a0%` : `${n}%`;
};

/** Écart en % entre le prix le plus bas et le plus haut d'une liste. */
export const ecartPct = (liste) => {
  const valides = (liste || []).map(Number).filter((n) => Number.isFinite(n) && n > 0);
  if (valides.length < 2) return null;
  const min = Math.min(...valides);
  const max = Math.max(...valides);
  return Math.round(((max - min) / min) * 100);
};

// --- Format unique : prix comparables ----------------------------------------
// Le backend renvoie, pour chaque offre normalisée, `prix_unite_base_ht`
// (prix par mètre, m², kg… ou par pièce) et `qte_par_conditionnement`
// (100 pour un câble YESSS vendu par 100 m). Le prix publié reste
// `prix_net_ht`.

const prixFin = () => format('prix_fin', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 4,
});

const qte = () => format('quantite', { maximumFractionDigits: 3 });

/** Prix par unité de base : 4 décimales sous 1 € (0,0123 €/m), sinon 2. */
export const prixUnitaire = (valeur) => {
  if (valeur === null || valeur === undefined || valeur === '' || Number.isNaN(Number(valeur))) {
    return '\u2014';
  }
  const n = Number(valeur);
  return (Math.abs(n) < 1 ? prixFin() : prix()).format(n);
};

/** Quantité de conditionnement : 100, 1,08… */
export const quantite = (valeur) => qte().format(Number(valeur) || 0);

/** Prix servant à comparer : par unité de base s'il est connu, sinon brut. */
export const prixComparable = (offre) => {
  const u = Number(offre?.prix_unite_base_ht);
  if (Number.isFinite(u) && u > 0) return u;
  const p = Number(offre?.prix_net_ht);
  return Number.isFinite(p) && p > 0 ? p : null;
};

/** Vrai si le prix publié porte sur plusieurs unités de base (lot, rouleau…). */
export const estLot = (offre) => {
  const q = Number(offre?.qte_par_conditionnement);
  return Number.isFinite(q) && q > 0 && q !== 1;
};
