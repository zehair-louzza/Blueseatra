import { BadgeCommun } from '@/components/CatalogueCommunPanel';
import React from 'react';
import { Card } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { TruncatedText } from '@/components/TruncatedText';
import { prixHT, prixComparable } from '@/lib/fournisseursFormat';
import { PrixParUnite, BadgesAnomalies } from '@/components/SupplierProductGroups';
import { useTranslation } from 'react-i18next';

// Tableau des resultats, trie par prix comparable croissant : prix par
// unite de base (format unique) quand il est connu, sinon prix net HT.
// Le tri est refait cote client : meme si le backend renvoie un ordre de
// pertinence, la colonne prix doit etre lisible de haut en bas.
const triParPrix = (resultats) =>
  [...(resultats || [])].sort((a, b) => {
    const pa = prixComparable(a);
    const pb = prixComparable(b);
    if (pa === null) return 1;
    if (pb === null) return -1;
    return pa - pb;
  });

export const SupplierResultsTable = ({ resultats }) => {
  const { t } = useTranslation();
  const lignes = triParPrix(resultats);

  return (
    <Card className="card-shadow overflow-hidden border-0" data-testid="fournisseurs-resultats">
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b px-4 py-3 sm:px-5">
        <h2 className="font-display text-base font-semibold">{t('fo.r_titre')}</h2>
        <p className="text-xs text-muted-foreground">{t('fo.r_tri')}</p>
      </div>

      {/* Tablette et ordinateur : tableau dense, defilement horizontal si besoin. */}
      <div className="hidden overflow-x-auto md:block">
        <Table>
          <caption className="sr-only">
            {t('fo.r_legende')}
          </caption>
          <TableHeader>
            <TableRow>
              <TableHead className="w-40 min-w-[9rem]">{t('fo.col_fournisseur')}</TableHead>
              <TableHead className="min-w-[18rem]">{t('fo.col_designation')}</TableHead>
              <TableHead className="w-36 min-w-[8rem]">{t('fo.col_marque')}</TableHead>
              <TableHead className="w-36 min-w-[8rem]">{t('fo.col_reference')}</TableHead>
              <TableHead className="w-32 text-right">{t('fo.col_prix_net')}</TableHead>
              <TableHead className="w-28 text-right">{t('fo.col_prix_public')}</TableHead>
              <TableHead className="w-28 min-w-[6rem]">{t('fo.col_unite_vente')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {lignes.map((o) => (
              <TableRow key={o.id} data-testid="fournisseurs-resultat-ligne">
                <TableCell className="max-w-[10rem] align-top">
                  <TruncatedText className="text-sm font-medium">{o.fournisseur}</TruncatedText>
                  {o.catalogue_commun && <BadgeCommun />}
                </TableCell>
                <TableCell className="max-w-[24rem] align-top text-sm">
                  <TruncatedText testid="fournisseurs-designation">{o.designation}</TruncatedText>
                  <BadgesAnomalies anomalies={o.anomalies} />
                </TableCell>
                <TableCell className="max-w-[9rem] align-top text-sm">
                  <TruncatedText className="text-sm">{o.marque}</TruncatedText>
                </TableCell>
                <TableCell className="max-w-[9rem] align-top">
                  <TruncatedText className="font-mono text-xs">
                    {o.reference_fournisseur || o.reference_fabricant}
                  </TruncatedText>
                </TableCell>
                {/* Prix ramené à l'unité de base ; le prix publié du lot en dessous. */}
                <TableCell className="align-top text-right text-sm" data-testid="fournisseurs-prix-unite">
                  <PrixParUnite offre={o} />
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
              <p className="min-w-0 flex-1 text-sm font-medium">{o.fournisseur}{o.catalogue_commun && <BadgeCommun />}</p>
              <p className="shrink-0 text-right text-sm">
                <PrixParUnite offre={o} />
              </p>
            </div>
            <p className="mt-1 text-sm leading-snug text-foreground/90">{o.designation}<BadgesAnomalies anomalies={o.anomalies} /></p>
            <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-muted-foreground">
              <div className="flex min-w-0 gap-1">
                <dt>{t('fo.carte_marque')}</dt>
                <dd className="truncate font-medium text-foreground">{o.marque || '\u2014'}</dd>
              </div>
              <div className="flex min-w-0 gap-1">
                <dt>{t('fo.carte_ref')}</dt>
                <dd className="truncate font-mono text-foreground">
                  {o.reference_fournisseur || o.reference_fabricant || '\u2014'}
                </dd>
              </div>
              <div className="flex min-w-0 gap-1">
                <dt>{t('fo.carte_public')}</dt>
                <dd className="tabular-nums">{prixHT(o.prix_public_ht)}</dd>
              </div>
              <div className="flex min-w-0 gap-1">
                <dt>{t('fo.carte_unite')}</dt>
                <dd className="truncate">{o.unite_vente || '\u2014'}</dd>
              </div>
            </dl>
          </li>
        ))}
      </ul>
    </Card>
  );
};
