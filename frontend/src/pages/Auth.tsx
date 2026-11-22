import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Apple, ArrowRight, Check, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { authApi, messageOf } from '../lib/api';
import { useApp } from '../lib/store';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';

export function Auth({ mode }: { mode: 'signin' | 'signup' }) {
  const navigate = useNavigate();
  const hydrate = useApp((s) => s.hydrate);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const isSignup = mode === 'signup';

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      const { user } = isSignup
        ? await authApi.signup(name, email, password)
        : await authApi.signin(email, password);
      useApp.getState().setUser(user);
      await hydrate();
      toast.success(isSignup ? 'Account created!' : `Welcome back, ${user.name.split(' ')[0]}!`);
      navigate(useApp.getState().plan ? '/app/dashboard' : '/onboarding');
    } catch (error) {
      toast.error(messageOf(error));
    } finally {
      setBusy(false);
    }
  };

  const demo = async () => {
    setBusy(true);
    try {
      const { user } = await authApi.demo();
      useApp.getState().setUser(user);
      await hydrate();
      navigate(useApp.getState().plan ? '/app/dashboard' : '/onboarding');
    } catch (error) {
      toast.error(messageOf(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="np-gradient grid min-h-screen lg:grid-cols-2">
      <div className="flex items-center justify-center px-5 py-12">
        <div className="w-full max-w-md">
          <Link to="/" className="inline-flex items-center gap-2.5">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand-600 text-white shadow-glow"><Apple className="h-5 w-5" /></span>
            <span className="font-display text-lg font-extrabold">NutriPlan</span>
          </Link>
          <h1 className="mt-9 text-3xl font-extrabold">{isSignup ? 'Create your account' : 'Welcome back'}</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {isSignup ? 'Start your personalised Indian nutrition journey.' : 'Sign in to continue to your meal plan.'}
          </p>

          <form onSubmit={submit} className="mt-7 space-y-4">
            {isSignup && (
              <div>
                <label className="mb-1.5 block text-xs font-bold text-ink">Full name</label>
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ananya Sharma" required minLength={1} />
              </div>
            )}
            <div>
              <label className="mb-1.5 block text-xs font-bold text-ink">Email address</label>
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" required />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-bold text-ink">Password</label>
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="At least 6 characters" required minLength={6} />
            </div>
            <Button type="submit" className="w-full" disabled={busy}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
              {isSignup ? 'Create account' : 'Sign in'}
            </Button>
          </form>

          <div className="my-6 flex items-center gap-3 text-xs font-semibold text-muted-foreground">
            <span className="h-px flex-1 bg-brand-100" /> or <span className="h-px flex-1 bg-brand-100" />
          </div>
          <Button variant="outline" className="w-full" onClick={demo} disabled={busy}>
            Explore with demo account
          </Button>

          <p className="mt-6 text-center text-sm text-muted-foreground">
            {isSignup ? 'Already have an account?' : 'New to NutriPlan?'}{' '}
            <Link to={isSignup ? '/signin' : '/signup'} className="font-bold text-brand-700 hover:underline">
              {isSignup ? 'Sign in' : 'Create one'}
            </Link>
          </p>
          <Link to="/" className="mt-4 block text-center text-xs text-muted-foreground hover:text-brand-700">← Back to home</Link>
        </div>
      </div>

      <div className="relative hidden overflow-hidden bg-brand-700 p-12 text-white lg:flex lg:items-center">
        <img src="/images/hero.svg" alt="" className="absolute inset-0 h-full w-full object-cover opacity-25" />
        <div className="relative max-w-md">
          <span className="rounded-full bg-white/15 px-3 py-1.5 text-xs font-bold">Made for Indian kitchens</span>
          <h2 className="mt-6 font-display text-4xl font-extrabold leading-tight">A plan that respects your food, your goals and your time.</h2>
          <div className="mt-8 space-y-3 text-sm text-white/85">
            {['Personalised calories and macros from clinical formulas', '7-day plans across four meals with recipes', 'Allergy-safe swaps and a smart grocery list', 'AI Nutritionist with cited nutrition sources'].map((item) => (
              <div key={item} className="flex items-start gap-2.5"><Check className="mt-0.5 h-4 w-4 shrink-0 text-brand-200" />{item}</div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
