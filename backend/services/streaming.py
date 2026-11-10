from collections.abc import Callable
from starlette.responses import StreamingResponse

class ManagedStreamingResponse(StreamingResponse):
    """Release admission even when the client disconnects before iteration starts."""
    def __init__(self,*args,on_close:Callable[[],None],**kwargs):
        super().__init__(*args,**kwargs)
        self.on_close=on_close

    async def __call__(self,scope,receive,send):
        try:
            await super().__call__(scope,receive,send)
        finally:
            try:
                close=getattr(self.body_iterator,'aclose',None)
                if close:
                    await close()
            finally:
                self.on_close()
