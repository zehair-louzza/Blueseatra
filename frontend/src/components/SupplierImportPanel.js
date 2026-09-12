// Import de catalogues fournisseurs — panneau multi-fichiers.
//
// Meme experience que l'onglet Catalogue (depot du fichier, apercu,
// association des colonnes, bouton d'import), mais pour PLUSIEURS fichiers a
// la fois : le chiffreur recoit cinq tarifs par mail, il les depose ensemble,
// verifie cinq cartes, et lance un seul import. Chaque fichier devient le
// catalogue d'un fournisseur, et tous restent actifs -- la recherche les
// interroge simultanement.
//
// Contrat backend respecte a la lettre :
//   POST /fournisseurs/import/preview : champ `files` repete.
//   POST /fournisseurs/import : `files` repete + `fournisseurs`, `mappings`,
//   `onglets`, trois tableaux JSON ALIGNES sur l'ordre des fichiers. Cet
//   alignement est garanti par une seule source de verite : le tableau
//   `entrees` ci-dessous, parcouru une fois pour tout construire.
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { apiError } from '@/lib/api';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { SupplierImportFileCard } from '@/components/SupplierImportFileCard';
import { SupplierCatalogsPanel } from '@/components/SupplierCatalogsPanel';
import { TruncatedText } from '@/components/TruncatedText';
import { entier } from '@/lib/fournisseursFormat';
import {
  previsualiserTarifs, importerTarifs, listerCatalogues,
  extensionAcceptee, tailleLisible, ACCEPT_INPUT, EXTENSIONS_ACCEPTEES,
  MAX_FICHIERS,
} from '@/lib/fournisseursImportApi';
import { toast } from 'sonner';
import {
  Upload, UploadCloud, Loader2, AlertTriangle, CheckCircle2, XCircle,
  Trash2, FileSpreadsheet, ClipboardList, ArrowRight,
} from 'lucide-react';

// Deux fichiers sont consideres identiques s'ils ont meme nom et meme taille :
// suffisant pour eviter le doublon d'un double depot accidentel.
const memeFichier = (a, b) => a.name === b.name && a.size === b.size;

// Message francais utile par code d'erreur du contrat.
const messageErreur = (err, contexte) => {
  const status = err?.response?.status;
  const detail = apiError(err, 'Le serveur n’a pas répondu.');
  if (status === 400) return { titre: 'Fichiers refusés', texte: detail };
  if (status === 401) {
    return {
      titre: 'Session expirée',
      texte: 'Votre jeton d’accès n’est plus valide. Reconnectez-vous, puis relancez l’envoi.',
      detail,
    };
  }
  if (status === 403) {
    return {
      titre: 'Accès refusé',
      texte: 'L’import de tarifs est réservé aux rôles owner, admin et operator. Demandez l’autorisation à un owner.',
      detail,
    };
  }
  if (status === 413) {
    return {
      titre: 'Fichiers trop volumineux',
      texte: 'L’envoi dépasse la taille acceptée. Découpez le tarif par famille, ou envoyez les fichiers en deux fois.',
      detail,
    };
  }
  if (status === 422) {
    return { titre: 'Paramètres invalides', texte: detail };
  }
  return {
    titre: contexte === 'import' ? 'Import impossible' : 'Analyse impossible',
    texte: 'Le serveur n’a pas pu traiter les fichiers. Les tarifs sont volumineux : vérifiez votre connexion, puis réessayez.',
    detail,
  };
};

export const SupplierImportPanel = () => {
  // Fichiers choisis, pas encore analyses.
  const [enAttente, setEnAttente] = useState([]);
  // Fichiers analyses : source de verite de l'ordre envoye au backend.
  const [entrees, setEntrees] = useState([]);
  const [champsStandards, setChampsStandards] = useState([]);
  const [travail, setTravail] = useState(null); // 'analyse' | 'import' | null
  const [progression, setProgression] = useState(null);
  const [erreur, setErreur] = useState(null);
  const [rapports, setRapports] = useState(null);
  const [survol, setSurvol] = useState(false);

  const [catalogues, setCatalogues] = useState(null);
  const [cataloguesChargement, setCataloguesChargement] = useState(true);
  const [cataloguesErreur, setCataloguesErreur] = useState(null);

  const inputRef = useRef(null);
  const occupe = travail !== null;

  const chargerCatalogues = useCallback(() => {
    setCataloguesChargement(true);
    setCataloguesErreur(null);
    return listerCatalogues()
      .then((data) => setCatalogues(data))
      .catch((err) => setCataloguesErreur(apiError(err, 'Le serveur n’a pas répondu.')))
      .finally(() => setCataloguesChargement(false));
  }, []);

  useEffect(() => { chargerCatalogues(); }, [chargerCatalogues]);

  // --- Depot des fichiers -------------------------------------------------

  const ajouterFichiers = useCallback((liste) => {
    const proposes = Array.from(liste || []);
    if (proposes.length === 0) return;
    const refuses = proposes.filter((f) => !extensionAcceptee(f.name));
    if (refuses.length > 0) {
      toast.error(
        `Format non pris en charge : ${refuses.map((f) => f.name).join(', ')}. `
        + `Formats acceptés : ${EXTENSIONS_ACCEPTEES.join(', ')}.`
      );
    }
    const acceptes = proposes.filter((f) => extensionAcceptee(f.name));
    if (acceptes.length === 0) return;
    setEnAttente((precedent) => {
      const fusion = [...precedent];
      let doublons = 0;
      acceptes.forEach((f) => {
        if (fusion.some((g) => memeFichier(f, g))) { doublons += 1; return; }
        fusion.push(f);
      });
      if (doublons > 0) toast.info(`${doublons} fichier(s) déjà dans la liste, ignoré(s).`);
      if (fusion.length > MAX_FICHIERS) {
        toast.error(`${MAX_FICHIERS} fichiers au maximum par envoi. Les fichiers en trop n’ont pas été ajoutés.`);
        return fusion.slice(0, MAX_FICHIERS);
      }
      return fusion;
    });
  }, []);

  const surDepot = (e) => {
    e.preventDefault();
    setSurvol(false);
    if (occupe) return;
    ajouterFichiers(e.dataTransfer?.files);
  };

  const retirerEnAttente = (index) => {
    setEnAttente((p) => p.filter((_, i) => i !== index));
  };

  // --- Previsualisation ---------------------------------------------------

  const analyser = async () => {
    if (enAttente.length === 0) {
      toast.error('Déposez au moins un fichier de tarif.');
      return;
    }
    setTravail('analyse');
    setProgression(0);
    setErreur(null);
    setRapports(null);
    try {
      const data = await previsualiserTarifs(enAttente, { onProgression: setProgression });
      const recus = data?.fichiers || [];
      setChampsStandards(data?.champs_standards || []);
      // On garde l'objet File a cote de son analyse : c'est ce couple qui
      // garantit l'alignement fichier / fournisseur / mapping / onglet.
      setEntrees((precedent) => [
        ...precedent,
        ...recus.map((f, i) => ({
          ...f,
          fichier: enAttente[i],
          fournisseur: f.fournisseur_suggere || '',
          mapping: { ...(f.mapping_suggere || {}) },
          onglet: f.onglet_retenu || null,
        })),
      ]);
      setEnAttente([]);
      if (inputRef.current) inputRef.current.value = '';
      const echecs = recus.filter((f) => !f.ok).length;
      if (echecs > 0) {
        toast.warning(`${recus.length - echecs} fichier(s) analysé(s), ${echecs} illisible(s).`);
      } else {
        toast.success(`${recus.length} fichier(s) analysé(s). Vérifiez les associations.`);
      }
    } catch (err) {
      const msg = messageErreur(err, 'analyse');
      setErreur(msg);
      toast.error(msg.titre);
    } finally {
      setTravail(null);
      setProgression(null);
    }
  };

  // --- Edition des cartes -------------------------------------------------

  const majEntree = (index, transformation) => {
    setEntrees((p) => p.map((e, i) => (i === index ? { ...e, ...transformation(e) } : e)));
  };

  const surFournisseur = (index, valeur) => majEntree(index, () => ({ fournisseur: valeur }));
  const surOnglet = (index, valeur) => majEntree(index, () => ({ onglet: valeur }));
  const surMapping = (index, cleChamp, colonne) => majEntree(index, (e) => ({
    mapping: { ...e.mapping, [cleChamp]: colonne },
  }));
  const retirerEntree = (index) => setEntrees((p) => p.filter((_, i) => i !== index));

  // --- Import -------------------------------------------------------------

  const importables = entrees.filter((e) => e.ok);
  const requis = (champsStandards || []).filter((c) => c.requis);
  const invalides = importables.filter(
    (e) => !((e.fournisseur || '').trim()) || requis.some((c) => !e.mapping?.[c.cle])
  );
  const exclus = entrees.filter((e) => !e.ok);
  const peutImporter = importables.length > 0 && invalides.length === 0 && !occupe;
  const lignesAImporter = importables.reduce((s, e) => s + (e.lignes_total || 0), 0);

  const importer = async () => {
    if (!peutImporter) return;
    setTravail('import');
    setProgression(0);
    setErreur(null);
    try {
      const data = await importerTarifs(
        importables.map((e) => ({
          fichier: e.fichier,
          fournisseur: e.fournisseur,
          mapping: e.mapping,
          onglet: e.onglet,
        })),
        { onProgression: setProgression }
      );
      const liste = data?.rapports || [];
      setRapports(liste);
      setEntrees([]);
      const reussis = liste.filter((r) => r.ok).length;
      if (reussis === liste.length) {
        toast.success(`${reussis} catalogue(s) importé(s) et activé(s).`);
      } else if (reussis === 0) {
        toast.error('Aucun fichier n’a pu être importé. Consultez le rapport.');
      } else {
        toast.warning(`${reussis} import(s) réussi(s) sur ${liste.length}. Consultez le rapport.`);
      }
      chargerCatalogues();
    } catch (err) {
      const msg = messageErreur(err, 'import');
      setErreur(msg);
      toast.error(msg.titre);
    } finally {
      setTravail(null);
      setProgression(null);
    }
  };

  // --- Rendu --------------------------------------------------------------

  const libelleTravail = travail === 'import'
    ? 'Import en cours'
    : 'Analyse des fichiers en cours';
  const envoiTermine = progression !== null && progression >= 100;

  return (
    <div className="space-y-4" data-testid="fournisseurs-import-panneau">
      <Card className="card-shadow border-0 p-4 sm:p-5">
        <div className="min-w-0">
          <h2 className="font-display inline-flex items-center gap-2 text-base font-semibold">
            <UploadCloud className="h-4 w-4 text-primary" />
            Importer des tarifs fournisseurs
          </h2>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
            Déposez plusieurs tarifs d’un coup (CSV, Excel&nbsp;.xlsx ou .xlsm),
            {' '}{MAX_FICHIERS} fichiers au maximum par envoi. Un fichier
            = un fournisseur = un catalogue&nbsp;: aucun besoin de fusionner les fichiers,
            la recherche interroge tous les catalogues actifs en même temps.
          </p>
        </div>

        <label
          onDragOver={(e) => { e.preventDefault(); if (!occupe) setSurvol(true); }}
          onDragLeave={() => setSurvol(false)}
          onDrop={surDepot}
          className={`mt-4 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border border-dashed px-4 py-8 text-center text-sm transition-colors focus-within:ring-2 focus-within:ring-ring ${
            survol ? 'border-primary bg-primary/5' : 'bg-card hover:bg-muted/40'
          } ${occupe ? 'pointer-events-none opacity-60' : ''}`}
          data-testid="fournisseurs-import-dropzone"
        >
          <Upload className="h-6 w-6 text-muted-foreground" />
          <span className="font-medium">
            Glissez vos fichiers ici, ou cliquez pour les choisir
          </span>
          <span className="text-xs text-muted-foreground">
            Plusieurs fichiers acceptés&nbsp;: {EXTENSIONS_ACCEPTEES.join(', ')}
          </span>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept={ACCEPT_INPUT}
            className="sr-only"
            disabled={occupe}
            onChange={(e) => ajouterFichiers(e.target.files)}
            data-testid="fournisseurs-import-input"
          />
        </label>

        {enAttente.length > 0 && (
          <div className="mt-4 space-y-2" data-testid="fournisseurs-import-attente">
            <p className="text-sm font-medium">
              {enAttente.length} fichier{enAttente.length > 1 ? 's' : ''} à analyser
            </p>
            <ul className="divide-y rounded-lg border">
              {enAttente.map((f, i) => (
                <li key={`${f.name}-${f.size}`} className="flex items-center gap-3 px-3 py-2">
                  <FileSpreadsheet className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <span className="min-w-0 flex-1 text-sm">
                    <TruncatedText className="text-sm">{f.name}</TruncatedText>
                  </span>
                  <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                    {tailleLisible(f.size)}
                  </span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-7 shrink-0 gap-1 px-2"
                    onClick={() => retirerEnAttente(i)}
                    disabled={occupe}
                    aria-label={`Retirer ${f.name}`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </li>
              ))}
            </ul>
            <Button
              type="button"
              className="gap-2"
              onClick={analyser}
              disabled={occupe}
              data-testid="fournisseurs-import-analyser"
            >
              {travail === 'analyse'
                ? <Loader2 className="h-4 w-4 animate-spin" />
                : <ArrowRight className="h-4 w-4" />}
              Analyser {enAttente.length} fichier{enAttente.length > 1 ? 's' : ''}
            </Button>
          </div>
        )}

        {occupe && (
          <div className="mt-4 space-y-1.5" data-testid="fournisseurs-import-progression">
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
              <span className="font-medium">
                {envoiTermine
                  ? `${libelleTravail} côté serveur… (envoi terminé)`
                  : `${libelleTravail} — envoi des fichiers`}
              </span>
              <span className="tabular-nums text-muted-foreground">
                {progression === null ? '' : `${progression}\u00a0%`}
              </span>
            </div>
            <Progress
              value={progression ?? 0}
              aria-label={libelleTravail}
              className={envoiTermine ? 'animate-pulse' : ''}
            />
            <p className="text-xs text-muted-foreground">
              Les fichiers de tarif sont volumineux&nbsp;: l’opération peut prendre
              plusieurs minutes. Ne fermez pas cet onglet.
            </p>
          </div>
        )}
      </Card>

      {erreur && (
        <Card
          className="card-shadow border-0 p-4 ring-1 ring-inset ring-destructive/30 sm:p-5"
          data-testid="fournisseurs-import-erreur"
        >
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
            <div className="min-w-0">
              <p className="text-sm font-semibold text-destructive">{erreur.titre}</p>
              <p className="mt-1 break-words text-sm text-foreground/90">{erreur.texte}</p>
              {erreur.detail && (
                <p className="mt-1 break-words text-xs text-muted-foreground">
                  Détail du serveur&nbsp;: {erreur.detail}
                </p>
              )}
            </div>
          </div>
        </Card>
      )}

      {entrees.length > 0 && (
        <div className="space-y-4">
          {entrees.map((entree, index) => (
            <SupplierImportFileCard
              key={`${entree.nom_fichier}-${index}`}
              fichier={entree}
              index={index}
              champsStandards={champsStandards}
              onFournisseur={surFournisseur}
              onOnglet={surOnglet}
              onMapping={surMapping}
              onRetirer={retirerEntree}
              desactive={occupe}
            />
          ))}

          <Card className="card-shadow border-0 p-4 sm:p-5" data-testid="fournisseurs-import-actions">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-0 text-sm">
                <p>
                  <b>{importables.length}</b> fichier{importables.length > 1 ? 's' : ''} prêt
                  {importables.length > 1 ? 's' : ''} à importer,{' '}
                  <span className="tabular-nums">{entier(lignesAImporter)}</span> lignes au total.
                </p>
                {exclus.length > 0 && (
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {exclus.length} fichier{exclus.length > 1 ? 's' : ''} illisible
                    {exclus.length > 1 ? 's' : ''} exclu{exclus.length > 1 ? 's' : ''} de l’import.
                  </p>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setEntrees([])}
                  disabled={occupe}
                  className="gap-1.5"
                  data-testid="fournisseurs-import-vider"
                >
                  <Trash2 className="h-4 w-4" />
                  Tout retirer
                </Button>
                <Button
                  type="button"
                  onClick={importer}
                  disabled={!peutImporter}
                  className="gap-2"
                  data-testid="fournisseurs-import-lancer"
                >
                  {travail === 'import'
                    ? <Loader2 className="h-4 w-4 animate-spin" />
                    : <CheckCircle2 className="h-4 w-4" />}
                  Importer {importables.length > 1 ? `les ${importables.length} tarifs` : 'le tarif'}
                </Button>
              </div>
            </div>
            {invalides.length > 0 && (
              <p
                className="mt-3 flex items-start gap-2 text-xs text-destructive"
                data-testid="fournisseurs-import-bloque"
              >
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span className="min-w-0">
                  Import bloqué&nbsp;: {invalides.length} fichier
                  {invalides.length > 1 ? 's' : ''} sans nom de fournisseur ou sans
                  colonne associée à la désignation. Complétez les cartes signalées en rouge.
                </span>
              </p>
            )}
          </Card>
        </div>
      )}

      {rapports && (
        <Card className="card-shadow overflow-hidden border-0" data-testid="fournisseurs-import-rapports">
          <div className="flex flex-wrap items-start justify-between gap-3 border-b bg-muted/40 px-4 py-3 sm:px-5">
            <h2 className="font-display inline-flex items-center gap-2 text-base font-semibold">
              <ClipboardList className="h-4 w-4 text-primary" />
              Rapport d’import
            </h2>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setRapports(null)}
              data-testid="fournisseurs-import-fermer-rapport"
            >
              Masquer
            </Button>
          </div>
          <ul className="divide-y">
            {rapports.map((r, i) => (
              <li
                key={`${r.nom_fichier}-${i}`}
                className="flex flex-wrap items-start gap-x-4 gap-y-1 px-4 py-3 sm:px-5"
                data-testid="fournisseurs-import-rapport-ligne"
              >
                {r.ok
                  ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                  : <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />}
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">
                    <TruncatedText className="text-sm font-medium">
                      {r.fournisseur ? `${r.fournisseur} — ${r.nom_fichier}` : r.nom_fichier}
                    </TruncatedText>
                  </p>
                  {r.ok ? (
                    <p className="mt-0.5 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-muted-foreground">
                      <span className="font-mono">version v{r.version_numero}</span>
                      <span className="tabular-nums text-emerald-700">
                        {entier(r.lignes_importees)} lignes importées
                      </span>
                      <span className={`tabular-nums ${r.lignes_en_erreur ? 'text-rose-600' : ''}`}>
                        {entier(r.lignes_en_erreur)} lignes en erreur
                      </span>
                      {r.onglet_retenu ? <span>onglet&nbsp;: {r.onglet_retenu}</span> : null}
                    </p>
                  ) : (
                    <p className="mt-0.5 break-words text-xs text-destructive">
                      {r.erreur || 'Import refusé par le serveur.'}
                    </p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <SupplierCatalogsPanel
        donnees={catalogues}
        chargement={cataloguesChargement}
        erreur={cataloguesErreur}
        onRecharger={chargerCatalogues}
      />
    </div>
  );
};
