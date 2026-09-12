// Recherche et comparaison fournisseurs — acces aux donnees.
//
// Le backend `GET /api/fournisseurs/recherche` n'est pas encore deploye.
// Ce module expose une seule fonction, `rechercherFournisseurs`, et un
// commutateur unique (`UTILISER_JEU_EXEMPLE`) : tant qu'il est actif, la
// reponse vient du jeu de donnees d'exemple ci-dessous, calque sur l'exemple
// JSON du contrat d'API (docs contrat_api.md). Quand le backend est en ligne,
// on passe REACT_APP_FOURNISSEURS_MOCK=false (ou on force la constante a
// false) et la page appelle le vrai endpoint sans aucune autre modification :
// la forme de la reponse est identique.
//
// Aucune donnee d'exemple n'est ecrite en dur dans le rendu : les composants
// ne connaissent que la charge utile du contrat.
import { api } from '@/lib/api';

export const UTILISER_JEU_EXEMPLE =
  (process.env.REACT_APP_FOURNISSEURS_MOCK ?? 'true') !== 'false';

// Latence simulee, pour que l'etat de chargement soit reellement observable.
const LATENCE_EXEMPLE_MS = 450;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// --- Jeu de donnees d'exemple -------------------------------------------
// Structure strictement conforme a `GET /fournisseurs/recherche` (200).

const OFFRES_COMPARABLES = [
  {
    id: '0f5a1e58-6d9b-4a1e-9a2f-2f0c1d7b8e01',
    fournisseur: 'Rexel',
    designation: 'SN201SL Disjoncteur modulaire System pro M compact - 1P+N - 16A - courbe C - 6kA - 1 module - vis/vis',
    marque: 'ABB',
    reference_fournisseur: 'SN201SL16C',
    reference_fabricant: 'SN201SL16C',
    code_ean: '4016779584241',
    prix_net_ht: 6.83,
    prix_public_ht: 21.34,
    unite_vente: 'Pièce',
    url_produit: null,
  },
  {
    id: '1b2c3d4e-5f60-4712-8a93-b4c5d6e7f802',
    fournisseur: 'Rexel',
    designation: 'iC60N Disjoncteur Acti9 - 1P+N - 16A - courbe C - 6000A - peignable - bornes à vis',
    marque: 'Schneider Electric',
    reference_fournisseur: 'A9F77216',
    reference_fabricant: 'A9F77216',
    code_ean: '3606480081538',
    prix_net_ht: 11.47,
    prix_public_ht: 38.9,
    unite_vente: 'Pièce',
    url_produit: null,
  },
  {
    id: '2c3d4e5f-6071-4823-9ba4-c5d6e7f8a903',
    fournisseur: 'La Plateforme du Bâtiment',
    designation: 'Disjoncteur phase + neutre 16A courbe C 4,5kA Resi9 XE - connexion automatique - largeur 1 module',
    marque: 'Schneider Electric',
    reference_fournisseur: 'R9EFC616',
    reference_fabricant: 'R9EFC616',
    code_ean: '3606481182401',
    prix_net_ht: 13.98,
    prix_public_ht: 24.5,
    unite_vente: 'Pièce',
    url_produit: null,
  },
  {
    id: '3d4e5f60-7182-4934-8cb5-d6e7f8a9ba04',
    fournisseur: 'La Plateforme du Bâtiment',
    designation: 'Disjoncteur modulaire U+N 16A courbe C DX3 4500A/6kA - 1 module - bornes automatiques à ressort',
    marque: 'Legrand',
    reference_fournisseur: '406775',
    reference_fabricant: '406775',
    code_ean: '3414971049543',
    prix_net_ht: 16.2,
    prix_public_ht: 41.8,
    unite_vente: 'Pièce',
    url_produit: null,
  },
  {
    id: '4e5f6071-8293-4a45-9dc6-e7f8a9bacb05',
    fournisseur: 'Prolians',
    designation: 'Disjoncteur DNX3 1P+N 16A courbe C 4500A pouvoir de coupure - vis automatique - livré par lot de 1',
    marque: 'Legrand',
    reference_fournisseur: 'LEG406775P',
    reference_fabricant: '406775',
    code_ean: '3414971049543',
    prix_net_ht: 18.02,
    prix_public_ht: 41.8,
    unite_vente: 'Pièce',
    url_produit: null,
  },
  {
    id: '5f607182-93a4-4b56-8ed7-f8a9bacbdc06',
    fournisseur: 'Prolians',
    designation: 'Disjoncteur phase neutre 16A courbe C série Hager MFN - 1 module - raccordement à vis - 3kA',
    marque: 'Hager',
    reference_fournisseur: 'HAGMFN716',
    reference_fabricant: 'MFN716',
    code_ean: '3250612345678',
    prix_net_ht: 24.75,
    prix_public_ht: 52.1,
    unite_vente: 'Pièce',
    url_produit: null,
  },
  {
    id: '60718293-a4b5-4c67-9fe8-a9bacbdced07',
    fournisseur: 'Sonepar',
    designation: 'Disjoncteur 1P+N 16A courbe C 10kA industriel S200 - bornes cage - montage sur rail DIN 35mm',
    marque: 'ABB',
    reference_fournisseur: 'S201-C16NA',
    reference_fabricant: 'S201-C16NA',
    code_ean: '4016779578042',
    prix_net_ht: 31.4,
    prix_public_ht: 68.0,
    unite_vente: 'Pièce',
    url_produit: null,
  },
  {
    id: '718293a4-b5c6-4d78-8af9-bacbdcedfe08',
    fournisseur: 'Sonepar',
    designation: 'Lot de 3 disjoncteurs modulaires U+N 16A courbe C 6kA - conditionnement atelier - livraison sous 48h',
    marque: 'Schneider Electric',
    reference_fournisseur: 'A9F77216X3',
    reference_fabricant: 'A9F77216',
    code_ean: '3606480081545',
    prix_net_ht: 38.9,
    prix_public_ht: 116.7,
    unite_vente: 'Lot de 3',
    url_produit: null,
  },
  {
    id: '9a0b1c2d-3e4f-4506-8718-293a4b5c6d20',
    fournisseur: 'Rexel',
    designation: 'Disjoncteur modulaire 4P 16A courbe C 6kA - Acti9 iC60N tétrapolaire - 4 modules - bornes à vis',
    marque: 'Schneider Electric',
    reference_fournisseur: 'A9F77416',
    reference_fabricant: 'A9F77416',
    code_ean: '3606480081736',
    prix_net_ht: 44.6,
    prix_public_ht: 101.2,
    unite_vente: 'Pièce',
    url_produit: null,
  },
  {
    id: 'a1b2c3d4-4e5f-4617-8829-3a4b5c6d7e21',
    fournisseur: 'Prolians',
    designation: 'Disjoncteur 3P+N 16A courbe C 4500A DX3 - tétrapolaire - 4 modules - raccordement à vis',
    marque: 'Legrand',
    reference_fournisseur: 'LEG407865',
    reference_fabricant: '407865',
    code_ean: '3414971055667',
    prix_net_ht: 52.15,
    prix_public_ht: 118.9,
    unite_vente: 'Pièce',
    url_produit: null,
  },
  {
    id: '8293a4b5-c6d7-4e89-9b0a-cbdcedfe0f09',
    fournisseur: 'Rexel',
    designation: 'Disjoncteur 1P+N 16A courbe C avec contact auxiliaire de signalisation intégré - 2 modules',
    marque: 'Hager',
    reference_fournisseur: 'MFS716A',
    reference_fabricant: 'MFS716A',
    code_ean: '3250612987654',
    prix_net_ht: 62.3,
    prix_public_ht: 118.4,
    unite_vente: 'Pièce',
    url_produit: null,
  },
];

// Produits mis a part parce qu'ils sont d'une autre nature (qualifiants).
// Ils ne sont jamais supprimes : ils reintegrent la liste principale quand
// `inclure_qualifiants=true`.
const OFFRES_QUALIFIANTES = [
  {
    id: '93a4b5c6-d7e8-4f9a-8c1b-dcedfe0f1a10',
    fournisseur: 'Rexel',
    designation: 'Disjoncteur différentiel 1P+N 16A courbe C 30mA type AC - Acti9 iDPN Vigi - 2 modules',
    marque: 'Schneider Electric',
    reference_fournisseur: 'A9D31616',
    reference_fabricant: 'A9D31616',
    code_ean: '3606480099991',
    prix_net_ht: 88.4,
    prix_public_ht: 196.3,
    unite_vente: 'Pièce',
    url_produit: null,
    qualifiant: 'différentiel',
  },
  {
    id: 'a4b5c6d7-e8f9-4a0b-9d2c-edfe0f1a2b11',
    fournisseur: 'Prolians',
    designation: 'Disjoncteur différentiel phase neutre 16A courbe C 30mA type A - DX3 4500A - 3 modules',
    marque: 'Legrand',
    reference_fournisseur: 'LEG410705',
    reference_fabricant: '410705',
    code_ean: '3414971098765',
    prix_net_ht: 158.9,
    prix_public_ht: 289.0,
    unite_vente: 'Pièce',
    url_produit: null,
    qualifiant: 'différentiel',
  },
  {
    id: 'b5c6d7e8-f9a0-4b1c-8e3d-fe0f1a2b3c12',
    fournisseur: 'La Plateforme du Bâtiment',
    designation: 'Disjoncteur 1P+N 16A courbe C reconditionné - garantie atelier 6 mois - aspect d’usage',
    marque: 'Schneider Electric',
    reference_fournisseur: 'RECOND-A9F77216',
    reference_fabricant: 'A9F77216',
    code_ean: null,
    prix_net_ht: 8.79,
    prix_public_ht: 38.9,
    unite_vente: 'Pièce',
    url_produit: null,
    qualifiant: 'reconditionné',
  },
  {
    id: 'c6d7e8f9-a0b1-4c2d-9f4e-0f1a2b3c4d13',
    fournisseur: 'Sonepar',
    designation: 'Appareil combiné disjoncteur 1P+N 16A courbe C + parafoudre débrochable intégré - 4 modules',
    marque: 'ABB',
    reference_fournisseur: 'OVRSN201SL',
    reference_fabricant: 'OVRSN201SL',
    code_ean: '4016779599999',
    prix_net_ht: 64.25,
    prix_public_ht: 142.0,
    unite_vente: 'Pièce',
    url_produit: null,
    qualifiant: 'appareil combiné',
  },
];

const TERMES_CONNUS = {
  'ph+n': ['1P+N', 'Ph+N', 'U+N', 'phase neutre'],
  'ph n': ['1P+N', 'Ph+N', 'U+N', 'phase neutre'],
  courbe: ['courbe', 'Cbe', 'Crb'],
  '16a': ['16A', '16 A', 'In 16A'],
  disjoncteur: ['disjoncteur', 'disj.', 'Disj'],
  differentiel: ['différentiel', 'diff.', 'Vigi'],
  'd clencheur': ['déclencheur'],
};

const sansAccent = (s) =>
  (s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();

const mediane = (valeurs) => {
  if (!valeurs.length) return 0;
  const tri = [...valeurs].sort((a, b) => a - b);
  const milieu = Math.floor(tri.length / 2);
  return tri.length % 2 ? tri[milieu] : (tri[milieu - 1] + tri[milieu]) / 2;
};

const arrondi2 = (n) => Math.round(n * 100) / 100;

// Inclusion : une offre est retenue des qu'elle contient au moins un terme
// de la requete (la pertinence trie, elle ne filtre jamais — cf. contrat).
const correspond = (offre, jetons) => {
  if (!jetons.length) return true;
  const texte = sansAccent(
    `${offre.designation} ${offre.marque} ${offre.reference_fournisseur} ${offre.fournisseur}`
  );
  return jetons.some((j) => texte.includes(j));
};

const termesReconnus = (q) => {
  const brut = (q || '').toLowerCase().split(/\s+/).filter(Boolean);
  return brut
    .map((saisi) => {
      const cle = sansAccent(saisi).replace(/[^a-z0-9+]/g, ' ').trim();
      const equivalences = TERMES_CONNUS[cle];
      return equivalences ? { saisi, equivalences } : null;
    })
    .filter(Boolean);
};

const moinsCherParFournisseur = (offres) => {
  const parFournisseur = new Map();
  offres.forEach((o) => {
    const actuel = parFournisseur.get(o.fournisseur);
    if (!actuel || o.prix_net_ht < actuel.prix_net_ht) {
      parFournisseur.set(o.fournisseur, {
        fournisseur: o.fournisseur,
        prix_net_ht: o.prix_net_ht,
        designation: o.designation,
        id: o.id,
      });
    }
  });
  return [...parFournisseur.values()].sort((a, b) => a.prix_net_ht - b.prix_net_ht);
};

const reponseExemple = ({ q, limite, inclureQualifiants }) => {
  const jetons = sansAccent(q)
    .split(/\s+/)
    .map((j) => j.replace(/[^a-z0-9+]/g, ''))
    .filter((j) => j.length > 1);

  const comparables = OFFRES_COMPARABLES.filter((o) => correspond(o, jetons));
  const qualifiantes = OFFRES_QUALIFIANTES.filter((o) => correspond(o, jetons));

  const principaux = inclureQualifiants ? [...comparables, ...qualifiantes] : comparables;
  const resultats = [...principaux]
    .sort((a, b) => a.prix_net_ht - b.prix_net_ht)
    .slice(0, limite)
    .map(({ qualifiant, ...offre }) => offre); // eslint-disable-line no-unused-vars

  const prixTous = [...comparables, ...qualifiantes].map((o) => o.prix_net_ht);
  const min = prixTous.length ? Math.min(...prixTous) : 0;
  const max = prixTous.length ? Math.max(...prixTous) : 0;

  const groupesQualifiants = [];
  qualifiantes.forEach((o) => {
    const existant = groupesQualifiants.find((g) => g.libelle === o.qualifiant);
    if (existant) existant.prix.push(o.prix_net_ht);
    else groupesQualifiants.push({ libelle: o.qualifiant, prix: [o.prix_net_ht] });
  });

  const valeursPoles = [
    { valeur: '1P+N', nombre: comparables.filter((o) => /1P\+N|U\+N|phase \+ neutre|phase neutre/i.test(o.designation)).length },
    { valeur: '3P+N / 4P', nombre: comparables.filter((o) => /3P\+N|\b4P\b|t[ée]trapolaire/i.test(o.designation)).length },
  ].filter((v) => v.nombre > 0);

  const valeursMarques = [...new Set(comparables.map((o) => o.marque))]
    .map((marque) => ({ valeur: marque, nombre: comparables.filter((o) => o.marque === marque).length }))
    .sort((a, b) => b.nombre - a.nombre);

  const criteres = [];
  if (valeursPoles.length) criteres.push({ critere: 'pôles', valeurs: valeursPoles });
  if (valeursMarques.length > 1) criteres.push({ critere: 'marque', valeurs: valeursMarques });
  if (comparables.length > 1) {
    criteres.push({
      critere: 'pouvoir de coupure',
      valeurs: [
        { valeur: '4,5kA', nombre: comparables.filter((o) => /4[,.]5kA|4500A/i.test(o.designation)).length },
        { valeur: '6kA', nombre: comparables.filter((o) => /6kA|6000A/i.test(o.designation)).length },
        { valeur: '10kA', nombre: comparables.filter((o) => /10kA/i.test(o.designation)).length },
      ].filter((v) => v.nombre > 0),
    });
  }

  return {
    requete: q,
    total: comparables.length + qualifiantes.length,
    comparables: comparables.length,
    termes_reconnus: termesReconnus(q),
    prix: {
      min: arrondi2(min),
      max: arrondi2(max),
      median: arrondi2(mediane(prixTous)),
      ecart_pct: min > 0 ? Math.round(((max - min) / min) * 100) : 0,
    },
    resultats,
    moins_cher_par_fournisseur: moinsCherParFournisseur(principaux),
    qualifiants_isoles: groupesQualifiants.map((g) => ({
      libelle: g.libelle,
      nombre: g.prix.length,
      prix_median: arrondi2(mediane(g.prix)),
    })),
    criteres_a_affiner: criteres.filter((c) => c.valeurs.length > 1),
  };
};

// Erreur formatee comme une erreur axios, pour que la page traite de la meme
// facon le jeu d'exemple et le vrai backend (400 quand `q` est vide).
const erreurSimulee = (status, detail) => {
  const err = new Error(detail);
  err.response = { status, data: { detail } };
  return err;
};

/**
 * `GET /fournisseurs/recherche`
 * @param {{ q: string, limite?: number, inclureQualifiants?: boolean }} params
 * @returns {Promise<object>} charge utile conforme au contrat d'API
 */
export const rechercherFournisseurs = async ({ q, limite = 50, inclureQualifiants = false }) => {
  const requete = (q || '').trim();
  if (UTILISER_JEU_EXEMPLE) {
    await sleep(LATENCE_EXEMPLE_MS);
    if (!requete) throw erreurSimulee(400, 'La requête est obligatoire.');
    if (limite < 1 || limite > 200) throw erreurSimulee(422, 'La limite doit être comprise entre 1 et 200.');
    return reponseExemple({ q: requete, limite, inclureQualifiants });
  }
  const { data } = await api.get('/fournisseurs/recherche', {
    params: { q: requete, limite, inclure_qualifiants: inclureQualifiants },
  });
  return data;
};
