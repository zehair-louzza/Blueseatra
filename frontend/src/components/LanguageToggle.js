import React from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';

export const LanguageToggle = () => {
  const { i18n } = useTranslation();
  const setLang = (lng) => {
    i18n.changeLanguage(lng);
    localStorage.setItem('bs_lang', lng);
    if (document?.documentElement) document.documentElement.lang = lng;
  };
  return (
    <div className="inline-flex items-center rounded-lg border bg-card p-0.5" data-testid="language-toggle">
      {['fr', 'en'].map((lng) => (
        <Button key={lng} size="sm" variant={i18n.language === lng ? 'default' : 'ghost'}
          className="h-7 px-2.5 text-xs" onClick={() => setLang(lng)} data-testid={`lang-${lng}`}>
          <span className="sr-only">{lng === 'fr' ? 'Fran\u00e7ais' : 'English'}</span>
          {lng.toUpperCase()}
        </Button>
      ))}
    </div>
  );
};
