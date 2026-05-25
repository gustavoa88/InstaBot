import { Plus } from 'lucide-react';

export function CreateCarrosselForm({ form, onChange, onSubmit, loading }) {
  const update = (field, value) => onChange({ ...form, [field]: value });

  return (
    <form onSubmit={onSubmit} className="panel rounded-md p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-ink">1. Criar ideia</h2>
          <p className="text-xs text-ink/55">Descreva a base do carrossel. Depois, gere os slides no painel de ações.</p>
        </div>
        <button className="primary-button" disabled={loading || !form.ideia_original.trim()}>
          <Plus className="h-4 w-4" />
          Criar ideia
        </button>
      </div>
      <label className="mt-4 block">
        <span className="field-label">Ideia original</span>
        <textarea className="textarea mt-1" value={form.ideia_original} onChange={(event) => update('ideia_original', event.target.value)} placeholder="Descreva a ideia central antes de gerar os slides" />
      </label>
      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        <label>
          <span className="field-label">Slides</span>
          <input className="input mt-1" type="number" min="1" max="20" value={form.quantidade_slides} onChange={(event) => update('quantidade_slides', event.target.value)} />
        </label>
        <label>
          <span className="field-label">Tom</span>
          <input className="input mt-1" value={form.tom} onChange={(event) => update('tom', event.target.value)} placeholder="Prático, inspirador, técnico" />
        </label>
        <label>
          <span className="field-label">Observações</span>
          <input className="input mt-1" value={form.observacoes_adicionais} onChange={(event) => update('observacoes_adicionais', event.target.value)} placeholder="Preferências, referências, restrições" />
        </label>
      </div>
    </form>
  );
}
