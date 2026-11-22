import React from 'react';
import { ShieldAlert, Inbox, Database, ArrowRight } from 'lucide-react';
import { Button } from './Button';

interface EmptyStateProps {
  title: string;
  description: string;
  icon?: React.ReactNode;
  actionText?: string;
  onAction?: () => void;
  isDatasetRestricted?: boolean;
  blockedDatasetName?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  icon,
  actionText,
  onAction,
  isDatasetRestricted = false,
  blockedDatasetName,
}) => {
  if (isDatasetRestricted) {
    return (
      <div className="rounded-2xl border border-dashed border-amber-300 bg-amber-50/40 p-8 text-center max-w-xl mx-auto my-6">
        <div className="w-12 h-12 rounded-2xl bg-amber-100 text-amber-700 flex items-center justify-center mx-auto mb-4 border border-amber-200">
          <ShieldAlert className="w-6 h-6" />
        </div>
        <div className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-200 mb-2">
          Dataset Restricted (Phase 5/6 Gate)
        </div>
        <h4 className="text-base font-semibold text-slate-900 mb-1">{title}</h4>
        <p className="text-xs text-slate-600 max-w-md mx-auto mb-3 leading-relaxed">
          {description}
        </p>
        {blockedDatasetName && (
          <div className="text-[11px] font-mono text-amber-900 bg-amber-100/70 py-1.5 px-3 rounded-lg inline-block border border-amber-200/80 mb-4">
            Blocked Dataset: {blockedDatasetName}
          </div>
        )}
        <div className="text-[11px] text-slate-500 italic block">
          In strict compliance with audit protocols, no synthetic or fabricated records are generated.
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/50 p-10 text-center max-w-md mx-auto my-6">
      <div className="w-12 h-12 rounded-2xl bg-white text-slate-400 flex items-center justify-center mx-auto mb-3 shadow-xs border border-slate-200">
        {icon || <Inbox className="w-6 h-6" />}
      </div>
      <h4 className="text-sm font-semibold text-slate-800 mb-1">{title}</h4>
      <p className="text-xs text-slate-500 mb-4 leading-relaxed">{description}</p>
      {actionText && onAction && (
        <Button size="sm" variant="outline" onClick={onAction} rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
          {actionText}
        </Button>
      )}
    </div>
  );
};
