// Recherche et comparaison fournisseurs.
//
// Interface traduite (dictionnaire `fo`, src/i18n_fournisseurs.js). Les
// donnees restent en francais : designations, familles, termes reconnus
// (« 1P+N », « courbe C ») et exemples de requete, qui doivent trouver des
// produits dans des catalogues francais. Conventions du projet : alias `@/`,
// composants shadcn/ui existants, `api`/`apiError` de `@/lib/api`, toasts
// sonner, `Spinner`/`EmptyState`, data-testid.
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { apiError } from '@/lib/api';
import { rechercherFournisseurs, listerFamilles, UTILISER_JEU_EXEMPLE } from '@/lib/fournisseursApi';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import SuggestionsMots from "@/components/SuggestionsMots";
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { SupplierFamilyFilter } from '@/components/SupplierFamilyFilter';
import { Spinner, EmptyState } from '@/components/Spinner';
import { SupplierSearchSummary, RecognizedTerms, NegationsExclues } from '@/components/SupplierSearchSummary';
import { SupplierCheapestPanel } from '@/components/SupplierCheapestPanel';
import { SupplierResultsTable } from '@/components/SupplierResultsTable';
import { SupplierProductGroups } from '@/components/SupplierProductGroups';
import { CatalogueCommunPanel } from '@/components/CatalogueCommunPanel';
import { IsolatedQualifiers, RefineCriteria } from '@/components/SupplierRefinePanels';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import i18n from '@/i18n';
import { entier } from '@/lib/fournisseursFormat';
import { Search, Loader2, AlertTriangle, PackageSearch, FlaskConical, RotateCcw, Layers, X } from 'lucide-react';

const LIMITE_PAR_DEFAUT = 50;

const EXEMPLES = [
  'disjoncteur 16a courbe c ph+n',
  'interrupteur différentiel 40a 30ma type ac',
  'câble r2v 3g2.5',
];

// Message utile pour chaque code d'erreur du contrat, dans la langue de
// l'interface.
const messageErreur = (err) => {
  const t = i18n.t.bind(i18n);
  const status = err?.response?.status;
  const detail = apiError(err, t('fo.e_echec'));
  const code = { 400: 'e400', 401: 'e401', 403: 'e403', 422: 'e422' }[status] || 'e';
  return {
    titre: t(`fo.${code}_t`),
    texte: t(`fo.${code}_d`, { n: LIMITE_PAR_DEFAUT }),
    detail,
  };
};

// Valeur technique du choix « Toutes les familles » (convertie en filtre vide
// par choisirFamille).
const TOUTES_FAMILLES = '__toutes__';

export default function SupplierSearch() {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const requeteUrl = params.get('q') || '';
  const inclureUrl = params.get('inclure_qualifiants') === 'true';
  const limiteUrl = Number(params.get('limite')) || LIMITE_PAR_DEFAUT;
  const familleUrl = params.get('famille') || '';

  const [saisie, setSaisie] = useState(requeteUrl);
  const [chargement, setChargement] = useState(false);
  const [erreur, setErreur] = useState(null);
  const [reponse, setReponse] = useState(null);
  const champRef = useRef(null);
  // Incremente quand le catalogue commun est masque/reaffiche : relance la recherche.
  const [generation, setGeneration] = useState(0);
  const relancer = useCallback(() => setGeneration((g) => g + 1), []);
  // Familles de produits des catalogues visibles (chargees une fois ; leur
  // absence n'empeche jamais de chercher).
  const [familles, setFamilles] = useState([]);
  const [famillesEnCours, setFamillesEnCours] = useState(true);
  useEffect(() => {
    let annule = false;
    setFamillesEnCours(true);
    listerFamilles()
      .then((d) => { if (!annule) setFamilles(d?.familles || []); })
      .catch(() => { if (!annule) setFamilles([]); })
      .finally(() => { if (!annule) setFamillesEnCours(false); });
    return () => { annule = true; };
  }, [generation]);

  // La recherche est pilotee par l'URL (q / inclure_qualifiants / limite) :
  // une relance (clic sur un qualifiant ou sur un critere a affiner) n'est
  // qu'une mise a jour de l'URL, et la recherche reste partageable et
  // rejouable via le bouton « retour » du navigateur.
  const lancer = useCallback(({ q, inclure = false, limite = LIMITE_PAR_DEFAUT, famille = familleUrl }) => {
    const suivant = { q: q.trim() };
    if (inclure) suivant.inclure_qualifiants = 'true';
    if (limite !== LIMITE_PAR_DEFAUT) suivant.limite = String(limite);
    if (famille) suivant.famille = famille;
    setParams(suivant);
  }, [setParams, familleUrl]);

  // Changer de famille relance la recherche en cours (s'il y en a une) ;
  // sinon la famille est simplement retenue pour la prochaine recherche.
  const choisirFamille = (valeur) => {
    const famille = valeur === TOUTES_FAMILLES ? '' : valeur;
    const q = (requeteUrl || saisie).trim();
    if (q) {
      lancer({ q, inclure: inclureUrl, limite: limiteUrl, famille });
    } else {
      const suivant = {};
      if (famille) suivant.famille = famille;
      setParams(suivant);
    }
  };

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
    rechercherFournisseurs({ q: requeteUrl, limite: limiteUrl, inclureQualifiants: inclureUrl, famille: familleUrl })
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
  }, [requeteUrl, inclureUrl, limiteUrl, familleUrl, generation]);

  const soumettre = (e) => {
    e.preventDefault();
    if (!saisie.trim()) {
      setErreur(messageErreur({ response: { status: 400, data: { detail: t('fo.requete_obligatoire') } } }));
      champRef.current?.focus();
      return;
    }
    lancer({ q: saisie, inclure: false, limite: limiteUrl });
  };

  // Un clic sur un qualifiant isole relance la meme requete avec
  // inclure_qualifiants=true (cf. contrat d'API).
  const inclureQualifiants = (libelle) => {
    lancer({ q: requeteUrl, inclure: true, limite: limiteUrl });
    toast.success(t('fo.qualifiants_reintegres', { l: libelle }));
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
    if (!reponse) return t('fo.sous_titre_vierge');
    return t('fo.sous_titre_requete', { q: reponse.requete });
  }, [reponse, t]);

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="font-display text-2xl font-semibold tracking-tight">
            {t('fo.titre')}
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{sousTitre}</p>
        </div>
        {UTILISER_JEU_EXEMPLE && (
          <span
            className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-800 ring-1 ring-inset ring-amber-200"
            data-testid="fournisseurs-badge-exemple"
            title={t('fo.exemple_aide')}
          >
            <FlaskConical className="h-3.5 w-3.5" />
            {t('fo.exemple_badge')}
          </span>
        )}
      </div>

      {!UTILISER_JEU_EXEMPLE && <CatalogueCommunPanel onChange={relancer} />}

      <Card className="card-shadow mt-5 border-0 p-4 sm:p-5">
        <form onSubmit={soumettre} className="space-y-3" role="search">
          <Label htmlFor="fournisseurs-q" className="text-sm">
            {t('fo.question')}
          </Label>
          <div className="flex flex-col gap-2 sm:flex-row">
            <SuggestionsMots
              value={saisie}
              onValueChange={setSaisie}
              portee="comparateur"
              inputProps={{
                ref: champRef,
                id: 'fournisseurs-q', placeholder: 'disjoncteur 16a courbe c ph+n',
                autoComplete: 'off', enterKeyHint: 'search', className: 'flex-1',
                'data-testid': 'fournisseurs-search-input',
                // Entrée sans suggestion surlignée : soumettre la recherche.
                onKeyDown: (e) => { if (e.key === 'Enter' && !e.defaultPrevented) soumettre(e); },
              }}
            />
            <Button type="submit" className="gap-2 sm:w-auto" disabled={chargement} data-testid="fournisseurs-search-button">
              {chargement ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
              {t('fo.rechercher')}
            </Button>
          </div>
          <SupplierFamilyFilter
            familles={familles}
            valeur={familleUrl}
            onChange={(f) => choisirFamille(f || TOUTES_FAMILLES)}
            desactive={chargement}
            chargement={famillesEnCours}
          />
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span>{t('fo.exemples')}</span>
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
                {t('fo.qualifiants_inclus')}
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
                {t('fo.remettre_a_part')}
              </Button>
            </div>
          )}
        </form>
      </Card>

      <div className="mt-5 space-y-4">
        {chargement && <Spinner label={t('fo.recherche_en_cours')} />}

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
                    {t('fo.detail_serveur', { d: erreur.detail })}
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
                  {t('fo.reessayer')}
                </Button>
              </div>
            </div>
          </Card>
        )}

        {!chargement && !erreur && rechercheVierge && (
          <EmptyState
            icon={Search}
            title={t('fo.vierge')}
          />
        )}

        {!chargement && !erreur && reponse && (
          <>
            {reponse.famille && (
              <div
                className="flex flex-wrap items-center gap-2 rounded-lg bg-muted/60 px-3 py-2 text-xs"
                data-testid="fournisseurs-famille-active"
              >
                <Layers className="h-3.5 w-3.5" />
                <span>
                  {t('fo.famille_seule', { f: reponse.famille })}
                  {reponse.tronque ? t('fo.famille_tronque', { n: entier(reponse.plafond) }) : '.'}
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-7 gap-1 px-2"
                  onClick={() => choisirFamille(TOUTES_FAMILLES)}
                  data-testid="fournisseurs-famille-retirer"
                >
                  <X className="h-3.5 w-3.5" />
                  {t('fo.toutes_familles')}
                </Button>
              </div>
            )}
            <SupplierSearchSummary reponse={reponse} />
            <RecognizedTerms termes={reponse.termes_reconnus} requete={reponse.requete} />
            <NegationsExclues rapport={reponse.negations_exclues} />

            {aucunResultat ? (
              <EmptyState
                icon={PackageSearch}
                title={t('fo.aucun_resultat')}
              />
            ) : (
              <>
                <SupplierCheapestPanel offres={reponse.moins_cher_par_fournisseur} />
                <SupplierProductGroups produits={reponse.produits_identiques} />
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
    </div>
  );
}
