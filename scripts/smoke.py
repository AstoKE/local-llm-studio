#!/usr/bin/env python3
"""Real HTTP smoke test. Inference/benchmark require explicit model selection."""
import argparse
import json
import os
import ssl
import sys
import time
from urllib.parse import urlsplit
import httpx

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--api-url',default='http://127.0.0.1:8000')
parser.add_argument('--web-url',default='http://127.0.0.1:3000')
parser.add_argument('--model')
parser.add_argument('--ca-file',help='Trusted CA certificate file for a local HTTPS gateway')
parser.add_argument('--inference',action='store_true')
parser.add_argument('--benchmark',action='store_true')
args=parser.parse_args()
if (args.inference or args.benchmark) and not args.model:
    parser.error('--inference/--benchmark require --model with an installed identifier')
for url in [args.api_url,args.web_url]:
    parsed=urlsplit(url)
    if parsed.scheme not in {'http','https'} or parsed.username or parsed.password:
        parser.error('Use HTTP(S) URLs without credentials')
    if parsed.scheme=='http' and parsed.hostname not in {'localhost','127.0.0.1','::1'}:
        parser.error('Remote smoke tests require HTTPS')
verification=ssl.create_default_context(cafile=args.ca_file) if args.ca_file else ssl.create_default_context()
headers={}
if token:=os.environ.get('STUDIO_SMOKE_ADMIN_TOKEN'):
    headers['Authorization']='Bearer '+token
job=None
try:
    with httpx.Client(base_url=args.api_url,headers=headers,timeout=300,trust_env=False,verify=verification) as client:
        def request(method,path,**kwargs):
            response=client.request(method,path,**kwargs)
            response.raise_for_status()
            return response.json()
        health=request('GET','/api/health')
        print(f"PASS: backend health; phase {health.get('phase')}")
        with httpx.Client(timeout=15,trust_env=False,verify=verification) as browser:
            response=browser.get(args.web_url.rstrip('/')+'/login')
            response.raise_for_status()
        print('PASS: frontend login route reachable (not a browser rendering test)')
        models=request('GET','/api/models')['models']
        print(f'PASS: provider connection; {len(models)} installed models')
        if args.model and args.model not in {m['name'] for m in models}:
            raise RuntimeError('Selected model is not installed at the configured provider.')
        if args.inference:
            done=False
            text=False
            with client.stream('POST','/api/chat',json={'model':args.model,'content':'Reply with a short greeting.','configuration':{'options':{'num_predict':32}}}) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    event=json.loads(line)
                    if event.get('type')=='error':
                        raise RuntimeError(event.get('detail','Inference failed'))
                    if event.get('type')=='token' and event.get('content'):
                        text=True
                    if event.get('type')=='done':
                        done=True
                        print('Provider counters:',json.dumps({k:v for k,v in event.get('statistics',{}).items() if k in {'eval_count','eval_duration','prompt_eval_count','total_duration','server_ttft_seconds'}}))
            if not (done and text):
                raise RuntimeError('Inference did not produce both content and completion.')
            print('PASS: real stateless inference response; monitoring metadata persists')
        if args.benchmark:
            job=request('POST','/api/benchmarks',json={'name':'Host smoke test','model':args.model,'prompt':'Reply with a short greeting.','warmups':0,'repeats':1,'configurations':[{'name':'Smoke configuration','configuration':{'options':{'num_predict':32}}}]})['id']
            deadline=time.monotonic()+360
            while time.monotonic()<deadline:
                result=request('GET',f'/api/benchmarks/{job}')
                if result['status']!='running':
                    if result['status']!='completed':
                        raise RuntimeError(f"Benchmark status: {result['status']}")
                    print(f'PASS: real benchmark {job} persisted')
                    job=None
                    break
                time.sleep(1)
            else:
                raise RuntimeError('Benchmark smoke timed out.')
        if not args.inference:
            print('SKIP: real inference (--inference --model required)')
        if not args.benchmark:
            print('SKIP: real benchmark (--benchmark --model required)')
except (Exception,KeyboardInterrupt) as error:
    if job is not None:
        try:
            with httpx.Client(base_url=args.api_url,headers=headers,timeout=10,trust_env=False,verify=verification) as client:
                client.post(f'/api/benchmarks/{job}/cancel').raise_for_status()
        except Exception:
            print(f'Benchmark {job} may still be active; inspect Benchmarks page.',file=sys.stderr)
    print(f'FAIL/BLOCKED: {type(error).__name__}: {error}',file=sys.stderr)
    raise SystemExit(1)
