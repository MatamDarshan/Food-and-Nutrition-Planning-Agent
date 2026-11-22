import { useState } from 'react';
import { fallbackImage } from '../lib/utils';

const PHOTOS: Record<string, string> = {
  breakfast:
    'https://images.unsplash.com/photo-1630383249896-424e482df921?auto=format&fit=crop&w=800&q=80',
  lunch:
    'https://images.unsplash.com/photo-1601050690597-df0568f70950?auto=format&fit=crop&w=800&q=80',
  snack:
    'https://images.unsplash.com/photo-1599599810769-bcde5a160d32?auto=format&fit=crop&w=800&q=80',
  dinner:
    'https://images.unsplash.com/photo-1585937421612-70a008356fbe?auto=format&fit=crop&w=800&q=80',
};

export function FoodImage({
  slot = 'lunch',
  src,
  alt,
  className = '',
  eager = false,
}: {
  slot?: string;
  src?: string;
  alt: string;
  className?: string;
  eager?: boolean;
}) {
  const key = Object.keys(PHOTOS).find((k) => slot.toLowerCase().includes(k));
  const base = src || (key ? PHOTOS[key] : PHOTOS.lunch);
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  const current = failedSrc === base ? fallbackImage(slot) : base;

  return (
    <img
      src={current}
      alt={alt}
      loading={eager ? 'eager' : 'lazy'}
      onError={() => setFailedSrc(base)}
      className={`bg-brand-50 object-cover ${className}`}
    />
  );
}
