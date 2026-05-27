import { KeyRound, X } from 'lucide-react';

export function SettingsPanel({ config, form, onChange, onClose, onSubmit, loading }) {
  return (
    <div className="fixed inset-0 z-20 bg-ink/20 px-4 py-6">
      <div className="ml-auto flex h-full w-full max-w-xl flex-col rounded-md border border-line bg-white shadow-soft">
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <div>
            <h2 className="text-base font-semibold">Configurações</h2>
            <p className="text-xs text-ink/55">As credenciais são salvas criptografadas no banco.</p>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Fechar configurações">
            <X className="h-4 w-4" />
          </button>
        </div>
        <form className="flex-1 space-y-4 overflow-auto p-4" onSubmit={onSubmit}>
          <div className="rounded-md border border-line p-3 text-sm">
            <div className="font-semibold">Status</div>
            <div className="mt-2 grid gap-1 text-ink/65">
              <span>OpenAI: {config?.openai_configurado ? `configurado (${config.openai_api_key_masked})` : 'não configurado'}</span>
              <span>Instagram: {config?.instagram_configurado ? 'configurado' : 'não configurado'}</span>
            </div>
          </div>
          {[
            ['openai_api_key', 'OPENAI_API_KEY', config?.openai_api_key_masked],
            ['instagram_access_token', 'INSTAGRAM_ACCESS_TOKEN', config?.instagram_access_token_masked],
            ['instagram_user_id', 'INSTAGRAM_USER_ID', config?.instagram_user_id_masked],
            ['facebook_page_id', 'FACEBOOK_PAGE_ID', config?.facebook_page_id_masked],
          ].map(([key, label, masked]) => (
            <label className="block" key={key}>
              <span className="field-label">{label}</span>
              <input
                className="input mt-1"
                type="password"
                value={form[key] || ''}
                onChange={(event) => onChange({ ...form, [key]: event.target.value })}
                placeholder={masked || 'não configurado'}
                autoComplete="off"
              />
            </label>
          ))}
          <div className="flex justify-end gap-2 border-t border-line pt-4">
            <button className="secondary-button" type="button" onClick={onClose}>Cancelar</button>
            <button className="primary-button" type="submit" disabled={loading}>
              <KeyRound className="h-4 w-4" /> Salvar configurações
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
