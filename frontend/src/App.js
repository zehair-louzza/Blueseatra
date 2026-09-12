import { useEffect } from 'react';
import '@/App.css';
import '@/i18n';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { AuthProvider } from '@/context/AuthContext';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { AppShell } from '@/components/AppShell';
import { Toaster } from '@/components/ui/sonner';
import Landing from '@/pages/Landing';
import { LoginPage, SignupPage } from '@/pages/Auth';
import Dashboard from '@/pages/Dashboard';
import Requests from '@/pages/Requests';
import RequestDetail from '@/pages/RequestDetail';
import Catalogs from '@/pages/Catalogs';
import SupplierSearch from '@/pages/SupplierSearch';
import CatalogImport from '@/pages/CatalogImport';
import Quotes from '@/pages/Quotes';
import QuoteEditor from '@/pages/QuoteEditor';
import Members from '@/pages/Members';
import Audit from '@/pages/Audit';
import Settings from '@/pages/Settings';
import Billing from '@/pages/Billing';

const Shell = ({ children }) => (
  <ProtectedRoute><AppShell>{children}</AppShell></ProtectedRoute>
);

function App() {
  const { i18n } = useTranslation();
  useEffect(() => { document.documentElement.lang = i18n.language; }, [i18n.language]);

  // Remove Emergent badge and fix page title
  useEffect(() => {
    // Fix title
    document.title = 'Blueseatra';

    // Remove Emergent badge element
    const removeBadge = () => {
      const badge = document.getElementById('emergent-badge');
      if (badge) badge.remove();
      // Also remove any element containing 'Made with Emergent'
      document.querySelectorAll('a[href*="emergent"], a[href*="emergent.sh"]').forEach(el => el.remove());
    };

    removeBadge();
    // Observe DOM for late injection
    const observer = new MutationObserver(removeBadge);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, []);

  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
            <Route path="/app" element={<Shell><Dashboard /></Shell>} />
            <Route path="/app/requests" element={<Shell><Requests /></Shell>} />
            <Route path="/app/requests/:id" element={<Shell><RequestDetail /></Shell>} />
            <Route path="/app/catalogs" element={<Shell><Catalogs /></Shell>} />
            <Route path="/app/catalogs/import" element={<Shell><CatalogImport /></Shell>} />
            <Route path="/app/fournisseurs" element={<Shell><SupplierSearch /></Shell>} />
            <Route path="/app/quotes" element={<Shell><Quotes /></Shell>} />
            <Route path="/app/quotes/:id" element={<Shell><QuoteEditor /></Shell>} />
            <Route path="/app/members" element={<Shell><Members /></Shell>} />
            <Route path="/app/audit" element={<Shell><Audit /></Shell>} />
            <Route path="/app/settings" element={<Shell><Settings /></Shell>} />
            <Route path="/app/billing" element={<Shell><Billing /></Shell>} />
          </Routes>
        </BrowserRouter>
        <Toaster position="top-right" richColors />
      </AuthProvider>
    </div>
  );
}

export default App;
