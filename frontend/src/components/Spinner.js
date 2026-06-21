import React from 'react';
import { Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

export const Spinner = ({ label }) => {
  const { t } = useTranslation();
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-muted-foreground" data-testid="spinner">
      <Loader2 className="h-5 w-5 animate-spin" />
      <span className="text-sm">{label || t('common.loading')}</span>
    </div>
  );
};

export const EmptyState = ({ icon: Icon, title, action }) => (
  <div className="flex flex-col items-center justify-center rounded-xl border border-dashed bg-card py-16 text-center" data-testid="empty-state">
    {Icon && <Icon className="mb-3 h-8 w-8 text-muted-foreground" />}
    <p className="text-sm text-muted-foreground">{title}</p>
    {action && <div className="mt-4">{action}</div>}
  </div>
);
