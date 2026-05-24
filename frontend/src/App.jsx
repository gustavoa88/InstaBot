import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Loader2 } from 'lucide-react';
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
  const [rescheduleForms, setRescheduleForms] = useState({});
  const [statusFilter, setStatusFilter] = useState('TODOS');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

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

  const createCarrossel = (event) => {
    event.preventDefault();
    run(async () => {
      const created = await api.createCarrossel(normalizeCreatePayload(createForm));
      setCreateForm(EMPTY_FORM);
      await loadData(created.id);
    }, 'Carrossel criado.').catch(() => {});
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
    simpleAction(api.regenerate, 'Slides regenerados.');
  };

  return (
    <div className="min-h-screen bg-paper text-ink">
      <header className="border-b border-line bg-white px-4 py-3">
        <div className="mx-auto flex max-w-[1800px] flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-lg font-semibold text-ink">Content Carousel Console</h1>
            <p className="text-sm text-ink/55">MVP operacional para criar, revisar, aprovar e agendar carrosséis.</p>
          </div>
          <div className="flex items-center gap-2 text-sm text-ink/60">
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            <span>{loading ? 'Processando' : 'Pronto'}</span>
          </div>
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
            onScheduleForm={setScheduleForm}
            onRescheduleForm={(publicationId, next) => setRescheduleForms((current) => ({ ...current, [publicationId]: next }))}
            onGenerate={() => simpleAction(api.generate, 'Slides gerados.')}
            onRegenerate={regenerateCarrossel}
            onRenderSlides={() => simpleAction(api.renderSlides, 'Slides renderizados.')}
            onApprove={() => simpleAction(api.approve, 'Carrossel aprovado.')}
            onReject={() => simpleAction(api.reject, 'Carrossel rejeitado.')}
            onSchedule={schedule}
            onReschedule={reschedule}
            onCancelPublication={cancelPublication}
            onPublishNow={() => simpleAction(api.publishNow, 'Publicação mock concluída.')}
            loading={loading}
          />
          <LogsPanel logs={logs} selectedId={selectedId} />
        </div>
      </div>
    </div>
  );
}
