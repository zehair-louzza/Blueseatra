/**
 * Repère de correspondance d'une offre avec la demande.
 *
 * POURQUOI CE REPERE EXISTE
 * -------------------------
 * Mesure sur le catalogue réel : la requête « disjoncteur 16A » retient
 * 14 052 lignes, dont 862 seulement annoncent 16A dans leur libellé. Les
 * 13 190 autres ne mentionnent aucun calibre — elles ne contredisent pas
 * la demande, donc on ne les écarte pas, mais elles ne la confirment pas
 * non plus.
 *
 * Les afficher sans distinction reviendrait à ne pas filtrer. Les
 * supprimer ferait perdre de vrais articles, le calibre pouvant figurer
 * dans une autre colonne ou sur la fiche produit.
 *
 * D'où ce repère, et la possibilité de masquer les libellés muets.
 */
import React from 'react';

const NIVEAUX = {
  exact: {
    libelle: 'Exact',
    classe: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
    aide: 'Toutes les précisions demandées sont confirmées par le libellé.',
  },
  partiel: {
    libelle: 'Partiel',
    classe: 'bg-amber-50 text-amber-800 ring-amber-600/20',
    aide: 'Une partie des précisions est confirmée, le reste n’est pas mentionné.',
  },
  'non precise': {
    libelle: 'Non précisé',
    classe: 'bg-slate-100 text-slate-600 ring-slate-500/20',
    aide:
      'Le libellé ne mentionne aucune des précisions demandées. L’article n’est pas ' +
      'écarté pour autant : une valeur absente n’est pas une valeur contraire.',
  },
};

export const SupplierMatchBadge = ({ niveau, confirmes = [], muets = [] }) => {
  const config = NIVEAUX[niveau];
  if (!config) return null;

  const detail = [
    confirmes.length ? `confirmé : ${confirmes.join(', ')}` : null,
    muets.length ? `non mentionné : ${muets.join(', ')}` : null,
  ]
    .filter(Boolean)
    .join(' · ');

  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-md px-1.5 py-0.5 text-[0.6875rem] font-medium ring-1 ring-inset ${config.classe}`}
      title={detail ? `${config.aide}\n${detail}` : config.aide}
      data-testid={`fournisseurs-niveau-${niveau.replace(' ', '-')}`}
    >
      {config.libelle}
    </span>
  );
};
