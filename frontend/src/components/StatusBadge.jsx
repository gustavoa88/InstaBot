const STATUS_STYLES = {
  RASCUNHO: 'bg-stone-100 text-stone-700 border-stone-200',
  IDEIA_SALVA: 'bg-slate-100 text-slate-700 border-slate-200',
  GERANDO: 'bg-sky-100 text-sky-800 border-sky-200',
  GERANDO_ESTRUTURA: 'bg-sky-100 text-sky-800 border-sky-200',
  DESENVOLVENDO_VISUAL: 'bg-violet-100 text-violet-800 border-violet-200',
  RENDERIZANDO_SLIDES: 'bg-indigo-100 text-indigo-800 border-indigo-200',
  AGUARDANDO_DOWNLOAD: 'bg-amber-100 text-amber-800 border-amber-200',
  FEITO_DOWNLOAD: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  ERRO: 'bg-rose-100 text-rose-800 border-rose-200',
  AGUARDANDO_APROVACAO: 'bg-amber-100 text-amber-800 border-amber-200',
  APROVADO: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  REJEITADO: 'bg-rose-100 text-rose-800 border-rose-200',
  AGENDADO: 'bg-blue-100 text-blue-800 border-blue-200',
  CANCELADO: 'bg-zinc-100 text-zinc-700 border-zinc-200',
  PUBLICADO: 'bg-moss/10 text-moss border-moss/20',
  ERRO_PUBLICACAO: 'bg-coral/10 text-coral border-coral/20',
};

const STATUS_LABELS = {
  RASCUNHO: 'Rascunho',
  IDEIA_SALVA: 'Ideia salva',
  GERANDO: 'Gerando',
  GERANDO_ESTRUTURA: 'Gerando estrutura',
  DESENVOLVENDO_VISUAL: 'Desenvolvendo visual',
  RENDERIZANDO_SLIDES: 'Renderizando slides',
  AGUARDANDO_DOWNLOAD: 'Aguardando download',
  FEITO_DOWNLOAD: 'Feito download',
  ERRO: 'Erro',
  AGUARDANDO_APROVACAO: 'Aguardando aprovação',
  APROVADO: 'Aprovado',
  REJEITADO: 'Rejeitado',
  AGENDADO: 'Agendado',
  CANCELADO: 'Cancelado',
  PUBLICADO: 'Publicado',
  ERRO_PUBLICACAO: 'Erro na publicação',
};

function humanizeStatus(status) {
  if (!status) return 'SEM_STATUS';
  return STATUS_LABELS[status] || status.split('_').map((word) => word[0] + word.slice(1).toLowerCase()).join(' ');
}

export function StatusBadge({ status }) {
  const style = STATUS_STYLES[status] || 'bg-stone-100 text-stone-700 border-stone-200';
  return (
    <span className={`inline-flex max-w-full items-center rounded-md border px-2 py-1 text-[11px] font-semibold ${style}`}>
      {humanizeStatus(status)}
    </span>
  );
}
