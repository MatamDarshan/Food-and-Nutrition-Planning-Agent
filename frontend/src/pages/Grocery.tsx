import { useEffect, useMemo, useState } from 'react';
import { Check, ClipboardCheck, Copy, Loader2, ShoppingBasket } from 'lucide-react';
import { toast } from 'sonner';
import { groceryApi, messageOf } from '../lib/api';
import type { GroceryItem } from '../lib/types';
import { useApp } from '../lib/store';
import { num } from '../lib/utils';
import { EmptyPlan, PageHeader } from '../components/Layout';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Progress } from '../components/ui/progress';
import { CardSkeleton } from '../components/ui/skeleton';
import { FoodImage } from '../components/FoodImage';

export function Grocery() {
  const planId = useApp((s) => s.planId);
  const plan = useApp((s) => s.plan);
  const checked = useApp((s) => s.checked);
  const setChecked = useApp((s) => s.setChecked);
  const [items, setItems] = useState<GroceryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!planId) { setLoading(false); return; }
    setLoading(true);
    groceryApi.get(planId)
      .then((data) => { setItems(data.items); setChecked(data.checked); })
      .catch((e) => setError(messageOf(e)))
      .finally(() => setLoading(false));
  }, [planId, setChecked]);

  const groups = useMemo(() => {
    const map = new Map<string, GroceryItem[]>();
    items.forEach((item) => {
      const key = item.category || 'General';
      map.set(key, [...(map.get(key) || []), item]);
    });
    return Array.from(map.entries());
  }, [items]);

  const done = items.filter((item) => checked[item.name.toLowerCase()]).length;
  const pct = items.length ? (done / items.length) * 100 : 0;

  const toggle = async (item: GroceryItem) => {
    const key = item.name.toLowerCase();
    const next = { ...checked, [key]: !checked[key] };
    setChecked(next);
    try {
      setChecked(await groceryApi.check(next));
    } catch (e) {
      setChecked(checked);
      toast.error(messageOf(e));
    }
  };

  const copy = async () => {
    const text = items.map((item) => `${checked[item.name.toLowerCase()] ? '[x]' : '[ ]'} ${item.name} — ${num(item.total_grams)} g`).join('\n');
    try {
      await navigator.clipboard.writeText(text);
      toast.success('Grocery list copied');
    } catch {
      toast.error('Could not copy to clipboard');
    }
  };

  if (!plan) return <EmptyPlan label="Create a plan for my grocery list" />;
  if (error) return <div className="np-card p-8 text-center text-sm text-red-600">{error}</div>;
  if (loading) return <div className="space-y-5"><CardSkeleton /><CardSkeleton /></div>;

  return (
    <>
      <PageHeader
        eyebrow="Everything you need for the week"
        title="Grocery & shopping list"
        description="Generated automatically from all 28 meals in your plan. Tick items as you shop."
        action={<Button variant="outline" onClick={copy}><Copy className="h-4 w-4" /> Copy list</Button>}
      />

      <div className="np-card mb-5 flex flex-wrap items-center gap-5 p-5">
        <span className="grid h-12 w-12 place-items-center rounded-2xl bg-brand-50 text-brand-600"><ShoppingBasket className="h-6 w-6" /></span>
        <div className="min-w-[180px] flex-1">
          <div className="flex items-center justify-between text-sm">
            <span className="font-bold">{done} of {items.length} items picked up</span>
            <span className="font-bold text-brand-700">{num(pct)}%</span>
          </div>
          <Progress value={pct} className="mt-2" />
        </div>
        <Badge variant="success"><ClipboardCheck className="h-3 w-3" /> Auto-generated</Badge>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        {groups.map(([category, group]) => (
          <div key={category} className="np-card p-5">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="font-display text-lg font-bold">{category}</h3>
              <Badge variant="muted">{group.length} items</Badge>
            </div>
            <div className="space-y-2">
              {group.map((item) => {
                const isChecked = !!checked[item.name.toLowerCase()];
                return (
                  <button
                    key={item.name}
                    onClick={() => toggle(item)}
                    className={`flex w-full items-center gap-3 rounded-xl border p-2.5 text-left transition ${isChecked ? 'border-brand-200 bg-brand-50/60 opacity-65' : 'border-brand-100 hover:border-brand-300'}`}
                  >
                    <span className={`grid h-5 w-5 shrink-0 place-items-center rounded-md border-2 transition ${isChecked ? 'border-brand-600 bg-brand-600 text-white' : 'border-brand-200'}`}>
                      {isChecked ? <Check className="h-3 w-3" /> : loading ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
                    </span>
                    <FoodImage slot={category} src={item.image} alt={item.name} className="h-10 w-10 shrink-0 rounded-lg" />
                    <span className="min-w-0 flex-1">
                      <span className={`block truncate text-sm font-bold ${isChecked ? 'line-through' : ''}`}>{item.name}</span>
                      <span className="block truncate text-[11px] text-muted-foreground">{item.serving || 'As needed'} · {item.days.slice(0, 3).join(', ')}{item.days.length > 3 ? '…' : ''}</span>
                    </span>
                    <span className="shrink-0 text-xs font-bold text-brand-700">{num(item.total_grams)} g</span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {!items.length && (
        <div className="np-card p-10 text-center text-sm text-muted-foreground">No grocery items found for this plan.</div>
      )}
    </>
  );
}
