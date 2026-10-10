// Adresse publique de contact de Blueseatra (boîte Hostinger du domaine blueseatra.com).
// Source unique pour l'application ; les pages statiques de public/ la reprennent en dur.
// Voir docs/contact-blueseatra.md.
import { localeCourante } from '@/lib/locale';

export const CONTACT_EMAIL = 'contact@blueseatra.com';

// Objet prérempli selon le motif, pour trier les messages dans la boîte.
const OBJETS = {
  fr: { prestations: 'Prestations', offres: 'Offres et abonnement', entreprise: 'Contact entreprise', aide: 'Aide' },
  en: { prestations: 'Services', offres: 'Plans and subscription', entreprise: 'Company enquiry', aide: 'Help' },
};

export function mailtoContact(motif = 'entreprise', { precision = '', corps = '' } = {}) {
  // Langue de l'interface au moment du clic (sélecteur FR / EN).
  const libelles = localeCourante().startsWith('en') ? OBJETS.en : OBJETS.fr;
  const objet = `[Blueseatra] ${libelles[motif] || libelles.entreprise}${precision ? ` : ${precision}` : ''}`;
  const params = [`subject=${encodeURIComponent(objet)}`];
  if (corps) params.push(`body=${encodeURIComponent(corps)}`);
  return `mailto:${CONTACT_EMAIL}?${params.join('&')}`;
}
