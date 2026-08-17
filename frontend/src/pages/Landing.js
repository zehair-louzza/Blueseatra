import React from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { LanguageToggle } from '@/components/LanguageToggle';
import { FileSearch, BookOpen, Sparkles, ShieldCheck, ArrowRight, Check } from 'lucide-react';
import { BrandLogo } from '@/components/BrandLogo';
import { motion } from 'framer-motion';

const Feature = ({ icon: Icon, title, desc }) => (
  <Card className="card-shadow border-0 p-6">
    <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-accent/10 text-accent">
      <Icon className="h-5 w-5" />
    </div>
    <h3 className="font-display text-base font-semibold text-foreground">{title}</h3>
    <p className="mt-1.5 text-sm leading-6 text-muted-foreground">{desc}</p>
  </Card>
);

export default function Landing() {
  const { t } = useTranslation();
  const plans = [
    { key: 'plan_starter', price: '\u20ac0', items: 3 },
    { key: 'plan_pro', price: '\u20ac49', items: 4, featured: true },
    { key: 'plan_ent', price: 'Custom', items: 4 },
  ];
  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <BrandLogo to="/" />
          <div className="flex items-center gap-2">
            <LanguageToggle />
            <Link to="/login"><Button variant="ghost" size="sm" data-testid="nav-login">{t('nav.login')}</Button></Link>
            <Link to="/signup"><Button size="sm" data-testid="nav-signup">{t('nav.signup')}</Button></Link>
          </div>
        </div>
      </header>

      <section className="relative overflow-hidden">
        <div className="hero-ocean absolute inset-0 -z-10" />
        <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6 lg:px-8 lg:py-28">
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} className="max-w-3xl">
            <span className="inline-flex items-center gap-1.5 rounded-full border bg-card px-3 py-1 text-xs font-medium text-accent">
              <Sparkles className="h-3.5 w-3.5" /> {t('brand_tag')}
            </span>
            <h1 className="mt-5 font-display text-4xl font-semibold tracking-tight text-foreground sm:text-5xl lg:text-6xl">{t('landing.hero_title')}</h1>
            <p className="mt-5 max-w-2xl text-base leading-7 text-muted-foreground md:text-lg">{t('landing.hero_sub')}</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/signup"><Button size="lg" className="gap-2" data-testid="hero-cta-primary">{t('landing.cta_primary')} <ArrowRight className="h-4 w-4" /></Button></Link>
              <a href="#how"><Button size="lg" variant="secondary" data-testid="hero-cta-secondary">{t('landing.cta_secondary')}</Button></a>
            </div>
            <div className="mt-6 font-mono text-xs text-muted-foreground">{t('landing.steps_title')}</div>
          </motion.div>
        </div>
      </section>

      <section id="how" className="mx-auto max-w-6xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <Feature icon={FileSearch} title={t('landing.f1_t')} desc={t('landing.f1_d')} />
          <Feature icon={BookOpen} title={t('landing.f2_t')} desc={t('landing.f2_d')} />
          <Feature icon={Sparkles} title={t('landing.f3_t')} desc={t('landing.f3_d')} />
          <Feature icon={ShieldCheck} title={t('landing.f4_t')} desc={t('landing.f4_d')} />
        </div>
      </section>

      <section id="plans" className="mx-auto max-w-6xl px-4 py-12 sm:px-6 lg:px-8">
        <h2 className="font-display text-2xl font-semibold tracking-tight text-foreground">{t('landing.plans_title')}</h2>
        <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-3">
          {plans.map((p) => (
            <Card key={p.key} className={`card-shadow border-0 p-6 ${p.featured ? 'ring-2 ring-accent' : ''}`}>
              <h3 className="font-display text-lg font-semibold text-foreground">{t(`landing.${p.key}`)}</h3>
              <div className="mt-2 font-display text-3xl font-semibold text-primary">{p.price}<span className="text-sm font-normal text-muted-foreground">/mo</span></div>
              <ul className="mt-4 space-y-2 text-sm text-muted-foreground">
                {Array.from({ length: p.items }).map((_, i) => (
                  <li key={i} className="flex items-center gap-2"><Check className="h-4 w-4 text-accent" /> {t(`landing.f${i + 1}_t`)}</li>
                ))}
              </ul>
              <Link to="/signup"><Button className="mt-6 w-full" variant={p.featured ? 'default' : 'secondary'}>{t('landing.plan_cta')}</Button></Link>
              <p className="mt-2 text-center text-xs text-muted-foreground">{t('landing.plan_soon')}</p>
            </Card>
          ))}
        </div>
      </section>

      <footer className="border-t">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-2 px-4 py-8 text-sm text-muted-foreground sm:flex-row sm:px-6 lg:px-8">
          <span>\u00a9 {new Date().getFullYear()} Blueseatra</span>
          <span className="font-mono text-xs">{t('landing.steps_title')}</span>
        </div>
      </footer>
    </div>
  );
}
