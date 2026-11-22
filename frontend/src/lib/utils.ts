import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const num = (value: number | null | undefined, digits = 0) =>
  Number(value ?? 0).toLocaleString('en-IN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });

export const kcal = (value: number | null | undefined) => `${num(value)} kcal`;

export const slug = (value: string) => value.toLowerCase().replace(/\s+/g, '-');

export const titleCase = (value: string) =>
  value
    .replace(/[_-]/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

export const fallbackImage = (slot: string) => {
  const key = slot.toLowerCase();
  if (key.includes('breakfast')) return '/images/breakfast.svg';
  if (key.includes('snack')) return '/images/snack.svg';
  if (key.includes('dinner') || key.includes('soup')) return '/images/dinner.svg';
  return '/images/lunch.svg';
};
