import { FileText } from 'lucide-react';

export function EmptyState({ title, description }) {
  return (
    <div className="flex min-h-48 flex-col items-center justify-center rounded-md border border-dashed border-line bg-white px-5 py-8 text-center">
      <FileText className="mb-3 h-8 w-8 text-ink/35" />
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      <p className="mt-1 max-w-sm text-sm text-ink/60">{description}</p>
    </div>
  );
}
