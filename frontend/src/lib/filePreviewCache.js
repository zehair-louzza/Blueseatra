// Cache de previsualisation 100% cote client, en memoire uniquement.
//
// Le fichier original (PDF, image...) n'est jamais envoye a un stockage
// serveur pour etre reaffiche plus tard : cette Map ne vit que dans l'onglet
// du navigateur, le temps de la session. Objectif : permettre a l'utilisateur
// de revoir le document qu'il vient d'importer, juste apres l'import, pour
// comparer visuellement avec le resultat d'extraction — sans que le SaaS ne
// conserve la moindre copie du fichier en base ou sur disque.
//
// Consequence attendue et voulue : un rechargement de page, une navigation
// directe par URL, ou le retour plus tard sur une demande deja traitee ne
// donnera plus acces a l'apercu (le bouton disparait alors naturellement).

const cache = new Map(); // requestId -> { file: File, url: string }

export function setFilePreview(requestId, file) {
  if (!requestId || !file) return;
  clearFilePreview(requestId);
  cache.set(requestId, { file, url: null });
}

export function hasFilePreview(requestId) {
  return cache.has(requestId);
}

export function openFilePreview(requestId) {
  const entry = cache.get(requestId);
  if (!entry) return false;
  if (!entry.url) entry.url = URL.createObjectURL(entry.file);
  window.open(entry.url, '_blank', 'noopener');
  return true;
}

export function clearFilePreview(requestId) {
  const entry = cache.get(requestId);
  if (entry && entry.url) URL.revokeObjectURL(entry.url);
  cache.delete(requestId);
}
