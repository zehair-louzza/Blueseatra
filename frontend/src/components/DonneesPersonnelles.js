import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { api, apiError } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog';
import { toast } from 'sonner';
import { Download, UserX, Loader2, ShieldCheck } from 'lucide-react';

// Ticket #93 : export des données de l'entreprise, anonymisation d'une personne,
// contacts arrivés à échéance de conservation. Tout est tracé au journal d'audit.
export default function DonneesPersonnelles({ canManage }) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [email, setEmail] = useState('');
  const [confirmer, setConfirmer] = useState(false);
  const [echeances, setEcheances] = useState(null);

  useEffect(() => {
    if (!canManage) return;
    api.get('/rgpd/echeances').then((r) => setEcheances(r.data)).catch(() => setEcheances(null));
  }, [canManage]);

  if (!canManage) return <p className="text-sm text-muted-foreground">{t('cl.g_reserve')}</p>;

  const exporter = async () => {
    setBusy(true);
    try {
      const r = await api.get('/rgpd/export', { responseType: 'blob' });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement('a');
      a.href = url; a.download = `blueseatra-export-${new Date().toISOString().slice(0, 10)}.zip`; a.click();
      URL.revokeObjectURL(url);
      toast.success(t('cl.g_export_ok'));
    } catch (e) { toast.error(apiError(e, 'Failed')); } finally { setBusy(false); }
  };

  const anonymiser = async () => {
    try {
      const { data } = await api.post('/rgpd/personnes/anonymiser', { email: email.trim() });
      toast.success(t('cl.g_anon_ok', { c: data.contacts_anonymises, f: data.fiches_client_modifiees, r: data.relances_annulees }));
      setEmail('');
    } catch (e) { toast.error(apiError(e, 'Failed')); } finally { setConfirmer(false); }
  };

  return (
    <div className="space-y-4">
      <Card className="card-shadow border-0 p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="font-semibold">{t('cl.g_export_titre')}</h3>
            <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{t('cl.g_export_aide')}</p>
          </div>
          <Button className="shrink-0 gap-2" onClick={exporter} disabled={busy} data-testid="rgpd-export-button">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}{t('cl.g_export_bouton')}
          </Button>
        </div>
      </Card>
      <Card className="card-shadow border-0 p-5">
        <h3 className="font-semibold">{t('cl.g_anon_titre')}</h3>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{t('cl.g_anon_aide')}</p>
        <div className="mt-3 flex max-w-xl gap-2">
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="prenom.nom@exemple.fr" data-testid="rgpd-email-input" />
          <Button variant="destructive" className="gap-2" disabled={!/.+@.+\..+/.test(email)} onClick={() => setConfirmer(true)} data-testid="rgpd-anonymise-button">
            <UserX className="h-4 w-4" />{t('cl.g_anon_bouton')}
          </Button>
        </div>
      </Card>
      <Card className="card-shadow border-0 p-5">
        <h3 className="flex items-center gap-2 font-semibold"><ShieldCheck className="h-4 w-4 text-primary" />{t('cl.g_ech_titre', { n: echeances?.duree_conservation_ans ?? 3 })}</h3>
        {!echeances ? null : echeances.a_anonymiser.length === 0 ? (
          <p className="mt-1 text-sm text-muted-foreground">{t('cl.g_ech_aucun')}</p>
        ) : (
          <ul className="mt-2 divide-y divide-border text-sm">
            {echeances.a_anonymiser.map((c) => (
              <li key={c.id} className="flex justify-between py-2"><span>{c.raison_sociale}</span><span className="text-muted-foreground">{t('cl.g_ech_archive', { d: new Date(c.archive_le).toLocaleDateString('fr-FR') })}</span></li>
            ))}
          </ul>
        )}
      </Card>
      <AlertDialog open={confirmer} onOpenChange={setConfirmer}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('cl.g_anon_confirmer', { e: email })}</AlertDialogTitle>
            <AlertDialogDescription>{t('cl.g_anon_definitif')}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={anonymiser} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">{t('cl.g_anon_bouton')}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
