import { RefreshCw, Save, Trash2 } from 'lucide-react';
import { EmptyState } from './EmptyState.jsx';
import { StatusBadge } from './StatusBadge.jsx';

function hashtagsToText(hashtags) {
  return Array.isArray(hashtags) ? hashtags.join(' ') : '';
}

function resolveMediaUrl(url) {
  if (!url) return '';
  if (/^https?:\/\//.test(url)) return url;
  return `/api${url}`;
}

export function Workspace({ selected, draft, slideDrafts, onDraftChange, onSlideDraftChange, onSaveCarrossel, onSaveSlide, onRenderSlide, onDelete, loading }) {
  if (!selected) {
    return <EmptyState title="Selecione ou crie um carrossel" description="A revisão de slides, legenda e metadados aparece aqui assim que houver um item ativo." />;
  }

  const updateDraft = (field, value) => onDraftChange({ ...draft, [field]: value });
  const slideOptions = Array.from({ length: 7 }, (_, index) => index + 1);

  return (
    <main className="flex min-h-0 flex-col gap-4 overflow-y-auto">
      <section className="panel rounded-md p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="mb-2 flex items-center gap-2">
              <StatusBadge status={selected.status} />
              <span className="text-xs text-ink/50">#{selected.id}</span>
            </div>
            <h2 className="text-lg font-semibold text-ink">{selected.titulo || draft.titulo || 'Carrossel sem título'}</h2>
            <p className="mt-1 text-sm text-ink/60">Revise os dados principais e salve antes de avançar no fluxo.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button className="secondary-button" onClick={onSaveCarrossel} disabled={loading}>
              <Save className="h-4 w-4" />
              Salvar conteúdo
            </button>
            <button className="danger-button" onClick={onDelete} disabled={loading}>
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
            <select className="input mt-1" value={draft.quantidade_slides || 1} onChange={(event) => updateDraft('quantidade_slides', Number(event.target.value))}>
              {slideOptions.map((value) => (
                <option key={value} value={value}>{value}</option>
              ))}
            </select>
          </label>
          <label>
            <span className="field-label">Hashtags</span>
            <input className="input mt-1" value={draft.hashtagsText ?? hashtagsToText(draft.hashtags)} onChange={(event) => updateDraft('hashtagsText', event.target.value)} placeholder="#conteudo #carrossel" />
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
            <p className="text-xs text-ink/55">Revise textos e observações antes de renderizar os previews.</p>
          </div>
        </div>
        {Boolean(selected.slides?.length) && (
          <p className="mb-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-700">
            Alterações de texto só aparecem no preview depois de salvar e renderizar novamente.
          </p>
        )}
        <div className="grid auto-cols-[minmax(360px,1fr)] grid-flow-col gap-3 overflow-x-auto pb-4 scroll-smooth snap-x snap-mandatory">
          {(selected.slides || []).map((slide) => {
            const draftSlide = slideDrafts[slide.id] || slide;
            const updateSlide = (field, value) => onSlideDraftChange(slide.id, { ...draftSlide, [field]: value });
            const renderMeta = slide.layout_config || {};
            const hasUnsavedTextChanges = Boolean(slide.imagem_url) && ['titulo', 'texto_principal', 'texto_secundario', 'observacao_visual'].some((field) => (draftSlide[field] || '') !== (slide[field] || ''));
            return (
              <article key={slide.id} className="min-w-[360px] snap-start rounded-md border border-line bg-white p-3">
                <div className="mb-3 flex items-center justify-between gap-2">
                  <span className="inline-flex h-7 min-w-7 items-center justify-center rounded-md bg-steel/10 px-2 text-xs font-semibold text-steel">{slide.numero_slide}</span>
                  <div className="flex gap-2">
                    <button className="secondary-button py-1.5" onClick={() => onSaveSlide(slide.id)} disabled={loading}>
                      <Save className="h-4 w-4" />
                      Salvar
                    </button>
                    <button className="secondary-button py-1.5" onClick={() => onRenderSlide(slide.id)} disabled={loading}>
                      <RefreshCw className="h-4 w-4" />
                      Regerar
                    </button>
                  </div>
                </div>
                {draftSlide.imagem_url && (
                  <figure className="mb-3 overflow-hidden rounded-md border border-line bg-stone-50">
                    <img className="aspect-[4/5] w-full object-cover" src={resolveMediaUrl(draftSlide.imagem_url)} alt={`Preview renderizado do slide ${slide.numero_slide}`} />
                    <figcaption className="border-t border-line px-3 py-2 text-xs text-ink/55">
                      Preview renderizado · {renderMeta.template || 'template'}{renderMeta.asset_id ? ` · asset #${renderMeta.asset_id}` : ''}{renderMeta.rendered_at ? ` · ${new Date(renderMeta.rendered_at).toLocaleString()}` : ''}
                    </figcaption>
                  </figure>
                )}
                {hasUnsavedTextChanges && (
                  <p className="mb-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-700">
                    Texto alterado após o último render. Renderize novamente para atualizar o preview.
                  </p>
                )}
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
        {!selected.slides?.length && (
          <div className="rounded-md border border-dashed border-moss/40 bg-moss/10 p-4">
            <EmptyState title="Sem slides gerados" description="Use Gerar no painel de ações para criar a estrutura do carrossel." />
          </div>
        )}
      </section>
    </main>
  );
}
