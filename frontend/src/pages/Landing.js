import React from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { motion, useReducedMotion } from 'framer-motion';
import {
  ArrowRight, Check, Mail, FileText, Camera, Layers, Receipt, ShieldCheck, Search,
  Inbox, ScanText, GitCompareArrows, ClipboardCheck, FileCheck2, FileSpreadsheet,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { LanguageToggle } from '@/components/LanguageToggle';
import { BrandLogo } from '@/components/BrandLogo';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';

// Chiffres reels du catalogue commun en production (24/09/2026).
const FOURNISSEURS = ['Rexel', 'Prolians', 'Point.P', 'YESSS', 'La Plateforme du Bâtiment',
  'Au Forum du Bâtiment', 'SFIC', 'Chausson Matériaux', 'Icilux'];

const reveal = (reduce, delay = 0) => (reduce ? {} : {
  initial: { opacity: 0, y: 20 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, amount: 0.2 },
  transition: { duration: 0.6, delay, ease: [0.16, 1, 0.3, 1] },
});

const Container = ({ className = '', children }) => (
  <div className={`mx-auto w-full max-w-7xl px-4 sm:px-6 lg:px-8 ${className}`}>{children}</div>
);

function Header({ t }) {
  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-background/80 backdrop-blur-md">
      <Container className="flex h-16 items-center justify-between gap-6">
        <BrandLogo to="/" imgClassName="h-9 max-w-[180px]" />
        <nav className="hidden items-center gap-7 text-[14px] text-muted-foreground lg:flex">
          <a href="#valeurs" className="transition-colors hover:text-foreground">{t('lp.nav_values')}</a>
          <a href="#fonctions" className="transition-colors hover:text-foreground">{t('lp.nav_features')}</a>
          <a href="#parcours" className="transition-colors hover:text-foreground">{t('lp.nav_how')}</a>
          <a href="#offres" className="transition-colors hover:text-foreground">{t('lp.nav_plans')}</a>
          <a href="#faq" className="transition-colors hover:text-foreground">{t('lp.nav_faq')}</a>
        </nav>
        <div className="flex items-center gap-2">
          <LanguageToggle />
          <Link to="/login" className="hidden sm:block">
            <Button variant="ghost" size="sm" data-testid="nav-login">{t('lp.login')}</Button>
          </Link>
          <Link to="/signup"><Button size="sm" data-testid="nav-signup">{t('lp.cta')}</Button></Link>
        </div>
      </Container>
    </header>
  );
}

function Hero({ t, reduce }) {
  return (
    <section className="relative overflow-hidden">
      <div aria-hidden className="bg-grid pointer-events-none absolute inset-0" />
      <div aria-hidden className="hero-ocean pointer-events-none absolute inset-0" />
      <Container className="relative grid items-center gap-12 pb-20 pt-14 md:pt-20 lg:grid-cols-12 lg:gap-10">
        <motion.div className="lg:col-span-5" {...reveal(reduce)}>
          <h1 className="font-display text-4xl font-semibold leading-[1.08] text-foreground md:text-5xl lg:text-[3.4rem]">
            {t('lp.hero_title')}
          </h1>
          <p className="mt-6 max-w-[44ch] text-[17px] leading-7 text-muted-foreground">{t('lp.hero_sub')}</p>
          <div className="mt-9 flex flex-wrap gap-3">
            <Link to="/signup">
              <Button size="lg" className="gap-2" data-testid="hero-cta-primary">
                {t('lp.cta')} <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
            <a href="#parcours">
              <Button size="lg" variant="outline" data-testid="hero-cta-secondary">{t('lp.cta_second')}</Button>
            </a>
          </div>
        </motion.div>
        <motion.figure className="lg:col-span-7" {...reveal(reduce, 0.1)}>
          <div className="shadow-lift overflow-hidden rounded-2xl border border-border/80 bg-card">
            <div className="flex h-9 items-center gap-1.5 border-b border-border/70 bg-muted/60 px-4">
              <span className="h-2.5 w-2.5 rounded-full bg-border" />
              <span className="h-2.5 w-2.5 rounded-full bg-border" />
              <span className="h-2.5 w-2.5 rounded-full bg-border" />
              <span className="ml-3 truncate text-xs text-muted-foreground">blueseatra.com/app/fournisseurs/catalogue</span>
            </div>
            <img
              src="/landing/app-catalogue.jpg"
              alt={t('lp.hero_alt')}
              width={1600}
              height={1000}
              fetchpriority="high"
              className="block aspect-[16/10] w-full object-cover object-top"
            />
          </div>
        </motion.figure>
      </Container>
    </section>
  );
}

function Proof({ t }) {
  const stats = [
    { v: '967 563', l: t('lp.stat_refs') },
    { v: '9', l: t('lp.stat_suppliers') },
    { v: '4', l: t('lp.stat_vat') },
    { v: '0', l: t('lp.stat_zero') },
  ];
  return (
    <section className="border-y border-border/70 bg-card">
      <Container className="py-12">
        <dl className="grid grid-cols-2 gap-y-8 md:grid-cols-4">
          {stats.map((s) => (
            <div key={s.l} className="px-2">
              <dt className="sr-only">{s.l}</dt>
              <dd className="tabular font-display text-3xl font-semibold text-primary md:text-4xl">{s.v}</dd>
              <dd className="mt-1 text-sm text-muted-foreground">{s.l}</dd>
            </div>
          ))}
        </dl>
        <div className="mt-10 border-t border-border/70 pt-8">
          <p className="text-sm font-medium text-foreground">{t('lp.suppliers_label')}</p>
          <ul className="mt-4 flex flex-wrap gap-2">
            {FOURNISSEURS.map((f) => (
              <li key={f} className="rounded-full border border-border bg-background px-3.5 py-1.5 text-[13px] font-medium text-foreground/80">{f}</li>
            ))}
          </ul>
        </div>
        <div className="mt-8 grid items-center gap-6 rounded-2xl border border-accent/30 bg-[hsl(185_45%_96%)] p-6 md:grid-cols-12 md:p-8">
          <div className="flex items-start gap-4 md:col-span-9">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent text-accent-foreground">
              <FileSpreadsheet className="h-5 w-5" />
            </span>
            <div>
              <h3 className="font-display text-xl font-semibold">{t('lp.own_t')}</h3>
              <p className="mt-2 max-w-[70ch] text-[15px] leading-7 text-muted-foreground">{t('lp.own_d')}</p>
            </div>
          </div>
          <div className="md:col-span-3 md:text-right">
            <Link to="/signup"><Button variant="outline" className="gap-2">{t('lp.own_cta')} <ArrowRight className="h-4 w-4" /></Button></Link>
          </div>
        </div>
      </Container>
    </section>
  );
}

function Values({ t, reduce }) {
  const vals = [
    { k: 'BLUE', t: t('lp.blue_t'), d: t('lp.blue_d'), color: 'text-primary' },
    { k: 'SEA', t: t('lp.sea_t'), d: t('lp.sea_d'), color: 'text-[hsl(var(--brand-teal))]' },
    { k: 'TRA', t: t('lp.tra_t'), d: t('lp.tra_d'), color: 'text-accent' },
  ];
  return (
    <section id="valeurs" className="scroll-mt-20">
      <Container className="py-24">
        <div className="grid gap-12 lg:grid-cols-12">
          <div className="lg:col-span-4">
            <div className="lg:sticky lg:top-28">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">{t('lp.nav_values')}</p>
              <h2 className="mt-3 max-w-[22ch] font-display text-3xl font-semibold leading-tight md:text-4xl">{t('lp.values_title')}</h2>
              {/* L'icone raconte le parcours : un signal brut (la demande) devient le coin d'un document valide. */}
              <img src="/brand/blueseatra-mark.png" alt="" width={512} height={512} loading="lazy" className="mt-10 hidden h-44 w-44 object-contain lg:block" />
              <p className="mt-4 hidden max-w-[34ch] text-sm leading-6 text-muted-foreground lg:block">{t('lp.mark_d')}</p>
            </div>
          </div>
          <div className="space-y-4 lg:col-span-8">
            {vals.map((v, i) => (
              <motion.article
                key={v.k}
                className="grid gap-3 rounded-2xl border border-border/80 bg-card px-6 py-7 shadow-soft md:grid-cols-12 md:items-center md:px-8"
                {...reveal(reduce, i * 0.06)}
              >
                <span className={`font-display text-5xl font-bold tracking-tight md:col-span-4 ${v.color}`}>{v.k}</span>
                <div className="md:col-span-8">
                  <h3 className="font-display text-xl font-semibold">{v.t}</h3>
                  <p className="mt-2 text-[15px] leading-7 text-muted-foreground">{v.d}</p>
                </div>
              </motion.article>
            ))}
          </div>
        </div>
      </Container>
    </section>
  );
}

function Features({ t, reduce }) {
  return (
    <section id="fonctions" className="scroll-mt-20 bg-card">
      <Container className="py-24">
        <h2 className="max-w-[22ch] font-display text-3xl font-semibold leading-tight md:text-4xl">{t('lp.feat_title')}</h2>
        <div className="mt-12 grid gap-4 md:grid-cols-6">
          <motion.article className="overflow-hidden rounded-2xl border border-border/80 bg-primary text-primary-foreground md:col-span-4 md:row-span-2" {...reveal(reduce)}>
            <div className="p-8">
              <div className="flex gap-2 text-primary-foreground/80">
                <Mail className="h-5 w-5" /><FileText className="h-5 w-5" /><Camera className="h-5 w-5" />
              </div>
              <h3 className="mt-5 font-display text-2xl font-semibold">{t('lp.f_intake_t')}</h3>
              <p className="mt-3 max-w-[52ch] text-[15px] leading-7 text-primary-foreground/80">{t('lp.f_intake_d')}</p>
            </div>
            <img src="/landing/hero-desk.jpg" alt="" width={1600} height={900} loading="lazy" className="h-64 w-full object-cover md:h-80" />
          </motion.article>
          <motion.article className="rounded-2xl border border-border/80 bg-[hsl(185_45%_95%)] p-7 md:col-span-2" {...reveal(reduce, 0.05)}>
            <Search className="h-5 w-5 text-accent" />
            <h3 className="mt-4 font-display text-lg font-semibold">{t('lp.f_catalog_t')}</h3>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{t('lp.f_catalog_d')}</p>
          </motion.article>
          <motion.article className="rounded-2xl border border-border/80 bg-background p-7 md:col-span-2" {...reveal(reduce, 0.1)}>
            <Layers className="h-5 w-5 text-primary" />
            <h3 className="mt-4 font-display text-lg font-semibold">{t('lp.f_lots_t')}</h3>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{t('lp.f_lots_d')}</p>
          </motion.article>
          <motion.article className="rounded-2xl border border-border/80 bg-background p-7 md:col-span-3" {...reveal(reduce, 0.05)}>
            <Receipt className="h-5 w-5 text-primary" />
            <h3 className="mt-4 font-display text-lg font-semibold">{t('lp.f_vat_t')}</h3>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{t('lp.f_vat_d')}</p>
          </motion.article>
          <motion.article className="relative overflow-hidden rounded-2xl border border-border/80 md:col-span-3" {...reveal(reduce, 0.1)}>
            <img src="/landing/chantier.jpg" alt="" width={1400} height={577} loading="lazy" className="absolute inset-0 h-full w-full object-cover" />
            <div className="absolute inset-0 bg-gradient-to-t from-[hsl(218_45%_10%/0.92)] via-[hsl(218_45%_10%/0.6)] to-[hsl(218_45%_10%/0.2)]" />
            <div className="relative p-7 text-white">
              <ShieldCheck className="h-5 w-5" />
              <h3 className="mt-16 font-display text-lg font-semibold">{t('lp.f_audit_t')}</h3>
              <p className="mt-2 text-sm leading-6 text-white/85">{t('lp.f_audit_d')}</p>
            </div>
          </motion.article>
        </div>
      </Container>
    </section>
  );
}

function Steps({ t, reduce }) {
  const steps = [
    { k: 's1', icon: Inbox }, { k: 's2', icon: ScanText }, { k: 's3', icon: GitCompareArrows },
    { k: 's4', icon: ClipboardCheck }, { k: 's5', icon: FileCheck2 },
  ];
  return (
    <section id="parcours" className="scroll-mt-20">
      <Container className="py-24">
        <h2 className="max-w-[20ch] font-display text-3xl font-semibold leading-tight md:text-4xl">{t('lp.how_title')}</h2>
        <ol className="relative mt-14 grid gap-8 md:grid-cols-5 md:gap-6">
          <span aria-hidden className="absolute left-5 right-5 top-5 hidden h-px bg-gradient-to-r from-primary/40 via-[hsl(var(--brand-teal)/0.6)] to-primary/40 md:block" />
          {steps.map(({ k, icon: Icon }, i) => (
            <motion.li key={k} className="relative" {...reveal(reduce, i * 0.06)}>
              <span className="relative flex h-10 w-10 items-center justify-center rounded-full border border-border bg-card text-primary shadow-soft">
                <Icon className="h-[18px] w-[18px]" />
              </span>
              <h3 className="mt-5 font-display text-lg font-semibold">{t(`lp.${k}_t`)}</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{t(`lp.${k}_d`)}</p>
            </motion.li>
          ))}
        </ol>
      </Container>
    </section>
  );
}

function PriceControl({ t, reduce }) {
  return (
    <section className="bg-card">
      <Container className="grid items-center gap-12 py-24 md:grid-cols-12">
        <motion.figure className="md:col-span-6" {...reveal(reduce)}>
          <img src="/landing/catalog.jpg" alt={t('lp.price_alt')} width={1200} height={900} loading="lazy" className="aspect-[4/3] w-full rounded-2xl object-cover" />
        </motion.figure>
        <motion.div className="md:col-span-5 md:col-start-8" {...reveal(reduce, 0.08)}>
          <h2 className="font-display text-3xl font-semibold leading-tight md:text-4xl">{t('lp.price_title')}</h2>
          <p className="mt-4 text-[16px] leading-7 text-muted-foreground">{t('lp.price_d')}</p>
          <ul className="mt-8 space-y-4">
            {['price_b1', 'price_b2', 'price_b3'].map((k) => (
              <li key={k} className="flex gap-3 text-[15px]">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent/10 text-accent"><Check className="h-3.5 w-3.5" /></span>
                <span>{t(`lp.${k}`)}</span>
              </li>
            ))}
          </ul>
        </motion.div>
      </Container>
    </section>
  );
}

function Plans({ t }) {
  const plans = [
    { key: 'plan_starter', price: '0 €', items: ['p1', 'p2', 'p3'] },
    { key: 'plan_pro', price: '49 €', items: ['p1', 'p2', 'p3', 'p4'], featured: true },
    { key: 'plan_ent', price: t('lp.plan_custom'), items: ['p1', 'p2', 'p3', 'p4'] },
  ];
  return (
    <section id="offres" className="scroll-mt-20">
      <Container className="py-24">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">{t('lp.nav_plans')}</p>
        <h2 className="mt-3 font-display text-3xl font-semibold md:text-4xl">{t('lp.plans_title')}</h2>
        <p className="mt-3 max-w-[56ch] text-[15px] text-muted-foreground">{t('lp.plans_note')}</p>
        <div className="mt-12 grid items-stretch gap-5 md:grid-cols-3">
          {plans.map((p) => (
            <article key={p.key} className={`relative flex flex-col rounded-2xl border p-7 ${p.featured ? 'border-primary bg-primary text-primary-foreground shadow-lift' : 'border-border/80 bg-card shadow-soft'}`}>
              {p.featured && (
                <span className="absolute right-6 top-6 rounded-full bg-[hsl(var(--brand-teal))] px-2.5 py-1 text-[11px] font-semibold text-[hsl(218_45%_12%)]">{t('lp.popular')}</span>
              )}
              <h3 className="font-display text-lg font-semibold">{t(`lp.${p.key}`)}</h3>
              <p className="tabular mt-4 font-display text-4xl font-semibold">
                {p.price}
                {p.key !== 'plan_ent' && <span className={`text-sm font-normal ${p.featured ? 'text-primary-foreground/70' : 'text-muted-foreground'}`}> / {t('lp.per_month')}</span>}
              </p>
              <ul className={`mt-6 flex-1 space-y-3 text-sm ${p.featured ? 'text-primary-foreground/90' : 'text-muted-foreground'}`}>
                {p.items.map((k) => (
                  <li key={k} className="flex gap-2.5">
                    <Check className={`mt-0.5 h-4 w-4 shrink-0 ${p.featured ? 'text-[hsl(var(--brand-teal))]' : 'text-accent'}`} />
                    {t(`lp.${k}`)}
                  </li>
                ))}
              </ul>
              <Link to="/signup" className="mt-8">
                <Button className={`w-full ${p.featured ? 'bg-white text-primary hover:bg-white/90' : ''}`} variant={p.featured ? 'default' : 'outline'}>
                  {t('lp.signup')}
                </Button>
              </Link>
            </article>
          ))}
        </div>
      </Container>
    </section>
  );
}

function Faq({ t }) {
  return (
    <section id="faq" className="scroll-mt-20 bg-card">
      <Container className="grid gap-10 py-24 md:grid-cols-12">
        <h2 className="font-display text-3xl font-semibold md:col-span-4 md:text-4xl">{t('lp.faq_title')}</h2>
        <Accordion type="single" collapsible className="md:col-span-8">
          {['1', '2', '3', '4'].map((n) => (
            <AccordionItem key={n} value={n} className="border-border/80">
              <AccordionTrigger className="py-5 text-left text-[16px] font-medium hover:no-underline">{t(`lp.q${n}`)}</AccordionTrigger>
              <AccordionContent className="pb-5 text-[15px] leading-7 text-muted-foreground">{t(`lp.a${n}`)}</AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </Container>
    </section>
  );
}

function Closing({ t }) {
  return (
    <section className="px-4 py-20 sm:px-6 lg:px-8">
      <div className="relative mx-auto max-w-7xl overflow-hidden rounded-3xl bg-primary px-8 py-16 text-primary-foreground md:px-16">
        <div aria-hidden className="pointer-events-none absolute -right-24 -top-24 h-80 w-80 rounded-full bg-[hsl(var(--brand-teal)/0.28)] blur-3xl" />
        <img aria-hidden src="/brand/blueseatra-mark.png" alt="" width={512} height={512} loading="lazy" className="pointer-events-none absolute -bottom-16 right-10 hidden h-72 w-72 object-contain opacity-[0.12] md:block" />
        <div className="relative flex flex-col items-start justify-between gap-8 md:flex-row md:items-center">
          <div>
            <h2 className="max-w-[22ch] font-display text-3xl font-semibold leading-tight md:text-4xl">{t('lp.close_title')}</h2>
            <p className="mt-3 text-primary-foreground/80">{t('lp.close_d')}</p>
          </div>
          <Link to="/signup">
            <Button size="lg" className="gap-2 bg-white text-primary hover:bg-white/90">
              {t('lp.cta')} <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
        </div>
      </div>
    </section>
  );
}

function Footer({ t }) {
  const year = new Date().getFullYear();
  return (
    <footer className="border-t border-border/70">
      <Container className="grid gap-10 py-14 md:grid-cols-12">
        <div className="md:col-span-5">
          <BrandLogo to="/" imgClassName="h-8 max-w-[170px]" />
          <p className="mt-4 max-w-[36ch] text-sm text-muted-foreground">{t('lp.foot_tag')}</p>
        </div>
        <div className="grid grid-cols-2 gap-8 text-sm md:col-span-7 md:grid-cols-3">
          <div>
            <p className="font-semibold">{t('lp.foot_product')}</p>
            <ul className="mt-3 space-y-2 text-muted-foreground">
              <li><a href="#fonctions" className="hover:text-foreground">{t('lp.nav_features')}</a></li>
              <li><a href="#parcours" className="hover:text-foreground">{t('lp.nav_how')}</a></li>
              <li><a href="#offres" className="hover:text-foreground">{t('lp.nav_plans')}</a></li>
            </ul>
          </div>
          <div>
            <p className="font-semibold">{t('lp.foot_company')}</p>
            <ul className="mt-3 space-y-2 text-muted-foreground">
              <li><a href="#valeurs" className="hover:text-foreground">{t('lp.nav_values')}</a></li>
              <li><a href="#faq" className="hover:text-foreground">{t('lp.nav_faq')}</a></li>
            </ul>
          </div>
          <div>
            <p className="font-semibold">{t('lp.foot_account')}</p>
            <ul className="mt-3 space-y-2 text-muted-foreground">
              <li><Link to="/login" className="hover:text-foreground">{t('lp.login')}</Link></li>
              <li><Link to="/signup" className="hover:text-foreground">{t('lp.signup')}</Link></li>
            </ul>
          </div>
        </div>
      </Container>
      <Container className="border-t border-border/70 py-6 text-sm text-muted-foreground">© {year} Blueseatra</Container>
    </footer>
  );
}

export default function Landing() {
  const { t } = useTranslation();
  const reduce = useReducedMotion();
  return (
    <div className="min-h-[100dvh] bg-background text-foreground">
      <a href="#contenu" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-primary focus:px-3 focus:py-2 focus:text-primary-foreground">
        {t('landing.skip')}
      </a>
      <Header t={t} />
      <main id="contenu">
        <Hero t={t} reduce={reduce} />
        <Proof t={t} />
        <Values t={t} reduce={reduce} />
        <Features t={t} reduce={reduce} />
        <Steps t={t} reduce={reduce} />
        <PriceControl t={t} reduce={reduce} />
        <Plans t={t} />
        <Faq t={t} />
        <Closing t={t} />
      </main>
      <Footer t={t} />
    </div>
  );
}
