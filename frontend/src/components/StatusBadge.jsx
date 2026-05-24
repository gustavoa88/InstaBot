const STATUS_STYLES = {
  RASCUNHO: 'bg-stone-100 text-stone-700 border-stone-200',
  GERANDO: 'bg-sky-100 text-sky-800 border-sky-200',
  AGUARDANDO_APROVACAO: 'bg-amber-100 text-amber-800 border-amber-200',
  APROVADO: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  REJEITADO: 'bg-rose-100 text-rose-800 border-rose-200',
  AGENDADO: 'bg-blue-100 text-blue-800 border-blue-200',
  CANCELADO: 'bg-zinc-100 text-zinc-700 border-zinc-200',
  PUBLICADO: 'bg-moss/10 text-moss border-moss/20',
  ERRO_PUBLICACAO: 'bg-coral/10 text-coral border-coral/20',
};

export function StatusBadge({ status }) {
  const style = STATUS_STYLES[status] || 'bg-stone-100 text-stone-700 border-stone-200';
  return (
    <span className={`inline-flex max-w-full items-center rounded-md border px-2 py-1 text-[11px] font-semibold ${style}`}>
      {status || 'SEM_STATUS'}
    </span>
  );
}
