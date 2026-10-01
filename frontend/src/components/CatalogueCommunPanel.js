// Catalogue fournisseurs commun a toutes les entreprises.
//
// Le catalogue commun n'est JAMAIS supprime depuis le site : il se masque
// pour son entreprise (proprietaire / admin), ou pour toutes les
// entreprises (compte Blueseatra uniquement). Masquer est instantane et
// reversible ; les imports propres a l'entreprise ne sont pas concernes.
import React, { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Eye, EyeOff, Globe2, Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { apiError } from '@/lib/api';
import { changerMasquageCatalogueCommun, etatCatalogueCommun } from '@/lib/fournisseursApi';

import { entier as nombre } from '@/lib/fournisseursFormat';

export function BadgeCommun() {
  const { t } = useTranslation();
  return (
    <span
      className="ml-1.5 inline-flex items-center gap-1 rounded-full bg-sky-50 px-1.5 py-0.5 align-middle text-[11px] font-medium text-sky-800 ring-1 ring-inset ring-sky-200"
      title={t('fo.commun_aide')}
      data-testid="badge-catalogue-commun"
    >
      <Globe2 className="h-3 w-3" aria-hidden="true" />
      {t('fo.commun')}
    </span>
  );
}

export function CatalogueCommunPanel({ onChange }) {
  const { t } = useTranslation();
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
          ? t(pourTous ? 'fo.cc_ok_masque_tous' : 'fo.cc_ok_masque')
          : t(pourTous ? 'fo.cc_ok_affiche_tous' : 'fo.cc_ok_affiche'),
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

  let statut = t('fo.cc_visible');
  if (etat.masque_pour_tous) statut = t('fo.cc_masque_tous');
  else if (etat.masque_pour_moi) statut = t('fo.cc_masque_moi');

  return (
    <Card className="card-shadow mt-4 border-0 p-4" data-testid="catalogue-commun-panneau">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-sm font-semibold">
            <Globe2 className="h-4 w-4 text-sky-700" aria-hidden="true" />
            {t('fo.cc_titre')}
            <span className="font-normal text-muted-foreground">
              {t('fo.cc_volume', { l: nombre(etat.lignes), f: nombre(etat.fournisseurs) })}
            </span>
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {t('fo.cc_aide', { statut })}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {etat.peut_masquer && !etat.masque_pour_tous && (
            etat.masque_pour_moi
              ? bouton(false, false, t('fo.cc_reafficher'))
              : bouton(true, false, t('fo.cc_masquer'))
          )}
          {etat.peut_masquer_pour_tous && (
            etat.masque_pour_tous
              ? bouton(false, true, t('fo.cc_reafficher_tous'))
              : bouton(true, true, t('fo.cc_masquer_tous'))
          )}
        </div>
      </div>
    </Card>
  );
}
