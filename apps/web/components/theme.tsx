'use client';
import {useEffect} from 'react';
import {api} from '@/lib/api';
export function Theme(){useEffect(()=>{const media=window.matchMedia('(prefers-color-scheme: light)');function apply(){const preference=localStorage.getItem('studio-theme')??'dark';document.documentElement.dataset.theme=preference==='system'?(media.matches?'light':'dark'):preference}apply();api<{theme:string}>('/preferences').then(p=>{localStorage.setItem('studio-theme',p.theme);apply()}).catch(()=>{});window.addEventListener('studio-theme',apply);media.addEventListener('change',apply);return()=>{window.removeEventListener('studio-theme',apply);media.removeEventListener('change',apply)}},[]);return null}
