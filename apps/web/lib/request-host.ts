/** Reject DNS-rebinding hosts before rewriting requests to the trusted backend. */
export function allowedRequestHost(host:string|null,origin:string):boolean{
 if(!host)return false;
 try{const actual=new URL(`http://${host}`),configured=new URL(origin);if(actual.username||actual.password||actual.pathname!=='/'||actual.search||actual.hash)return false;return ['127.0.0.1','localhost','[::1]',configured.hostname].includes(actual.hostname)}catch{return false}
}

export function lanModeEnabled(value:string|undefined):boolean{return ['true','1','yes','on','y','t'].includes((value??'').toLowerCase())}
