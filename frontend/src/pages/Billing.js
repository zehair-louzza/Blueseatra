import React from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { CreditCard, Sparkles } from 'lucide-react';

export default function Billing() {
  const { t } = useTranslation();
  const { tenant } = useAuth();
  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="font-display text-2xl font-semibold tracking-tight">{t('billing.title')}</h1>
      <Card className="card-shadow mt-5 border-0 p-6">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-accent/10 text-accent"><CreditCard className="h-5 w-5" /></div>
          <div>
            <div className="text-xs uppercase text-muted-foreground">{t('billing.current_plan')}</div>
            <div className="font-display text-lg font-semibold capitalize">Starter</div>
          </div>
        </div>
        <div className="mt-5 flex items-start gap-2 rounded-lg bg-muted/50 p-4 text-sm text-muted-foreground">
          <Sparkles className="mt-0.5 h-4 w-4 text-accent" />
          <span>{t('billing.soon')}</span>
        </div>
        <Button className="mt-5" variant="secondary" disabled data-testid="manage-subscription-button">{t('billing.manage')}</Button>
      </Card>
    </div>
  );
}
