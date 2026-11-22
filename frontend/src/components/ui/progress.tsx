import { cn } from '../../lib/utils';

export function Progress({
  value,
  className,
  indicatorClassName,
}: {
  value: number;
  className?: string;
  indicatorClassName?: string;
}) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div className={cn('h-2 w-full overflow-hidden rounded-full bg-brand-50', className)}>
      <div
        className={cn('h-full rounded-full bg-brand-500 transition-all duration-700', indicatorClassName)}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}
