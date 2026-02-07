import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './index.css'
import App from './App.tsx'
import PracticePage from './PracticePage.tsx'

// Handle SPA redirect from 404.html on GitHub Pages
const redirect = sessionStorage.redirect as string | undefined;
if (redirect) {
  sessionStorage.removeItem('redirect');
  const url = new URL(redirect);
  window.history.replaceState(null, '', url.pathname + url.search + url.hash);
}
// Also handle ?/ redirect pattern
const { search } = window.location;
if (search.startsWith('?/')) {
  const decoded = search.slice(2).split('&').map(s => s.replace(/~and~/g, '&')).join('&');
  const path = '/' + decoded;
  window.history.replaceState(null, '', '/ragOS' + path);
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter basename="/ragOS">
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/practice" element={<PracticePage />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
