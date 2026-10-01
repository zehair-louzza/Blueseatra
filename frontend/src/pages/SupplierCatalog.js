// Catalogue fournisseurs : liste des fournisseurs visibles par l'entreprise
// (ses propres imports + le catalogue commun), puis consultation de leurs
// produits page par page, avec filtre par famille et par mot.
//
// Texte en francais en dur, comme l'ecran de recherche fournisseurs : le
// vocabulaire (prix net HT, unite de vente, famille) vient des catalogues
// francais eux-memes.
import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { apiError } from '@/lib/api';
import {
  listerCatalogueFournisseurs, produitsFournisseur, famillesFournisseur,
  basculerSourceChiffrage,
} from '@/lib/fournisseursApi';
import { prixHT, entier } from '@/lib/fournisseursFormat';
import { BadgeCommun } from '@/components/CatalogueCommunPanel';
import { Spinner, EmptyState } from '@/components/Spinner';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { toast } from 'sonner';
import {
  Store, Search, ChevronLeft, ChevronRight, ExternalLink, PackageSearch, Loader2, X,
} from 'lucide-react';

const TAILLE = 50;

export default function SupplierCatalog() {
  const [params, setParams] = useSearchParams();
  const cle = params.get('f') || '';
  const page = Math.max(1, Number(params.get('page')) || 1);
  const q = params.get('q') || '';
  const famille = params.get('famille') || '';

  const [fournisseurs, setFournisseurs] = useState(null);
  const [total, setTotal] = useState(0);
  const [familles, setFamilles] = useState([]);
  const [donnees, setDonnees] = useState(null);
  const [chargement, setChargement] = useState(false);
  const [saisie, setSaisie] = useState(q);
  const [bascule, setBascule] = useState(null); // cle en cours de bascule chiffrage

  const maj = useCallback((changes) => {
    const p = new URLSearchParams(params);
    Object.entries(changes).forEach(([k, v]) => (v ? p.set(k, String(v)) : p.delete(k)));
    setParams(p);
  }, [params, setParams]);

  useEffect(() => {
    listerCatalogueFournisseurs()
      .then((d) => { setFournisseurs(d.fournisseurs || []); setTotal(d.total_references || 0); })
      .catch((e) => { setFournisseurs([]); toast.error(apiError(e, 'Liste des fournisseurs indisponible.')); });
  }, []);

  // Bouton poussoir : active/desactive le catalogue de CE fournisseur pour le
  // chiffrage des devis (visible ensuite dans Catalogues -> chiffrage). Le
  // contenu du fournisseur n'est jamais modifie ni supprime.
  const basculerChiffrage = async (f, actif) => {
    if (bascule) return;
    setBascule(f.cle);
    try {
      await basculerSourceChiffrage(f.cle, actif);
      toast.success(actif
        ? `Catalogue ${f.fournisseur} activé pour le chiffrage. Ses produits apparaissent dans la recherche d'articles du devis.`
        : `Catalogue ${f.fournisseur} désactivé pour le chiffrage — contenu conservé.`);
      setFournisseurs((prev) => (prev || []).map((x) =>
        (x.cle === f.cle ? { ...x, actif_chiffrage: actif } : x)));
    } catch (e) { toast.error(apiError(e, 'Bascule impossible.')); }
    finally { setBascule(null); }
  };

  useEffect(() => { setSaisie(q); }, [q, cle]);

  useEffect(() => {
    if (!cle) { setFamilles([]); return; }
    famillesFournisseur(cle).then((d) => setFamilles(d.familles || [])).catch(() => setFamilles([]));
  }, [cle]);

  useEffect(() => {
    if (!cle) { setDonnees(null); return; }
    let annule = false;
    setChargement(true);
    produitsFournisseur({ cle, page, taille: TAILLE, q, famille })
      .then((d) => { if (!annule) setDonnees(d); })
      .catch((e) => { if (!annule) { setDonnees(null); toast.error(apiError(e, 'Produits indisponibles.')); } })
      .finally(() => { if (!annule) setChargement(false); });
    return () => { annule = true; };
  }, [cle, page, q, famille]);

  const choisi = (fournisseurs || []).find((f) => f.cle === cle);
  const nbTotal = donnees?.total ?? (q || famille ? null : choisi?.references);
  const nbPages = nbTotal ? Math.ceil(nbTotal / TAILLE) : null;

  return (
    <div className="space-y-6" data-testid="catalogue-fournisseurs">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-semibold tracking-tight">Catalogue fournisseurs</h1>
          <p className="text-sm text-muted-foreground">
            {fournisseurs ? `${fournisseurs.length} fournisseurs · ${entier(total)} produits` : 'Chargement…'}
          </p>
        </div>
        <Button asChild variant="outline" size="sm">
          <Link to="/app/fournisseurs"><Search className="mr-1.5 h-4 w-4" />Comparer les prix</Link>
        </Button>
      </div>

      {!fournisseurs ? <Spinner /> : fournisseurs.length === 0 ? (
        <EmptyState icon={Store} title="Aucun catalogue fournisseur visible pour votre entreprise." />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5" data-testid="liste-fournisseurs">
          {fournisseurs.map((f) => (
            <div key={f.cle}
              className={`rounded-xl border bg-card p-4 transition ${f.cle === cle ? 'border-primary ring-1 ring-primary' : ''}`}>
              <button type="button"
                onClick={() => maj({ f: f.cle, page: null, q: null, famille: null })}
                data-testid={`fournisseur-${f.fournisseur}`}
                className="w-full rounded-lg text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                <div className="flex items-start justify-between gap-2">
                  <span className="font-medium leading-tight">{f.fournisseur}</span>
                  {f.catalogue_commun && <BadgeCommun />}
                </div>
                <p className="mt-2 text-lg font-semibold tabular-nums">{entier(f.references)}</p>
                <p className="text-xs text-muted-foreground">produits</p>
              </button>
              <div className="mt-3 flex items-center justify-between gap-2 border-t pt-3"
                data-testid={`chiffrage-fournisseur-${f.fournisseur}`}>
                <span className="text-xs text-muted-foreground">Chiffrage</span>
                <Switch checked={!!f.actif_chiffrage} disabled={bascule === f.cle}
                  onCheckedChange={(v) => basculerChiffrage(f, v)}
                  aria-label={`Utiliser ${f.fournisseur} dans le chiffrage`} />
              </div>
            </div>
          ))}
        </div>
      )}

      {cle && (
        <Card className="card-shadow overflow-hidden border-0" data-testid="produits-fournisseur">
          <div className="flex flex-wrap items-center gap-3 border-b px-4 py-3 sm:px-5">
            <h2 className="mr-auto font-display text-base font-semibold">{choisi?.fournisseur || 'Fournisseur'}</h2>
            <form className="flex items-center gap-2"
              onSubmit={(e) => { e.preventDefault(); maj({ q: saisie.trim(), page: null }); }}>
              <Input value={saisie} onChange={(e) => setSaisie(e.target.value)}
                placeholder="Filtrer : désignation, référence, marque…" className="h-9 w-64"
                data-testid="filtre-produits" />
              <Button type="submit" size="sm" variant="secondary">Filtrer</Button>
              {q && <Button type="button" size="sm" variant="ghost" onClick={() => maj({ q: null, page: null })}><X className="h-4 w-4" /></Button>}
            </form>
            <select value={famille} onChange={(e) => maj({ famille: e.target.value, page: null })}
              className="h-9 max-w-[16rem] rounded-md border bg-background px-2 text-sm" data-testid="filtre-famille">
              <option value="">Toutes les familles</option>
              {familles.map((fa) => <option key={fa.famille} value={fa.famille}>{fa.famille} ({entier(fa.nb)})</option>)}
            </select>
          </div>

          {chargement && !donnees ? <Spinner /> : !donnees || donnees.produits.length === 0 ? (
            <div className="p-6"><EmptyState icon={PackageSearch} title="Aucun produit ne correspond à ce filtre." /></div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="min-w-[22rem]">Désignation</TableHead>
                      <TableHead>Marque</TableHead>
                      <TableHead>Réf. fournisseur</TableHead>
                      <TableHead>EAN</TableHead>
                      <TableHead className="text-right">Prix net HT</TableHead>
                      <TableHead className="text-right">Prix public HT</TableHead>
                      <TableHead>Unité</TableHead>
                      <TableHead>Famille</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {donnees.produits.map((p) => (
                      <TableRow key={p.id}>
                        <TableCell className="text-sm">
                          {p.url_produit ? (
                            <a href={p.url_produit} target="_blank" rel="noopener noreferrer"
                              className="inline-flex items-start gap-1 hover:underline">
                              {p.designation}<ExternalLink className="mt-0.5 h-3 w-3 shrink-0 opacity-60" />
                            </a>
                          ) : p.designation}
                        </TableCell>
                        <TableCell className="text-sm">{p.marque || '—'}</TableCell>
                        <TableCell className="font-mono text-xs">{p.reference_fournisseur || '—'}</TableCell>
                        <TableCell className="font-mono text-xs">{p.code_ean || '—'}</TableCell>
                        <TableCell className="text-right font-semibold tabular-nums">{prixHT(p.prix_net_ht)}</TableCell>
                        <TableCell className="text-right tabular-nums text-muted-foreground">{prixHT(p.prix_public_ht)}</TableCell>
                        <TableCell className="text-sm">
                          {p.unite_vente || '—'}
                          {p.conditionnement && Number(p.conditionnement) !== 1 ? ` · ${String(p.conditionnement).replace('.', ',')}` : ''}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">{p.famille || '—'}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2 border-t px-4 py-3 text-sm sm:px-5">
                <span className="text-muted-foreground">
                  {nbTotal != null
                    ? `${donnees.total_plafonne ? 'Plus de ' : ''}${entier(nbTotal)} produits · page ${page}${nbPages ? ` / ${entier(nbPages)}` : ''}`
                    : `Page ${page}`}
                  {chargement && <Loader2 className="ml-2 inline h-4 w-4 animate-spin" />}
                </span>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" disabled={page <= 1 || chargement}
                    onClick={() => maj({ page: page - 1 > 1 ? page - 1 : null })} data-testid="page-precedente">
                    <ChevronLeft className="h-4 w-4" />Précédente
                  </Button>
                  <Button size="sm" variant="outline" disabled={!donnees.page_suivante || chargement}
                    onClick={() => maj({ page: page + 1 })} data-testid="page-suivante">
                    Suivante<ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </>
          )}
        </Card>
      )}
    </div>
  );
}
