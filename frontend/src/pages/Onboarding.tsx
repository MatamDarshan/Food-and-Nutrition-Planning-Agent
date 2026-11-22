import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Apple, ArrowLeft, ArrowRight, Check, ChefHat, CircleDollarSign, Clock3, HeartPulse,
  Leaf, Loader2, Minus, Plus, Salad, ShieldCheck, Sparkles, Target, X,
} from 'lucide-react';
import { toast } from 'sonner';
import { groceryApi, messageOf, planApi, profileApi } from '../lib/api';
import type { Profile } from '../lib/types';
import { useApp } from '../lib/store';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Progress } from '../components/ui/progress';
import { cn } from '../lib/utils';

const STEPS = [
  { title: 'About you', icon: HeartPulse, subtitle: 'The basics we use for your metabolism' },
  { title: 'Activity', icon: Salad, subtitle: 'How much do you move in a typical week?' },
  { title: 'Your goal', icon: Target, subtitle: 'What are you working towards?' },
  { title: 'Diet preference', icon: Leaf, subtitle: 'What does your plate look like?' },
  { title: 'Allergies', icon: ShieldCheck, subtitle: 'Foods we must always avoid' },
  { title: 'Dislikes', icon: X, subtitle: 'Foods you would rather skip' },
  { title: 'Cuisines', icon: ChefHat, subtitle: 'Flavours you enjoy' },
  { title: 'Kitchen', icon: CircleDollarSign, subtitle: 'Budget and time in the kitchen' },
];

const ACTIVITY = [
  { value: 'sedentary', label: 'Sedentary', text: 'Desk job, little exercise' },
  { value: 'lightly_active', label: 'Lightly active', text: 'Exercise 1–3 days/week' },
  { value: 'moderately_active', label: 'Moderately active', text: 'Exercise 3–5 days/week' },
  { value: 'very_active', label: 'Very active', text: 'Exercise 6–7 days/week' },
  { value: 'extra_active', label: 'Extra active', text: 'Hard training or physical job' },
];

const GOALS = [
  { value: 'weight_loss', label: 'Lose weight', text: 'A gentle, sustainable calorie deficit', emoji: '⚖️' },
  { value: 'maintenance', label: 'Stay healthy', text: 'Maintain your current weight and energy', emoji: '🌿' },
  { value: 'muscle_gain', label: 'Build muscle', text: 'More protein and fuel for training', emoji: '💪' },
];

const DIETS = [
  { value: 'veg', label: 'Vegetarian', text: 'No meat, fish or eggs', emoji: '🥬' },
  { value: 'vegan', label: 'Vegan', text: 'Plant-only, no dairy or eggs', emoji: '🌱' },
  { value: 'eggetarian', label: 'Eggetarian', text: 'Vegetarian plus eggs', emoji: '🥚' },
  { value: 'non-veg', label: 'Non-vegetarian', text: 'Includes meat and fish', emoji: '🍗' },
];

const ALLERGENS = ['gluten', 'dairy', 'eggs', 'fish', 'tree_nuts', 'peanuts', 'soy', 'shellfish'];
const CUISINES = ['North Indian', 'South Indian', 'Gujarati', 'Bengali', 'Punjabi', 'Maharashtrian', 'Rajasthani', 'Continental'];
const DISLIKE_SUGGESTIONS = ['Cucumber', 'Coriander', 'Paneer', 'Lentils', 'Okra', 'Mushrooms', 'Onion', 'Garlic'];

const DEFAULT_PROFILE: Profile = {
  name: '',
  age: 30,
  gender: 'female',
  height_cm: 165,
  weight_kg: 65,
  activity_level: 'moderately_active',
  fitness_goal: 'maintenance',
  diet_type: 'veg',
  allergies: [],
  disliked_foods: [],
  cuisine_preferences: [],
  budget: 'medium',
  cooking_time_minutes: 30,
  health_conditions: [],
};

function OptionCard({
  active, onClick, label, text, emoji, icon: Icon,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  text: string;
  emoji?: string;
  icon?: typeof Leaf;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'flex items-center gap-3 rounded-2xl border-2 p-4 text-left transition-all',
        active ? 'border-brand-500 bg-brand-50/70 shadow-soft' : 'border-brand-100 bg-white hover:border-brand-300',
      )}
    >
      <span className={cn('grid h-10 w-10 shrink-0 place-items-center rounded-xl text-lg', active ? 'bg-brand-600 text-white' : 'bg-brand-50')}>
        {emoji || (Icon && <Icon className="h-5 w-5" />)}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-bold">{label}</span>
        <span className="block text-xs text-muted-foreground">{text}</span>
      </span>
      <span className={cn('grid h-5 w-5 shrink-0 place-items-center rounded-full border-2', active ? 'border-brand-600 bg-brand-600 text-white' : 'border-brand-200')}>
        {active && <Check className="h-3 w-3" />}
      </span>
    </button>
  );
}

export function Onboarding() {
  const navigate = useNavigate();
  const saved = useApp((s) => s.profile);
  const user = useApp((s) => s.user);
  const applyPlanResponse = useApp((s) => s.applyPlanResponse);
  const setProfile = useApp((s) => s.setProfile);
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<Profile>(
    saved ? { ...saved, name: saved.name || user?.name || '' } : { ...DEFAULT_PROFILE, name: user?.name || '' },
  );
  const [dislikeInput, setDislikeInput] = useState('');
  const [generating, setGenerating] = useState(false);
  const [progressText, setProgressText] = useState('');

  useEffect(() => {
    if (!localStorage.getItem('np_token')) navigate('/signin');
  }, [navigate]);

  const patch = (value: Partial<Profile>) => setForm((current) => ({ ...current, ...value }));
  const toggle = (key: 'allergies' | 'disliked_foods' | 'cuisine_preferences', value: string) =>
    setForm((current) => ({
      ...current,
      [key]: current[key].includes(value) ? current[key].filter((v) => v !== value) : [...current[key], value],
    }));

  const next = () => setStep((s) => Math.min(STEPS.length - 1, s + 1));
  const back = () => setStep((s) => Math.max(0, s - 1));

  const addDislike = () => {
    const value = dislikeInput.trim();
    if (value && !form.disliked_foods.some((f) => f.toLowerCase() === value.toLowerCase())) {
      patch({ disliked_foods: [...form.disliked_foods, value] });
    }
    setDislikeInput('');
  };

  const generate = async (mode: 'fast' | 'ai' = 'fast') => {
    setGenerating(true);
    setProgressText('Validating your profile…');
    let timer: number | undefined;
    try {
      await profileApi.save(form);
      timer = window.setInterval(() => {
        setProgressText((text) =>
          text === 'Validating your profile…' ? 'Selecting ICMR-NIN foods…'
            : text === 'Selecting ICMR-NIN foods…' ? 'Balancing macros and micronutrients…'
              : 'Running safety checks…',
        );
      }, 900);
      const response = await planApi.generate(form, mode);
      applyPlanResponse(response);
      setProfile(form);
      const grocery = await groceryApi.get(response.plan_id);
      useApp.getState().setChecked(grocery.checked);
      toast.success('Your 7-day plan is ready!');
      navigate('/app/dashboard');
    } catch (error) {
      toast.error(messageOf(error));
    } finally {
      if (timer) window.clearInterval(timer);
      setGenerating(false);
    }
  };

  const canAdvance =
    (step === 0 && !!form.name.trim() && form.age >= 18) ||
    [1, 2, 3, 4, 5, 6, 7].includes(step);

  const renderStep = () => {
    switch (step) {
      case 0:
        return (
          <div className="space-y-5">
            <div>
              <label className="mb-1.5 block text-xs font-bold">What should we call you?</label>
              <Input value={form.name} onChange={(e) => patch({ name: e.target.value })} placeholder="Your name" />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              {([
                ['age', 'Age', 'years', 18, 90],
                ['height_cm', 'Height', 'cm', 120, 220],
                ['weight_kg', 'Weight', 'kg', 35, 200],
              ] as const).map(([field, label, unit, min, max]) => (
                <div key={field}>
                  <label className="mb-1.5 block text-xs font-bold">{label} ({unit})</label>
                  <Input
                    type="number"
                    min={min}
                    max={max}
                    value={form[field]}
                    onChange={(e) => patch({ [field]: Number(e.target.value) } as Partial<Profile>)}
                  />
                </div>
              ))}
              <div>
                <label className="mb-1.5 block text-xs font-bold">Sex (for BMR formula)</label>
                <div className="flex gap-2">
                  {(['female', 'male'] as const).map((gender) => (
                    <button
                      key={gender}
                      type="button"
                      onClick={() => patch({ gender })}
                      className={cn('h-11 flex-1 rounded-xl border-2 text-sm font-semibold capitalize transition', form.gender === gender ? 'border-brand-500 bg-brand-50 text-brand-700' : 'border-brand-100 hover:border-brand-300')}
                    >
                      {gender}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <div className="rounded-xl bg-brand-50 p-4 text-xs text-muted-foreground">
              We use the Mifflin–St Jeor equation with your activity level and goal to calculate a safe daily target.
            </div>
          </div>
        );
      case 1:
        return <div className="grid gap-3 sm:grid-cols-2">{ACTIVITY.map((item) => (
          <OptionCard key={item.value} active={form.activity_level === item.value} onClick={() => patch({ activity_level: item.value as Profile['activity_level'] })} label={item.label} text={item.text} icon={Salad} />
        ))}</div>;
      case 2:
        return <div className="grid gap-3 sm:grid-cols-3">{GOALS.map((item) => (
          <OptionCard key={item.value} active={form.fitness_goal === item.value} onClick={() => patch({ fitness_goal: item.value as Profile['fitness_goal'] })} label={item.label} text={item.text} emoji={item.emoji} />
        ))}</div>;
      case 3:
        return <div className="grid gap-3 sm:grid-cols-2">{DIETS.map((item) => (
          <OptionCard key={item.value} active={form.diet_type === item.value} onClick={() => patch({ diet_type: item.value as Profile['diet_type'] })} label={item.label} text={item.text} emoji={item.emoji} />
        ))}</div>;
      case 4:
        return (
          <div>
            <p className="mb-4 text-sm text-muted-foreground">Select all that apply. We exclude these ingredients from every meal.</p>
            <div className="flex flex-wrap gap-2">
              {ALLERGENS.map((item) => (
                <button key={item} type="button" onClick={() => toggle('allergies', item)} className={cn('rounded-full border-2 px-4 py-2 text-sm font-semibold capitalize transition', form.allergies.includes(item) ? 'border-brand-500 bg-brand-600 text-white' : 'border-brand-100 bg-white hover:border-brand-300')}>
                  {item.replace('_', ' ')}
                </button>
              ))}
            </div>
            {!form.allergies.length && <p className="mt-4 text-xs text-muted-foreground">No allergies selected — that's fine.</p>}
          </div>
        );
      case 5:
        return (
          <div>
            <div className="flex gap-2">
              <Input value={dislikeInput} onChange={(e) => setDislikeInput(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addDislike(); } }} placeholder="Type a food and press Enter" />
              <Button type="button" variant="outline" onClick={addDislike}><Plus className="h-4 w-4" /></Button>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {DISLIKE_SUGGESTIONS.map((item) => (
                <button key={item} type="button" onClick={() => toggle('disliked_foods', item)} className={cn('rounded-full border px-3 py-1.5 text-xs font-semibold transition', form.disliked_foods.includes(item) ? 'border-coral bg-coral/10 text-coral' : 'border-brand-100 bg-white text-muted-foreground hover:border-coral')}>
                  {form.disliked_foods.includes(item) ? '− ' : '+ '}{item}
                </button>
              ))}
            </div>
            {!!form.disliked_foods.length && (
              <div className="mt-5 flex flex-wrap gap-2">
                {form.disliked_foods.map((item) => (
                  <span key={item} className="inline-flex items-center gap-1 rounded-full bg-brand-50 px-3 py-1.5 text-xs font-semibold text-brand-700">
                    {item}<button type="button" onClick={() => toggle('disliked_foods', item)}><Minus className="h-3 w-3" /></button>
                  </span>
                ))}
              </div>
            )}
          </div>
        );
      case 6:
        return (
          <div>
            <p className="mb-4 text-sm text-muted-foreground">We lean into the cuisines you enjoy when choosing foods.</p>
            <div className="flex flex-wrap gap-2">
              {CUISINES.map((item) => (
                <button key={item} type="button" onClick={() => toggle('cuisine_preferences', item)} className={cn('rounded-full border-2 px-4 py-2 text-sm font-semibold transition', form.cuisine_preferences.includes(item) ? 'border-brand-500 bg-brand-50 text-brand-700' : 'border-brand-100 bg-white hover:border-brand-300')}>
                  {form.cuisine_preferences.includes(item) && <Check className="mr-1 inline h-3 w-3" />}{item}
                </button>
              ))}
            </div>
          </div>
        );
      case 7:
        return (
          <div className="space-y-6">
            <div>
              <p className="mb-3 text-sm font-bold">Typical grocery budget</p>
              <div className="grid gap-3 sm:grid-cols-3">
                {[['low', '₹ Budget-friendly', 'Everyday staples'], ['medium', '₹₹ Balanced', 'Mix of staples and fresh produce'], ['premium', '₹₹₹ Premium', 'More fresh and speciality items']].map(([value, label, text]) => (
                  <OptionCard key={value} active={form.budget === value} onClick={() => patch({ budget: value as Profile['budget'] })} label={label} text={text} icon={CircleDollarSign} />
                ))}
              </div>
            </div>
            <div>
              <p className="mb-3 text-sm font-bold">Time you can cook per meal: <span className="text-brand-700">{form.cooking_time_minutes} minutes</span></p>
              <input
                type="range"
                min={10}
                max={90}
                step={5}
                value={form.cooking_time_minutes}
                onChange={(e) => patch({ cooking_time_minutes: Number(e.target.value) })}
                className="w-full accent-brand-600"
              />
              <div className="flex justify-between text-xs text-muted-foreground"><span>10 min</span><span>90 min</span></div>
            </div>
            <div className="rounded-2xl border border-brand-100 bg-brand-50/60 p-5">
              <p className="text-sm font-bold">Ready to build your plan?</p>
              <p className="mt-1 text-xs text-muted-foreground">We'll generate 28 meals and validate each one against your targets and restrictions.</p>
              <div className="mt-4 flex flex-wrap gap-3">
                <Button onClick={() => generate('fast')} disabled={generating} size="lg">
                  {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />} Generate my plan
                </Button>
                <Button variant="outline" onClick={() => generate('ai')} disabled={generating} size="lg">Use AI mode</Button>
              </div>
            </div>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div className="np-gradient min-h-screen">
      {generating && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-ink/50 px-5 backdrop-blur-sm">
          <div className="np-card w-full max-w-sm p-8 text-center">
            <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-brand-600 text-white"><Loader2 className="h-7 w-7 animate-spin" /></span>
            <h3 className="mt-5 text-lg font-extrabold">Building your week</h3>
            <p className="mt-2 text-sm text-muted-foreground">{progressText}</p>
            <div className="mt-5"><Progress value={70} /></div>
            <p className="mt-3 text-xs text-muted-foreground">This usually takes just a few seconds.</p>
          </div>
        </div>
      )}

      <div className="mx-auto flex min-h-screen max-w-3xl flex-col px-5 py-8">
        <Link to="/" className="inline-flex items-center gap-2 self-start">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand-600 text-white"><Apple className="h-5 w-5" /></span>
          <span className="font-display font-extrabold">AI Nutrition Planner</span>
        </Link>

        <div className="mt-8">
          <div className="flex items-center justify-between text-xs font-bold text-muted-foreground">
            <span>STEP {step + 1} OF {STEPS.length}</span>
            <span>{Math.round(((step + 1) / STEPS.length) * 100)}% complete</span>
          </div>
          <Progress value={((step + 1) / STEPS.length) * 100} className="mt-2" />
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {STEPS.map((item, index) => (
            <button
              key={item.title}
              onClick={() => index <= step && setStep(index)}
              title={item.title}
              className={cn('h-2 flex-1 rounded-full transition-all', index <= step ? 'bg-brand-500' : 'bg-brand-100', index === step && 'ring-2 ring-brand-500 ring-offset-2')}
            />
          ))}
        </div>

        <div className="np-card mt-7 flex-1 p-6 sm:p-9">
          <AnimatePresence mode="wait">
            <motion.div
              key={step}
              initial={{ opacity: 0, x: 24 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -24 }}
              transition={{ duration: 0.25 }}
            >
              <div className="flex items-center gap-3">
                {(() => { const Icon = STEPS[step].icon; return <span className="grid h-11 w-11 place-items-center rounded-xl bg-brand-600 text-white"><Icon className="h-5 w-5" /></span>; })()}
                <div>
                  <h2 className="text-xl font-extrabold sm:text-2xl">{STEPS[step].title}</h2>
                  <p className="text-xs text-muted-foreground">{STEPS[step].subtitle}</p>
                </div>
              </div>
              <div className="mt-7">{renderStep()}</div>
            </motion.div>
          </AnimatePresence>

          {step < STEPS.length - 1 && (
            <div className="mt-9 flex items-center justify-between border-t border-brand-100 pt-5">
              <Button variant="ghost" onClick={back} disabled={step === 0}><ArrowLeft className="h-4 w-4" /> Back</Button>
              <Button onClick={next} disabled={!canAdvance}>Continue <ArrowRight className="h-4 w-4" /></Button>
            </div>
          )}
          {step > 0 && step < STEPS.length - 1 && (
            <button onClick={() => generate('fast')} disabled={generating} className="mx-auto mt-4 block text-xs font-semibold text-muted-foreground hover:text-brand-700">
              Skip ahead and generate my plan
            </button>
          )}
        </div>
        <p className="mt-5 text-center text-xs text-muted-foreground">
          <Clock3 className="mr-1 inline h-3 w-3" /> Your answers are saved privately and can be edited any time.
        </p>
      </div>
    </div>
  );
}
