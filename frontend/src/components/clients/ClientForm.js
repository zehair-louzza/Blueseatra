import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';

export const TYPES = ['entreprise', 'particulier', 'syndic', 'bailleur', 'collectivite', 'enseigne'];

export const nf = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 });
export const euro = (n) => `${nf.format(Number(n) || 0)} € HT`;
export const dfr = (iso) => (iso ? new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' }) : '—');
export const dtfr = (iso) => (iso ? new Date(iso).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—');

export const selectCls = 'h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

const vide = {
  type: 'entreprise', raison_sociale: '', nom_commercial: '', siret: '', tva_intra: '', email: '', telephone: '',
  adresse: { ligne1: '', code_postal: '', ville: '', pays: 'France' }, site_web: '', langue: 'fr',
  delai_paiement_j: '', etiquettes: [], notes: '',
};

function Champ({ label, children, className = '' }) {
  return (
    <label className={`block text-sm ${className}`}>
      <span className="mb-1 block text-xs font-medium text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}

export default function ClientForm({ initial, onSubmit, onCancel, busy }) {
  const { t } = useTranslation();
  const [f, setF] = useState(() => ({ ...vide, ...(initial || {}), adresse: { ...vide.adresse, ...((initial || {}).adresse || {}) } }));
  const [tags, setTags] = useState(((initial || {}).etiquettes || []).join(', '));
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const setA = (k, v) => setF((x) => ({ ...x, adresse: { ...x.adresse, [k]: v } }));
  const submit = (e) => {
    e.preventDefault();
    onSubmit({
      ...f,
      siret: f.siret || null, email: f.email || null, telephone: f.telephone || null, tva_intra: f.tva_intra || null,
      nom_commercial: f.nom_commercial || null, site_web: f.site_web || null, notes: f.notes || null,
      delai_paiement_j: f.delai_paiement_j === '' || f.delai_paiement_j === null ? null : Number(f.delai_paiement_j),
      etiquettes: tags.split(',').map((x) => x.trim()).filter(Boolean),
    });
  };
  return (
    <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
      <Champ label={t('cl.f_name')} className="sm:col-span-2">
        <Input required value={f.raison_sociale} onChange={(e) => set('raison_sociale', e.target.value)} data-testid="client-name" />
      </Champ>
      <Champ label={t('cl.f_type')}>
        <select className={selectCls} value={f.type} onChange={(e) => set('type', e.target.value)}>
          {TYPES.map((x) => <option key={x} value={x}>{t(`cl.types.${x}`)}</option>)}
        </select>
      </Champ>
      <Champ label={t('cl.f_trade')}><Input value={f.nom_commercial || ''} onChange={(e) => set('nom_commercial', e.target.value)} /></Champ>
      <Champ label={t('cl.f_siret')}><Input inputMode="numeric" value={f.siret || ''} onChange={(e) => set('siret', e.target.value)} placeholder="14 chiffres" /></Champ>
      <Champ label={t('cl.f_vat')}><Input value={f.tva_intra || ''} onChange={(e) => set('tva_intra', e.target.value)} /></Champ>
      <Champ label={t('cl.f_email')}><Input type="email" value={f.email || ''} onChange={(e) => set('email', e.target.value)} /></Champ>
      <Champ label={t('cl.f_phone')}><Input value={f.telephone || ''} onChange={(e) => set('telephone', e.target.value)} /></Champ>
      <Champ label={t('cl.f_address')} className="sm:col-span-2"><Input value={f.adresse.ligne1 || ''} onChange={(e) => setA('ligne1', e.target.value)} /></Champ>
      <Champ label={t('cl.f_zip')}><Input value={f.adresse.code_postal || ''} onChange={(e) => setA('code_postal', e.target.value)} /></Champ>
      <Champ label={t('cl.f_city')}><Input value={f.adresse.ville || ''} onChange={(e) => setA('ville', e.target.value)} /></Champ>
      <Champ label={t('cl.f_lang')}>
        <select className={selectCls} value={f.langue} onChange={(e) => set('langue', e.target.value)}>
          <option value="fr">Français</option><option value="en">English</option>
        </select>
      </Champ>
      <Champ label={t('cl.f_terms')}><Input type="number" min={0} max={120} value={f.delai_paiement_j ?? ''} onChange={(e) => set('delai_paiement_j', e.target.value)} /></Champ>
      <Champ label={t('cl.f_tags')} className="sm:col-span-2"><Input value={tags} onChange={(e) => setTags(e.target.value)} /></Champ>
      <Champ label={t('cl.f_notes')} className="sm:col-span-2"><Textarea rows={3} value={f.notes || ''} onChange={(e) => set('notes', e.target.value)} /></Champ>
      <div className="flex justify-end gap-2 sm:col-span-2">
        {onCancel && <Button type="button" variant="ghost" onClick={onCancel}>{t('cl.cancel')}</Button>}
        <Button type="submit" disabled={busy} data-testid="client-save">{t('cl.save')}</Button>
      </div>
    </form>
  );
}
