"""Bound request buffering before JSON parsing; does not buffer streaming responses."""
from starlette.responses import JSONResponse
from backend.core.config import settings

class RequestLimitMiddleware:
    def __init__(self, app):
        self.app=app

    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope['method'] not in {'POST','PUT','PATCH','DELETE'}:
            return await self.app(scope,receive,send)
        maximum=settings().max_request_bytes
        headers=dict(scope.get('headers',[]))
        try:
            length=int(headers.get(b'content-length',b'0'))
            if length<0:
                raise ValueError
        except ValueError:
            return await JSONResponse({'detail':'Invalid Content-Length.'},status_code=400)(scope,receive,send)
        async def reject():
            await JSONResponse({'detail':f'Request exceeds {maximum} bytes.'},status_code=413,headers={'Cache-Control':'no-store'})(scope,receive,send)
        if length>maximum:
            return await reject()
        body=bytearray()
        while True:
            message=await receive()
            if message['type']=='http.disconnect':
                return
            body.extend(message.get('body',b''))
            if len(body)>maximum:
                return await reject()
            if not message.get('more_body',False):
                break
        pending=True
        async def replay():
            nonlocal pending
            if pending:
                pending=False
                return {'type':'http.request','body':bytes(body),'more_body':False}
            return await receive()
        await self.app(scope,replay,send)
