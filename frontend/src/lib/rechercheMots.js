// Recherche par composition de mots (02/10/2026) : une requête à plusieurs
// mots doit AFFINER, pas exclure. Chaque mot tapé doit être présent, mais
// pas forcément collé : « porte coupe feu » doit trouver « porte coupe-feu »
// (tiret) ou « Ventouse pour porte coupe-feu ». On compare sans accents et
// sans ponctuation, comme la normalisation serveur (normalise_recherche).
export function motsRequis(requete) {
  return String(requete || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .split(/[^a-z0-9.+]+/)
    .filter(Boolean);
}

export function sansAccents(txt) {
  return String(txt || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}

// Vrai si TOUS les mots de la requête apparaissent dans le texte.
export function correspondMots(texte, requete) {
  const mots = motsRequis(requete);
  if (mots.length === 0) return true;
  const cible = sansAccents(texte);
  return mots.every((m) => cible.includes(m));
}
