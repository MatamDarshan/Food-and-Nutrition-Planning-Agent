import { useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft, CalendarDays, ChefHat, Clock3, Flame, Heart, Leaf, Lightbulb,
  Plus, ShieldCheck, Users, Utensils,
} from 'lucide-react';
import { toast } from 'sonner';
import { libraryApi, messageOf, planApi } from '../lib/api';
import { mealKey, useApp } from '../lib/store';
import type { Meal, Plan } from '../lib/types';
import { num, titleCase } from '../lib/utils';
import { FoodImage } from '../components/FoodImage';
import { EmptyPlan } from '../components/Layout';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Progress } from '../components/ui/progress';

export function Recipe() {
  const { day = 'Monday', meal: slot = 'lunch' } = useParams();
  const [params] = useSearchParams();
  const planId = params.get('plan') || useApp.getState().planId;
  const storedPlan = useApp((s) => s.plan);
  const favorites = useApp((s) => s.favorites);
  const setFavorites = useApp((s) => s.setFavorites);
  const setHistory = useApp((s) => s.setHistory);
  const [fetchedPlan, setFetchedPlan] = useState<Plan | null>(null);
  const [loading, setLoading] = useState(!storedPlan && !!planId);
  const [prevPlanId, setPrevPlanId] = useState(planId);

  if (prevPlanId !== planId) {
    setPrevPlanId(planId);
    setFetchedPlan(null);
    setLoading(!storedPlan && !!planId);
  }

  useEffect(() => {
    if (storedPlan || !planId) return;
    let active = true;
    planApi.get(planId)
      .then((res) => { if (active) setFetchedPlan(res.plan); })
      .catch(() => { if (active) toast.error('Could not load this recipe'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [planId, storedPlan]);

  const plan = storedPlan || fetchedPlan;

  if (loading) return <div className="np-card h-96 animate-pulse" />;
  if (!plan) return <EmptyPlan label="Create a plan first" />;

  const dayPlan = plan.days.find((d) => d.day_name.toLowerCase() === day.toLowerCase());
  const meal: Meal | null = dayPlan?.meals[slot.toLowerCase()] || null;
  if (!meal) {
    return (
      <div className="np-card p-10 text-center">
        <h2 className="text-xl font-bold">Recipe not found</h2>
        <p className="mt-2 text-sm text-muted-foreground">This meal is no longer in your plan.</p>
        <Button asChild className="mt-5"><Link to="/app/planner">Back to planner</Link></Button>
      </div>
    );
  }

  const key = mealKey(day, slot);
  const isFavorite = favorites.includes(key);
  const micros = Object.entries(meal.micronutrients || {}).filter(([, value]) => value !== null && Number(value) > 0);
  const allergens = Array.from(
    new Set(
      (meal.items || []).flatMap((item) =>
        String((item as unknown as Record<string, unknown>).allergens || '')
          .replace(/none/gi, '')
          .split(/[;,|]/)
          .map((a) => a.trim())
          .filter(Boolean),
      ),
    ),
  );

  const logMeal = async () => {
    try {
      const entries = await libraryApi.add({
        day,
        meal: slot,
        food_name: meal.items?.[0]?.food_name || meal.label,
        total_calories: meal.total_calories,
        total_protein: meal.total_protein,
        plan_id: planId || '',
      });
      setHistory(entries);
      toast.success('Meal added to your history');
    } catch (error) {
      toast.error(messageOf(error));
    }
  };

  const toggleFavorite = async () => {
    try {
      setFavorites(await libraryApi.toggle(key));
      toast.success(isFavorite ? 'Removed from favorites' : 'Saved to favorites');
    } catch {
      toast.error('Could not update favorites');
    }
  };

  return (
    <>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <Button asChild variant="ghost" size="sm"><Link to="/app/planner"><ArrowLeft className="h-4 w-4" /> Back to planner</Link></Button>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={toggleFavorite}>
            <Heart className={`h-4 w-4 ${isFavorite ? 'fill-coral text-coral' : ''}`} /> {isFavorite ? 'Saved' : 'Favorite'}
          </Button>
          <Button size="sm" onClick={logMeal}><Plus className="h-4 w-4" /> Log as eaten</Button>
        </div>
      </div>

      <div className="np-card overflow-hidden">
        <div className="relative h-64 sm:h-80">
          <FoodImage slot={slot} src={meal.image} alt={meal.label} eager className="h-full w-full" />
          <div className="absolute inset-0 bg-gradient-to-t from-ink/85 via-ink/10 to-transparent" />
          <div className="absolute inset-x-0 bottom-0 p-6 text-white sm:p-8">
            <div className="flex flex-wrap gap-2">
              <Badge className="bg-white/90 text-brand-800">{meal.label}</Badge>
              {(meal.tags || []).map((tag) => <Badge key={tag} className="bg-brand-600 text-white">{tag}</Badge>)}
            </div>
            <h1 className="mt-3 font-display text-3xl font-extrabold sm:text-4xl">
              {meal.items?.[0]?.food_name || meal.meal_name}
            </h1>
            <p className="mt-1 text-sm text-white/80">
              {meal.items?.map((item) => item.food_name).join(' + ')} · {day}
            </p>
          </div>
        </div>

        <div className="grid gap-6 p-6 sm:p-8 lg:grid-cols-[1.4fr_1fr]">
          <div className="space-y-8">
            <section>
              <h2 className="flex items-center gap-2 font-display text-lg font-bold"><Utensils className="h-5 w-5 text-brand-600" /> Ingredients with quantities</h2>
              <div className="mt-4 space-y-3">
                {(meal.ingredients || meal.items || []).map((item) => {
                  const name = 'name' in item ? item.name : (item as { food_name: string }).food_name;
                  const qty = 'quantity_g' in item ? item.quantity_g : 0;
                  const serving = 'serving' in item ? item.serving : (item as { serving_display?: string }).serving_display || '';
                  const pantry = 'pantry' in item ? item.pantry : [];
                  return (
                    <div key={name} className="flex items-start gap-3 rounded-xl border border-brand-100 p-3.5">
                      <FoodImage slot={slot} src={'image' in item ? item.image : undefined} alt={name} className="h-12 w-12 shrink-0 rounded-lg" />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="font-bold">{name}</p>
                          <Badge variant="outline">{num(qty)} g</Badge>
                        </div>
                        <p className="text-xs text-muted-foreground">{serving}</p>
                        {!!pantry.length && <p className="mt-1 text-[11px] text-muted-foreground">Pantry: {pantry.join(', ')}</p>}
                      </div>
                    </div>
                  );
                })}
              </div>
              <p className="mt-3 text-xs text-muted-foreground">
                <Users className="mr-1 inline h-3 w-3" /> Portions are for one adult and use ICMR-NIN household serving guides.
              </p>
            </section>

            <section>
              <h2 className="flex items-center gap-2 font-display text-lg font-bold"><ChefHat className="h-5 w-5 text-brand-600" /> Suggested preparation</h2>
              <div className="mt-4 space-y-3">
                {(meal.steps || []).map((step, index) => (
                  <div key={step} className="flex gap-3">
                    <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-brand-600 text-xs font-bold text-white">{index + 1}</span>
                    <p className="pt-0.5 text-sm leading-relaxed text-ink/80">{step}</p>
                  </div>
                ))}
              </div>
              <p className="mt-4 rounded-xl bg-brand-50 p-3 text-xs text-muted-foreground">{meal.note}</p>
            </section>

            <section className="rounded-2xl border border-brand-200 bg-brand-50/50 p-5">
              <h2 className="flex items-center gap-2 font-display text-lg font-bold"><Lightbulb className="h-5 w-5 text-coral" /> Why the AI recommended this</h2>
              <p className="mt-3 text-sm leading-relaxed text-ink/80">{meal.why}</p>
            </section>
          </div>

          <div className="space-y-5">
            <section className="np-card p-5">
              <h2 className="font-display text-lg font-bold">Nutrition breakdown</h2>
              <div className="mt-4 flex items-center gap-4 rounded-xl bg-orange-50 p-4">
                <Flame className="h-7 w-7 text-coral" />
                <div><p className="text-2xl font-extrabold text-coral">{num(meal.total_calories)}</p><p className="text-xs text-muted-foreground">kcal per serving</p></div>
              </div>
              <div className="mt-4 space-y-3">
                {[
                  ['Protein', meal.total_protein, 50, 'bg-brand-500'],
                  ['Carbohydrates', meal.total_carbs, 100, 'bg-amber-500'],
                  ['Fats', meal.total_fat, 30, 'bg-coral'],
                  ['Fibre', meal.total_fiber, 12, 'bg-emerald-400'],
                ].map(([label, value, max, color]) => (
                  <div key={label as string}>
                    <div className="flex justify-between text-xs font-semibold"><span>{label as string}</span><span>{num(value as number, 1)} g</span></div>
                    <Progress value={((value as number) / (max as number)) * 100} indicatorClassName={color as string} className="mt-1 h-1.5" />
                  </div>
                ))}
              </div>
              <div className="mt-5 flex flex-wrap gap-3 border-t border-brand-100 pt-4 text-xs text-muted-foreground">
                <span className="inline-flex items-center gap-1"><Clock3 className="h-3.5 w-3.5" /> {meal.prep_time_minutes ?? 15} min prep</span>
                <span className="inline-flex items-center gap-1"><ChefHat className="h-3.5 w-3.5" /> {meal.cook_time_minutes ?? 20} min cook</span>
                <span className="inline-flex items-center gap-1"><CalendarDays className="h-3.5 w-3.5" /> {meal.suggested_time || 'Anytime'}</span>
              </div>
            </section>

            <section className="np-card p-5">
              <h2 className="flex items-center gap-2 font-display text-lg font-bold"><Leaf className="h-5 w-5 text-brand-600" /> Micronutrients</h2>
              <div className="mt-4 grid grid-cols-2 gap-2">
                {micros.slice(0, 12).map(([key, value]) => (
                  <div key={key} className="rounded-lg bg-brand-50 p-2.5">
                    <p className="text-[10px] font-semibold text-muted-foreground">{titleCase(key.replace(/_mcg$|_mg$|_g$/, ''))}</p>
                    <p className="text-sm font-bold">{num(Number(value), 2)} <span className="text-[10px] font-normal text-muted-foreground">{key.endsWith('mcg') ? 'µg' : 'mg'}</span></p>
                  </div>
                ))}
                {!micros.length && <p className="col-span-2 text-xs text-muted-foreground">Not reported in IFCT for these foods.</p>}
              </div>
            </section>

            <section className="np-card p-5">
              <h2 className="flex items-center gap-2 font-display text-lg font-bold"><ShieldCheck className="h-5 w-5 text-brand-600" /> Allergens & diet</h2>
              <p className="mt-3 text-xs font-semibold text-muted-foreground">Diet compatibility</p>
              <Badge className="mt-1" variant="success">{titleCase(useApp.getState().profile?.diet_type || 'veg')} compliant</Badge>
              <p className="mt-4 text-xs font-semibold text-muted-foreground">Allergens in this meal</p>
              <div className="mt-1 flex flex-wrap gap-2">
                {allergens.length ? allergens.map((a) => <Badge key={a} variant="warning">{titleCase(a)}</Badge>) : <Badge variant="success">None flagged</Badge>}
              </div>
              <p className="mt-4 text-[11px] leading-relaxed text-muted-foreground">
                Allergen filtering is applied by the planner using both the food database tags and ingredient lists.
              </p>
            </section>
          </div>
        </div>
      </div>
    </>
  );
}
