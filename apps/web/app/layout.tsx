import type { Metadata } from 'next';
import './globals.css';
import {Theme} from '@/components/theme';
export const metadata: Metadata = {title:'Local LLM Studio', description:'Your local inference workspace'};
export default function Layout({children}:{children:React.ReactNode}) {return <html lang="en" suppressHydrationWarning><body><Theme/>{children}</body></html>}
