import React from 'react';
import { Card } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { TruncatedText } from '@/components/TruncatedText';
import { prixHT } from '@/lib/fournisseursFormat';

// Tableau des resultats, trie par prix net HT croissant.
// Le tri est refait cote client : meme si le backend renvoie un ordre de
// pertinence, la colonne prix doit etre lisible de haut en bas.
const triParPrix = (resultats) =>
  [...(resultats || [])].sort((a, b) => {
    const pa = Number(a?.prix_net_ht);
    const pb = Number(b?.prix_net_ht);
    if (!Number.isFinite(pa)) return 1;
    if (!Number.isFinite(pb)) return -1;
    return pa - pb;
  });

export const SupplierResultsTable = ({ resultats }) => {
  const lignes = triParPrix(resultats);

  return (
    <Card className="card-shadow overflow-hidden border-0" data-testid="fournisseurs-resultats">
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b px-4 py-3 sm:px-5">
        <h2 className="font-display text-base font-semibold">Résultats comparables</h2>
        <p className="text-xs text-muted-foreground">Triés par prix net HT croissant</p>
      </div>

      {/* Tablette et ordinateur : tableau dense, defilement horizontal si besoin. */}
      <div className="hidden overflow-x-auto md:block">
        <Table>
          <caption className="sr-only">
            Offres fournisseurs comparables, triées par prix net hors taxes croissant
          </caption>
          <TableHeader>
            <TableRow>
              <TableHead className="w-40 min-w-[9rem]">Fournisseur</TableHead>
              <TableHead className="min-w-[18rem]">Désignation</TableHead>
              <TableHead className="w-36 min-w-[8rem]">Marque</TableHead>
              <TableHead className="w-36 min-w-[8rem]">Référence</TableHead>
              <TableHead className="w-28 text-right">Prix net HT</TableHead>
              <TableHead className="w-28 text-right">Prix public HT</TableHead>
              <TableHead className="w-28 min-w-[6rem]">Unité de vente</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {lignes.map((o) => (
              <TableRow key={o.id} data-testid="fournisseurs-resultat-ligne">
                <TableCell className="max-w-[10rem] align-top">
                  <TruncatedText className="text-sm font-medium">{o.fournisseur}</TruncatedText>
                </TableCell>
                <TableCell className="max-w-[24rem] align-top text-sm">
                  <TruncatedText testid="fournisseurs-designation">{o.designation}</TruncatedText>
                </TableCell>
                <TableCell className="max-w-[9rem] align-top text-sm">
                  <TruncatedText className="text-sm">{o.marque}</TruncatedText>
                </TableCell>
                <TableCell className="max-w-[9rem] align-top">
                  <TruncatedText className="font-mono text-xs">
                    {o.reference_fournisseur || o.reference_fabricant}
                  </TruncatedText>
                </TableCell>
                <TableCell className="align-top text-right text-sm font-semibold tabular-nums">
                  {prixHT(o.prix_net_ht)}
                </TableCell>
                <TableCell className="align-top text-right text-sm tabular-nums text-muted-foreground">
                  {prixHT(o.prix_public_ht)}
                </TableCell>
                <TableCell className="align-top text-sm">{o.unite_vente || '\u2014'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Portable de chantier : une carte par offre, rien ne se coupe. */}
      <ul className="divide-y md:hidden">
        {lignes.map((o) => (
          <li key={o.id} className="px-4 py-3" data-testid="fournisseurs-resultat-carte">
            <div className="flex items-start justify-between gap-3">
              <p className="min-w-0 flex-1 text-sm font-medium">{o.fournisseur}</p>
              <p className="shrink-0 text-right text-sm font-semibold tabular-nums">
                {prixHT(o.prix_net_ht)}
                <span className="ml-1 text-xs font-normal text-muted-foreground">HT</span>
              </p>
            </div>
            <p className="mt-1 text-sm leading-snug text-foreground/90">{o.designation}</p>
            <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-muted-foreground">
              <div className="flex min-w-0 gap-1">
                <dt>Marque&nbsp;:</dt>
                <dd className="truncate font-medium text-foreground">{o.marque || '\u2014'}</dd>
              </div>
              <div className="flex min-w-0 gap-1">
                <dt>Réf.&nbsp;:</dt>
                <dd className="truncate font-mono text-foreground">
                  {o.reference_fournisseur || o.reference_fabricant || '\u2014'}
                </dd>
              </div>
              <div className="flex min-w-0 gap-1">
                <dt>Public HT&nbsp;:</dt>
                <dd className="tabular-nums">{prixHT(o.prix_public_ht)}</dd>
              </div>
              <div className="flex min-w-0 gap-1">
                <dt>Unité&nbsp;:</dt>
                <dd className="truncate">{o.unite_vente || '\u2014'}</dd>
              </div>
            </dl>
          </li>
        ))}
      </ul>
    </Card>
  );
};
