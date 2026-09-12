// Recherche et comparaison fournisseurs.
//
// Texte d'interface volontairement en francais en dur (et non via i18n) :
// l'ecran manipule du vocabulaire de negoce electrique francais (« 1P+N »,
// « courbe C », « prix net HT », « unite de vente ») et le catalogue source
// est francais. Une traduction anglaise donnerait un ecran illisible pour le
// chiffreur. Les autres conventions du projet sont respectees : alias `@/`,
// composants shadcn/ui existants, `api`/`apiError` de `@/lib/api`, toasts
// sonner, `Spinner`/`EmptyState`, data-testid.
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { apiError } from '@/lib/api';
import { rechercherFournisseurs, UTILISER_JEU_EXEMPLE } from '@/lib/fournisseursApi';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Spinner, EmptyState } from '@/components/Spinner';
import { SupplierSearchSummary, RecognizedTerms } from '@/components/SupplierSearchSummary';
import { SupplierCheapestPanel } from '@/components/SupplierCheapestPanel';
import { SupplierResultsTable } from '@/components/SupplierResultsTable';
import { IsolatedQualifiers, RefineCriteria } from '@/components/SupplierRefinePanels';
import { SupplierImportPanel } from '@/components/SupplierImportPanel';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import { Search, Loader2, AlertTriangle, PackageSearch, FlaskConical, RotateCcw, UploadCloud } from 'lucide-react';

const LIMITE_PAR_DEFAUT = 50;

const EXEMPLES = [
  'disjoncteur 16a courbe c ph+n',
  'interrupteur différentiel 40a 30ma type ac',
  'câble r2v 3g2.5',
];

// Message francais utile pour chaque code d'erreur du contrat.
const messageErreur = (err) => {
  const status = err?.response?.status;
  const detail = apiError(err, 'La recherche a échoué.');
  if (status === 400) {
    return {
      titre: 'Requête vide',
      texte: 'Saisissez au moins un terme à rechercher, par exemple « disjoncteur 16a courbe c ph+n ».',
      detail,
    };
  }
  if (status === 401) {
    return {
      titre: 'Session expirée',
      texte: 'Votre jeton d’accès n’est plus valide. Reconnectez-vous, puis relancez la recherche.',
      detail,
    };
  }
  if (status === 403) {
    return {
      titre: 'Accès refusé',
      texte: 'Votre rôle ne donne pas accès au catalogue fournisseurs de cet espace. Demandez l’autorisation à un owner.',
      detail,
    };
  }
  if (status === 422) {
    return {
      titre: 'Paramètre hors bornes',
      texte: `La limite doit être comprise entre 1 et 200. Elle a été ramenée à ${LIMITE_PAR_DEFAUT} lignes.`,
      detail,
    };
  }
  return {
    titre: 'Recherche impossible',
    texte: 'Le catalogue fournisseurs n’a pas répondu. Vérifiez votre connexion puis réessayez.',
    detail,
  };
};

export default function SupplierSearch() {
  const [params, setParams] = useSearchParams();
  const requeteUrl = params.get('q') || '';
  const inclureUrl = params.get('inclure_qualifiants') === 'true';
  const limiteUrl = Number(params.get('limite')) || LIMITE_PAR_DEFAUT;

  // L'onglet actif vit aussi dans l'URL : un lien vers l'import est
  // partageable, et le bouton « retour » du navigateur revient a la recherche.
  const vue = params.get('vue') === 'import' ? 'import' : 'recherche';

  const [saisie, setSaisie] = useState(requeteUrl);
  const [chargement, setChargement] = useState(false);
  const [erreur, setErreur] = useState(null);
  const [reponse, setReponse] = useState(null);
  const champRef = useRef(null);

  // La recherche est pilotee par l'URL (q / inclure_qualifiants / limite) :
  // une relance (clic sur un qualifiant ou sur un critere a affiner) n'est
  // qu'une mise a jour de l'URL, et la recherche reste partageable et
  // rejouable via le bouton « retour » du navigateur.
  const lancer = useCallback(({ q, inclure = false, limite = LIMITE_PAR_DEFAUT }) => {
    // Lancer une recherche ramene toujours sur l'onglet recherche : le
    // parametre `vue` n'est donc pas reconduit.
    const suivant = { q: q.trim() };
    if (inclure) suivant.inclure_qualifiants = 'true';
    if (limite !== LIMITE_PAR_DEFAUT) suivant.limite = String(limite);
    setParams(suivant);
  }, [setParams]);

  useEffect(() => {
    setSaisie(requeteUrl);
  }, [requeteUrl]);

  useEffect(() => {
    if (!requeteUrl.trim()) {
      setReponse(null);
      setErreur(null);
      return undefined;
    }
    let annule = false;
    setChargement(true);
    setErreur(null);
    rechercherFournisseurs({ q: requeteUrl, limite: limiteUrl, inclureQualifiants: inclureUrl })
      .then((data) => { if (!annule) setReponse(data); })
      .catch((err) => {
        if (annule) return;
        const msg = messageErreur(err);
        setErreur(msg);
        setReponse(null);
        toast.error(msg.titre);
      })
      .finally(() => { if (!annule) setChargement(false); });
    return () => { annule = true; };
  }, [requeteUrl, inclureUrl, limiteUrl]);

  const soumettre = (e) => {
    e.preventDefault();
    if (!saisie.trim()) {
      setErreur(messageErreur({ response: { status: 400, data: { detail: 'La requête est obligatoire.' } } }));
      champRef.current?.focus();
      return;
    }
    lancer({ q: saisie, inclure: false, limite: limiteUrl });
  };

  // Un clic sur un qualifiant isole relance la meme requete avec
  // inclure_qualifiants=true (cf. contrat d'API).
  const inclureQualifiants = (libelle) => {
    lancer({ q: requeteUrl, inclure: true, limite: limiteUrl });
    toast.success(`Produits « ${libelle} » réintégrés à la liste principale`);
  };

  // Un clic sur une valeur de criteres_a_affiner ajoute le terme a la requete
  // et relance.
  const ajouterTerme = (valeur) => {
    const terme = String(valeur).trim();
    if (!terme) return;
    const nouvelle = `${requeteUrl} ${terme}`.replace(/\s+/g, ' ').trim();
    setSaisie(nouvelle);
    lancer({ q: nouvelle, inclure: inclureUrl, limite: limiteUrl });
  };

  const resultats = reponse?.resultats || [];
  const aucunResultat = !!reponse && resultats.length === 0;
  const rechercheVierge = !requeteUrl.trim();

  const sousTitre = useMemo(() => {
    if (vue === 'import') {
      return 'Chaque fichier importé devient le catalogue d’un fournisseur, et tous les catalogues actifs sont interrogés ensemble.';
    }
    if (!reponse) return 'Tout produit contenant vos termes est renvoyé. La pertinence trie, elle ne filtre jamais.';
    return `Requête analysée : « ${reponse.requete} »`;
  }, [reponse, vue]);

  // Changer d'onglet conserve la requete en cours : revenir a la recherche
  // apres un import raffiche le resultat sans le relancer a la main.
  const changerVue = (valeur) => {
    const suivant = {};
    if (requeteUrl.trim()) suivant.q = requeteUrl.trim();
    if (inclureUrl) suivant.inclure_qualifiants = 'true';
    if (limiteUrl !== LIMITE_PAR_DEFAUT) suivant.limite = String(limiteUrl);
    if (valeur === 'import') suivant.vue = 'import';
    setParams(suivant);
  };

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="font-display text-2xl font-semibold tracking-tight">
            Recherche et comparaison fournisseurs
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{sousTitre}</p>
        </div>
        {UTILISER_JEU_EXEMPLE && (
          <span
            className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-800 ring-1 ring-inset ring-amber-200"
            data-testid="fournisseurs-badge-exemple"
            title="Le backend /fournisseurs/recherche n’est pas encore déployé : l’écran fonctionne sur un jeu de données d’exemple conforme au contrat d’API."
          >
            <FlaskConical className="h-3.5 w-3.5" />
            Jeu de données d’exemple
          </span>
        )}
      </div>

      <Tabs value={vue} onValueChange={changerVue} className="mt-5">
        <TabsList>
          <TabsTrigger value="recherche" className="gap-1.5" data-testid="fournisseurs-onglet-recherche">
            <Search className="h-4 w-4" />
            Rechercher
          </TabsTrigger>
          <TabsTrigger value="import" className="gap-1.5" data-testid="fournisseurs-onglet-import">
            <UploadCloud className="h-4 w-4" />
            Importer des tarifs
          </TabsTrigger>
        </TabsList>

        <TabsContent value="import" className="mt-4">
          <SupplierImportPanel />
        </TabsContent>

        <TabsContent value="recherche" className="mt-4">
        <Card className="card-shadow border-0 p-4 sm:p-5">
          <form onSubmit={soumettre} className="space-y-3" role="search">
            <Label htmlFor="fournisseurs-q" className="text-sm">
              Que cherchez-vous&nbsp;?
            </Label>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Input
                id="fournisseurs-q"
                ref={champRef}
                value={saisie}
                onChange={(e) => setSaisie(e.target.value)}
                placeholder="disjoncteur 16a courbe c ph+n"
                autoComplete="off"
                enterKeyHint="search"
                className="flex-1"
                data-testid="fournisseurs-search-input"
              />
              <Button type="submit" className="gap-2 sm:w-auto" disabled={chargement} data-testid="fournisseurs-search-button">
                {chargement ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                Rechercher
              </Button>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span>Exemples&nbsp;:</span>
              {EXEMPLES.map((ex) => (
                <button
                  key={ex}
                  type="button"
                  onClick={() => { setSaisie(ex); lancer({ q: ex }); }}
                  className="rounded-full border px-2.5 py-1 transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  data-testid="fournisseurs-exemple-requete"
                >
                  {ex}
                </button>
              ))}
            </div>
            {inclureUrl && (
              <div className="flex flex-wrap items-center gap-2 rounded-lg bg-muted/60 px-3 py-2 text-xs">
                <span>
                  Les produits d’une autre nature sont inclus dans la liste principale.
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-7 gap-1 px-2"
                  onClick={() => lancer({ q: requeteUrl, inclure: false, limite: limiteUrl })}
                  data-testid="fournisseurs-exclure-qualifiants"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  Les remettre à part
                </Button>
              </div>
            )}
          </form>
        </Card>

        <div className="mt-5 space-y-4">
          {chargement && <Spinner label="Recherche dans les catalogues fournisseurs…" />}

          {!chargement && erreur && (
            <Card
              className="card-shadow border-0 p-4 ring-1 ring-inset ring-destructive/30 sm:p-5"
              data-testid="fournisseurs-erreur"
            >
              <div className="flex items-start gap-3">
                <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-destructive">{erreur.titre}</p>
                  <p className="mt-1 text-sm text-foreground/90">{erreur.texte}</p>
                  {erreur.detail && (
                    <p className="mt-1 break-words text-xs text-muted-foreground">
                      Détail du serveur&nbsp;: {erreur.detail}
                    </p>
                  )}
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    className="mt-3 gap-1.5"
                    onClick={() => lancer({ q: saisie || requeteUrl, inclure: inclureUrl, limite: LIMITE_PAR_DEFAUT })}
                    data-testid="fournisseurs-reessayer"
                  >
                    <RotateCcw className="h-4 w-4" />
                    Réessayer
                  </Button>
                </div>
              </div>
            </Card>
          )}

          {!chargement && !erreur && rechercheVierge && (
            <EmptyState
              icon={Search}
              title="Saisissez une désignation, une référence ou une marque pour comparer les offres de vos fournisseurs."
            />
          )}

          {!chargement && !erreur && reponse && (
            <>
              <SupplierSearchSummary reponse={reponse} />
              <RecognizedTerms termes={reponse.termes_reconnus} requete={reponse.requete} />

              {aucunResultat ? (
                <EmptyState
                  icon={PackageSearch}
                  title="Aucun produit ne contient ces termes dans les catalogues de cet espace. Vérifiez ci-dessus comment vos termes ont été interprétés, puis retirez le terme le plus restrictif."
                />
              ) : (
                <>
                  <SupplierCheapestPanel offres={reponse.moins_cher_par_fournisseur} />
                  <SupplierResultsTable resultats={resultats} />
                </>
              )}

              <div className="grid gap-4 lg:grid-cols-2">
                <IsolatedQualifiers
                  qualifiants={reponse.qualifiants_isoles}
                  inclus={inclureUrl}
                  onInclure={inclureQualifiants}
                />
                <RefineCriteria
                  criteres={reponse.criteres_a_affiner}
                  requete={reponse.requete}
                  onAjouterTerme={ajouterTerme}
                />
              </div>
            </>
          )}
        </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
