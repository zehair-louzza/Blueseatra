import React from 'react';

export default function TceReview({ meta, isDraft, checked, onChange }) {
  if (!meta?.tce_version) return null;
  const candidates = meta.tce_nomenclature || [];
  const issues = [...(meta.tce_issues || []), ...(meta.reserves || [])];
  return (
    <section className="rounded-lg border border-border bg-muted/30 p-4 space-y-3" aria-labelledby="tce-review-title" data-testid="tce-review">
      <h2 id="tce-review-title" className="font-semibold text-sm">Contrôle technique TCE</h2>
      <p className="text-xs text-muted-foreground">
        Ces éléments sont des points à vérifier, pas des achats ajoutés automatiquement.
        Confirmez le périmètre, les métrés et le contenu des kits avant validation.
      </p>
      {issues.length > 0 && (
        <ul className="list-disc pl-4 space-y-1 text-xs">
          {[...new Set(issues)].map((issue, i) => <li key={i}>{issue}</li>)}
        </ul>
      )}
      {candidates.length > 0 && (
        <details>
          <summary className="cursor-pointer text-sm font-medium">
            {candidates.length} {candidates.length > 1 ? 'points de contrôle internes' : 'point de contrôle interne'}
          </summary>
          <ul className="mt-3 space-y-3 max-h-80 overflow-y-auto text-xs" tabIndex={0} aria-label="Nomenclature candidate">
            {candidates.map((row, i) => (
              <li key={row.id || i}>
                <div className="font-medium">Lot {row.lot} : {row.designation}</div>
                <p className="text-muted-foreground mt-1">{row.details}</p>
              </li>
            ))}
          </ul>
        </details>
      )}
      {meta.exclusions && <p className="text-xs">Hors périmètre : {meta.exclusions}</p>}
      {isDraft && (
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-1" checked={checked} onChange={(e) => onChange(e.target.checked)} data-testid="tce-review-checkbox" />
          <span>J’ai vérifié le périmètre, les quantités, les kits, les accessoires et les réserves.</span>
        </label>
      )}
    </section>
  );
}
