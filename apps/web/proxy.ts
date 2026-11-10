import {NextResponse,type NextRequest} from 'next/server';
import {allowedRequestHost,lanModeEnabled} from './lib/request-host';
export async function proxy(request:NextRequest){
 if(!allowedRequestHost(request.headers.get('host'),process.env.STUDIO_WEB_ORIGIN??'http://127.0.0.1:3000'))return NextResponse.json({detail:'Host is not allowed.'},{status:400});
 if(request.nextUrl.pathname.startsWith('/api/'))return NextResponse.next();
 if(!lanModeEnabled(process.env.STUDIO_LAN_MODE)||request.nextUrl.pathname==='/login')return NextResponse.next();
 try{const response=await fetch('http://127.0.0.1:8000/api/auth/me',{headers:{cookie:request.headers.get('cookie')??''},cache:'no-store',signal:AbortSignal.timeout(5000)});const status=await response.json();if(response.ok&&status.authenticated)return NextResponse.next()}catch{}
 return NextResponse.redirect(new URL('/login',process.env.STUDIO_WEB_ORIGIN??request.url));
}
export const config={matcher:['/((?!_next|favicon.ico).*)']};
