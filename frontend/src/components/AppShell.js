import React, { useState } from 'react';
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
  Settings as SettingsIcon, CreditCard, Menu, LogOut, ChevronDown, Building2,
} from 'lucide-react';
import { BrandLogo } from '@/components/BrandLogo';
import { cn } from '@/lib/utils';

const navItems = [
  { to: '/app', key: 'dashboard', icon: LayoutDashboard, end: true },
  { to: '/app/requests', key: 'requests', icon: Inbox },
  { to: '/app/catalogs', key: 'catalogs', icon: BookOpen },
  { to: '/app/quotes', key: 'quotes', icon: FileText },
  { to: '/app/members', key: 'members', icon: Users },
  { to: '/app/audit', key: 'audit', icon: ScrollText },
  { to: '/app/settings', key: 'settings', icon: SettingsIcon },
  { to: '/app/billing', key: 'billing', icon: CreditCard },
];

const NavList = ({ onNavigate }) => {
  const { t } = useTranslation();
  return (
    <nav className="flex flex-col gap-1 p-3">
      {navItems.map((item) => (
        <NavLink key={item.key} to={item.to} end={item.end} onClick={onNavigate}
          data-testid={`nav-${item.key}`}
          className={({ isActive }) => cn(
            'flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            isActive ? 'bg-muted font-medium text-foreground' : 'text-muted-foreground')}>
          <item.icon className="h-4 w-4" />
          {t(`nav2.${item.key}`)}
        </NavLink>
      ))}
    </nav>
  );
};

const Brand = () => (
  <div className="px-2">
    <BrandLogo to="/app" />
  </div>
);

export const AppShell = ({ children }) => {
  const { t } = useTranslation();
  const { user, tenant, tenants, logout, switchTenant } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 flex h-14 items-center justify-between gap-3 border-b bg-background/80 px-3 backdrop-blur sm:px-4">
        <div className="flex items-center gap-2">
          <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="lg:hidden" data-testid="mobile-menu-button" aria-label="Menu">
                <Menu className="h-5 w-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-72 p-0">
              <div className="flex h-14 items-center border-b px-3"><Brand /></div>
              <NavList onNavigate={() => setMobileOpen(false)} />
            </SheetContent>
          </Sheet>
          <div className="hidden lg:block"><Brand /></div>
          {tenant && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" className="ml-2 gap-1.5" data-testid="tenant-switcher">
                  <Building2 className="h-3.5 w-3.5" />
                  <span className="max-w-[140px] truncate">{tenant.name}</span>
                  <ChevronDown className="h-3.5 w-3.5 opacity-60" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-56">
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
          )}
        </div>
        <div className="flex items-center gap-2">
          <LanguageToggle />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="gap-1.5" data-testid="user-menu">
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-accent text-xs font-semibold text-accent-foreground">
                  {(user?.name || user?.email || '?').slice(0, 1).toUpperCase()}
                </span>
                <span className="hidden max-w-[120px] truncate text-sm sm:inline">{user?.name || user?.email}</span>
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
      <div className="flex">
        <aside className="hidden w-64 shrink-0 border-r lg:block" style={{ minHeight: 'calc(100vh - 3.5rem)' }}>
          <NavList />
        </aside>
        <main className="w-full px-3 py-6 sm:px-4 lg:px-6">{children}</main>
      </div>
    </div>
  );
};
