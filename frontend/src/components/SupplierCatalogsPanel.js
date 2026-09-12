// Catalogues fournisseurs actifs.
//
// Point cle de l'ecran : tous les catalogues actifs sont interroges
// SIMULTANEMENT par la recherche. Cinq fichiers deposes separement donnent
// donc exactement le meme resultat qu'un fichier consolide, sans jamais avoir
// a fusionner les tarifs a la main -- et mettre a jour un fournisseur ne
// touche pas aux quatre autres. Le bandeau ci-dessous le dit explicitement,
// parce que c'est la question que se pose l'utilisateur en voyant plusieurs
// lignes de catalogues.
import React from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import { Spinner, EmptyState } from '@/components/Spinner';
import { TruncatedText } from '@/components/TruncatedText';
import { entier } from '@/lib/fournisseursFormat';
import { dateLisible } from '@/lib/fournisseursImportApi';
import {
  Library, Layers, AlertTriangle, RotateCcw, PackageSearch,
} from 'lucide-react';

export const SupplierCatalogsPanel = ({ donnees, chargement, erreur, onRecharger }) => {
  const catalogues = donnees?.catalogues || [];
  const actifs = catalogues.filter((c) => c.version_active !== null && c.version_active !== undefined);
  const lignesTotal = donnees?.lignes_actives_total ?? actifs.reduce((s, c) => s + (c.lignes || 0), 0);

  return (
    <Card className="card-shadow overflow-hidden border-0" data-testid="fournisseurs-catalogues">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b bg-muted/40 px-4 py-3 sm:px-5">
        <div className="min-w-0">
          <h2 className="font-display inline-flex items-center gap-2 text-base font-semibold">
            <Library className="h-4 w-4 text-primary" />
            Catalogues fournisseurs actifs
          </h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Un fichier importé&nbsp;= un fournisseur&nbsp;= un catalogue, versionné à chaque
            réimport.
          </p>
        </div>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="gap-1.5"
          onClick={onRecharger}
          disabled={chargement}
          data-testid="fournisseurs-catalogues-recharger"
        >
          <RotateCcw className="h-4 w-4" />
          Actualiser
        </Button>
      </div>

      <div className="p-4 sm:p-5">
        <div
          className="mb-4 flex items-start gap-2 rounded-lg bg-primary/5 px-3 py-2.5 text-xs ring-1 ring-inset ring-primary/20"
          data-testid="fournisseurs-catalogues-note"
        >
          <Layers className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
          <p className="min-w-0 leading-relaxed">
            <span className="font-semibold">
              Tous les catalogues actifs sont interrogés simultanément par la recherche.
            </span>{' '}
            {actifs.length > 0 ? (
              <>
                Vos {actifs.length} catalogue{actifs.length > 1 ? 's' : ''} actif
                {actifs.length > 1 ? 's' : ''} forment un ensemble de{' '}
                <span className="tabular-nums">{entier(lignesTotal)}</span> lignes interrogées
                d’un seul coup&nbsp;:{' '}
              </>
            ) : (
              <>{' '}</>
            )}
            déposer plusieurs fichiers séparés donne exactement le même résultat qu’un
            catalogue consolidé, sans fusion manuelle. Réimporter le tarif d’un fournisseur
            crée une nouvelle version pour lui seul et ne désactive jamais les autres.
          </p>
        </div>

        {chargement && <Spinner label="Chargement des catalogues fournisseurs…" />}

        {!chargement && erreur && (
          <div
            className="flex items-start gap-3 rounded-lg px-3 py-3 ring-1 ring-inset ring-destructive/30"
            data-testid="fournisseurs-catalogues-erreur"
          >
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
            <div className="min-w-0">
              <p className="text-sm font-semibold text-destructive">
                Impossible de lister les catalogues
              </p>
              <p className="mt-1 break-words text-xs text-muted-foreground">{erreur}</p>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                className="mt-2 gap-1.5"
                onClick={onRecharger}
                data-testid="fournisseurs-catalogues-reessayer"
              >
                <RotateCcw className="h-4 w-4" />
                Réessayer
              </Button>
            </div>
          </div>
        )}

        {!chargement && !erreur && catalogues.length === 0 && (
          <EmptyState
            icon={PackageSearch}
            title="Aucun catalogue fournisseur pour le moment. Déposez un ou plusieurs tarifs ci-dessus : chaque fichier deviendra un catalogue interrogé par la recherche."
          />
        )}

        {!chargement && !erreur && catalogues.length > 0 && (
          <div className="overflow-x-auto rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="min-w-[10rem]">Fournisseur</TableHead>
                  <TableHead className="w-24">Version active</TableHead>
                  <TableHead className="w-24 text-right">Lignes</TableHead>
                  <TableHead className="min-w-[12rem]">Fichier source</TableHead>
                  <TableHead className="w-40">Importé le</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {catalogues.map((c) => (
                  <TableRow key={c.catalog_id} data-testid="fournisseurs-catalogue-ligne">
                    <TableCell className="max-w-[16rem] text-sm font-medium">
                      <TruncatedText className="text-sm font-medium">{c.nom}</TruncatedText>
                    </TableCell>
                    <TableCell className="text-xs">
                      {c.version_active ? (
                        <span className="inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 font-mono text-emerald-700 ring-1 ring-inset ring-emerald-200">
                          v{c.version_active}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">aucune version active</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right text-sm tabular-nums">
                      {entier(c.lignes)}
                    </TableCell>
                    <TableCell className="max-w-[18rem] text-xs text-muted-foreground">
                      <TruncatedText className="text-xs">
                        {c.fichier_source || '\u2014'}
                      </TruncatedText>
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-xs tabular-nums text-muted-foreground">
                      {dateLisible(c.importe_le)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </Card>
  );
};
