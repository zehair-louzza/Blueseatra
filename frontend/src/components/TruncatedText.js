import React from 'react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

// Texte tronque sur une ligne avec info-bulle contenant le libelle complet.
// Les designations fournisseurs font souvent 80 a 140 caracteres : on ne les
// laisse jamais deborder ni casser la grille du tableau. Le declencheur est un
// <button> : l'info-bulle s'ouvre aussi au clavier (Tab puis focus), et
// l'attribut title assure un repli si le portail Radix est indisponible.
export const TruncatedText = ({ children, className = '', testid }) => {
  const texte = typeof children === 'string' ? children : String(children ?? '');
  if (!texte) return <span className="text-muted-foreground">{'\u2014'}</span>;
  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            title={texte}
            aria-label={texte}
            data-testid={testid}
            className={`block w-full cursor-help truncate text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${className}`}
          >
            {texte}
          </button>
        </TooltipTrigger>
        <TooltipContent className="max-w-sm">
          <p className="text-xs leading-relaxed">{texte}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};
