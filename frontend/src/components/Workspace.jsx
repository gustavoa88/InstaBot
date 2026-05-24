import { Save, Trash2 } from 'lucide-react';
import { EmptyState } from './EmptyState.jsx';
import { StatusBadge } from './StatusBadge.jsx';

function hashtagsToText(hashtags) {
  return Array.isArray(hashtags) ? hashtags.join(' ') : '';
}

export function Workspace({ selected, draft, slideDrafts, onDraftChange, onSlideDraftChange, onSaveCarrossel, onSaveSlide, onDelete, loading }) {
  if (!selected) {
    return <EmptyState title="Selecione ou crie um carrossel" description="A revisão de slides, legenda e metadados aparece aqui assim que houver um item ativo." />;
  }

  const updateDraft = (field, value) => onDraftChange({ ...draft, [field]: value });

  return (
    <main className="flex min-h-0 flex-col gap-4 overflow-y-auto">
      <section className="panel rounded-md p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="mb-2 flex items-center gap-2">
              <StatusBadge status={selected.status} />
              <span className="text-xs text-ink/50">#{selected.id}</span>
            </div>
            <h2 className="text-lg font-semibold text-ink">{selected.titulo || 'Carrossel sem título'}</h2>
            <p className="mt-1 text-sm text-ink/60">{selected.slides?.length || 0} slides cadastrados</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button className="secondary-button" onClick={onSaveCarrossel} disabled={loading}>
              <Save className="h-4 w-4" />
              Salvar conteúdo
            </button>
            <button className="danger-button" onClick={onDelete} disabled={loading || selected.status === 'PUBLICADO'}>
              <Trash2 className="h-4 w-4" />
              Remover
            </button>
          </div>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <label>
            <span className="field-label">Título</span>
            <input className="input mt-1" value={draft.titulo || ''} onChange={(event) => updateDraft('titulo', event.target.value)} />
          </label>
          <label>
            <span className="field-label">Tema</span>
            <input className="input mt-1" value={draft.tema || ''} onChange={(event) => updateDraft('tema', event.target.value)} />
          </label>
          <label>
            <span className="field-label">Tom</span>
            <input className="input mt-1" value={draft.tom || ''} onChange={(event) => updateDraft('tom', event.target.value)} />
          </label>
          <label>
            <span className="field-label">Público-alvo</span>
            <input className="input mt-1" value={draft.publico_alvo || ''} onChange={(event) => updateDraft('publico_alvo', event.target.value)} />
          </label>
          <label>
            <span className="field-label">Quantidade de slides</span>
            <input className="input mt-1" type="number" min="1" max="20" value={draft.quantidade_slides || 1} onChange={(event) => updateDraft('quantidade_slides', event.target.value)} />
          </label>
          <label>
            <span className="field-label">Hashtags</span>
            <input className="input mt-1" value={draft.hashtagsText ?? hashtagsToText(draft.hashtags)} onChange={(event) => updateDraft('hashtagsText', event.target.value)} placeholder="#conteudo #instagram" />
          </label>
        </div>
        <div className="mt-3 grid gap-3 lg:grid-cols-2">
          <label>
            <span className="field-label">Ideia original</span>
            <textarea className="textarea mt-1" value={draft.ideia_original || ''} onChange={(event) => updateDraft('ideia_original', event.target.value)} />
          </label>
          <label>
            <span className="field-label">Legenda</span>
            <textarea className="textarea mt-1" value={draft.legenda || ''} onChange={(event) => updateDraft('legenda', event.target.value)} />
          </label>
        </div>
      </section>

      <section className="panel rounded-md p-4">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-ink">Slides</h2>
            <p className="text-xs text-ink/55">Edite textos e observações visuais geradas pelo mock</p>
          </div>
        </div>
        <div className="grid gap-3 xl:grid-cols-2">
          {(selected.slides || []).map((slide) => {
            const draftSlide = slideDrafts[slide.id] || slide;
            const updateSlide = (field, value) => onSlideDraftChange(slide.id, { ...draftSlide, [field]: value });
            return (
              <article key={slide.id} className="rounded-md border border-line bg-white p-3">
                <div className="mb-3 flex items-center justify-between gap-2">
                  <span className="inline-flex h-7 min-w-7 items-center justify-center rounded-md bg-steel/10 px-2 text-xs font-semibold text-steel">{slide.numero_slide}</span>
                  <button className="secondary-button py-1.5" onClick={() => onSaveSlide(slide.id)} disabled={loading}>
                    <Save className="h-4 w-4" />
                    Salvar
                  </button>
                </div>
                <label className="block">
                  <span className="field-label">Título do slide</span>
                  <input className="input mt-1" value={draftSlide.titulo || ''} onChange={(event) => updateSlide('titulo', event.target.value)} />
                </label>
                <label className="mt-3 block">
                  <span className="field-label">Texto principal</span>
                  <textarea className="textarea mt-1" value={draftSlide.texto_principal || ''} onChange={(event) => updateSlide('texto_principal', event.target.value)} />
                </label>
                <label className="mt-3 block">
                  <span className="field-label">Texto secundário</span>
                  <input className="input mt-1" value={draftSlide.texto_secundario || ''} onChange={(event) => updateSlide('texto_secundario', event.target.value)} />
                </label>
                <label className="mt-3 block">
                  <span className="field-label">Observação visual</span>
                  <textarea className="textarea mt-1 min-h-16" value={draftSlide.observacao_visual || ''} onChange={(event) => updateSlide('observacao_visual', event.target.value)} />
                </label>
              </article>
            );
          })}
        </div>
        {!selected.slides?.length && <EmptyState title="Sem slides gerados" description="Use Gerar no painel de ações para criar a estrutura mockada do carrossel." />}
      </section>
    </main>
  );
}
