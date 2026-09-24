import React, { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { NavLink, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/context/AuthContext';
import { LanguageToggle } from '@/components/LanguageToggle';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  LayoutDashboard, Inbox, BookOpen, FileText, Users, ScrollText,
  Settings as SettingsIcon, CreditCard, Menu, LogOut, ChevronDown, Store, Library, Building2, BellRing,
} from 'lucide-react';
import { BrandLogo } from '@/components/BrandLogo';
import { cn } from '@/lib/utils';

// Menu groupe par usage : ventes, achats, entreprise.
const navGroups = [
  { key: null, items: [
    { to: '/app', key: 'dashboard', icon: LayoutDashboard, end: true },
  ] },
  { key: 'sales', items: [
    { to: '/app/requests', key: 'requests', icon: Inbox },
    { to: '/app/quotes', key: 'quotes', icon: FileText },
  ] },
  { key: 'clients', items: [
    { to: '/app/clients', key: 'clients', icon: Building2 },
    { to: '/app/relances', key: 'relances', icon: BellRing, badge: true },
  ] },
  { key: 'purchases', items: [
    { to: '/app/catalogs', key: 'catalogs', icon: BookOpen },
    { to: '/app/fournisseurs/catalogue', key: 'supplierCatalog', icon: Library },
    { to: '/app/fournisseurs', key: 'suppliers', icon: Store, end: true },
  ] },
  { key: 'company', items: [
    { to: '/app/members', key: 'members', icon: Users },
    { to: '/app/audit', key: 'audit', icon: ScrollText },
    { to: '/app/settings', key: 'settings', icon: SettingsIcon },
    { to: '/app/billing', key: 'billing', icon: CreditCard },
  ] },
];

const GROUP_LABELS = {
  fr: { sales: 'Ventes', clients: 'Clients', purchases: 'Achats et prix', company: 'Entreprise' },
  en: { sales: 'Sales', clients: 'Clients', purchases: 'Purchasing', company: 'Company' },
};

const NavList = ({ onNavigate }) => {
  const { t, i18n } = useTranslation();
  const labels = GROUP_LABELS[i18n.language?.startsWith('en') ? 'en' : 'fr'];
  const [aRelancer, setARelancer] = useState(0);
  useEffect(() => {
    api.get('/relances', { params: { periode: 'aujourdhui' } })
      .then((r) => setARelancer(r.data?.compte?.aujourdhui + r.data?.compte?.retard || 0)).catch(() => {});
  }, []);
  return (
    <nav className="flex flex-col gap-5 px-3 py-4">
      {navGroups.map((g) => (
        <div key={g.key || 'root'}>
          {g.key && (
            <p className="mb-1.5 px-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground/80">{labels[g.key]}</p>
          )}
          <div className="flex flex-col gap-0.5">
            {g.items.map((item) => (
              <NavLink key={item.key} to={item.to} end={item.end} onClick={onNavigate}
                data-testid={`nav-${item.key}`}
                className={({ isActive }) => cn(
                  'group relative flex items-center gap-2.5 rounded-lg px-3 py-2 text-[14px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  isActive
                    ? 'bg-primary/[0.07] font-medium text-primary before:absolute before:left-0 before:top-1.5 before:h-[calc(100%-12px)] before:w-[3px] before:rounded-full before:bg-[hsl(var(--brand-teal))]'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground')}>
                <item.icon className="h-[17px] w-[17px] shrink-0" />
                {t(`nav2.${item.key}`)}
                {item.badge && aRelancer > 0 && (
                  <span className="ml-auto rounded-full bg-primary px-1.5 py-0.5 text-[11px] font-semibold leading-none text-primary-foreground" aria-label={`${aRelancer}`}>{aRelancer}</span>
                )}
              </NavLink>
            ))}
          </div>
        </div>
      ))}
    </nav>
  );
};

const Brand = () => (
  <div className="px-2">
    <BrandLogo to="/app" imgClassName="h-9 max-w-[170px]" />
  </div>
);

export const AppShell = ({ children }) => {
  const { t } = useTranslation();
  const { user, tenant, tenants, logout, switchTenant } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const navigate = useNavigate();

  const tenantSwitcher = tenant && (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className="h-9 w-full justify-between gap-1.5 px-3" data-testid="tenant-switcher">
          <span className="flex min-w-0 items-center gap-2">
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-primary text-[10px] font-semibold text-primary-foreground">
              {(tenant.name || '?').slice(0, 1).toUpperCase()}
            </span>
            <span className="truncate text-[13px]">{tenant.name}</span>
          </span>
          <ChevronDown className="h-3.5 w-3.5 shrink-0 opacity-60" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-60">
        <DropdownMenuLabel>Workspaces</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {tenants.map((tn) => (
          <DropdownMenuItem key={tn.id} onClick={() => switchTenant(tn.id)}
            data-testid={`tenant-option-${tn.id}`} className="flex items-center justify-between">
            <span className="truncate">{tn.name}</span>
            <span className="ml-2 text-[10px] uppercase text-muted-foreground">{tn.role}</span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );

  const sidebar = (onNavigate) => (
    <div className="flex h-full flex-col">
      <div className="flex h-16 items-center px-5"><Brand /></div>
      <div className="px-3 pb-1">{tenantSwitcher}</div>
      <div className="flex-1 overflow-y-auto"><NavList onNavigate={onNavigate} /></div>
      <div className="border-t border-border/70 p-3 text-[11px] text-muted-foreground">
        <span className="px-3">Blueseatra</span>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-background">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-border/70 bg-card lg:block">
        {sidebar()}
      </aside>
      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between gap-3 border-b border-border/70 bg-background/85 px-4 backdrop-blur-md sm:px-6">
          <div className="flex items-center gap-2">
            <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="lg:hidden" data-testid="mobile-menu-button" aria-label="Menu">
                  <Menu className="h-5 w-5" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-72 p-0">
                {sidebar(() => setMobileOpen(false))}
              </SheetContent>
            </Sheet>
            <div className="lg:hidden"><BrandLogo variant="mark" to="/app" imgClassName="h-8 w-8" /></div>
          </div>
          <div className="flex items-center gap-2">
            <LanguageToggle />
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm" className="h-9 gap-2 pl-1.5 pr-2.5" data-testid="user-menu">
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
                    {(user?.name || user?.email || '?').slice(0, 1).toUpperCase()}
                  </span>
                  <span className="hidden max-w-[140px] truncate text-sm sm:inline">{user?.name || user?.email}</span>
                  <ChevronDown className="h-3.5 w-3.5 opacity-60" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel className="truncate">{user?.email}</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => navigate('/app/settings')}>
                  <SettingsIcon className="mr-2 h-4 w-4" />{t('nav2.settings')}
                </DropdownMenuItem>
                <DropdownMenuItem onClick={logout} data-testid="logout-button" className="text-destructive">
                  <LogOut className="mr-2 h-4 w-4" />{t('nav2.logout')}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1400px] px-4 py-8 sm:px-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
};
