import os
import uvicorn
if __name__=='__main__':
    host=os.getenv('TEXTILEHR_HOST','127.0.0.1')
    if host not in {'127.0.0.1','::1','localhost'}:raise SystemExit('Only loopback hosting is approved')
    uvicorn.run('backend.api:app',host=host,port=int(os.getenv('TEXTILEHR_PORT','8765')),
                reload=False,access_log=False,workers=1)
