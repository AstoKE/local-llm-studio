import {api} from './api.ts';
import type {Configuration} from '../components/inference-settings';
export type InstalledModel={name:string};
export type ChatPreferences={default_model:string;configuration:Configuration};
/** Publish runtime models independently of optional application preferences. */
export async function loadModelCatalog(onModels:(models:InstalledModel[])=>void){
 const preferences=api<ChatPreferences>('/preferences').then(value=>({value,warning:''}),error=>({value:null,warning:`Default settings could not be loaded; installed models are still available. ${String(error)}`}));
 const response=await api<{models:InstalledModel[]}>('/models');
 if(!Array.isArray(response.models))throw Error('The runtime returned an invalid model list.');
 onModels(response.models);
 return {models:response.models,...await preferences};
}
