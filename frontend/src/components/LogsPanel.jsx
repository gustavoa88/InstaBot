import { Activity } from 'lucide-react';

function formatDate(value) {
  if (!value) return '-';
  return new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
}

export function LogsPanel({ logs, selectedId }) {
  const visibleLogs = selectedId
    ? logs.filter((log) => log.carrossel_id === selectedId || log.carrossel_id === null)
    : logs;

  return (
    <section className="panel rounded-md p-4">
      <div className="flex items-center gap-2">
        <Activity className="h-4 w-4 text-steel" />
        <h2 className="text-sm font-semibold text-ink">Logs</h2>
      </div>
      <div className="mt-3 max-h-64 overflow-y-auto pr-1">
        {visibleLogs.slice(0, 20).map((log) => (
          <div key={log.id} className="border-b border-line py-2 last:border-0">
            <div className="flex items-start justify-between gap-2">
              <p className="text-xs font-semibold text-ink">{log.etapa || 'evento'} · {log.status || 'INFO'}</p>
              <span className="shrink-0 text-[11px] text-ink/45">{formatDate(log.created_at)}</span>
            </div>
            <p className="mt-1 text-xs leading-5 text-ink/60">{log.mensagem}</p>
          </div>
        ))}
        {!visibleLogs.length && <p className="text-sm text-ink/55">Nenhum log disponível.</p>}
      </div>
    </section>
  );
}
