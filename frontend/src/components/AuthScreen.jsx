import { useState } from 'react';
import { LogIn, UserPlus } from 'lucide-react';

export function AuthScreen({ onLogin, loading, error }) {
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({ nome: '', email: '', password: '' });

  const submit = (event) => {
    event.preventDefault();
    const payload = mode === 'register' ? form : { email: form.email, password: form.password };
    onLogin(mode, payload);
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-paper px-4 py-8 text-ink">
      <div className="w-full max-w-md rounded-md border border-line bg-white p-6 shadow-soft">
        <div className="mb-5">
          <h1 className="text-xl font-semibold">Content Carousel Console</h1>
          <p className="mt-1 text-sm text-ink/60">Entre para gerenciar seus carrosséis e credenciais.</p>
        </div>
        <div className="mb-4 grid grid-cols-2 gap-2">
          <button className={mode === 'login' ? 'primary-button' : 'secondary-button'} type="button" onClick={() => setMode('login')}>
            <LogIn className="h-4 w-4" /> Entrar
          </button>
          <button className={mode === 'register' ? 'primary-button' : 'secondary-button'} type="button" onClick={() => setMode('register')}>
            <UserPlus className="h-4 w-4" /> Criar conta
          </button>
        </div>
        {error && <div className="mb-4 rounded-md border border-coral/30 bg-coral/10 px-3 py-2 text-sm text-coral">{error}</div>}
        <form className="space-y-3" onSubmit={submit}>
          {mode === 'register' && (
            <label className="block">
              <span className="field-label">Nome</span>
              <input className="input mt-1" value={form.nome} onChange={(event) => setForm({ ...form, nome: event.target.value })} required />
            </label>
          )}
          <label className="block">
            <span className="field-label">Email</span>
            <input className="input mt-1" type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} required />
          </label>
          <label className="block">
            <span className="field-label">Senha</span>
            <input className="input mt-1" type="password" minLength={mode === 'register' ? 8 : 1} value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} required />
          </label>
          <button className="primary-button w-full" type="submit" disabled={loading}>
            {mode === 'register' ? <UserPlus className="h-4 w-4" /> : <LogIn className="h-4 w-4" />}
            {mode === 'register' ? 'Criar conta' : 'Entrar'}
          </button>
        </form>
      </div>
    </div>
  );
}
