import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Activity, Download, Loader2, Save, UserRound } from 'lucide-react';
import { toast } from 'sonner';
import { messageOf, planApi, profileApi } from '../lib/api';
import type { Profile as ProfileType, Targets } from '../lib/types';
import { useApp } from '../lib/store';
import { num } from '../lib/utils';
import { PageHeader } from '../components/Layout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';

export function ProfilePage() {
  const navigate = useNavigate();
  const profile = useApp((s) => s.profile);
  const user = useApp((s) => s.user);
  const targets = useApp((s) => s.targets);
  const planId = useApp((s) => s.planId);
  const setProfile = useApp((s) => s.setProfile);
  const setTargets = useApp((s) => s.setTargets);
  const [form, setForm] = useState<ProfileType | null>(profile);
  const [preview, setPreview] = useState<Targets | null>(targets);
  const [saving, setSaving] = useState(false);
  const [calculating, setCalculating] = useState(false);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    if (!form) profileApi.get().then(setForm).catch(() => undefined);
  }, [form]);

  if (!form) return <div className="np-card h-64 animate-pulse" />;

  const patch = (value: Partial<ProfileType>) => setForm({ ...form, ...value });

  const recalc = async () => {
    setCalculating(true);
    try {
      setPreview(await profileApi.targets(form));
      toast.success('Targets recalculated');
    } catch (error) {
      toast.error(messageOf(error));
    } finally {
      setCalculating(false);
    }
  };

  const exportPlan = async () => {
    if (!planId) return;
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

  const save = async () => {
    setSaving(true);
    try {
      const saved = await profileApi.save(form);
      setProfile(saved);
      const updated = await profileApi.targets(form);
      setTargets(updated);
      toast.success('Profile saved. Regenerate meals to apply changes.');
      navigate('/app/planner');
    } catch (error) {
      toast.error(messageOf(error));
    } finally {
      setSaving(false);
    }
  };

  const t = preview || targets;

  return (
    <>
      <PageHeader
        eyebrow="Account & preferences"
        title="My profile"
        description="Keep your preferences current so every meal stays aligned with your goals."
        action={planId ? (
          <Button variant="outline" onClick={() => void exportPlan()} disabled={exporting}>
            {exporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            Export PDF
          </Button>
        ) : undefined}
      />

      <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
        <div className="np-card p-6">
          <div className="flex items-center gap-3">
            <span className="grid h-11 w-11 place-items-center rounded-xl bg-brand-50 text-brand-600"><UserRound className="h-5 w-5" /></span>
            <div><h3 className="font-bold">Personal details</h3><p className="text-xs text-muted-foreground">{user?.email}</p></div>
          </div>

          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <label className="mb-1.5 block text-xs font-bold">Name</label>
              <Input value={form.name} onChange={(e) => patch({ name: e.target.value })} />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-bold">Age</label>
              <Input type="number" value={form.age} onChange={(e) => patch({ age: Number(e.target.value) })} />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-bold">Sex</label>
              <div className="flex gap-2">
                {(['female', 'male'] as const).map((gender) => (
                  <button key={gender} type="button" onClick={() => patch({ gender })} className={`h-11 flex-1 rounded-xl border-2 text-sm font-semibold capitalize ${form.gender === gender ? 'border-brand-500 bg-brand-50 text-brand-700' : 'border-brand-100'}`}>{gender}</button>
                ))}
              </div>
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-bold">Height (cm)</label>
              <Input type="number" value={form.height_cm} onChange={(e) => patch({ height_cm: Number(e.target.value) })} />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-bold">Weight (kg)</label>
              <Input type="number" value={form.weight_kg} onChange={(e) => patch({ weight_kg: Number(e.target.value) })} />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-bold">Activity level</label>
              <select
                value={form.activity_level}
                onChange={(e) => patch({ activity_level: e.target.value as ProfileType['activity_level'] })}
                className="h-11 w-full rounded-xl border border-input bg-white px-3 text-sm outline-none focus:border-brand-500"
              >
                {['sedentary', 'lightly_active', 'moderately_active', 'very_active', 'extra_active'].map((v) => <option key={v} value={v}>{v.replace(/_/g, ' ')}</option>)}
              </select>
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-bold">Goal</label>
              <select
                value={form.fitness_goal}
                onChange={(e) => patch({ fitness_goal: e.target.value as ProfileType['fitness_goal'] })}
                className="h-11 w-full rounded-xl border border-input bg-white px-3 text-sm outline-none focus:border-brand-500"
              >
                {['weight_loss', 'maintenance', 'muscle_gain'].map((v) => <option key={v} value={v}>{v.replace(/_/g, ' ')}</option>)}
              </select>
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-bold">Diet</label>
              <select
                value={form.diet_type}
                onChange={(e) => patch({ diet_type: e.target.value as ProfileType['diet_type'] })}
                className="h-11 w-full rounded-xl border border-input bg-white px-3 text-sm outline-none focus:border-brand-500"
              >
                {['veg', 'vegan', 'eggetarian', 'non-veg'].map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-bold">Budget</label>
              <select
                value={form.budget}
                onChange={(e) => patch({ budget: e.target.value as ProfileType['budget'] })}
                className="h-11 w-full rounded-xl border border-input bg-white px-3 text-sm outline-none focus:border-brand-500"
              >
                {['low', 'medium', 'premium'].map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            </div>
          </div>

          <div className="mt-5 rounded-xl bg-brand-50/60 p-4">
            <p className="text-xs font-bold">Allergies & dislikes</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {form.allergies.map((a) => <Badge key={a} variant="warning">{a}</Badge>)}
              {form.disliked_foods.map((f) => <Badge key={f} variant="muted">{f}</Badge>)}
              {!form.allergies.length && !form.disliked_foods.length && <span className="text-xs text-muted-foreground">None set</span>}
            </div>
            <p className="mt-3 text-[11px] text-muted-foreground">To change these in detail, run the onboarding wizard again.</p>
            <Button asChild variant="ghost" size="sm" className="mt-1"><button onClick={() => navigate('/onboarding')}>Edit preferences</button></Button>
          </div>

          <div className="mt-6 flex flex-wrap gap-3">
            <Button onClick={save} disabled={saving}>{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save changes</Button>
            <Button variant="outline" onClick={recalc} disabled={calculating}>{calculating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Activity className="h-4 w-4" />} Preview targets</Button>
          </div>
        </div>

        <div className="space-y-5">
          <div className="np-card p-6">
            <h3 className="flex items-center gap-2 font-display text-lg font-bold"><Activity className="h-5 w-5 text-brand-600" /> Your daily targets</h3>
            {t ? (
              <>
                <div className="mt-5 rounded-2xl bg-brand-600 p-5 text-white">
                  <p className="text-xs text-white/70">Calorie target</p>
                  <p className="font-display text-3xl font-extrabold">{num(t.calorie_target)} <span className="text-sm font-semibold text-white/70">kcal</span></p>
                  <p className="mt-1 text-xs text-white/70">BMI {num(t.bmi, 1)} · {t.bmi_category}</p>
                </div>
                <div className="mt-5 space-y-4">
                  {[
                    ['Protein', t.protein_g, 'g', 'bg-brand-500'],
                    ['Carbohydrates', t.carbs_g, 'g', 'bg-amber-500'],
                    ['Fats', t.fats_g, 'g', 'bg-coral'],
                    ['Fibre', t.fiber_g, 'g', 'bg-emerald-400'],
                  ].map(([label, value, unit, color]) => (
                    <div key={label as string}>
                      <div className="flex justify-between text-xs font-semibold"><span>{label as string}</span><span>{num(value as number, 1)}{unit as string}</span></div>
                      <Progress value={((value as number) / ((label === 'Protein' ? t.protein_g : label === 'Carbohydrates' ? t.carbs_g : label === 'Fats' ? t.fats_g : t.fiber_g) || 1)) * 100} indicatorClassName={color as string} className="mt-1 h-1.5" />
                    </div>
                  ))}
                </div>
                <div className="mt-5 space-y-1 border-t border-brand-100 pt-4 text-xs text-muted-foreground">
                  <p className="flex justify-between"><span>BMR</span><strong className="text-ink">{num(t.bmr)} kcal</strong></p>
                  <p className="flex justify-between"><span>TDEE</span><strong className="text-ink">{num(t.tdee)} kcal</strong></p>
                </div>
              </>
            ) : <p className="mt-4 text-sm text-muted-foreground">No targets calculated yet.</p>}
          </div>

          <div className="np-card p-6">
            <h3 className="font-bold">Need a fresh plan?</h3>
            <p className="mt-2 text-xs text-muted-foreground">Regenerating builds a new 7-day plan from your latest answers.</p>
            <Button asChild className="mt-4 w-full"><button onClick={() => navigate('/onboarding')}>Rebuild my plan</button></Button>
          </div>
        </div>
      </div>
    </>
  );
}
