import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity, ArrowRight, Bot, CheckCircle2, Flame, Leaf, Plus, TrendingUp, Utensils,
} from 'lucide-react';
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { insightsApi } from '../lib/api';
import type { InsightData } from '../lib/types';
import { useApp } from '../lib/store';
import { num } from '../lib/utils';
import { PageHeader, EmptyPlan } from '../components/Layout';
import { DashboardSkeleton } from '../components/ui/skeleton';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Progress } from '../components/ui/progress';
import { FoodImage } from '../components/FoodImage';

function Ring({ value, target, label }: { value: number; target: number; label: string }) {
  const pct = target ? Math.min(100, (value / target) * 100) : 0;
  const radius = 58;
  const circumference = 2 * Math.PI * radius;
  return (
    <div className="relative h-40 w-40 shrink-0">
      <svg viewBox="0 0 140 140" className="h-full w-full -rotate-90">
        <circle cx="70" cy="70" r={radius} fill="none" stroke="#e6f4ec" strokeWidth="12" />
        <circle
          cx="70" cy="70" r={radius} fill="none" stroke="#219e68" strokeWidth="12" strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - pct / 100)}
          className="transition-all duration-1000"
        />
      </svg>
      <div className="absolute inset-0 grid place-content-center text-center">
        <Flame className="mx-auto h-4 w-4 text-coral" />
        <p className="text-2xl font-extrabold">{num(value)}</p>
        <p className="text-[10px] font-semibold text-muted-foreground">{label} / {num(target)}</p>
      </div>
    </div>
  );
}

export function Dashboard() {
  const plan = useApp((s) => s.plan);
  const targets = useApp((s) => s.targets);
  const history = useApp((s) => s.history);
  const user = useApp((s) => s.user);
  const hydrated = useApp((s) => s.hydrated);
  const planId = useApp((s) => s.planId);
  const [insights, setInsights] = useState<InsightData | null>(null);

  useEffect(() => {
    if (planId) insightsApi.get(planId).then(setInsights).catch(() => setInsights(null));
  }, [planId]);

  const consumed = useMemo(() => {
    const today = new Date().toDateString();
    return history
      .filter((entry) => new Date(String(entry.eaten_at)).toDateString() === today)
      .reduce((sum, entry) => sum + Number(entry.total_calories || entry.calories || 0), 0);
  }, [history]);

  if (!hydrated) return <DashboardSkeleton />;
  if (!plan || !targets) return <EmptyPlan />;

  const today = plan.days[new Date().getDay() === 0 ? 6 : new Date().getDay() - 1] || plan.days[0];
  const avg = plan.weekly_averages;
  const macroData = [
    { name: 'Protein', value: avg.avg_protein, target: targets.protein_g, color: '#219e68' },
    { name: 'Carbs', value: avg.avg_carbs, target: targets.carbs_g, color: '#e5a53c' },
    { name: 'Fats', value: avg.avg_fat, target: targets.fats_g, color: '#f48563' },
  ];
  const trend = insights?.trend || plan.days.map((d) => ({ day: d.day_name.slice(0, 3), calories: d.total_calories, protein: d.total_protein, carbs: d.total_carbs, fats: d.total_fat }));

  return (
    <>
      <PageHeader
        eyebrow="Your nutrition at a glance"
        title={`Good to see you, ${user?.name?.split(' ')[0] || 'there'} 👋`}
        description="Here's how your plan is shaping up this week. Small consistent steps add up."
        action={
          <Button asChild variant="outline">
            <Link to="/app/planner"><Utensils className="h-4 w-4" /> Open weekly planner</Link>
          </Button>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[auto_1fr]">
        <div className="np-card flex flex-col items-center gap-4 p-6 sm:flex-row lg:w-[420px]">
          <Ring value={consumed} target={targets.calorie_target} label="kcal eaten" />
          <div className="flex-1">
            <p className="np-eyebrow">Daily target</p>
            <p className="mt-1 font-display text-3xl font-extrabold">{num(targets.calorie_target)} <span className="text-base font-semibold text-muted-foreground">kcal</span></p>
            <div className="mt-3 space-y-1.5 text-xs text-muted-foreground">
              <p>BMR {num(targets.bmr)} · TDEE {num(targets.tdee)}</p>
              <p>BMI {num(targets.bmi, 1)} · {targets.bmi_category}</p>
            </div>
            <Badge className="mt-3" variant="success"><TrendingUp className="h-3 w-3" /> Weekly avg {num(avg.avg_calories)} kcal</Badge>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          {macroData.map((macro) => (
            <div key={macro.name} className="np-card flex flex-col justify-between p-5">
              <div className="flex items-center justify-between">
                <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">{macro.name}</p>
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: macro.color }} />
              </div>
              <p className="mt-3 font-display text-2xl font-extrabold">{num(macro.value)}<span className="text-sm text-muted-foreground">/{num(macro.target)}g</span></p>
              <div className="mt-3"><Progress value={(macro.value / (macro.target || 1)) * 100} indicatorClassName="" /></div>
              <p className="mt-2 text-[11px] text-muted-foreground">{Math.round((macro.value / (macro.target || 1)) * 100)}% of daily target</p>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <div className="np-card p-5 lg:col-span-2">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h3 className="font-bold">Weekly calorie trend</h3>
              <p className="text-xs text-muted-foreground">Daily totals against your target of {num(targets.calorie_target)} kcal</p>
            </div>
            <Badge variant="outline"><Activity className="h-3 w-3" /> 7 days</Badge>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trend} margin={{ top: 8, right: 8, left: -22, bottom: 0 }}>
                <defs>
                  <linearGradient id="cal" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#219e68" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#219e68" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e6f4ec" vertical={false} />
                <XAxis dataKey="day" tickLine={false} axisLine={false} fontSize={11} stroke="#8ca095" />
                <YAxis tickLine={false} axisLine={false} fontSize={11} stroke="#8ca095" />
                <Tooltip formatter={(v) => [`${num(Number(v))} kcal`, 'Calories']} contentStyle={{ borderRadius: 12, border: '1px solid #d6f5e3' }} />
                <Area type="monotone" dataKey="calories" stroke="#219e68" strokeWidth={2.5} fill="url(#cal)" dot={{ r: 3, fill: '#219e68' }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="np-card flex flex-col p-5">
          <div className="flex items-center gap-2">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand-50 text-brand-600"><Bot className="h-5 w-5" /></span>
            <div><h3 className="font-bold">AI Nutritionist</h3><p className="text-xs text-muted-foreground">Always on, always personal</p></div>
          </div>
          <p className="mt-4 flex-1 text-sm leading-relaxed text-muted-foreground">
            Ask about a food swap, a nutrient, or why today's meal was chosen. Answers use your plan and cited nutrition sources.
          </p>
          <Button asChild className="mt-4 w-full"><Link to="/app/nutritionist">Ask a question <ArrowRight className="h-4 w-4" /></Link></Button>
        </div>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <div className="np-card p-5 lg:col-span-2">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="font-bold">Today's meals · {today.day_name}</h3>
            <Link to="/app/planner" className="text-xs font-bold text-brand-700 hover:underline">Full planner →</Link>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {Object.entries(today.meals).map(([slot, meal]) => (
              <Link
                key={slot}
                to={`/app/meal/${encodeURIComponent(today.day_name)}/${slot}?plan=${planId || ''}`}
                className="flex items-center gap-3 rounded-xl border border-brand-100 p-2.5 transition hover:border-brand-300 hover:bg-brand-50/40"
              >
                <FoodImage slot={slot} src={meal.image} alt={meal.label} className="h-14 w-14 shrink-0 rounded-lg" />
                <div className="min-w-0 flex-1">
                  <p className="text-[10px] font-bold uppercase tracking-wide text-brand-600">{meal.label}</p>
                  <p className="truncate text-sm font-bold">{meal.items?.[0]?.food_name || slot}</p>
                  <p className="text-xs text-muted-foreground">{num(meal.total_calories)} kcal · {num(meal.total_protein)}g protein</p>
                </div>
              </Link>
            ))}
          </div>
        </div>

        <div className="np-card p-5">
          <div className="flex items-center gap-2">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-orange-50 text-coral"><Leaf className="h-5 w-5" /></span>
            <div><h3 className="font-bold">Personalised insights</h3><p className="text-xs text-muted-foreground">From your weekly averages</p></div>
          </div>
          <div className="mt-4 space-y-3">
            {(insights?.focus || []).slice(0, 3).map((nutrient) => (
              <div key={nutrient.key} className="rounded-xl bg-brand-50/60 p-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold">{nutrient.label}</span>
                  <span className="font-bold text-coral">{num(nutrient.percent)}% RDA</span>
                </div>
                <p className="mt-1 text-[11px] text-muted-foreground">Try: {nutrient.foods.slice(0, 3).join(', ')}</p>
              </div>
            ))}
            {!insights?.focus?.length && (
              <div className="flex items-start gap-2 rounded-xl bg-emerald-50 p-3 text-xs text-emerald-800">
                <CheckCircle2 className="h-4 w-4 shrink-0" /> All tracked nutrients are within range this week.
              </div>
            )}
          </div>
          <Button asChild variant="outline" className="mt-4 w-full"><Link to="/app/insights">See all insights <ArrowRight className="h-4 w-4" /></Link></Button>
        </div>
      </div>

      <div className="np-card mt-5 flex flex-wrap items-center justify-between gap-4 p-5">
        <div>
          <p className="font-bold">Keep your kitchen ready</p>
          <p className="text-xs text-muted-foreground">Your grocery list is generated automatically from this week's recipes.</p>
        </div>
        <div className="flex gap-2">
          <Button asChild variant="secondary"><Link to="/app/grocery"><Plus className="h-4 w-4" /> View grocery list</Link></Button>
          <Button asChild variant="ghost"><Link to="/app/planner">Refine plan <ArrowRight className="h-4 w-4" /></Link></Button>
        </div>
      </div>

      <div className="mt-6 np-card p-5">
        <h3 className="font-bold">Macro balance this week</h3>
        <div className="mt-4 h-52">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={macroData} margin={{ top: 4, right: 8, left: -22, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e6f4ec" vertical={false} />
              <XAxis dataKey="name" tickLine={false} axisLine={false} fontSize={11} stroke="#8ca095" />
              <YAxis tickLine={false} axisLine={false} fontSize={11} stroke="#8ca095" />
              <Tooltip formatter={(v) => [`${num(Number(v))} g`, 'Daily average']} contentStyle={{ borderRadius: 12, border: '1px solid #d6f5e3' }} />
              <Bar dataKey="value" radius={[8, 8, 0, 0]}>
                {macroData.map((entry) => <Cell key={entry.name} fill={entry.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </>
  );
}
