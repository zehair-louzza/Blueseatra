// Catalogue fournisseurs commun a toutes les entreprises.
//
// Le catalogue commun n'est JAMAIS supprime depuis le site : il se masque
// pour son entreprise (proprietaire / admin), ou pour toutes les
// entreprises (compte Blueseatra uniquement). Masquer est instantane et
// reversible ; les imports propres a l'entreprise ne sont pas concernes.
import React, { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Eye, EyeOff, Globe2, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { apiError } from '@/lib/api';
import { changerMasquageCatalogueCommun, etatCatalogueCommun } from '@/lib/fournisseursApi';

const nombre = (n) => new Intl.NumberFormat('fr-FR').format(n || 0);

export function BadgeCommun() {
  return (
    <span
      className="ml-1.5 inline-flex items-center gap-1 rounded-full bg-sky-50 px-1.5 py-0.5 align-middle text-[11px] font-medium text-sky-800 ring-1 ring-inset ring-sky-200"
      title="Offre issue du catalogue commun Blueseatra, partagé par toutes les entreprises"
      data-testid="badge-catalogue-commun"
    >
      <Globe2 className="h-3 w-3" aria-hidden="true" />
      Commun
    </span>
  );
}

export function CatalogueCommunPanel({ onChange }) {
  const [etat, setEtat] = useState(null);
  const [enCours, setEnCours] = useState(null);

  const charger = useCallback(async () => {
    try {
      setEtat(await etatCatalogueCommun());
    } catch {
      setEtat(null); // backend pas encore deploye : panneau masque
    }
  }, []);

  useEffect(() => { charger(); }, [charger]);

  if (!etat || !etat.existe) return null;

  const agir = async (masquer, pourTous) => {
    const cle = `${masquer}-${pourTous}`;
    setEnCours(cle);
    try {
      await changerMasquageCatalogueCommun({ masquer, pourTous });
      toast.success(
        masquer
          ? pourTous ? 'Catalogue commun masqué pour toutes les entreprises' : 'Catalogue commun masqué pour votre entreprise'
          : pourTous ? 'Catalogue commun réaffiché pour toutes les entreprises' : 'Catalogue commun réaffiché',
      );
      await charger();
      onChange?.();
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setEnCours(null);
    }
  };

  const bouton = (masquer, pourTous, libelle) => (
    <Button
      type="button"
      size="sm"
      variant={masquer ? 'outline' : 'default'}
      disabled={enCours !== null}
      onClick={() => agir(masquer, pourTous)}
      data-testid={`catalogue-commun-${masquer ? 'masquer' : 'afficher'}${pourTous ? '-tous' : ''}`}
    >
      {enCours === `${masquer}-${pourTous}` ? (
        <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
      ) : masquer ? (
        <EyeOff className="mr-1.5 h-4 w-4" />
      ) : (
        <Eye className="mr-1.5 h-4 w-4" />
      )}
      {libelle}
    </Button>
  );

  let statut = 'Visible dans vos recherches';
  if (etat.masque_pour_tous) statut = 'Masqué pour toutes les entreprises par Blueseatra';
  else if (etat.masque_pour_moi) statut = 'Masqué pour votre entreprise';

  return (
    <Card className="card-shadow mt-4 border-0 p-4" data-testid="catalogue-commun-panneau">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-sm font-semibold">
            <Globe2 className="h-4 w-4 text-sky-700" aria-hidden="true" />
            Catalogue commun Blueseatra
            <span className="font-normal text-muted-foreground">
              · {nombre(etat.lignes)} articles, {nombre(etat.fournisseurs)} fournisseurs
            </span>
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {statut}. Vos propres imports restent privés à votre entreprise. Ce catalogue n’est jamais supprimé : il peut seulement être masqué.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {etat.peut_masquer && !etat.masque_pour_tous && (
            etat.masque_pour_moi
              ? bouton(false, false, 'Réafficher')
              : bouton(true, false, 'Masquer pour mon entreprise')
          )}
          {etat.peut_masquer_pour_tous && (
            etat.masque_pour_tous
              ? bouton(false, true, 'Réafficher pour toutes les entreprises')
              : bouton(true, true, 'Masquer pour toutes les entreprises')
          )}
        </div>
      </div>
    </Card>
  );
}
