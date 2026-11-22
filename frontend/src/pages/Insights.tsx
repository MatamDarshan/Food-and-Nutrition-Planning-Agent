import { useEffect, useState } from 'react';
import {
  Activity, AlertTriangle, ArrowUpRight, CheckCircle2, Info, Leaf, Loader2, Microscope,
} from 'lucide-react';
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { insightsApi, messageOf } from '../lib/api';
import type { InsightData, Nutrient } from '../lib/types';
import { useApp } from '../lib/store';
import { num } from '../lib/utils';
import { EmptyPlan, PageHeader } from '../components/Layout';
import { Badge } from '../components/ui/badge';
import { CardSkeleton } from '../components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';

function NutrientCard({ nutrient }: { nutrient: Nutrient }) {
  const statusStyle =
    nutrient.status === 'low' ? 'border-coral/40 bg-orange-50/60'
      : nutrient.status === 'high' ? 'border-amber-200 bg-amber-50/60'
        : 'border-emerald-200 bg-emerald-50/40';
  const bar = nutrient.status === 'low' ? 'bg-coral' : nutrient.status === 'high' ? 'bg-amber-500' : 'bg-brand-500';
  return (
    <div className={`rounded-2xl border p-4 ${statusStyle}`}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs font-bold text-muted-foreground">{nutrient.category}</p>
          <p className="font-display text-base font-extrabold">{nutrient.label}</p>
        </div>
        {nutrient.status === 'low'
          ? <AlertTriangle className="h-4 w-4 shrink-0 text-coral" />
          : <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />}
      </div>
      <p className="mt-3 text-xl font-extrabold">{num(nutrient.average, 2)} <span className="text-xs font-semibold text-muted-foreground">{nutrient.unit} / {num(nutrient.target)}{nutrient.unit}</span></p>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/80">
        <div className={`h-full rounded-full ${bar} transition-all`} style={{ width: `${Math.min(100, nutrient.percent)}%` }} />
      </div>
      <div className="mt-1.5 flex justify-between text-[10px] font-semibold text-muted-foreground">
        <span>{num(nutrient.percent)}% of RDA</span>
        <span className="capitalize">{nutrient.status === 'low' ? 'Needs attention' : nutrient.status === 'high' ? 'Above RDA' : 'On track'}</span>
      </div>
      {nutrient.status === 'low' && !!nutrient.foods.length && (
        <p className="mt-3 border-t border-white/70 pt-2 text-[11px] text-muted-foreground">
          <Leaf className="mr-1 inline h-3 w-3 text-brand-600" /> Try {nutrient.foods.slice(0, 3).join(', ')}.
        </p>
      )}
    </div>
  );
}

export function Insights() {
  const plan = useApp((s) => s.plan);
  const planId = useApp((s) => s.planId);
  const [data, setData] = useState<InsightData | null>(null);
  const [error, setError] = useState('');
  const [prevPlanId, setPrevPlanId] = useState(planId);

  if (prevPlanId !== planId) {
    setPrevPlanId(planId);
    setData(null);
    setError('');
  }

  useEffect(() => {
    if (!planId) return;
    let active = true;
    insightsApi.get(planId)
      .then((result) => { if (active) setData(result); })
      .catch((e) => { if (active) setError(messageOf(e)); });
    return () => { active = false; };
  }, [planId]);

  if (!plan) return <EmptyPlan label="Create a plan to see insights" />;
  if (error) return <div className="np-card p-8 text-center text-sm text-red-600">{error}</div>;
  if (!data) return <div className="space-y-5"><CardSkeleton /><CardSkeleton /></div>;

  const macroChart = data.macros.map((m) => ({ name: m.label, average: m.average, target: m.target }));
  const microChart = data.micronutrients
    .filter((n) => ['iron_mg', 'calcium_mg', 'zinc_mg', 'vitamin_a_mcg', 'vitamin_b12_mcg', 'vitamin_c_mg', 'vitamin_d_mcg', 'vitamin_b9_mcg'].includes(n.key))
    .map((n) => ({ name: n.label.replace(/ \(.*\)/, ''), percent: n.percent, average: n.average, target: n.target, unit: n.unit }));

  return (
    <>
      <PageHeader
        eyebrow="Beyond calories"
        title="Nutrition insights"
        description="Compare your weekly intake with ICMR-NIN Recommended Dietary Allowances and see where to focus next."
        action={<Badge variant="outline"><Microscope className="h-3 w-3" /> {num(data.micronutrients.length)} nutrients</Badge>}
      />

      <div className="mb-5 flex items-start gap-3 rounded-2xl border border-brand-100 bg-white p-4 text-xs text-muted-foreground">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" />
        <p><strong className="text-ink">Reference:</strong> {data.rda_population}. {data.rda_source}. Nutrients marked "not reported" are unavailable in IFCT for the foods in your plan.</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {data.macros.map((macro, index) => (
          <div key={macro.key} className="np-card p-5">
            <div className="flex items-center justify-between">
              <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">{macro.label}</p>
              <span className={`h-2.5 w-2.5 rounded-full ${['bg-brand-500', 'bg-amber-500', 'bg-coral', 'bg-emerald-400'][index]}`} />
            </div>
            <p className="mt-3 font-display text-2xl font-extrabold">{num(macro.average, 1)}<span className="text-sm text-muted-foreground">/{num(macro.target)}{macro.unit}</span></p>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-brand-50">
              <div className="h-full rounded-full bg-brand-500" style={{ width: `${Math.min(100, (macro.average / (macro.target || 1)) * 100)}%` }} />
            </div>
          </div>
        ))}
      </div>

      <Tabs defaultValue="trends" className="mt-6">
        <TabsList>
          <TabsTrigger value="trends"><Activity className="mr-1 inline h-3.5 w-3.5" /> Weekly trends</TabsTrigger>
          <TabsTrigger value="micros"><Microscope className="mr-1 inline h-3.5 w-3.5" /> Micronutrients</TabsTrigger>
          <TabsTrigger value="focus"><Leaf className="mr-1 inline h-3.5 w-3.5" /> Focus areas</TabsTrigger>
        </TabsList>

        <TabsContent value="trends" className="space-y-5">
          <div className="np-card p-5">
            <h3 className="font-bold">Calories & protein by day</h3>
            <p className="text-xs text-muted-foreground">Daily totals across your 7-day plan</p>
            <div className="mt-4 h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data.trend} margin={{ top: 8, right: 12, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e6f4ec" vertical={false} />
                  <XAxis dataKey="day" tickLine={false} axisLine={false} fontSize={11} stroke="#8ca095" />
                  <YAxis tickLine={false} axisLine={false} fontSize={11} stroke="#8ca095" />
                  <Tooltip contentStyle={{ borderRadius: 12, border: '1px solid #d6f5e3' }} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Line type="monotone" dataKey="calories" name="Calories (kcal)" stroke="#219e68" strokeWidth={2.5} dot={{ r: 3 }} />
                  <Line type="monotone" dataKey="protein" name="Protein (g)" stroke="#f48563" strokeWidth={2.5} dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="np-card p-5">
            <h3 className="font-bold">Macro distribution by day</h3>
            <div className="mt-4 h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.trend} margin={{ top: 8, right: 12, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e6f4ec" vertical={false} />
                  <XAxis dataKey="day" tickLine={false} axisLine={false} fontSize={11} stroke="#8ca095" />
                  <YAxis tickLine={false} axisLine={false} fontSize={11} stroke="#8ca095" />
                  <Tooltip contentStyle={{ borderRadius: 12, border: '1px solid #d6f5e3' }} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar dataKey="carbs" name="Carbs (g)" fill="#e5a53c" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="fats" name="Fats (g)" fill="#f48563" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="np-card p-5">
            <h3 className="font-bold">Macros vs target</h3>
            <div className="mt-4 h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={macroChart} margin={{ top: 8, right: 12, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e6f4ec" vertical={false} />
                  <XAxis dataKey="name" tickLine={false} axisLine={false} fontSize={11} stroke="#8ca095" />
                  <YAxis tickLine={false} axisLine={false} fontSize={11} stroke="#8ca095" />
                  <Tooltip contentStyle={{ borderRadius: 12, border: '1px solid #d6f5e3' }} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar dataKey="average" name="Your average" fill="#219e68" radius={[6, 6, 0, 0]} />
                  <Bar dataKey="target" name="Target" fill="#d6f5e3" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="micros">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {data.micronutrients.map((nutrient) => <NutrientCard key={nutrient.key} nutrient={nutrient} />)}
          </div>
          <div className="np-card mt-5 p-5">
            <h3 className="font-bold">Key nutrients: % of RDA</h3>
            <div className="mt-4 h-80">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={microChart} layout="vertical" margin={{ top: 4, right: 24, left: 36, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e6f4ec" horizontal={false} />
                  <XAxis type="number" domain={[0, 150]} tickLine={false} axisLine={false} fontSize={11} stroke="#8ca095" />
                  <YAxis type="category" dataKey="name" tickLine={false} axisLine={false} fontSize={11} stroke="#8ca095" width={90} />
                  <Tooltip formatter={(v) => [`${num(Number(v))}%`, 'of RDA']} contentStyle={{ borderRadius: 12, border: '1px solid #d6f5e3' }} />
                  <Bar dataKey="percent" name="% RDA" fill="#43bd84" radius={[0, 6, 6, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="focus">
          {data.focus.length ? (
            <>
              <div className="mb-5 flex items-center gap-3 rounded-2xl border border-orange-200 bg-orange-50 p-4 text-sm text-orange-900">
                <AlertTriangle className="h-5 w-5 shrink-0" />
                <p>{data.focus.length} nutrient{data.focus.length > 1 ? 's are' : ' is'} below 70% of the daily RDA on average. Small food swaps can close the gap.</p>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                {data.focus.map((nutrient) => (
                  <div key={nutrient.key} className="np-card p-5">
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">{nutrient.label}</p>
                        <p className="mt-1 text-2xl font-extrabold text-coral">{num(nutrient.percent)}% <span className="text-xs font-semibold text-muted-foreground">of RDA</span></p>
                      </div>
                      <ArrowUpRight className="h-5 w-5 text-coral" />
                    </div>
                    <p className="mt-3 text-xs text-muted-foreground">Foods that can help:</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {nutrient.foods.map((food) => <Badge key={food} variant="success"><Leaf className="h-3 w-3" /> {food}</Badge>)}
                    </div>
                    <p className="mt-4 text-[11px] text-muted-foreground">Average {num(nutrient.average, 2)} {nutrient.unit} against {num(nutrient.target)} {nutrient.unit} RDA.</p>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="np-card p-10 text-center">
              <CheckCircle2 className="mx-auto h-10 w-10 text-emerald-500" />
              <h3 className="mt-4 text-lg font-bold">Nicely done!</h3>
              <p className="mt-2 text-sm text-muted-foreground">All tracked nutrients are at or above 70% of their RDA in your plan.</p>
            </div>
          )}
        </TabsContent>
      </Tabs>

      {data.validation && !data.validation.is_valid && (
        <div className="np-card mt-5 border-amber-200 bg-amber-50 p-5">
          <h3 className="flex items-center gap-2 font-bold text-amber-900"><Loader2 className="h-4 w-4" /> Validation notes</h3>
          <ul className="mt-3 list-inside list-disc space-y-1 text-xs text-amber-900/80">
            {data.validation.issues.map((issue) => <li key={issue}>{issue}</li>)}
          </ul>
        </div>
      )}
    </>
  );
}
