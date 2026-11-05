import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
const variants = cva('inline-flex items-center justify-center gap-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-emerald-400', {variants:{variant:{default:'bg-emerald-400 px-4 py-2 text-zinc-950 hover:bg-emerald-300',outline:'border border-zinc-700 bg-zinc-900 px-4 py-2 text-zinc-200 hover:bg-zinc-800'}},defaultVariants:{variant:'default'}});
export function Button({className, variant, asChild=false, ...props}: React.ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof variants> & {asChild?:boolean}) { const Comp=asChild?Slot:'button'; return <Comp className={twMerge(clsx(variants({variant}),className))} {...props}/>; }
