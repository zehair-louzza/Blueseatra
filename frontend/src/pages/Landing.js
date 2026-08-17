import React from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { LanguageToggle } from '@/components/LanguageToggle';
import { BrandLogo } from '@/components/BrandLogo';
import { motion, useReducedMotion } from 'framer-motion';
import { ArrowRight, Check } from 'lucide-react';

const fade = (reduce, delay = 0) =>
  reduce
    ? {}
    : {
        initial: { opacity: 0, y: 18 },
        whileInView: { opacity: 1, y: 0 },
        viewport: { once: true, amount: 0.25 },
        transition: { duration: 0.55, delay, ease: [0.16, 1, 0.3, 1] },
      };

export default function Landing() {
  const { t } = useTranslation();
  const reduce = useReducedMotion();
  const year = new Date().getFullYear();
  const steps = ['s1', 's2', 's3', 's4', 's5'];
  const feats = ['intake', 'match', 'lots', 'rules', 'pdf', 'audit'];
  const plans = [
    { key: 'plan_starter', price: '0 €', items: ['p1', 'p2', 'p3'] },
    { key: 'plan_pro', price: '49 €', items: ['p1', 'p2', 'p3', 'p4'], featured: true },
    { key: 'plan_ent', price: t('landing.plan_custom'), items: ['p1', 'p2', 'p3', 'p4'] },
  ];

  return (
    <div className="min-h-[100dvh] bg-background text-foreground">
      <a href="#contenu" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:bg-primary focus:px-3 focus:py-2 focus:text-primary-foreground">
        {t('landing.skip')}
      </a>
      <header className="sticky top-0 z-40 border-b border-border/80 bg-background/85 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <BrandLogo to="/" />
          <nav className="hidden items-center gap-7 text-sm text-muted-foreground md:flex">
            <a href="#parcours" className="hover:text-foreground">{t('nav.how')}</a>
            <a href="#fonctions" className="hover:text-foreground">{t('nav.features')}</a>
            <a href="#offres" className="hover:text-foreground">{t('nav.plans')}</a>
          </nav>
          <div className="flex items-center gap-2">
            <LanguageToggle />
            <Link to="/login"><Button variant="ghost" size="sm" data-testid="nav-login">{t('nav.login')}</Button></Link>
            <Link to="/signup"><Button size="sm" data-testid="nav-signup">{t('nav.signup')}</Button></Link>
          </div>
        </div>
      </header>

      <main id="contenu">
        <section className="mx-auto grid max-w-6xl items-center gap-10 px-4 pb-16 pt-10 sm:px-6 md:grid-cols-12 md:pt-14 lg:gap-14">
          <motion.div className="md:col-span-6" {...fade(reduce)}>
            <h1 className="font-display text-4xl font-semibold leading-[1.12] tracking-tight text-foreground md:text-5xl lg:text-[3.25rem]">
              {t('landing.hero_title')}
            </h1>
            <p className="mt-5 max-w-[36ch] text-base leading-7 text-muted-foreground">
              {t('landing.hero_sub')}
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/signup">
                <Button size="lg" className="gap-2" data-testid="hero-cta-primary">
                  {t('landing.cta_primary')} <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
              <a href="#parcours">
                <Button size="lg" variant="secondary" data-testid="hero-cta-secondary">{t('landing.cta_secondary')}</Button>
              </a>
            </div>
          </motion.div>
          <motion.figure className="md:col-span-6" {...fade(reduce, 0.08)}>
            <img
              src="/landing/hero-desk.jpg"
              alt={t('landing.hero_alt')}
              width={1600}
              height={900}
              className="aspect-[16/10] w-full rounded-xl object-cover"
            />
            <figcaption className="mt-3 text-sm text-muted-foreground">{t('landing.hero_cap')}</figcaption>
          </motion.figure>
        </section>

        <section className="border-y border-border bg-card">
          <div className="mx-auto grid max-w-6xl gap-10 px-4 py-16 sm:px-6 md:grid-cols-2">
            <div>
              <h2 className="font-display text-2xl font-semibold tracking-tight">{t('landing.time_before_t')}</h2>
              <p className="mt-4 max-w-[52ch] text-base leading-7 text-muted-foreground">{t('landing.time_before_d')}</p>
            </div>
            <div>
              <h2 className="font-display text-2xl font-semibold tracking-tight text-primary">{t('landing.time_after_t')}</h2>
              <p className="mt-4 max-w-[52ch] text-base leading-7 text-muted-foreground">{t('landing.time_after_d')}</p>
            </div>
          </div>
        </section>

        <section id="parcours" className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
          <h2 className="max-w-[18ch] font-display text-3xl font-semibold tracking-tight">{t('landing.path_title')}</h2>
          <ol className="mt-12 space-y-0">
            {steps.map((key, i) => (
              <motion.li key={key} className="grid gap-3 border-t border-border py-7 md:grid-cols-12 md:items-baseline" {...fade(reduce, i * 0.04)}>
                <span className="font-mono text-sm text-accent md:col-span-2">{String(i + 1).padStart(2, '0')}</span>
                <h3 className="font-display text-xl font-semibold md:col-span-4">{t(`landing.${key}_t`)}</h3>
                <p className="text-base leading-7 text-muted-foreground md:col-span-6">{t(`landing.${key}_d`)}</p>
              </motion.li>
            ))}
          </ol>
        </section>

        <section id="fonctions" className="bg-primary text-primary-foreground">
          <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
            <h2 className="max-w-[20ch] font-display text-3xl font-semibold tracking-tight">{t('landing.feat_title')}</h2>
            <div className="mt-12 grid gap-px overflow-hidden rounded-xl bg-primary-foreground/15 md:grid-cols-6">
              {feats.map((key, i) => (
                <article
                  key={key}
                  className={`bg-primary p-6 md:p-8 ${i === 0 ? 'md:col-span-4' : i === 1 ? 'md:col-span-2' : 'md:col-span-2'}`}
                >
                  <h3 className="font-display text-lg font-semibold">{t(`landing.${key}_t`)}</h3>
                  <p className="mt-3 text-sm leading-6 text-primary-foreground/80">{t(`landing.${key}_d`)}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto grid max-w-6xl items-center gap-10 px-4 py-20 sm:px-6 md:grid-cols-12">
          <figure className="md:col-span-7">
            <img src="/landing/catalog.jpg" alt={t('landing.cat_alt')} width={1200} height={900} className="w-full rounded-xl object-cover" />
          </figure>
          <div className="md:col-span-5">
            <h2 className="font-display text-3xl font-semibold tracking-tight">{t('landing.cat_title')}</h2>
            <p className="mt-4 text-base leading-7 text-muted-foreground">{t('landing.cat_d')}</p>
            <ul className="mt-6 space-y-3 text-sm leading-6">
              {['cat_b1', 'cat_b2', 'cat_b3'].map((k) => (
                <li key={k} className="flex gap-2">
                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
                  <span>{t(`landing.${k}`)}</span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="border-y border-border">
          <div className="mx-auto grid max-w-6xl md:grid-cols-2">
            <img src="/landing/chantier.jpg" alt={t('landing.site_alt')} width={1400} height={577} className="h-full min-h-[240px] w-full object-cover" />
            <div className="flex flex-col justify-center px-4 py-14 sm:px-10">
              <h2 className="font-display text-3xl font-semibold tracking-tight">{t('landing.value_title')}</h2>
              <p className="mt-4 max-w-[48ch] text-base leading-7 text-muted-foreground">{t('landing.value_d')}</p>
            </div>
          </div>
        </section>

        <section id="offres" className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
          <h2 className="font-display text-3xl font-semibold tracking-tight">{t('landing.plans_title')}</h2>
          <p className="mt-3 max-w-[50ch] text-base text-muted-foreground">{t('landing.plan_soon')}</p>
          <div className="mt-10 grid gap-4 md:grid-cols-3">
            {plans.map((p) => (
              <article key={p.key} className={`rounded-xl border bg-card p-6 ${p.featured ? 'border-accent' : 'border-border'}`}>
                <h3 className="font-display text-lg font-semibold">{t(`landing.${p.key}`)}</h3>
                <p className="mt-3 font-display text-3xl font-semibold text-primary">
                  {p.price}
                  <span className="text-sm font-normal text-muted-foreground"> / {t('landing.per_month')}</span>
                </p>
                <ul className="mt-5 space-y-2 text-sm text-muted-foreground">
                  {p.items.map((k) => (
                    <li key={k} className="flex gap-2">
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
                      {t(`landing.${k}`)}
                    </li>
                  ))}
                </ul>
                <Link to="/signup">
                  <Button className="mt-6 w-full" variant={p.featured ? 'default' : 'secondary'}>{t('landing.plan_cta')}</Button>
                </Link>
              </article>
            ))}
          </div>
        </section>

        <section className="bg-primary px-4 py-16 text-primary-foreground sm:px-6">
          <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-6 md:flex-row md:items-center">
            <h2 className="max-w-[18ch] font-display text-3xl font-semibold tracking-tight">{t('landing.close_title')}</h2>
            <Link to="/signup">
              <Button size="lg" variant="secondary" className="gap-2">
                {t('landing.cta_primary')} <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t">
        <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-3 px-4 py-8 text-sm text-muted-foreground sm:flex-row sm:items-center sm:px-6">
          <BrandLogo to="/" imgClassName="h-7 max-w-[160px] opacity-90" />
          <span>© {year} Blueseatra</span>
        </div>
      </footer>
    </div>
  );
}
