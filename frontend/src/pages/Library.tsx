import { Link } from 'react-router-dom';
import { CalendarDays, Clock3, Flame, Heart, History, Utensils } from 'lucide-react';
import { useApp, mealKey } from '../lib/store';
import { num } from '../lib/utils';
import { EmptyPlan, PageHeader } from '../components/Layout';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { FoodImage } from '../components/FoodImage';

export function Library() {
  const plan = useApp((s) => s.plan);
  const favorites = useApp((s) => s.favorites);
  const history = useApp((s) => s.history);
  const planId = useApp((s) => s.planId);

  const savedMeals = (plan?.days || []).flatMap((day) =>
    Object.entries(day.meals)
      .filter(([slot]) => favorites.includes(mealKey(day.day_name, slot)))
      .map(([slot, meal]) => ({ day: day.day_name, slot, meal })),
  );

  return (
    <>
      <PageHeader
        eyebrow="Your food library"
        title="Favorites & meal history"
        description="Quickly return to the meals you loved and keep track of what you've eaten."
      />

      <Tabs defaultValue="favorites">
        <TabsList>
          <TabsTrigger value="favorites"><Heart className="mr-1 inline h-3.5 w-3.5" /> Favorites ({favorites.length})</TabsTrigger>
          <TabsTrigger value="history"><History className="mr-1 inline h-3.5 w-3.5" /> Meal history ({history.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="favorites">
          {!plan ? <EmptyPlan label="Create a plan first" /> : savedMeals.length ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {savedMeals.map(({ day, slot, meal }) => (
                <Link
                  key={`${day}-${slot}`}
                  to={`/app/meal/${encodeURIComponent(day)}/${slot}?plan=${planId || ''}`}
                  className="np-card group overflow-hidden transition hover:-translate-y-1 hover:shadow-lift"
                >
                  <FoodImage slot={slot} src={meal.image} alt={meal.label} className="h-40 w-full transition-transform duration-500 group-hover:scale-105" />
                  <div className="p-4">
                    <div className="flex items-center justify-between">
                      <Badge>{meal.label}</Badge>
                      <span className="text-xs text-muted-foreground">{day}</span>
                    </div>
                    <h3 className="mt-2 font-bold">{meal.items?.[0]?.food_name || meal.meal_name}</h3>
                    <p className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
                      <span className="inline-flex items-center gap-1"><Flame className="h-3 w-3" /> {num(meal.total_calories)} kcal</span>
                      <span>{num(meal.total_protein)}g protein</span>
                    </p>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <div className="np-card p-10 text-center">
              <Heart className="mx-auto h-9 w-9 text-brand-300" />
              <h3 className="mt-4 font-bold">No favorites yet</h3>
              <p className="mt-1 text-sm text-muted-foreground">Tap the heart on any meal card to save it here.</p>
              <Link to="/app/planner" className="mt-4 inline-block text-sm font-bold text-brand-700 hover:underline">Browse your planner →</Link>
            </div>
          )}
        </TabsContent>

        <TabsContent value="history">
          {history.length ? (
            <div className="np-card divide-y divide-brand-100">
              {history.map((entry) => (
                <div key={String(entry.id)} className="flex flex-wrap items-center gap-4 p-4">
                  <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand-50 text-brand-600"><Utensils className="h-5 w-5" /></span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-bold">{String(entry.food_name || entry.meal || 'Meal')}</p>
                    <p className="text-xs text-muted-foreground">
                      <CalendarDays className="mr-1 inline h-3 w-3" /> {String(entry.day || '—')} · {String(entry.meal || 'meal')}
                    </p>
                  </div>
                  <Badge variant="outline"><Flame className="h-3 w-3" /> {num(Number(entry.total_calories || 0))} kcal</Badge>
                  <Badge variant="success">{num(Number(entry.total_protein || 0))}g protein</Badge>
                  <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                    <Clock3 className="h-3 w-3" /> {new Date(String(entry.eaten_at)).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="np-card p-10 text-center">
              <History className="mx-auto h-9 w-9 text-brand-300" />
              <h3 className="mt-4 font-bold">Nothing logged yet</h3>
              <p className="mt-1 text-sm text-muted-foreground">Open a recipe and tap "Log as eaten" to build your history.</p>
              <Link to="/app/planner" className="mt-4 inline-block text-sm font-bold text-brand-700 hover:underline">Open meal planner →</Link>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </>
  );
}
