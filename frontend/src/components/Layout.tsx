import { useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  Apple, Bot, BookOpen, ChartNoAxesCombined, ChevronRight, Heart, LayoutDashboard,
  ListChecks, LogOut, Menu, Settings, ShoppingBasket, Sparkles, X,
} from 'lucide-react';
import { toast } from 'sonner';
import { authApi } from '../lib/api';
import { cn } from '../lib/utils';
import { useApp } from '../lib/store';

const NAV = [
  { to: '/app/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/app/planner', label: 'Meal Planner', icon: BookOpen },
  { to: '/app/insights', label: 'Nutrition Insights', icon: ChartNoAxesCombined },
  { to: '/app/nutritionist', label: 'AI Nutritionist', icon: Bot },
  { to: '/app/grocery', label: 'Grocery List', icon: ShoppingBasket },
  { to: '/app/library', label: 'Favorites & History', icon: Heart },
  { to: '/app/profile', label: 'My Profile', icon: Settings },
];

export function Layout() {
  const [open, setOpen] = useState(false);
  const user = useApp((s) => s.user);
  const reset = useApp((s) => s.reset);
  const location = useLocation();
  const navigate = useNavigate();
  const [prevPath, setPrevPath] = useState(location.pathname);

  if (prevPath !== location.pathname) {
    setPrevPath(location.pathname);
    setOpen(false);
  }

  const signout = async () => {
    await authApi.signout();
    reset();
    toast.success('Signed out');
    navigate('/');
  };

  const active = NAV.find((item) => location.pathname.startsWith(item.to));

  return (
    <div className="min-h-screen bg-cream">
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-brand-100 bg-white transition-transform duration-300 lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <Link to="/" className="flex items-center gap-2.5 px-6 py-6">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand-600 text-white shadow-glow">
            <Apple className="h-5 w-5" />
          </span>
          <span className="font-display text-lg font-extrabold tracking-tight">NutriPlan</span>
        </Link>

        <nav className="np-scrollbar flex-1 space-y-1 overflow-y-auto px-3">
          <p className="px-4 pb-2 pt-3 text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
            Workspace
          </p>
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  'group flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-semibold transition',
                  isActive
                    ? 'bg-brand-600 text-white shadow-soft'
                    : 'text-muted-foreground hover:bg-brand-50 hover:text-ink',
                )
              }
            >
              <Icon className="h-[18px] w-[18px]" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="m-4 rounded-2xl bg-gradient-to-br from-brand-600 to-brand-800 p-4 text-white">
          <Sparkles className="h-5 w-5 text-brand-200" />
          <p className="mt-2 text-sm font-bold">Need a second opinion?</p>
          <p className="mt-1 text-xs text-white/70">Your AI Nutritionist is available 24/7.</p>
          <Link
            to="/app/nutritionist"
            className="mt-3 inline-flex items-center gap-1 text-xs font-bold text-brand-100 hover:text-white"
          >
            Ask now <ChevronRight className="h-3 w-3" />
          </Link>
        </div>

        <div className="flex items-center gap-3 border-t border-brand-100 px-5 py-4">
          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-brand-100 text-sm font-bold text-brand-700">
            {user?.name?.charAt(0).toUpperCase() || 'U'}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold">{user?.name || 'Guest'}</p>
            <p className="truncate text-xs text-muted-foreground">{user?.email}</p>
          </div>
          <button onClick={signout} title="Sign out" className="rounded-lg p-2 text-muted-foreground hover:bg-brand-50 hover:text-red-600">
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </aside>

      {open && (
        <button
          aria-label="Close menu"
          onClick={() => setOpen(false)}
          className="fixed inset-0 z-30 bg-ink/40 lg:hidden"
        >
          <X className="sr-only" />
        </button>
      )}

      <div className="lg:pl-72">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-4 border-b border-brand-100/80 bg-cream/90 px-5 backdrop-blur-xl sm:px-8">
          <button onClick={() => setOpen(true)} className="rounded-lg p-2 hover:bg-brand-50 lg:hidden" aria-label="Open menu">
            <Menu className="h-5 w-5" />
          </button>
          <div className="min-w-0">
            <p className="text-[11px] font-bold uppercase tracking-widest text-brand-600">NutriPlan</p>
            <h1 className="truncate text-base font-bold sm:text-lg">{active?.label || 'Dashboard'}</h1>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <Link
              to="/app/nutritionist"
              className="hidden items-center gap-2 rounded-xl border border-brand-200 bg-white px-4 py-2 text-sm font-semibold text-brand-700 shadow-sm transition hover:border-brand-400 sm:inline-flex"
            >
              <Bot className="h-4 w-4" /> Ask Nutritionist
            </Link>
            <div className="grid h-9 w-9 place-items-center rounded-full bg-brand-600 text-sm font-bold text-white">
              {user?.name?.charAt(0).toUpperCase() || 'U'}
            </div>
          </div>
        </header>

        <main className="mx-auto w-full max-w-7xl px-5 py-7 sm:px-8 sm:py-9">
          <Outlet />
        </main>

        <nav className="fixed bottom-0 left-0 right-0 z-20 flex items-center justify-around border-t border-brand-100 bg-white/95 px-2 py-2 backdrop-blur lg:hidden">
          {NAV.slice(0, 5).map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  'flex flex-col items-center gap-0.5 rounded-lg px-2 py-1.5 text-[10px] font-semibold',
                  isActive ? 'text-brand-700' : 'text-muted-foreground',
                )
              }
            >
              <Icon className="h-5 w-5" />
              {label.split(' ')[0]}
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
      <div>
        {eyebrow && <p className="np-eyebrow mb-2">{eyebrow}</p>}
        <h2 className="text-2xl font-extrabold sm:text-3xl">{title}</h2>
        {description && <p className="mt-1.5 max-w-2xl text-sm text-muted-foreground">{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function EmptyPlan({ label = 'Create your plan' }: { label?: string }) {
  const navigate = useNavigate();
  return (
    <div className="np-card mx-auto max-w-lg p-10 text-center">
      <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-brand-50 text-brand-600">
        <ListChecks className="h-7 w-7" />
      </div>
      <h3 className="mt-5 text-xl font-bold">No meal plan yet</h3>
      <p className="mt-2 text-sm text-muted-foreground">
        Complete the quick onboarding and we'll build your personalised 7-day Indian meal plan in seconds.
      </p>
      <button
        onClick={() => navigate('/onboarding')}
        className="mt-6 inline-flex h-11 items-center gap-2 rounded-xl bg-brand-600 px-5 text-sm font-semibold text-white hover:bg-brand-700"
      >
        {label} <ChevronRight className="h-4 w-4" />
      </button>
    </div>
  );
}
