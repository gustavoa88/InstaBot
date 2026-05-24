import { Plus } from 'lucide-react';

export function CreateCarrosselForm({ form, onChange, onSubmit, loading }) {
  const update = (field, value) => onChange({ ...form, [field]: value });

  return (
    <form onSubmit={onSubmit} className="panel rounded-md p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-ink">Nova ideia</h2>
          <p className="text-xs text-ink/55">Cadastro inicial para geração mockada</p>
        </div>
        <button className="primary-button" disabled={loading || !form.ideia_original.trim()}>
          <Plus className="h-4 w-4" />
          Criar
        </button>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <label>
          <span className="field-label">Título</span>
          <input className="input mt-1" value={form.titulo} onChange={(event) => update('titulo', event.target.value)} placeholder="Ex: 7 hábitos para criar conteúdo" />
        </label>
        <label>
          <span className="field-label">Tema</span>
          <input className="input mt-1" value={form.tema} onChange={(event) => update('tema', event.target.value)} placeholder="Automação, vendas, marca pessoal" />
        </label>
        <label>
          <span className="field-label">Tom</span>
          <input className="input mt-1" value={form.tom} onChange={(event) => update('tom', event.target.value)} placeholder="Prático, inspirador, técnico" />
        </label>
        <label>
          <span className="field-label">Público-alvo</span>
          <input className="input mt-1" value={form.publico_alvo} onChange={(event) => update('publico_alvo', event.target.value)} placeholder="Criadores independentes" />
        </label>
        <label>
          <span className="field-label">Slides</span>
          <input className="input mt-1" type="number" min="1" max="20" value={form.quantidade_slides} onChange={(event) => update('quantidade_slides', event.target.value)} />
        </label>
        <label>
          <span className="field-label">Observações</span>
          <input className="input mt-1" value={form.observacoes_adicionais} onChange={(event) => update('observacoes_adicionais', event.target.value)} placeholder="Preferências, referências, restrições" />
        </label>
      </div>
      <label className="mt-3 block">
        <span className="field-label">Ideia original</span>
        <textarea className="textarea mt-1" value={form.ideia_original} onChange={(event) => update('ideia_original', event.target.value)} placeholder="Descreva a ideia que deve virar carrossel" />
      </label>
    </form>
  );
}
