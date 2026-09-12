// Carte d'un fichier de tarif fournisseur en cours de preparation.
//
// Une carte = un fichier = un fournisseur = un catalogue. L'utilisateur y
// verifie trois choses avant d'importer : le nom du fournisseur (obligatoire,
// c'est lui qui nomme le catalogue), l'association des colonnes du fichier aux
// champs standards, et l'apercu des 5 premieres lignes. Meme experience que
// l'onglet Catalogue (depot, apercu, association, import), mais repetee pour
// chaque fichier au lieu d'un assistant en quatre etapes : avec cinq tarifs
// deposes d'un coup, un assistant lineaire obligerait a vingt clics.
import React from 'react';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import { TruncatedText } from '@/components/TruncatedText';
import { tailleLisible } from '@/lib/fournisseursImportApi';
import { entier } from '@/lib/fournisseursFormat';
import { AlertTriangle, FileSpreadsheet, FileX2, Trash2, Sheet } from 'lucide-react';

// Radix Select interdit une valeur vide : sentinelle pour « aucune colonne ».
export const AUCUNE_COLONNE = '__aucune__';

const cle = (nom, index) => `${index}-${nom}`;

export const SupplierImportFileCard = ({
  fichier,          // entree preparee (voir SupplierImportPanel)
  index,
  champsStandards,
  onFournisseur,
  onOnglet,
  onMapping,
  onRetirer,
  desactive,
}) => {
  const apercu = fichier.apercu || [];
  const colonnes = fichier.colonnes || [];
  const onglets = fichier.onglets_disponibles || [];
  const nomVide = !((fichier.fournisseur || '').trim());
  const idNom = `fournisseur-${index}`;

  // Champs requis encore non associes, recalcules a chaque modification :
  // `champs_requis_manquants` renvoye par le backend ne vaut que pour le
  // mapping suggere, or l'utilisateur peut casser une association valide.
  const manquants = (champsStandards || [])
    .filter((c) => c.requis && !fichier.mapping?.[c.cle])
    .map((c) => c.libelle);

  // Onglet choisi different de celui analyse : les colonnes affichees ne
  // correspondent peut-etre plus, on le dit franchement.
  const ongletDeplace = !!fichier.onglet
    && !!fichier.onglet_retenu
    && fichier.onglet !== fichier.onglet_retenu;

  if (!fichier.ok) {
    return (
      <Card
        className="card-shadow border-0 p-4 ring-1 ring-inset ring-destructive/30 sm:p-5"
        data-testid="fournisseurs-import-fichier-erreur"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex min-w-0 items-start gap-3">
            <FileX2 className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold" title={fichier.nom_fichier}>
                {fichier.nom_fichier}
              </p>
              <p className="mt-1 break-words text-sm text-destructive">
                {fichier.erreur || 'Fichier illisible.'}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                Ce fichier est exclu de l’import. Les autres fichiers déposés restent importables.
              </p>
            </div>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="gap-1.5"
            onClick={() => onRetirer(index)}
            disabled={desactive}
            data-testid="fournisseurs-import-retirer"
          >
            <Trash2 className="h-4 w-4" />
            Retirer
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <Card
      className="card-shadow overflow-hidden border-0"
      data-testid="fournisseurs-import-fichier"
    >
      <div className="flex flex-wrap items-start justify-between gap-3 border-b bg-muted/40 px-4 py-3 sm:px-5">
        <div className="flex min-w-0 items-start gap-3">
          <FileSpreadsheet className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold" title={fichier.nom_fichier}>
              {fichier.nom_fichier}
            </p>
            <p className="mt-0.5 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
              <span className="tabular-nums">{entier(fichier.lignes_total)} lignes</span>
              <span className="tabular-nums">{colonnes.length} colonnes</span>
              {fichier.taille_octets ? (
                <span className="tabular-nums">{tailleLisible(fichier.taille_octets)}</span>
              ) : null}
              {fichier.onglet_retenu ? (
                <span className="inline-flex min-w-0 items-center gap-1">
                  <Sheet className="h-3 w-3 shrink-0" />
                  <span className="truncate">onglet analysé&nbsp;: {fichier.onglet_retenu}</span>
                </span>
              ) : null}
            </p>
          </div>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="gap-1.5"
          onClick={() => onRetirer(index)}
          disabled={desactive}
          data-testid="fournisseurs-import-retirer"
        >
          <Trash2 className="h-4 w-4" />
          Retirer
        </Button>
      </div>

      <div className="space-y-4 p-4 sm:p-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="min-w-0 space-y-1.5">
            <Label htmlFor={idNom} className="text-xs">
              Nom du fournisseur <span className="text-rose-600">*</span>
            </Label>
            <Input
              id={idNom}
              value={fichier.fournisseur || ''}
              onChange={(e) => onFournisseur(index, e.target.value)}
              placeholder="Rexel, La Plateforme du Bâtiment…"
              autoComplete="off"
              disabled={desactive}
              aria-invalid={nomVide}
              aria-describedby={nomVide ? `${idNom}-aide` : undefined}
              className={nomVide ? 'border-destructive focus-visible:ring-destructive' : ''}
              data-testid="fournisseurs-import-nom"
            />
            <p
              id={`${idNom}-aide`}
              className={`text-xs ${nomVide ? 'text-destructive' : 'text-muted-foreground'}`}
            >
              {nomVide
                ? 'Obligatoire : ce nom identifie le catalogue et apparaît dans la comparaison.'
                : 'Réimporter avec le même nom crée une nouvelle version de ce catalogue.'}
            </p>
          </div>

          {onglets.length > 1 && (
            <div className="min-w-0 space-y-1.5">
              <Label htmlFor={`onglet-${index}`} className="text-xs">
                Onglet du classeur
              </Label>
              <Select
                value={fichier.onglet || onglets[0]}
                onValueChange={(v) => onOnglet(index, v)}
                disabled={desactive}
              >
                <SelectTrigger
                  id={`onglet-${index}`}
                  className="h-9"
                  data-testid="fournisseurs-import-onglet"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {onglets.map((o) => (
                    <SelectItem key={o} value={o}>{o}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                {onglets.length} onglets détectés. L’onglet le plus fourni est sélectionné par défaut.
              </p>
            </div>
          )}
        </div>

        {ongletDeplace && (
          <div
            className="flex items-start gap-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900 ring-1 ring-inset ring-amber-200"
            data-testid="fournisseurs-import-onglet-change"
          >
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span className="min-w-0">
              L’aperçu et les colonnes ci-dessous proviennent de l’onglet
              «&nbsp;{fichier.onglet_retenu}&nbsp;». Vous avez choisi
              «&nbsp;{fichier.onglet}&nbsp;»&nbsp;: vérifiez après l’import que les
              colonnes de cet onglet portent bien les mêmes en-têtes.
            </span>
          </div>
        )}

        {manquants.length > 0 && (
          <div
            className="flex items-start gap-2 rounded-lg bg-destructive/10 px-3 py-2 text-xs text-destructive ring-1 ring-inset ring-destructive/30"
            data-testid="fournisseurs-import-manquants"
          >
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span className="min-w-0">
              Champ obligatoire non associé&nbsp;: {manquants.join(', ')}. Choisissez la
              colonne correspondante ci-dessous, sinon ce fichier ne peut pas être importé.
            </span>
          </div>
        )}

        <div className="space-y-3 rounded-lg border bg-muted/30 p-3 sm:p-4">
          <div className="min-w-0">
            <p className="text-sm font-medium">Association des colonnes</p>
            <p className="text-xs text-muted-foreground">
              À gauche le champ standard de Blueseatra, à droite la colonne du fichier.
              Les correspondances évidentes sont déjà remplies&nbsp;; laissez «&nbsp;Aucune
              colonne&nbsp;» pour ce que vous n’utilisez pas.
            </p>
          </div>
          <div
            className="grid gap-x-4 gap-y-3 sm:grid-cols-2 xl:grid-cols-3"
            data-testid="fournisseurs-import-mapping"
          >
            {(champsStandards || []).map((champ) => {
              const valeur = fichier.mapping?.[champ.cle];
              // Une colonne mappee mais absente du fichier (onglet change,
              // fichier remplace) doit rester visible dans le select.
              const options = valeur && !colonnes.includes(valeur)
                ? [valeur, ...colonnes]
                : colonnes;
              const manque = champ.requis && !valeur;
              return (
                <div key={champ.cle} className="min-w-0 space-y-1">
                  <Label
                    htmlFor={`map-${index}-${champ.cle}`}
                    className="block truncate text-xs"
                    title={champ.libelle}
                  >
                    {champ.libelle}
                    {champ.requis && <span className="ml-1 text-rose-600">*</span>}
                  </Label>
                  <Select
                    value={valeur || AUCUNE_COLONNE}
                    onValueChange={(v) => onMapping(index, champ.cle, v === AUCUNE_COLONNE ? null : v)}
                    disabled={desactive}
                  >
                    <SelectTrigger
                      id={`map-${index}-${champ.cle}`}
                      className={`h-9 w-full min-w-0 ${manque ? 'border-destructive text-destructive' : ''}`}
                      data-testid={`fournisseurs-import-map-${champ.cle}`}
                    >
                      <span className="min-w-0 truncate text-left">
                        <SelectValue />
                      </span>
                    </SelectTrigger>
                    <SelectContent className="max-h-72">
                      <SelectItem value={AUCUNE_COLONNE}>Aucune colonne</SelectItem>
                      {options.map((c, i) => (
                        <SelectItem key={cle(c, i)} value={c}>{c}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              );
            })}
          </div>
        </div>

        <div className="min-w-0 space-y-2">
          <p className="text-sm font-medium">
            Aperçu <span className="font-normal text-muted-foreground">
              ({apercu.length} premières lignes sur {entier(fichier.lignes_total)})
            </span>
          </p>
          {apercu.length === 0 ? (
            <p className="rounded-lg border border-dashed px-3 py-4 text-xs text-muted-foreground">
              Aucune ligne de données à afficher pour ce fichier.
            </p>
          ) : (
            <div className="overflow-x-auto rounded-lg border" data-testid="fournisseurs-import-apercu">
              <Table>
                <TableHeader>
                  <TableRow>
                    {colonnes.map((c, i) => (
                      <TableHead key={cle(c, i)} className="max-w-[14rem] font-mono text-xs">
                        <TruncatedText className="font-mono text-xs">{c}</TruncatedText>
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {apercu.map((ligne, i) => (
                    <TableRow key={i}>
                      {colonnes.map((c, j) => (
                        <TableCell key={cle(c, j)} className="max-w-[14rem] text-xs">
                          <TruncatedText className="text-xs">{String(ligne[c] ?? '')}</TruncatedText>
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
};
