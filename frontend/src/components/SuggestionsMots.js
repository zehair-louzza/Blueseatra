// Suggestions de mots pendant la frappe (02/10/2026) :
// les mots qui EXISTENT dans les catalogues de l'entreprise, du plus fréquent
// au plus rare, avec leurs synonymes du métier. La recherche lourde ne part
// que sur un mot complet choisi — plus besoin de la lancer à chaque pause.
import { useEffect, useRef, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { api } from '@/lib/api';
import { useTranslation } from 'react-i18next';

const OUVERT_MIN = 2;

export default function SuggestionsMots({ value, onValueChange, portee = 'devis', inputProps = {}, prependIcon = null }) {
  const { t } = useTranslation();
  const [items, setItems] = useState([]);
  const [ouvert, setOuvert] = useState(false);
  const [actif, setActif] = useState(-1);
  const { ref: inputRef, ...propsSansRef } = inputProps;
  const seq = useRef(0);
  const blurTimer = useRef(null);

  // Dernier mot en cours de frappe = préfixe proposé. Espace final : rien à proposer.
  const prefixe = value && !/\s$/.test(value) ? (value.trim().split(/\s+/).pop() || '') : '';

  useEffect(() => {
    const s = ++seq.current;
    if (prefixe.length < OUVERT_MIN) { setItems([]); setOuvert(false); setActif(-1); return undefined; }
    const timer = setTimeout(() => {
      api.get('/catalog/suggestions', { params: { q: value || '', portee } })
        .then((r) => { if (s === seq.current) { setItems(r.data?.suggestions || []); setOuvert(true); setActif(-1); } })
        .catch(() => { if (s === seq.current) { setItems([]); setOuvert(false); } });
    }, 180);
    return () => clearTimeout(timer);
  }, [prefixe, portee, value]);

  const choisir = (mot) => {
    const debut = (value || '').trim().split(/\s+/).slice(0, -1).join(' ');
    const suivant = `${debut ? `${debut} ` : ''}${mot} `;
    onValueChange(suivant);
    setOuvert(false); setItems([]);
  };

  const clavier = (e) => {
    if (!ouvert || items.length === 0) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); setActif((a) => (a + 1) % items.length); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActif((a) => (a <= 0 ? items.length - 1 : a - 1)); }
    else if (e.key === 'Tab') { e.preventDefault(); choisir(items[Math.max(actif, 0)].mot); }
    else if (e.key === 'Escape') { setOuvert(false); }
    else if (e.key === 'Enter' && actif >= 0) { e.preventDefault(); choisir(items[actif].mot); }
  };

  return (
    <div className="relative flex-1">
      {prependIcon}
      <Input
        ref={inputRef}
        {...propsSansRef}
        value={value}
        onChange={(e) => onValueChange(e.target.value)}
        onKeyDown={(e) => { clavier(e); if (inputProps.onKeyDown) inputProps.onKeyDown(e); }}
        onBlur={() => { blurTimer.current = setTimeout(() => setOuvert(false), 150); }}
        onFocus={() => { if (items.length > 0) setOuvert(true); if (blurTimer.current) clearTimeout(blurTimer.current); }}
        autocomplete="off"
        role="combobox"
        aria-expanded={ouvert}
        aria-autocomplete="list"
      />
      {ouvert && items.length > 0 && (
        <div className="absolute z-[110] mt-1 max-h-72 w-full overflow-auto rounded-md border bg-popover p-1 shadow-lg" role="listbox" data-testid="suggestions-mots">
          {items.map((s, i) => (
            <button
              type="button"
              key={s.mot}
              role="option"
              aria-selected={i === actif}
              className={`flex w-full flex-wrap items-center gap-2 rounded px-2.5 py-2 text-left text-sm ${i === actif ? 'bg-accent' : ''} hover:bg-accent/60`}
              data-testid="suggestion-mot"
              onMouseEnter={() => setActif(i)}
              onMouseDown={(e) => { e.preventDefault(); choisir(s.mot); }}
              onClick={() => choisir(s.mot)}
            >
              <span className="font-medium">{s.mot}</span>
              {s.nb_offres != null ? (
                <span className="text-xs text-muted-foreground" data-testid="suggestion-nb">{s.nb_offres.toLocaleString()} {t('sug.offres')}</span>
              ) : (
                <span className="text-xs text-muted-foreground">{t('sug.terme_metier')}</span>
              )}
              {(s.synonymes || []).length > 0 && (
                <span className="flex flex-wrap items-center gap-1">
                  {(s.synonymes || []).map((x) => <Badge key={x} variant="secondary" className="text-[10px] font-normal">{x}</Badge>)}
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
