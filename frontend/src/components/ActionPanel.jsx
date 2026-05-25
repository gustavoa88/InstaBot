import { CalendarClock, CheckCircle2, Image, ImagePlus, Play, RefreshCw, Send, Trash2, XCircle } from 'lucide-react';

function toDatetimeLocalValue(date = new Date()) {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

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

export function ActionPanel({
  selected,
  scheduleForm,
  rescheduleForms,
  renderForm,
  onScheduleForm,
  onRescheduleForm,
  onRenderForm,
  onGenerate,
  onRegenerate,
  onRenderSlides,
  onGenerateAsset,
  onDeleteAsset,
  onApprove,
  onReject,
  onSchedule,
  onReschedule,
  onCancelPublication,
  onPublishNow,
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

  const activeAsset = [...(selected.assets || [])].filter((asset) => asset.status === 'ATIVO').sort((a, b) => b.id - a.id)[0];
  const canGenerate = !selected.slides?.length;
  const canRender = Boolean(selected.slides?.length);
  const canApprove = selected.slides?.length && selected.status !== 'PUBLICADO';
  const canSchedule = selected.status === 'APROVADO';
  const canPublish = ['APROVADO', 'AGENDADO'].includes(selected.status);
  const normalizedColor = /^#[0-9A-Fa-f]{6}$/.test(renderForm.primary_color) ? renderForm.primary_color : '#6f9684';

  return (
    <aside className="panel rounded-md p-4">
      <h2 className="text-sm font-semibold text-ink">Fluxo do carrossel</h2>
      <p className="mt-1 text-xs leading-5 text-ink/55">Siga as etapas em ordem: gere a estrutura, revise, renderize e publique.</p>

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
        </div>
      </section>

      <section className="mt-4 rounded-md border border-line bg-white p-3">
        <h3 className="text-sm font-semibold text-ink">3. Revisão</h3>
        <p className="mt-1 text-xs text-ink/55">Aprove somente depois de revisar textos e previews renderizados.</p>
        <div className="mt-3 grid gap-2">
          <button className="primary-button justify-start" onClick={onApprove} disabled={loading || !canApprove}>
            <CheckCircle2 className="h-4 w-4" />
            Aprovar
          </button>
          <button className="danger-button justify-start" onClick={onReject} disabled={loading || !canRender || selected.status === 'PUBLICADO'}>
            <XCircle className="h-4 w-4" />
            Rejeitar
          </button>
        </div>
      </section>

      <section className="mt-4 rounded-md border border-line bg-white p-3">
        <h3 className="text-sm font-semibold text-ink">4. Publicação</h3>
        <p className="mt-1 text-xs text-ink/55">Após aprovar, agende a publicação ou faça um teste imediato.</p>
        <label className="mt-3 block">
          <span className="field-label">Data e hora</span>
          <input className="input mt-1" type="datetime-local" value={scheduleForm.agendado_para || toDatetimeLocalValue(new Date(Date.now() + 3600000))} onChange={(event) => onScheduleForm({ ...scheduleForm, agendado_para: event.target.value })} />
        </label>
        <label className="mt-3 block">
          <span className="field-label">Plataforma</span>
          <input className="input mt-1" value={scheduleForm.plataforma} onChange={(event) => onScheduleForm({ ...scheduleForm, plataforma: event.target.value })} />
        </label>
        <div className="mt-3 grid gap-2">
          <button className="primary-button justify-start" onClick={onSchedule} disabled={loading || !canSchedule}>
            <CalendarClock className="h-4 w-4" />
            Agendar
          </button>
          <button className="secondary-button justify-start" onClick={onPublishNow} disabled={loading || !canPublish}>
            <Send className="h-4 w-4" />
            Publicar teste
          </button>
        </div>
      </section>

      <section className="mt-5 border-t border-line pt-4">
        <h3 className="text-sm font-semibold text-ink">Publicações</h3>
        <div className="mt-3 grid gap-3">
          {(selected.publicacoes || []).map((publicacao) => {
            const form = rescheduleForms[publicacao.id] || {
              agendado_para: toDatetimeLocalValue(new Date(publicacao.agendado_para)),
              plataforma: publicacao.plataforma,
            };
            return (
              <div key={publicacao.id} className="rounded-md border border-line bg-white p-3">
                <div className="flex items-center justify-between gap-2 text-xs text-ink/60">
                  <span>#{publicacao.id} · {publicacao.status}</span>
                  <span>{publicacao.plataforma}</span>
                </div>
                <label className="mt-3 block">
                  <span className="field-label">Novo horário</span>
                  <input className="input mt-1" type="datetime-local" value={form.agendado_para} onChange={(event) => onRescheduleForm(publicacao.id, { ...form, agendado_para: event.target.value })} disabled={publicacao.status !== 'AGENDADO'} />
                </label>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <button className="secondary-button" onClick={() => onReschedule(publicacao.id)} disabled={loading || publicacao.status !== 'AGENDADO'}>Reagendar</button>
                  <button className="danger-button" onClick={() => onCancelPublication(publicacao.id)} disabled={loading || publicacao.status === 'PUBLICADO'}>Cancelar</button>
                </div>
              </div>
            );
          })}
          {!selected.publicacoes?.length && <p className="text-sm text-ink/55">Nenhuma publicação criada.</p>}
        </div>
      </section>
    </aside>
  );
}
