import React from 'react';
import ReactDOM from 'react-dom/client';
import { HashRouter, MemoryRouter } from 'react-router-dom';
import { registerSW } from 'virtual:pwa-register';
import App from './App';
import './index.css';

registerSW({ immediate: true });

// En la versión de artefacto el visor no admite deep links por hash: se enruta en memoria.
const Router = import.meta.env.VITE_ARTIFACT ? MemoryRouter : HashRouter;

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Router>
      <App />
    </Router>
  </React.StrictMode>,
);
