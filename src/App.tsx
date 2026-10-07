import { useEffect } from 'react';
import { NavLink, Navigate, Route, Routes } from 'react-router-dom';
import { useApp } from './store/useApp';
import Disclaimer from './features/Disclaimer';
import Learn from './features/Learn';
import ModuleView from './features/ModuleView';
import Search from './features/Search';
import About from './features/About';
import Placeholder from './features/Placeholder';
import Simulator from './features/simulator/Simulator';
import Calculators from './features/Calculators';
import Practice from './features/Practice';
import ScenarioList from './features/scenarios/ScenarioList';
import ScenarioPlayer from './features/scenarios/ScenarioPlayer';

const tabs = [
  { to: '/aprender', label: 'Aprender', icon: '📘' },
  { to: '/simulador', label: 'Simulador', icon: '📟' },
  { to: '/casos', label: 'Casos', icon: '🩺' },
  { to: '/quiz', label: 'Quiz', icon: '❓' },
  { to: '/repaso', label: 'Repaso', icon: '🔁' },
];

export default function App() {
  const { theme, setTheme, disclaimerAccepted } = useApp();

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
  }, [theme]);

  if (!disclaimerAccepted) return <Disclaimer />;

  return (
    <div className="mx-auto flex min-h-screen max-w-3xl flex-col">
      <header className="flex items-center justify-between px-4 py-3">
        <h1 className="text-lg font-bold text-brand dark:text-brand-light">V60 Academy</h1>
        <div className="flex gap-1">
          <NavLink to="/buscar" aria-label="Buscar" className="flex h-12 w-12 items-center justify-center text-xl">🔍</NavLink>
          <NavLink to="/acerca" aria-label="Acerca de" className="flex h-12 w-12 items-center justify-center text-xl">ℹ️</NavLink>
          <button
            aria-label={theme === 'dark' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
            className="h-12 w-12 text-xl"
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          >
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>
        </div>
      </header>

      <main className="flex-1 px-4 pb-28 fade-in">
        <Routes>
          <Route path="/" element={<Navigate to="/aprender" replace />} />
          <Route path="/aprender" element={<Learn />} />
          <Route path="/aprender/:moduleId" element={<ModuleView />} />
          <Route path="/simulador" element={<Simulator />} />
          <Route path="/calculadoras" element={<Calculators />} />
          <Route path="/casos" element={<Placeholder title="Casos clínicos" phase="C" />} />
          <Route path="/quiz" element={<Practice />} />
          <Route path="/escenarios" element={<ScenarioList />} />
          <Route path="/escenarios/:id" element={<ScenarioPlayer />} />
          <Route path="/repaso" element={<Placeholder title="Repaso" phase="C" />} />
          <Route path="/buscar" element={<Search />} />
          <Route path="/acerca" element={<About />} />
        </Routes>
      </main>

      <nav
        aria-label="Navegación principal"
        className="fixed inset-x-0 bottom-0 z-10 mx-auto flex max-w-3xl border-t border-slate-200 bg-white pb-[env(safe-area-inset-bottom)] dark:border-slate-700 dark:bg-slate-800"
      >
        {tabs.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            className={({ isActive }) =>
              `flex min-h-[56px] flex-1 flex-col items-center justify-center text-xs ${
                isActive ? 'font-bold text-brand dark:text-brand-light' : 'text-slate-500 dark:text-slate-400'
              }`
            }
          >
            <span aria-hidden className="text-xl">{t.icon}</span>
            {t.label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
