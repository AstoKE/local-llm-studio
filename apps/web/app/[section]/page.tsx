import { notFound } from 'next/navigation';
import { Studio } from '@/components/studio';
export default async function Page({params}:{params:Promise<{section:string}>}) {const {section}=await params; if(!['chat','models','playground','benchmarks','monitoring','settings'].includes(section))notFound(); return <Studio section={section}/>}
