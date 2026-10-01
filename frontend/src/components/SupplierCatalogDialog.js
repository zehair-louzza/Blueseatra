// Boite de dialogue : contenu d'un catalogue fournisseur (produits page par
// page, filtrables par mot). Utilise par la page Catalogues pour afficher le
// contenu d'un fournisseur sans quitter le chiffrage. Reutilise l'API du
// parcours fournisseurs : aucune donnee n'est copiee.
import React, { useEffect, useState } from 'react';
import { produitsFournisseur } from '@/lib/fournisseursApi';
import { prixHT, entier } from '@/lib/fournisseursFormat';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Spinner, EmptyState } from '@/components/Spinner';
import { toast } from 'sonner';
import { ChevronLeft, ChevronRight, ExternalLink, PackageSearch, Search } from 'lucide-react';

const TAILLE = 50;

export default function SupplierCatalogDialog({ source, open, onOpenChange }) {
  const [page, setPage] = useState(1);
  const [q, setQ] = useState('');
  const [saisie, setSaisie] = useState('');
  const [donnees, setDonnees] = useState(null);
  const [chargement, setChargement] = useState(false);

  useEffect(() => {
    if (!open) { setPage(1); setQ(''); setSaisie(''); setDonnees(null); }
  }, [open, source?.cle]);

  useEffect(() => {
    if (!open || !source?.cle) return undefined;
    let annule = false;
    setChargement(true);
    produitsFournisseur({ cle: source.cle, page, taille: TAILLE, q })
      .then((d) => { if (!annule) setDonnees(d); })
      .catch(() => { if (!annule) { setDonnees(null); toast.error('Produits indisponibles.'); } })
      .finally(() => { if (!annule) setChargement(false); });
    return () => { annule = true; };
  }, [open, source?.cle, page, q]);

  if (!source) return null;
  const nbPages = donnees?.total ? Math.ceil(donnees.total / TAILLE) : null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[85vh] flex-col overflow-hidden sm:max-w-5xl" data-testid="dialog-catalogue-fournisseur">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-baseline gap-2">
            {source.fournisseur}
            <span className="text-sm font-normal text-muted-foreground">
              {entier(source.references)} produits
            </span>
          </DialogTitle>
        </DialogHeader>

        <form className="flex items-center gap-2"
          onSubmit={(e) => { e.preventDefault(); setPage(1); setQ(saisie.trim()); }}>
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input value={saisie} onChange={(e) => setSaisie(e.target.value)}
              placeholder="Filtrer : désignation, référence, marque…" className="pl-8"
              data-testid="dialog-filtre-produits" />
          </div>
          <Button type="submit" size="sm" variant="secondary">Filtrer</Button>
        </form>

        <div className="min-h-0 flex-1 overflow-auto">
          {chargement && !donnees ? <Spinner /> : !donnees || donnees.produits.length === 0 ? (
            <EmptyState icon={PackageSearch} title="Aucun produit ne correspond à ce filtre." />
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="min-w-[20rem]">Désignation</TableHead>
                    <TableHead>Marque</TableHead>
                    <TableHead>Réf.</TableHead>
                    <TableHead className="text-right">Prix net HT</TableHead>
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
                      <TableCell className="text-right font-semibold tabular-nums">{prixHT(p.prix_net_ht)}</TableCell>
                      <TableCell className="text-sm">{p.unite_vente || '—'}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">{p.famille || '—'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>

        <div className="flex items-center justify-between gap-2 border-t pt-3 text-sm">
          <span className="text-muted-foreground">
            {donnees?.total != null
              ? `${donnees.total_plafonne ? 'Plus de ' : ''}${entier(donnees.total)} produits · page ${page}${nbPages ? ` / ${entier(nbPages)}` : ''}`
              : `Page ${page}`}
          </span>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" disabled={page <= 1 || chargement}
              onClick={() => setPage(page - 1)} data-testid="dialog-page-precedente">
              <ChevronLeft className="h-4 w-4" />Précédente
            </Button>
            <Button size="sm" variant="outline" disabled={!donnees?.page_suivante || chargement}
              onClick={() => setPage(page + 1)} data-testid="dialog-page-suivante">
              Suivante<ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
