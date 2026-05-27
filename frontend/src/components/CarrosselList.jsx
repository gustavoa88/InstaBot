import { RefreshCw, Search } from 'lucide-react';
import { StatusBadge } from './StatusBadge.jsx';

const STATUS_LABELS = {
  IDEIA_SALVA: 'Ideia salva',
  GERANDO_ESTRUTURA: 'Gerando estrutura',
  DESENVOLVENDO_VISUAL: 'Desenvolvendo visual',
  RENDERIZANDO_SLIDES: 'Renderizando slides',
  AGUARDANDO_DOWNLOAD: 'Aguardando download',
  FEITO_DOWNLOAD: 'Feito download',
};

const STATUSES = [
  'TODOS',
  ...Object.keys(STATUS_LABELS),
];

export function CarrosselList({ carrosseis, selectedId, statusFilter, search, onStatusFilter, onSearch, onSelect, onRefresh, loading }) {
  const filtered = carrosseis.filter((item) => {
    const matchesStatus = statusFilter === 'TODOS' || item.status === statusFilter;
    const needle = search.trim().toLowerCase();
    const matchesSearch = !needle || [item.titulo, item.ideia_original, item.tema, item.publico_alvo]
      .filter(Boolean)
      .some((value) => value.toLowerCase().includes(needle));
    return matchesStatus && matchesSearch;
  });

  return (
    <aside className="panel flex min-h-0 flex-col rounded-md">
      <div className="border-b border-line p-4">
        <div className="flex items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold text-ink">Carrosséis</h2>
            <p className="text-xs text-ink/55">{filtered.length} de {carrosseis.length}</p>
          </div>
          <button className="icon-button" onClick={onRefresh} disabled={loading} title="Atualizar lista">
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
        <label className="mt-4 block">
          <span className="field-label">Busca</span>
          <span className="relative mt-1 block">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-ink/35" />
            <input className="input pl-9" value={search} onChange={(event) => onSearch(event.target.value)} placeholder="Título, tema, público" />
          </span>
        </label>
        <label className="mt-3 block">
          <span className="field-label">Status</span>
          <select className="input mt-1" value={statusFilter} onChange={(event) => onStatusFilter(event.target.value)}>
            {STATUSES.map((status) => (
              <option key={status} value={status}>
                {status === 'TODOS' ? 'Todos' : STATUS_LABELS[status] || status}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {filtered.map((item) => (
          <button
            key={item.id}
            onClick={() => onSelect(item.id)}
            className={`mb-2 block w-full rounded-md border p-3 text-left transition ${selectedId === item.id ? 'border-moss bg-moss/5' : 'border-line bg-white hover:border-moss/50'}`}
          >
            <div className="flex items-start justify-between gap-2">
              <h3 className="line-clamp-2 text-sm font-semibold text-ink">{item.titulo || `Carrossel #${item.id}`}</h3>
              <span className="shrink-0 text-xs text-ink/45">#{item.id}</span>
            </div>
            <p className="mt-2 line-clamp-2 text-xs leading-5 text-ink/60">{item.ideia_original}</p>
            <div className="mt-3 flex items-center justify-between gap-2">
              <StatusBadge status={item.status} />
              <span className="text-xs text-ink/50">{item.slides?.length || 0} slides</span>
            </div>
          </button>
        ))}
        {!filtered.length && <p className="px-2 py-6 text-center text-sm text-ink/55">Nenhum carrossel encontrado.</p>}
      </div>
    </aside>
  );
}
