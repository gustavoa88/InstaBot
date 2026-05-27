import { Download, Image, ImagePlus, Play, RefreshCw, Trash2 } from 'lucide-react';
import { api } from '../services/api.js';

function resolveMediaUrl(url) {
  if (!url) return '';
  if (/^https?:\/\//.test(url)) return url;
  return `/api${url}`;
}

const TEMPLATE_OPTIONS = [
  { value: 'clean_editorial', label: 'Clean editorial' },
  { value: 'bold_contrast', label: 'Bold contrast' },
  { value: 'soft_brand', label: 'Soft brand' },
];

const ASPECT_RATIO_OPTIONS = [
  { value: '1:1', label: 'Quadrado 1:1' },
  { value: '1.91:1', label: 'Horizontal 1,91:1' },
  { value: '4:5', label: 'Vertical 4:5' },
];

export function ActionPanel({
  selected,
  renderForm,
  onRenderForm,
  onGenerate,
  onRegenerate,
  onRenderSlides,
  onGenerateAsset,
  onDeleteAsset,
  loading,
}) {
  if (!selected) {
    return (
      <aside className="panel rounded-md p-4">
        <h2 className="text-sm font-semibold text-ink">Ações</h2>
        <p className="mt-2 text-sm text-ink/60">Selecione um carrossel para operar o fluxo.</p>
      </aside>
    );
  }

  const activeAsset = [...(selected.assets || [])].filter((asset) => asset.status === 'ATIVO' && asset.tipo === 'background').sort((a, b) => b.id - a.id)[0];
  const canGenerate = !selected.slides?.length;
  const canRender = Boolean(selected.slides?.length);
  const canDownload = Boolean(selected.slides?.some((slide) => slide.imagem_url));
  const normalizedColor = /^#[0-9A-Fa-f]{6}$/.test(renderForm.primary_color) ? renderForm.primary_color : '#6f9684';
  const paletteColors = (activeAsset?.provider_response?.palette?.colors || []).filter((color) => /^#[0-9A-Fa-f]{6}$/.test(color));

  const downloadSlides = async () => {
    try {
      const response = await api.downloadCarousel(selected.id);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'carousel_' + selected.id + '.zip';
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      window.alert(error?.message || 'Não foi possível baixar os slides.');
    }
  };

  return (
    <aside className="panel rounded-md p-4">
      <h2 className="text-sm font-semibold text-ink">Fluxo do carrossel</h2>
      <p className="mt-1 text-xs leading-5 text-ink/55">Siga as etapas em ordem: gere a estrutura, revise e renderize os slides.</p>

      <section className="mt-4 rounded-md border border-line bg-white p-3">
        <h3 className="text-sm font-semibold text-ink">1. Gerar estrutura</h3>
        <p className="mt-1 text-xs text-ink/55">Crie os slides a partir da ideia antes de revisar o texto.</p>
        <div className="mt-3 grid gap-2">
          <button className="secondary-button justify-start" onClick={onGenerate} disabled={loading || !canGenerate}>
            <Play className="h-4 w-4" />
            Gerar slides
          </button>
          <button className="secondary-button justify-start" onClick={onRegenerate} disabled={loading || canGenerate}>
            <RefreshCw className="h-4 w-4" />
            Regenerar slides
          </button>
        </div>
      </section>

      <section className="mt-4 rounded-md border border-line bg-white p-3">
        <h3 className="text-sm font-semibold text-ink">2. Visual</h3>
        <p className="mt-1 text-xs text-ink/55">Depois da revisão do texto, gere o asset e renderize os previews.</p>
        {activeAsset?.asset_url ? (
          <figure className="mt-3 overflow-hidden rounded-md border border-line bg-stone-50">
            <img className="aspect-[2/3] w-full object-cover" src={resolveMediaUrl(activeAsset.asset_url)} alt="Asset visual do carrossel" />
            <figcaption className="border-t border-line px-3 py-2 text-xs text-ink/55">
              #{activeAsset.id} · {activeAsset.modelo || 'asset'}
            </figcaption>
          </figure>
        ) : (
          <p className="mt-2 rounded-md border border-dashed border-line bg-stone-50 px-3 py-4 text-sm text-ink/55">Nenhum asset visual gerado.</p>
        )}
        <div className="mt-3 grid grid-cols-2 gap-2">
          <button className="secondary-button" onClick={onGenerateAsset} disabled={loading || !canRender}>
            <ImagePlus className="h-4 w-4" />
            {activeAsset ? 'Regenerar asset' : 'Gerar asset'}
          </button>
          <button className="danger-button" onClick={() => activeAsset && onDeleteAsset(activeAsset.id)} disabled={loading || !activeAsset}>
            <Trash2 className="h-4 w-4" />
            Remover
          </button>
        </div>

        <div className="mt-4 border-t border-line pt-3">
          <label className="block">
            <span className="field-label">Template</span>
            <select
              className="input mt-1"
              value={renderForm.template}
              onChange={(event) => onRenderForm({ ...renderForm, template: event.target.value })}
            >
              {TEMPLATE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </label>
          <label className="mt-3 block">
            <span className="field-label">Proporção dos slides</span>
            <select
              className="input mt-1"
              value={renderForm.aspect_ratio || '4:5'}
              onChange={(event) => onRenderForm({ ...renderForm, aspect_ratio: event.target.value })}
            >
              {ASPECT_RATIO_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </label>
          <label className="mt-3 block">
            <span className="field-label">Marca/assinatura</span>
            <input
              className="input mt-1"
              value={renderForm.brand_name}
              maxLength={80}
              placeholder={selected.tema || 'Content Carousel'}
              onChange={(event) => onRenderForm({ ...renderForm, brand_name: event.target.value })}
            />
          </label>
          <label className="mt-3 block">
            <span className="field-label">Cor principal</span>
            <div className="mt-1 flex items-center gap-2">
              <input
                className="h-10 w-12 rounded-md border border-line bg-white p-1"
                type="color"
                value={normalizedColor}
                onChange={(event) => onRenderForm({ ...renderForm, primary_color: event.target.value })}
              />
              <input
                className="input"
                value={renderForm.primary_color}
                maxLength={7}
                onChange={(event) => onRenderForm({ ...renderForm, primary_color: event.target.value })}
              />
            </div>
            {paletteColors.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {paletteColors.map((color) => (
                  <button
                    key={color}
                    type="button"
                    className={`h-7 w-7 rounded-md border ${normalizedColor.toLowerCase() === color.toLowerCase() ? 'border-ink ring-2 ring-ink/20' : 'border-line'}`}
                    style={{ backgroundColor: color }}
                    title={`Usar ${color}`}
                    aria-label={`Usar cor ${color}`}
                    onClick={() => onRenderForm({ ...renderForm, primary_color: color })}
                  />
                ))}
              </div>
            )}
          </label>
          <label className="mt-3 flex items-center gap-2 text-sm text-ink/70">
            <input
              type="checkbox"
              checked={Boolean(renderForm.use_asset)}
              onChange={(event) => onRenderForm({ ...renderForm, use_asset: event.target.checked })}
              disabled={!activeAsset}
            />
            Usar asset visual atual no render
          </label>
          <button className="secondary-button mt-3 w-full justify-start" onClick={onRenderSlides} disabled={loading || !canRender}>
            <Image className="h-4 w-4" />
            Renderizar slides
          </button>
          {canDownload && (
            <button className="secondary-button mt-2 w-full justify-start" onClick={downloadSlides} disabled={loading}>
              <Download className="h-4 w-4" />
              Download slides
            </button>
          )}
        </div>
      </section>
    </aside>
  );
}
