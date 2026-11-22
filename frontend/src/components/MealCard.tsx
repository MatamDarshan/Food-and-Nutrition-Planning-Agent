import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeftRight, BookOpen, Clock3, Flame, Heart, Lightbulb, Loader2, RefreshCw, Utensils,
} from 'lucide-react';
import { toast } from 'sonner';
import { foodApi, libraryApi } from '../lib/api';
import type { Meal, Substitute } from '../lib/types';
import { mealKey, useApp } from '../lib/store';
import { num } from '../lib/utils';
import { FoodImage } from './FoodImage';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from './ui/dialog';

export function MealCard({
  meal,
  day,
  onSwap,
  onRegenerate,
  busy = false,
}: {
  meal: Meal;
  day: string;
  onSwap: (foodName: string) => Promise<void>;
  onRegenerate: () => Promise<void>;
  busy?: boolean;
}) {
  const navigate = useNavigate();
  const favorites = useApp((s) => s.favorites);
  const setFavorites = useApp((s) => s.setFavorites);
  const planId = useApp((s) => s.planId);
  const [swapOpen, setSwapOpen] = useState(false);
  const [whyOpen, setWhyOpen] = useState(false);
  const [options, setOptions] = useState<Substitute[]>([]);
  const [loadingOptions, setLoadingOptions] = useState(false);
  const slot = meal.slot || 'lunch';
  const key = mealKey(day, slot);
  const isFavorite = favorites.includes(key);
  const primary = meal.items?.[0]?.food_name || meal.meal_name || slot;

  const openSwap = async () => {
    setSwapOpen(true);
    setLoadingOptions(true);
    try {
      setOptions(await foodApi.substitutes(primary, slot));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Could not load substitutes');
    } finally {
      setLoadingOptions(false);
    }
  };

  const applySwap = async (name: string) => {
    await onSwap(name);
    setSwapOpen(false);
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
    <div className="np-card group flex h-full flex-col overflow-hidden transition-all duration-300 hover:-translate-y-1 hover:shadow-lift">
      <div className="relative h-40 overflow-hidden bg-brand-50">
        <FoodImage
          slot={slot}
          src={meal.image}
          alt={`${meal.label} meal`}
          className="h-full w-full transition-transform duration-500 group-hover:scale-105"
        />
        <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-ink/70 to-transparent p-3 pt-8">
          <div className="flex items-center justify-between gap-2">
            <Badge className="bg-white/90 text-brand-800">{meal.label || slot}</Badge>
            <Badge className="bg-brand-600 text-white">
              <Flame className="h-3 w-3" /> {num(meal.total_calories)} kcal
            </Badge>
          </div>
        </div>
        <button
          onClick={toggleFavorite}
          aria-label="Toggle favorite"
          className="absolute right-3 top-3 grid h-8 w-8 place-items-center rounded-full bg-white/90 text-muted-foreground shadow-sm transition hover:text-coral"
        >
          <Heart className={`h-4 w-4 ${isFavorite ? 'fill-coral text-coral' : ''}`} />
        </button>
      </div>

      <div className="flex flex-1 flex-col p-4">
        <h4 className="line-clamp-1 font-display text-base font-bold">{primary}</h4>
        <p className="mt-0.5 line-clamp-1 text-xs text-muted-foreground">
          {meal.items?.map((i) => i.food_name).join(' · ') || 'Balanced meal'}
        </p>

        <div className="mt-3 grid grid-cols-3 gap-2 text-center">
          {[
            ['Protein', `${num(meal.total_protein)}g`, 'text-brand-700'],
            ['Carbs', `${num(meal.total_carbs)}g`, 'text-amber-600'],
            ['Fats', `${num(meal.total_fat)}g`, 'text-coral'],
          ].map(([label, value, color]) => (
            <div key={label} className="rounded-lg bg-brand-50/70 px-1 py-2">
              <p className={`text-sm font-bold ${color}`}>{value}</p>
              <p className="text-[10px] font-semibold text-muted-foreground">{label}</p>
            </div>
          ))}
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <Clock3 className="h-3.5 w-3.5" /> {meal.total_time_minutes ?? 20} min
          </span>
          <span className="inline-flex items-center gap-1">
            <Utensils className="h-3.5 w-3.5" /> {meal.items?.length ?? 0} foods
          </span>
          {meal.suggested_time && <span>{meal.suggested_time}</span>}
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2 border-t border-brand-100 pt-3">
          <Button size="sm" variant="outline" onClick={openSwap} disabled={busy}>
            <ArrowLeftRight className="h-3.5 w-3.5" /> Swap
          </Button>
          <Button size="sm" variant="outline" onClick={onRegenerate} disabled={busy}>
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            Regenerate
          </Button>
          <Button
            size="sm"
            onClick={() => navigate(`/app/meal/${encodeURIComponent(day)}/${slot}?plan=${planId || ''}`)}
          >
            <BookOpen className="h-3.5 w-3.5" /> View Recipe
          </Button>
          <Button size="sm" variant="secondary" onClick={() => setWhyOpen(true)}>
            <Lightbulb className="h-3.5 w-3.5" /> Why this meal?
          </Button>
        </div>
      </div>

      <Dialog open={swapOpen} onOpenChange={setSwapOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Swap {primary}</DialogTitle>
            <DialogDescription>
              Pick an engine-approved substitute that matches your diet, allergies and macros.
            </DialogDescription>
          </DialogHeader>
          {loadingOptions ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {[0, 1, 2, 3].map((i) => <div key={i} className="h-24 animate-pulse rounded-xl bg-brand-50" />)}
            </div>
          ) : options.length ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {options.map((option) => (
                <button
                  key={option.food_name}
                  onClick={() => applySwap(option.food_name)}
                  className="flex items-center gap-3 rounded-xl border border-brand-100 p-3 text-left transition hover:border-brand-400 hover:bg-brand-50/60"
                >
                  <FoodImage slot={slot} src={option.image} alt={option.food_name} className="h-14 w-14 rounded-lg" />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-bold">{option.food_name}</p>
                    <p className="text-xs text-muted-foreground">{num(option.calories)} kcal · {num(option.protein)}g protein</p>
                    <Badge className="mt-1" variant="success">{num(option.similarity_score * 100)}% match</Badge>
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <p className="rounded-xl bg-brand-50 p-4 text-sm text-muted-foreground">
              No compliant substitutes were found. Try removing a disliked food from your profile.
            </p>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={whyOpen} onOpenChange={setWhyOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Why this meal?</DialogTitle>
            <DialogDescription>{meal.label} · {day}</DialogDescription>
          </DialogHeader>
          <p className="text-sm leading-relaxed text-ink/80">{meal.why}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            {(meal.tags || []).map((tag) => <Badge key={tag} variant="success">{tag}</Badge>)}
          </div>
          <div className="mt-5 rounded-xl bg-brand-50 p-4 text-xs text-muted-foreground">
            Portions and nutrition are calculated from the Indian Food Composition Tables (IFCT 2017)
            and ICMR-NIN RDA 2020. Preparation notes are suggested guidance.
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
