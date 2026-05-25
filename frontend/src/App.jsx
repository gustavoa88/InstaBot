import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, KeyRound, Loader2 } from 'lucide-react';
import { ActionPanel } from './components/ActionPanel.jsx';
import { CarrosselList } from './components/CarrosselList.jsx';
import { CreateCarrosselForm } from './components/CreateCarrosselForm.jsx';
import { LogsPanel } from './components/LogsPanel.jsx';
import { Workspace } from './components/Workspace.jsx';
import { api } from './services/api.js';

const EMPTY_FORM = {
  ideia_original: '',
  tom: '',
  quantidade_slides: '7',
  observacoes_adicionais: '',
};

const DEFAULT_RENDER_FORM = {
  template: 'clean_editorial',
  brand_name: '',
  primary_color: '#6f9684',
  use_asset: true,
};

function toIsoFromLocal(value) {
  return new Date(value).toISOString();
}

function toLocalDateInput(date = new Date(Date.now() + 3600000)) {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function normalizeCarrosselPayload(draft) {
  const hashtagsText = draft.hashtagsText ?? (Array.isArray(draft.hashtags) ? draft.hashtags.join(' ') : '');
  return {
    titulo: draft.titulo || null,
    ideia_original: draft.ideia_original,
    tema: draft.tema || null,
    tom: draft.tom || null,
    publico_alvo: draft.publico_alvo || null,
    quantidade_slides: Number(draft.quantidade_slides || 7),
    legenda: draft.legenda || null,
    hashtags: hashtagsText.split(/\s+/).map((item) => item.trim()).filter(Boolean),
  };
}

function normalizeCreatePayload(form) {
  return {
    ideia_original: form.ideia_original,
    tom: form.tom || null,
    quantidade_slides: Number(form.quantidade_slides || 7),
    observacoes_adicionais: form.observacoes_adicionais || null,
  };
}

export default function App() {
  const [carrosseis, setCarrosseis] = useState([]);
  const [logs, setLogs] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [createForm, setCreateForm] = useState(EMPTY_FORM);
  const [draft, setDraft] = useState({});
  const [slideDrafts, setSlideDrafts] = useState({});
  const [scheduleForm, setScheduleForm] = useState({ agendado_para: toLocalDateInput(), plataforma: 'instagram' });
  const [renderForm, setRenderForm] = useState(DEFAULT_RENDER_FORM);
  const [rescheduleForms, setRescheduleForms] = useState({});
  const [statusFilter, setStatusFilter] = useState('TODOS');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [adminTokenInput, setAdminTokenInput] = useState(() => api.getAdminToken());

  const selected = useMemo(
    () => carrosseis.find((item) => item.id === selectedId) || null,
    [carrosseis, selectedId],
  );

  const showNotice = (message) => {
    setNotice(message);
    window.setTimeout(() => setNotice(''), 3200);
  };

  const run = async (action, successMessage) => {
    setLoading(true);
    setError('');
    try {
      const result = await action();
      if (successMessage) showNotice(successMessage);
      return result;
    } catch (err) {
      setError(err.message || 'Falha inesperada.');
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const loadData = async (nextSelectedId = selectedId) => {
    const [items, recentLogs] = await Promise.all([api.listCarrosseis(), api.listLogs()]);
    setCarrosseis(items);
    setLogs(recentLogs);
    if (nextSelectedId && items.some((item) => item.id === nextSelectedId)) {
      setSelectedId(nextSelectedId);
    } else if (!nextSelectedId && items.length) {
      setSelectedId(items[0].id);
    } else if (nextSelectedId && !items.some((item) => item.id === nextSelectedId)) {
      setSelectedId(items[0]?.id || null);
    }
  };

  useEffect(() => {
    run(() => loadData(null)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selected) {
      setDraft({});
      setSlideDrafts({});
      return;
    }
    setDraft({ ...selected, hashtagsText: Array.isArray(selected.hashtags) ? selected.hashtags.join(' ') : '' });
    setSlideDrafts(Object.fromEntries((selected.slides || []).map((slide) => [slide.id, { ...slide }])));
    const pendingPublication = (selected.publicacoes || []).find((publication) => publication.status === 'AGENDADO');
    setScheduleForm({
      agendado_para: pendingPublication ? toLocalDateInput(new Date(pendingPublication.agendado_para)) : toLocalDateInput(),
      plataforma: pendingPublication?.plataforma || 'instagram',
    });
    setRescheduleForms(Object.fromEntries((selected.publicacoes || []).map((publication) => [
      publication.id,
      {
        agendado_para: toLocalDateInput(new Date(publication.agendado_para)),
        plataforma: publication.plataforma,
      },
    ])));
  }, [selected]);

  const refresh = () => run(() => loadData(selectedId), 'Dados atualizados.').catch(() => {});

  const saveAdminToken = (event) => {
    event.preventDefault();
    api.setAdminToken(adminTokenInput);
    setAdminTokenInput(api.getAdminToken());
    showNotice('Token admin atualizado.');
  };

  const createCarrossel = (event) => {
    event.preventDefault();
    run(async () => {
      const created = await api.createCarrossel(normalizeCreatePayload(createForm));
      setCreateForm(EMPTY_FORM);
      await loadData(created.id);
    }, 'Ideia criada. Agora gere os slides no painel de ações.').catch(() => {});
  };

  const saveCarrossel = () => run(async () => {
    await api.updateCarrossel(selected.id, normalizeCarrosselPayload(draft));
    await loadData(selected.id);
  }, 'Conteúdo salvo.').catch(() => {});

  const saveSlide = (slideId) => run(async () => {
    const slide = slideDrafts[slideId];
    await api.updateSlide(slideId, {
      titulo: slide.titulo || null,
      texto_principal: slide.texto_principal || null,
      texto_secundario: slide.texto_secundario || null,
      observacao_visual: slide.observacao_visual || null,
      aprovado: slide.aprovado,
    });
    await loadData(selected.id);
  }, 'Slide salvo.').catch(() => {});

  const deleteSelected = () => run(async () => {
    await api.deleteCarrossel(selected.id);
    await loadData(null);
  }, 'Carrossel removido.').catch(() => {});

  const simpleAction = (fn, message) => run(async () => {
    await fn(selected.id);
    await loadData(selected.id);
  }, message).catch(() => {});

  const renderSlides = () => {
    const activeAsset = [...(selected?.assets || [])].filter((asset) => asset.status === 'ATIVO' && asset.tipo === 'background').sort((a, b) => b.id - a.id)[0];
    return simpleAction((id) => api.renderSlides(id, {
      template: renderForm.template || null,
      brand_name: renderForm.brand_name || null,
      primary_color: renderForm.primary_color || null,
      asset_id: renderForm.use_asset && activeAsset ? activeAsset.id : null,
    }), 'Slides renderizados. Agora revise e aprove.');
  };

  const schedule = () => run(async () => {
    await api.schedule(selected.id, {
      agendado_para: toIsoFromLocal(scheduleForm.agendado_para),
      plataforma: scheduleForm.plataforma || 'instagram',
    });
    await loadData(selected.id);
  }, 'Publicação agendada.').catch(() => {});

  const reschedule = (publicationId) => run(async () => {
    const form = rescheduleForms[publicationId];
    await api.reschedule(publicationId, {
      agendado_para: toIsoFromLocal(form.agendado_para),
      plataforma: form.plataforma || 'instagram',
    });
    await loadData(selected.id);
  }, 'Publicação reagendada.').catch(() => {});

  const cancelPublication = (publicationId) => run(async () => {
    await api.cancelPublication(publicationId);
    await loadData(selected.id);
  }, 'Publicação cancelada.').catch(() => {});

  const regenerateCarrossel = () => {
    const confirmed = window.confirm(
      'Regenerar substitui os slides atuais e pode gerar custo se a OpenAI estiver ativa. Deseja continuar?',
    );
    if (!confirmed) return;
    simpleAction(api.regenerate, 'Slides regenerados. Revise o texto antes de renderizar.');
  };

  return (
    <div className="min-h-screen bg-paper text-ink">
      <header className="border-b border-line bg-white px-4 py-3">
        <div className="mx-auto flex max-w-[1800px] flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-lg font-semibold text-ink">Content Carousel Console</h1>
            <p className="text-sm text-ink/55">Crie a ideia, gere slides, revise, renderize e então aprove ou agende.</p>
          </div>
          <form className="flex flex-wrap items-end justify-end gap-2" onSubmit={saveAdminToken}>
            <label className="min-w-[220px]">
              <span className="field-label">Token admin</span>
              <input
                className="input mt-1"
                type="password"
                value={adminTokenInput}
                onChange={(event) => setAdminTokenInput(event.target.value)}
                placeholder="ccp_admin_token"
                autoComplete="off"
              />
            </label>
            <button className="secondary-button" type="submit" disabled={loading}>
              <KeyRound className="h-4 w-4" />
              Salvar token
            </button>
            <div className="flex items-center gap-2 text-sm text-ink/60">
              {loading && <Loader2 className="h-4 w-4 animate-spin" />}
              <span>{loading ? 'Processando' : 'Pronto'}</span>
            </div>
          </form>
        </div>
      </header>

      <div className="mx-auto grid max-w-[1800px] gap-4 p-4 xl:grid-cols-[320px_minmax(0,1fr)_360px]">
        <CarrosselList
          carrosseis={carrosseis}
          selectedId={selectedId}
          statusFilter={statusFilter}
          search={search}
          onStatusFilter={setStatusFilter}
          onSearch={setSearch}
          onSelect={setSelectedId}
          onRefresh={refresh}
          loading={loading}
        />

        <div className="flex min-h-0 flex-col gap-4">
          {error && (
            <div className="flex items-start gap-2 rounded-md border border-coral/30 bg-coral/10 px-3 py-2 text-sm text-coral">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}
          {notice && <div className="rounded-md border border-moss/20 bg-moss/10 px-3 py-2 text-sm text-moss">{notice}</div>}
          <CreateCarrosselForm form={createForm} onChange={setCreateForm} onSubmit={createCarrossel} loading={loading} />
          <Workspace
            selected={selected}
            draft={draft}
            slideDrafts={slideDrafts}
            onDraftChange={setDraft}
            onSlideDraftChange={(slideId, next) => setSlideDrafts((current) => ({ ...current, [slideId]: next }))}
            onSaveCarrossel={saveCarrossel}
            onSaveSlide={saveSlide}
            onDelete={deleteSelected}
            loading={loading}
          />
        </div>

        <div className="flex min-h-0 flex-col gap-4">
          <ActionPanel
            selected={selected}
            scheduleForm={scheduleForm}
            rescheduleForms={rescheduleForms}
            renderForm={renderForm}
            onScheduleForm={setScheduleForm}
            onRescheduleForm={(publicationId, next) => setRescheduleForms((current) => ({ ...current, [publicationId]: next }))}
            onRenderForm={setRenderForm}
            onGenerate={() => simpleAction(api.generate, 'Slides gerados. Revise o texto antes de renderizar.')}
            onRegenerate={regenerateCarrossel}
            onRenderSlides={renderSlides}
            onGenerateAsset={() => simpleAction(api.generateAsset, 'Asset visual gerado.')}
            onDeleteAsset={(assetId) => run(async () => {
              await api.deleteAsset(assetId);
              await loadData(selected.id);
            }, 'Asset visual removido.').catch(() => {})}
            onApprove={() => simpleAction(api.approve, 'Carrossel aprovado. Agora você pode agendar ou publicar teste.')}
            onReject={() => simpleAction(api.reject, 'Carrossel rejeitado.')}
            onSchedule={schedule}
            onReschedule={reschedule}
            onCancelPublication={cancelPublication}
            onPublishNow={() => simpleAction(api.publishNow, 'Publicação teste concluída.')}
            loading={loading}
          />
          <LogsPanel logs={logs} selectedId={selectedId} />
        </div>
      </div>
    </div>
  );
}
