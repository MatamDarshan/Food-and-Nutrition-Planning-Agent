import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Apple, ArrowRight, BarChart3, Bot, Check, ChevronRight, Clock3, HeartPulse,
  Leaf, ListChecks, Loader2, Menu, Microscope, ShieldCheck, ShoppingBasket,
  Sparkles, Star, UtensilsCrossed, X,
} from 'lucide-react';
import { toast } from 'sonner';
import { authApi } from '../lib/api';
import { useApp } from '../lib/store';

const fade = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.22, 1, 0.36, 1] as const } },
};

const FEATURES = [
  { icon: Sparkles, title: 'Built around you', text: 'Age, activity, goal, diet, allergies, cuisines, budget and cooking time — every preference shapes your plan.' },
  { icon: BarChart3, title: 'Science you can see', text: 'Calories, macros, fibre and 17 micronutrients compared with ICMR-NIN Recommended Dietary Allowances.' },
  { icon: Bot, title: 'Nutritionist on call', text: 'Ask why a meal was chosen, request substitutions, or explore a nutrient — grounded in a FAISS nutrition knowledge base.' },
  { icon: ShoppingBasket, title: 'From plan to plate', text: 'An automatic grocery list, shopping checklist, favourites, meal history and one-tap partial regeneration.' },
];

const SAMPLE = [
  { day: 'Monday', time: '08:00', name: 'Idli with sambar', kcal: 320, macro: 'P 12g · C 52g · F 6g', slot: 'breakfast', color: 'from-amber-50 to-emerald-50' },
  { day: 'Monday', time: '13:00', name: 'Brown rice & palak paneer', kcal: 540, macro: 'P 28g · C 64g · F 18g', slot: 'lunch', color: 'from-emerald-50 to-amber-50' },
  { day: 'Monday', time: '16:30', name: 'Roasted chickpeas & fruit', kcal: 210, macro: 'P 9g · C 30g · F 5g', slot: 'snack', color: 'from-orange-50 to-emerald-50' },
  { day: 'Monday', time: '20:00', name: 'Dal tadka with roti', kcal: 480, macro: 'P 22g · C 68g · F 12g', slot: 'dinner', color: 'from-emerald-50 to-orange-50' },
];

export function Landing() {
  const navigate = useNavigate();
  const hydrate = useApp((s) => s.hydrate);
  const [busy, setBusy] = useState(false);
  const [menu, setMenu] = useState(false);

  const demo = async () => {
    setBusy(true);
    try {
      const { user } = await authApi.demo();
      useApp.getState().setUser(user);
      await hydrate();
      toast.success('Welcome to AI Nutrition Planner!');
      navigate(useApp.getState().plan ? '/app/dashboard' : '/onboarding');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Could not start the demo');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen overflow-hidden bg-cream">
      <header className="sticky top-0 z-40 border-b border-brand-100/70 bg-cream/85 backdrop-blur-xl">
        <div className="np-container flex items-center justify-between py-4">
          <Link to="/" className="flex items-center gap-2.5">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand-600 text-white shadow-glow">
              <Apple className="h-5 w-5" />
            </span>
            <span className="font-display text-lg font-extrabold">AI Nutrition Planner</span>
          </Link>
          <nav className="hidden items-center gap-8 text-sm font-semibold text-muted-foreground md:flex">
            <a href="#how" className="hover:text-brand-700">How it works</a>
            <a href="#features" className="hover:text-brand-700">Features</a>
            <a href="#science" className="hover:text-brand-700">Science</a>
            <a href="#sample" className="hover:text-brand-700">Sample plan</a>
          </nav>
          <div className="hidden items-center gap-3 md:flex">
            <Link to="/signin" className="px-3 py-2 text-sm font-semibold text-ink hover:text-brand-700">Sign in</Link>
            <Link to="/signup" className="inline-flex h-10 items-center rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white hover:bg-brand-700">Get started</Link>
          </div>
          <button onClick={() => setMenu(!menu)} className="rounded-lg p-2 md:hidden" aria-label="Toggle menu">
            {menu ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
        {menu && (
          <div className="border-t border-brand-100 bg-white px-5 py-4 md:hidden">
            <div className="flex flex-col gap-3 text-sm font-semibold">
              {[['How it works', '#how'], ['Features', '#features'], ['Science', '#science'], ['Sample plan', '#sample']].map(([label, href]) => (
                <a key={href} href={href} onClick={() => setMenu(false)}>{label}</a>
              ))}
              <Link to="/signin">Sign in</Link>
              <Link to="/signup" className="rounded-xl bg-brand-600 px-4 py-2 text-center text-white">Get started</Link>
            </div>
          </div>
        )}
      </header>

      <section className="np-gradient relative">
        <div className="np-container grid items-center gap-12 py-16 lg:grid-cols-[1.05fr_.95fr] lg:py-24">
          <motion.div initial="hidden" animate="visible" variants={fade}>
            <div className="inline-flex items-center gap-2 rounded-full border border-brand-200 bg-white/70 px-3.5 py-1.5 text-xs font-bold text-brand-700">
              <Sparkles className="h-3.5 w-3.5" /> AI-powered Indian meal planning
            </div>
            <h1 className="mt-6 font-display text-4xl font-extrabold leading-[1.08] tracking-tight sm:text-5xl lg:text-6xl">
              Eat better, <span className="text-brand-600">every single day.</span>
            </h1>
            <p className="mt-5 max-w-xl text-base leading-relaxed text-muted-foreground sm:text-lg">
              A personal nutrition planner that builds a 7-day Indian meal plan around your body, goals,
              diet and kitchen — then explains every meal, tracks 17 nutrients and answers your questions.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link to="/signup" className="inline-flex h-12 items-center gap-2 rounded-2xl bg-brand-600 px-6 font-semibold text-white shadow-glow transition hover:bg-brand-700">
                Create my free plan <ArrowRight className="h-4 w-4" />
              </Link>
              <button onClick={demo} disabled={busy} className="inline-flex h-12 items-center gap-2 rounded-2xl border border-brand-200 bg-white px-6 font-semibold text-ink transition hover:border-brand-400 disabled:opacity-60">
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <UtensilsCrossed className="h-4 w-4" />}
                Explore live demo
              </button>
            </div>
            <div className="mt-9 flex flex-wrap items-center gap-x-7 gap-y-3 text-xs font-semibold text-muted-foreground">
              <span className="inline-flex items-center gap-1.5"><Check className="h-4 w-4 text-brand-600" /> No credit card</span>
              <span className="inline-flex items-center gap-1.5"><Check className="h-4 w-4 text-brand-600" /> ICMR-NIN based</span>
              <span className="inline-flex items-center gap-1.5"><Check className="h-4 w-4 text-brand-600" /> Vegetarian friendly</span>
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, scale: 0.94 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }} className="relative">
            <div className="absolute -inset-6 rounded-[3rem] bg-gradient-to-br from-brand-200/60 to-coral/20 blur-2xl" />
            <img src="/images/hero.svg" alt="A balanced Indian thali" className="relative w-full rounded-[2.5rem] border border-white shadow-lift" />
            <div className="absolute -bottom-6 -left-4 hidden rotate-[-3deg] rounded-2xl border border-brand-100 bg-white p-4 shadow-lift sm:block">
              <div className="flex items-center gap-3">
                <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand-50 text-brand-600"><Leaf className="h-5 w-5" /></span>
                <div><p className="text-xs text-muted-foreground">Daily average</p><p className="text-lg font-extrabold">1,640 kcal</p></div>
              </div>
            </div>
            <div className="absolute -right-3 top-8 hidden rotate-[4deg] rounded-2xl border border-brand-100 bg-white p-4 shadow-lift sm:block">
              <div className="flex items-center gap-2 text-sm font-bold text-brand-700"><Star className="h-4 w-4 fill-amber-400 text-amber-400" /> 17 nutrients tracked</div>
            </div>
          </motion.div>
        </div>
      </section>

      <section className="border-y border-brand-100 bg-white py-8">
        <div className="np-container grid grid-cols-2 gap-6 text-center md:grid-cols-4">
          {[
            ['7 days', 'Complete plan'], ['17', 'Nutrients tracked'], ['4', 'Meals every day'], ['100%', 'Indian foods'],
          ].map(([value, label]) => (
            <div key={label}><p className="font-display text-2xl font-extrabold text-brand-700">{value}</p><p className="text-xs font-semibold text-muted-foreground">{label}</p></div>
          ))}
        </div>
      </section>

      <section id="how" className="np-container py-20">
        <div className="mx-auto max-w-2xl text-center">
          <p className="np-eyebrow">How it works</p>
          <h2 className="mt-3 text-3xl font-extrabold sm:text-4xl">From your profile to your plate in three steps</h2>
          <p className="mt-3 text-muted-foreground">No spreadsheets, no guesswork. Just a plan you can actually follow.</p>
        </div>
        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {[
            { n: '01', icon: HeartPulse, title: 'Tell us about you', text: 'A friendly 8-step wizard captures your body metrics, activity, goal, diet, allergies, dislikes, cuisines, budget and cooking time.' },
            { n: '02', icon: Sparkles, title: 'Get your 7-day plan', text: 'Our engine combines ICMR-NIN composition tables with clinical targets, then validates every day against calories, macros and restrictions.' },
            { n: '03', icon: ListChecks, title: 'Cook, track, ask', text: 'Open any recipe, swap a meal, check your grocery list, follow weekly trends and ask the AI Nutritionist anything.' },
          ].map(({ n, icon: Icon, title, text }, index) => (
            <motion.div key={n} initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fade} transition={{ delay: index * 0.1 }} className="np-card relative p-7">
              <span className="absolute right-6 top-5 font-display text-4xl font-extrabold text-brand-50">{n}</span>
              <span className="grid h-12 w-12 place-items-center rounded-2xl bg-brand-600 text-white"><Icon className="h-6 w-6" /></span>
              <h3 className="mt-5 text-lg font-bold">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{text}</p>
            </motion.div>
          ))}
        </div>
      </section>

      <section id="features" className="bg-white py-20">
        <div className="np-container">
          <div className="mx-auto max-w-2xl text-center">
            <p className="np-eyebrow">Everything you need</p>
            <h2 className="mt-3 text-3xl font-extrabold sm:text-4xl">A complete nutrition workspace</h2>
          </div>
          <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {FEATURES.map(({ icon: Icon, title, text }) => (
              <div key={title} className="rounded-2xl border border-brand-100 bg-cream p-6 transition hover:-translate-y-1 hover:shadow-soft">
                <Icon className="h-6 w-6 text-brand-600" />
                <h3 className="mt-4 font-bold">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="science" className="np-gradient py-20">
        <div className="np-container grid items-center gap-12 lg:grid-cols-2">
          <div>
            <p className="np-eyebrow">Nutrition science</p>
            <h2 className="mt-3 text-3xl font-extrabold sm:text-4xl">Grounded in Indian reference data</h2>
            <p className="mt-4 leading-relaxed text-muted-foreground">
              Targets start with the Mifflin–St Jeor equation for resting metabolism, adjusted for your
              activity level and goal. Food portions come from the Indian Food Composition Tables and
              household serving guides; micronutrients are compared with ICMR-NIN RDA 2020.
            </p>
            <div className="mt-6 space-y-3">
              {['Mifflin–St Jeor BMR and activity multipliers', 'IFCT 2017 food composition + ICMR-NIN RDA 2020', 'Automatic allergen, diet and exclusion validation', 'FAISS retrieval for cited nutrition guidance'].map((item) => (
                <div key={item} className="flex items-start gap-3 text-sm">
                  <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-brand-100 text-brand-700"><Check className="h-3 w-3" /></span>
                  {item}
                </div>
              ))}
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            {[
              { icon: Microscope, label: 'Food database', value: 'IFCT + ICMR/NIN', text: 'Macros, fibre, glycemic index and 17 micronutrients.' },
              { icon: ShieldCheck, label: 'Validation', value: 'Every day checked', text: '±15% calorie target, allergens, diet type and variety.' },
              { icon: Clock3, label: 'Real kitchens', value: 'Prep-aware', text: 'Cooking time and budget preferences are captured up front.' },
              { icon: Bot, label: 'RAG answers', value: 'With citations', text: 'Responses reference the source document and page.' },
            ].map(({ icon: Icon, label, value, text }) => (
              <div key={label} className="np-card p-5">
                <Icon className="h-5 w-5 text-brand-600" />
                <p className="mt-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">{label}</p>
                <p className="text-lg font-extrabold">{value}</p>
                <p className="mt-1 text-xs text-muted-foreground">{text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="sample" className="np-container py-20">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="np-eyebrow">Sample day</p>
            <h2 className="mt-3 text-3xl font-extrabold sm:text-4xl">What a plan looks like</h2>
            <p className="mt-2 text-muted-foreground">A real day from a 1,600 kcal vegetarian plan.</p>
          </div>
          <Link to="/signup" className="inline-flex items-center gap-2 text-sm font-bold text-brand-700 hover:text-brand-900">
            Build yours <ChevronRight className="h-4 w-4" />
          </Link>
        </div>
        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {SAMPLE.map((meal, index) => (
            <motion.div key={meal.slot} initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fade} transition={{ delay: index * 0.08 }} className={`overflow-hidden rounded-2xl border border-brand-100 bg-gradient-to-br ${meal.color} p-5`}>
              <img src={`/images/${meal.slot}.svg`} alt="" className="mb-4 h-32 w-full rounded-xl object-cover" />
              <div className="flex items-center justify-between text-[11px] font-bold uppercase tracking-wide text-brand-700">
                <span>{meal.slot}</span><span>{meal.time}</span>
              </div>
              <h3 className="mt-2 font-display text-base font-bold">{meal.name}</h3>
              <p className="mt-1 text-xs text-muted-foreground">{meal.macro}</p>
              <p className="mt-3 text-lg font-extrabold text-brand-700">{meal.kcal} <span className="text-xs font-semibold text-muted-foreground">kcal</span></p>
            </motion.div>
          ))}
        </div>
      </section>

      <section className="np-container pb-20">
        <div className="relative overflow-hidden rounded-[2.5rem] bg-brand-700 px-7 py-14 text-center text-white sm:px-14">
          <div className="absolute -right-16 -top-16 h-64 w-64 rounded-full bg-white/10" />
          <div className="absolute -bottom-24 -left-10 h-64 w-64 rounded-full bg-coral/30" />
          <div className="relative">
            <Sparkles className="mx-auto h-8 w-8 text-brand-200" />
            <h2 className="mt-4 text-3xl font-extrabold sm:text-4xl">Your healthiest week starts here</h2>
            <p className="mx-auto mt-3 max-w-xl text-white/75">Answer a few questions and get a complete, personalised Indian meal plan — free.</p>
            <div className="mt-7 flex flex-wrap justify-center gap-3">
              <Link to="/signup" className="inline-flex h-12 items-center gap-2 rounded-2xl bg-white px-6 font-bold text-brand-700 transition hover:bg-brand-50">
                Create my plan <ArrowRight className="h-4 w-4" />
              </Link>
              <button onClick={demo} disabled={busy} className="inline-flex h-12 items-center gap-2 rounded-2xl border border-white/40 px-6 font-semibold text-white hover:bg-white/10 disabled:opacity-60">
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Try the demo'}
              </button>
            </div>
          </div>
        </div>
      </section>

      <footer className="border-t border-brand-100 bg-white py-8">
        <div className="np-container flex flex-wrap items-center justify-between gap-4 text-xs text-muted-foreground">
          <div className="flex items-center gap-2"><Apple className="h-4 w-4 text-brand-600" /><span className="font-bold text-ink">AI-Based Food and Nutrition Planning Agent</span> · Indian nutrition, made personal.</div>
          <p>Nutrition data: ICMR-NIN RDA 2020 · IFCT 2017. Educational guidance only.</p>
        </div>
      </footer>
    </div>
  );
}
