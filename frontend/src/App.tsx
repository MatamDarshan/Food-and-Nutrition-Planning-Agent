import { lazy, Suspense, useEffect } from 'react';
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { Toaster } from 'sonner';
import { Apple, Loader2 } from 'lucide-react';
import { authApi } from './lib/api';
import { useApp } from './lib/store';

const Layout = lazy(() => import('./components/Layout').then((m) => ({ default: m.Layout })));
const Landing = lazy(() => import('./pages/Landing').then((m) => ({ default: m.Landing })));
const Auth = lazy(() => import('./pages/Auth').then((m) => ({ default: m.Auth })));
const Onboarding = lazy(() => import('./pages/Onboarding').then((m) => ({ default: m.Onboarding })));
const Dashboard = lazy(() => import('./pages/Dashboard').then((m) => ({ default: m.Dashboard })));
const Planner = lazy(() => import('./pages/Planner').then((m) => ({ default: m.Planner })));
const Recipe = lazy(() => import('./pages/Recipe').then((m) => ({ default: m.Recipe })));
const Nutritionist = lazy(() => import('./pages/Nutritionist').then((m) => ({ default: m.Nutritionist })));
const Insights = lazy(() => import('./pages/Insights').then((m) => ({ default: m.Insights })));
const Grocery = lazy(() => import('./pages/Grocery').then((m) => ({ default: m.Grocery })));
const Library = lazy(() => import('./pages/Library').then((m) => ({ default: m.Library })));
const ProfilePage = lazy(() => import('./pages/Profile').then((m) => ({ default: m.ProfilePage })));

function PageLoader() {
  return (
    <div className="grid min-h-[60vh] place-items-center">
      <Loader2 className="h-6 w-6 animate-spin text-brand-600" />
    </div>
  );
}

function Protected({ children }: { children: React.ReactNode }) {
  const user = useApp((s) => s.user);
  const location = useLocation();
  if (!user) return <Navigate to="/signin" replace state={{ from: location.pathname }} />;
  return <>{children}</>;
}

function Bootstrap() {
  const setUser = useApp((s) => s.setUser);
  const reset = useApp((s) => s.reset);
  const hydrate = useApp((s) => s.hydrate);
  const hydrated = useApp((s) => s.hydrated);

  useEffect(() => {
    const boot = async () => {
      if (!localStorage.getItem('np_token')) {
        hydrate();
        return;
      }
      try {
        const user = await authApi.me();
        setUser(user);
      } catch {
        localStorage.removeItem('np_token');
        reset();
      }
      await hydrate();
    };
    boot();
  }, [setUser, reset, hydrate]);

  if (!hydrated) {
    return (
      <div className="grid min-h-screen place-items-center bg-cream">
        <div className="text-center">
          <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-brand-600 text-white shadow-glow">
            <Apple className="h-7 w-7" />
          </span>
          <Loader2 className="mx-auto mt-5 h-5 w-5 animate-spin text-brand-600" />
          <p className="mt-3 text-xs font-semibold text-muted-foreground">Loading NutriPlan…</p>
        </div>
      </div>
    );
  }
  return null;
}

function NotFound() {
  return (
    <div className="grid min-h-screen place-items-center bg-cream px-5 text-center">
      <div>
        <p className="font-display text-7xl font-extrabold text-brand-200">404</p>
        <h1 className="mt-3 text-2xl font-extrabold">This page isn't on the menu</h1>
        <p className="mt-2 text-sm text-muted-foreground">Let's get you back to something nourishing.</p>
        <Link to="/" className="mt-6 inline-flex h-11 items-center rounded-xl bg-brand-600 px-5 text-sm font-semibold text-white">Back to home</Link>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Bootstrap />
      <Toaster position="top-right" richColors closeButton />
      <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/signin" element={<Auth mode="signin" />} />
        <Route path="/signup" element={<Auth mode="signup" />} />
        <Route path="/onboarding" element={<Protected><Onboarding /></Protected>} />
        <Route path="/app" element={<Protected><Layout /></Protected>}>
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="planner" element={<Planner />} />
          <Route path="meal/:day/:meal" element={<Recipe />} />
          <Route path="nutritionist" element={<Nutritionist />} />
          <Route path="insights" element={<Insights />} />
          <Route path="grocery" element={<Grocery />} />
          <Route path="library" element={<Library />} />
          <Route path="profile" element={<ProfilePage />} />
        </Route>
        <Route path="*" element={<NotFound />} />
      </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
