import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { api, apiError } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { toast } from 'sonner';
import { localeCourante } from '@/lib/locale';
import { Check, Loader2, ExternalLink, Zap, Mail } from 'lucide-react';
import { CONTACT_EMAIL, mailtoContact } from '@/lib/contact';

// Ticket #90 : choix de l'offre, recharges et portail Stripe.
const OFFRES = [
  { code: 'initial', nom: 'Initial', mensuel: 59, sieges: 1, devis: 60, pages: 150 },
  { code: 'pilotage', nom: 'Pilotage', mensuel: 149, sieges: 3, devis: 250, pages: 750, conseille: true },
  { code: 'performance', nom: 'Performance', mensuel: 399, sieges: 10, devis: 1000, pages: 3000 },
];
const PACKS = [
  { code: 'recharge_devis_25', prix: 19 }, { code: 'recharge_devis_100', prix: 59 }, { code: 'recharge_pages_500', prix: 39 },
];
// Nombres et prix dans la langue de l'interface : « 59 € HT / mois » en
// français, « €59 excl. VAT / month » en anglais.
const nf = { format: (n) => new Intl.NumberFormat(localeCourante()).format(n) };
const eur = (n) => new Intl.NumberFormat(localeCourante(), { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(n);

export default function ChoixOffre({ offreActuelle, peutPayer }) {
  const { t } = useTranslation();
  const [annuel, setAnnuel] = useState(false);
  const [busy, setBusy] = useState(null);
  const [stripe, setStripe] = useState(null);

  useEffect(() => { api.get('/abonnement/stripe').then((r) => setStripe(r.data)).catch(() => setStripe(null)); }, []);
  if (!stripe) return null;

  const aller = async (cle, chemin, corps) => {
    setBusy(cle);
    try {
      const { data } = await api.post(chemin, corps);
      window.location.assign(data.url);
    } catch (e) { toast.error(apiError(e, 'Paiement indisponible')); setBusy(null); }
  };

  return (
    <div className="mt-6 space-y-4" data-testid="choix-offre">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-lg font-semibold">{t('cl.p_titre')}</h2>
        <div className="flex items-center gap-3">
          {stripe.mode_test && stripe.paiement_disponible && <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800">{t('cl.p_mode_test')}</span>}
          <div className="flex rounded-full border border-border bg-card p-0.5 text-sm">
            <button type="button" onClick={() => setAnnuel(false)} className={`rounded-full px-3 py-1 ${!annuel ? 'bg-primary text-primary-foreground' : 'text-muted-foreground'}`}>{t('cl.p_mensuel')}</button>
            <button type="button" onClick={() => setAnnuel(true)} className={`rounded-full px-3 py-1 ${annuel ? 'bg-primary text-primary-foreground' : 'text-muted-foreground'}`}>{t('cl.p_annuel')}</button>
          </div>
        </div>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {OFFRES.map((o) => {
          const actuelle = offreActuelle === o.code;
          return (
            <Card key={o.code} className={`card-shadow relative border-0 p-5 ${o.conseille ? 'ring-2 ring-primary' : ''}`}>
              {o.conseille && <span className="absolute -top-2.5 left-5 rounded-full bg-primary px-2.5 py-0.5 text-xs font-medium text-primary-foreground">{t('cl.p_conseille')}</span>}
              <div className="font-display text-lg font-semibold">{o.nom}</div>
              <div className="mt-1"><span className="font-display text-3xl font-semibold">{eur(annuel ? o.mensuel * 10 : o.mensuel)}</span>
                <span className="text-sm text-muted-foreground"> {t('cl.p_ht')} / {annuel ? t('cl.p_an') : t('cl.p_mois')}</span></div>
              {annuel && <div className="text-xs text-emerald-700">{t('cl.p_deux_mois')}</div>}
              <ul className="mt-3 space-y-1.5 text-sm">
                {[t('cl.p_sieges', { n: o.sieges }), t('cl.p_devis', { n: nf.format(o.devis) }), t('cl.p_pages', { n: nf.format(o.pages) }), t('cl.p_illimite')].map((x) => (
                  <li key={x} className="flex gap-2"><Check className="mt-0.5 h-4 w-4 shrink-0 text-accent" />{x}</li>
                ))}
              </ul>
              <Button className="mt-4 w-full gap-2" variant={actuelle ? 'secondary' : 'default'} disabled={!peutPayer || !stripe.paiement_disponible || busy !== null || actuelle}
                onClick={() => aller(o.code, '/abonnement/checkout', { offre: o.code, periodicite: annuel ? 'annuel' : 'mensuel' })} data-testid={`choisir-${o.code}`}>
                {busy === o.code && <Loader2 className="h-4 w-4 animate-spin" />}{actuelle ? t('cl.p_actuelle') : t('cl.p_choisir')}
              </Button>
            </Card>
          );
        })}
      </div>
      {!stripe.paiement_disponible && (
        <p className="text-sm text-muted-foreground" data-testid="offre-contact">
          {t('cl.p_bientot')}{' '}
          <a className="inline-flex items-center gap-1 font-medium text-primary hover:underline" href={mailtoContact('offres')}>
            <Mail className="h-3.5 w-3.5" />{CONTACT_EMAIL}
          </a>
        </p>
      )}
      {stripe.paiement_disponible && peutPayer && (
        <Card className="card-shadow border-0 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 font-semibold"><Zap className="h-4 w-4 text-accent" />{t('cl.p_recharges')}</div>
            {stripe.abonnement && (
              <Button variant="outline" size="sm" className="gap-1" disabled={busy !== null} onClick={() => aller('portail', '/abonnement/portail')} data-testid="portail-stripe">
                {busy === 'portail' ? <Loader2 className="h-4 w-4 animate-spin" /> : <ExternalLink className="h-4 w-4" />}{t('cl.p_portail')}
              </Button>
            )}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {PACKS.map((p) => (
              <Button key={p.code} variant="secondary" size="sm" disabled={busy !== null} onClick={() => aller(p.code, '/abonnement/recharge', { pack: p.code })}>
                {busy === p.code && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}{t(`cl.p_${p.code}`)} · {eur(p.prix)} {t('cl.p_ht')}
              </Button>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
