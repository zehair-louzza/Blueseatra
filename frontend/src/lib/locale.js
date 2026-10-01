// Locale d'affichage des nombres, prix et dates, alignée sur la langue de
// l'interface : « 9 octobre 2026 » et « 3,20 € » en français, « 9 October
// 2026 » et « €3.20 » en anglais. Lue à chaque appel, pour suivre le
// sélecteur FR / EN sans recharger la page.
import i18n from '@/i18n';

export const localeCourante = () => (i18n.language?.startsWith('en') ? 'en-GB' : 'fr-FR');
