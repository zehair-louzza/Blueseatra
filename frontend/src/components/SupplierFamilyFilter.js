import React, { useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import {
  Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList,
} from '@/components/ui/command';
import { useTranslation } from 'react-i18next';
import { Check, ChevronsUpDown, Layers } from 'lucide-react';

// Filtre « Famille » du comparateur de prix.
//
// Les familles viennent de GET /fournisseurs/familles : plus de 2 000
// libelles (un fournisseur en emploie a lui seul 2 204). Une liste
// deroulante simple serait inutilisable : on filtre a la saisie, sans tenir
// compte des accents ni de la casse, et on n'affiche que les 100 premieres
// correspondances pour garder l'ecran fluide.
const MAX_AFFICHEES = 100;

const sansAccent = (s) => (s || '')
  .normalize('NFD')
  .replace(/[\u0300-\u036f]/g, '')
  .toLowerCase();

export const SupplierFamilyFilter = ({ familles, valeur, onChange, desactive = false, chargement = false }) => {
  const { t } = useTranslation();
  const [ouvert, setOuvert] = useState(false);
  const [saisie, setSaisie] = useState('');

  const correspondances = useMemo(() => {
    const q = sansAccent(saisie.trim());
    const toutes = q ? familles.filter((f) => sansAccent(f.famille).includes(q)) : familles;
    return { total: toutes.length, affichees: toutes.slice(0, MAX_AFFICHEES) };
  }, [familles, saisie]);

  const choisir = (famille) => {
    setOuvert(false);
    setSaisie('');
    onChange(famille);
  };

  return (
    <div className="flex flex-col gap-1.5 sm:flex-row sm:items-center sm:gap-3">
      <span id="fournisseurs-famille-label" className="flex items-center gap-1.5 text-sm text-muted-foreground">
        <Layers className="h-4 w-4" />
        {t('fo.famille')}
      </span>
      <Popover open={ouvert} onOpenChange={setOuvert}>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="outline"
            role="combobox"
            aria-expanded={ouvert}
            aria-labelledby="fournisseurs-famille-label"
            className="justify-between font-normal sm:w-96"
            disabled={desactive}
            data-testid="fournisseurs-famille"
          >
            <span className="truncate">{valeur || t('fo.toutes_familles')}</span>
            <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[min(24rem,calc(100vw-2rem))] p-0" align="start">
          <Command shouldFilter={false}>
            <CommandInput
              placeholder={t('fo.filtrer_familles')}
              value={saisie}
              onValueChange={setSaisie}
              data-testid="fournisseurs-famille-saisie"
            />
            <CommandList className="max-h-80">
              <CommandEmpty>
                {chargement ? t('fo.familles_chargement') : t('fo.aucune_famille')}
              </CommandEmpty>
              <CommandGroup>
                {!saisie.trim() && (
                  <CommandItem value="__toutes__" onSelect={() => choisir('')}>
                    <Check className={`mr-2 h-4 w-4 ${valeur ? 'opacity-0' : 'opacity-100'}`} />
                    {t('fo.toutes_familles')}
                  </CommandItem>
                )}
                {correspondances.affichees.map((f) => (
                  <CommandItem key={f.famille} value={f.famille} onSelect={() => choisir(f.famille)} className="group">
                    <Check className={`mr-2 h-4 w-4 shrink-0 ${valeur === f.famille ? 'opacity-100' : 'opacity-0'}`} />
                    <span className="min-w-0">
                      <span className="block truncate">{f.famille}</span>
                      {f.fournisseurs?.length > 0 && (
                        // Sur la ligne survolee (fond accent), le gris standard devenait
                        // illisible : blanc, contraste ~4,7:1 sur l'accent (AA texte).
                        <span className="block truncate text-xs text-muted-foreground group-data-[selected=true]:text-accent-foreground">
                          {f.fournisseurs.join(', ')}
                        </span>
                      )}
                    </span>
                  </CommandItem>
                ))}
              </CommandGroup>
              {correspondances.total > MAX_AFFICHEES && (
                <p className="px-3 py-2 text-xs text-muted-foreground">
                  {t('fo.autres_familles', { n: correspondances.total - MAX_AFFICHEES })}
                </p>
              )}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  );
};
