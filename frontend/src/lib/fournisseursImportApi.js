// Import de tarifs fournisseurs — acces aux donnees.
//
// Trois appels seulement, calques exactement sur le contrat du backend
// (backend/server.py) :
//   POST /fournisseurs/import/preview  -> champ `files` repete
//   POST /fournisseurs/import          -> `files` repete + `fournisseurs`,
//                                         `mappings`, `onglets` (JSON alignes
//                                         sur l'ordre des fichiers)
//   GET  /fournisseurs/catalogues      -> catalogues actifs du tenant
//
// Les tarifs fournisseurs pesent plusieurs dizaines de Mo : l'envoi expose
// une progression (`onProgression`) et desactive le timeout par defaut
// d'axios, qui couperait un import de 60 Mo en cours de route.
import { api } from '@/lib/api';

/** Extensions acceptees par le backend (CSV + Excel). */
export const EXTENSIONS_ACCEPTEES = ['.csv', '.xlsx', '.xlsm'];
export const ACCEPT_INPUT = EXTENSIONS_ACCEPTEES.join(',');

/** Le backend refuse au-dela de 12 fichiers par envoi. */
export const MAX_FICHIERS = 12;

/** Vrai si le nom de fichier porte une extension acceptee. */
export const extensionAcceptee = (nom) =>
  EXTENSIONS_ACCEPTEES.some((ext) => (nom || '').toLowerCase().endsWith(ext));

/** Taille lisible : 5,6 Mo. */
export const tailleLisible = (octets) => {
  const n = Number(octets);
  if (!Number.isFinite(n) || n <= 0) return '\u2014';
  if (n < 1024) return `${n} o`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} ko`;
  return `${(n / (1024 * 1024)).toFixed(1).replace('.', ',')} Mo`;
};

/** Date ISO -> 12/09/2026 14:05. '—' si absente. */
export const dateLisible = (iso) => {
  if (!iso) return '\u2014';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleString('fr-FR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
};

/**
 * Previsualise plusieurs fichiers d'un coup.
 * @returns {Promise<{fichiers: Array, champs_standards: Array}>}
 */
export const previsualiserTarifs = async (fichiers, { onProgression } = {}) => {
  const fd = new FormData();
  fichiers.forEach((f) => fd.append('files', f, f.name));
  const { data } = await api.post('/fournisseurs/import/preview', fd, {
    timeout: 0,
    onUploadProgress: (e) => {
      if (!onProgression) return;
      onProgression(e.total ? Math.round((e.loaded * 100) / e.total) : null);
    },
  });
  return data;
};

/**
 * Importe les fichiers previsualises.
 * Les trois tableaux JSON sont construits ICI, dans l'ordre exact de
 * `entrees`, et `files` est ajoute dans le meme ordre : le backend indexe
 * `fournisseurs[i]`, `mappings[i]` et `onglets[i]` par position.
 * @param {Array<{fichier: File, fournisseur: string, mapping: object, onglet: string|null}>} entrees
 * @returns {Promise<{rapports: Array}>}
 */
export const importerTarifs = async (entrees, { onProgression } = {}) => {
  const fd = new FormData();
  entrees.forEach((e) => fd.append('files', e.fichier, e.fichier.name));
  fd.append('fournisseurs', JSON.stringify(entrees.map((e) => (e.fournisseur || '').trim())));
  fd.append('mappings', JSON.stringify(entrees.map((e) => e.mapping || {})));
  fd.append('onglets', JSON.stringify(entrees.map((e) => e.onglet ?? null)));
  const { data } = await api.post('/fournisseurs/import', fd, {
    timeout: 0,
    onUploadProgress: (e) => {
      if (!onProgression) return;
      onProgression(e.total ? Math.round((e.loaded * 100) / e.total) : null);
    },
  });
  return data;
};

/** Catalogues fournisseurs du tenant, avec la version active de chacun. */
export const listerCatalogues = async () => {
  const { data } = await api.get('/fournisseurs/catalogues');
  return data;
};
