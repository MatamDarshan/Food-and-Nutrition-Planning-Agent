import { useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, CheckCircle2, Download, Loader2, RefreshCw, ShoppingBasket, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { messageOf, planApi } from '../lib/api';
import { useApp } from '../lib/store';
import { num } from '../lib/utils';
import { EmptyPlan, PageHeader } from '../components/Layout';
import { MealCard } from '../components/MealCard';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';

export function Planner() {
  const plan = useApp((s) => s.plan);
  const planId = useApp((s) => s.planId);
  const setPlan = useApp((s) => s.setPlan);
  const [day, setDay] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  if (!plan || !planId) return <EmptyPlan label="Build my planner" />;

  const activeDay = day || plan.days[0].day_name;
  const dayPlan = plan.days.find((d) => d.day_name === activeDay) || plan.days[0];

  const update = async (meal: string, action: 'swap' | 'regenerate', foodName?: string) => {
    const key = `${dayPlan.day_name}-${meal}`;
    setBusy(key);
    try {
      const response = action === 'swap'
        ? await planApi.swap(planId, dayPlan.day_name, meal, foodName || '')
        : await planApi.regenerate(planId, dayPlan.day_name, meal);
      setPlan(response.plan);
      toast.success(action === 'swap' ? 'Meal swapped successfully' : 'Meal regenerated');
    } catch (error) {
      toast.error(messageOf(error));
    } finally {
      setBusy(null);
    }
  };

  const exportPlan = async () => {
    setExporting(true);
    try {
      await planApi.export(planId);
      toast.success('Plan exported as PDF');
    } catch (error) {
      toast.error(messageOf(error));
    } finally {
      setExporting(false);
    }
  };

  const validation = plan.validation_result;

  return (
    <>
      <PageHeader
        eyebrow="Seven days, four meals, zero guesswork"
        title="Your weekly meal planner"
        description="Swap a food, regenerate one meal, or dive into the full recipe. The rest of your week stays exactly as it is."
        action={
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline"><Link to="/app/grocery"><ShoppingBasket className="h-4 w-4" /> Grocery list</Link></Button>
            <Button onClick={() => void exportPlan()} disabled={exporting}>
              {exporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
              Export PDF
            </Button>
          </div>
        }
      />

      {validation && (
        <div className={`mb-5 flex items-start gap-3 rounded-2xl border p-4 text-sm ${validation.is_valid ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-amber-200 bg-amber-50 text-amber-900'}`}>
          {validation.is_valid ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /> : <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />}
          <div>
            <p className="font-bold">{validation.is_valid ? 'Your plan passed all nutrition checks' : `${validation.issues.length} item(s) to review`}</p>
            <p className="mt-0.5 text-xs opacity-85">
              {validation.is_valid
                ? `Average daily calories are ${num(validation.planned_calories)} against a ${num(validation.target_calories)} kcal target.`
                : validation.issues.join(' · ')}
            </p>
          </div>
        </div>
      )}

      <Tabs value={activeDay} onValueChange={setDay}>
        <TabsList className="mb-5">
          {plan.days.map((d) => (
            <TabsTrigger key={d.day_name} value={d.day_name}>
              {d.day_name.slice(0, 3)}
              <span className="ml-1.5 hidden text-[10px] opacity-60 sm:inline">{num(d.total_calories)} kcal</span>
            </TabsTrigger>
          ))}
        </TabsList>

        {plan.days.map((d) => (
          <TabsContent key={d.day_name} value={d.day_name}>
            <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-brand-100 bg-white px-5 py-4">
              <div>
                <p className="font-display text-lg font-extrabold">{d.day_name}</p>
                <p className="text-xs text-muted-foreground">
                  {num(d.total_calories)} kcal · {num(d.total_protein)}g protein · {num(d.total_carbs)}g carbs · {num(d.total_fat)}g fats
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge variant="success"><CheckCircle2 className="h-3 w-3" /> Diet compliant</Badge>
                <Badge variant="outline"><Sparkles className="h-3 w-3" /> {num(d.total_fiber)}g fibre</Badge>
                <Badge variant={Math.abs(d.calorie_deviation_pct) > 15 ? 'warning' : 'muted'}>
                  {d.calorie_deviation_pct > 0 ? '+' : ''}{num(d.calorie_deviation_pct, 1)}% vs target
                </Badge>
              </div>
            </div>

            <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
              {Object.entries(d.meals).map(([slot, meal]) => (
                <MealCard
                  key={slot}
                  meal={meal}
                  day={d.day_name}
                  busy={busy === `${d.day_name}-${slot}`}
                  onSwap={(foodName) => update(slot, 'swap', foodName)}
                  onRegenerate={() => update(slot, 'regenerate')}
                />
              ))}
            </div>

            <div className="mt-6 rounded-2xl border border-brand-100 bg-white p-5">
              <div className="flex items-center justify-between">
                <h3 className="font-bold">Day nutrition breakdown</h3>
                <Badge variant="muted"><RefreshCw className="h-3 w-3" /> Recalculated after every change</Badge>
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-4">
                {[
                  ['Calories', `${num(d.total_calories)} kcal`, 'text-brand-700'],
                  ['Protein', `${num(d.total_protein)} g`, 'text-brand-700'],
                  ['Carbohydrates', `${num(d.total_carbs)} g`, 'text-amber-600'],
                  ['Fats', `${num(d.total_fat)} g`, 'text-coral'],
                ].map(([label, value, color]) => (
                  <div key={label} className="rounded-xl bg-brand-50/60 p-4">
                    <p className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground">{label}</p>
                    <p className={`mt-1 text-lg font-extrabold ${color}`}>{value}</p>
                  </div>
                ))}
              </div>
            </div>
          </TabsContent>
        ))}
      </Tabs>
    </>
  );
}
