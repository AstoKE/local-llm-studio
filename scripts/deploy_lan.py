#!/usr/bin/env python3
"""Stage or install native user services and a private-IP HTTPS gateway."""
import argparse
from datetime import datetime, timezone
import getpass
import errno
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import socket
import sqlite3
import ssl
import subprocess
import sys
import time
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))


def private_address(value:str) -> str:
    address=ipaddress.IPv4Address(value)
    ranges=['10.0.0.0/8','172.16.0.0/12','192.168.0.0/16']
    if not any(address in ipaddress.IPv4Network(network) for network in ranges):
        raise ValueError('Use the workstation RFC1918 LAN IPv4 address, not localhost or a public address.')
    return str(address)


def quoted(value:str) -> str:
    if any(character in value for character in '\n\r\x00'):
        raise ValueError('Paths/environment values must not contain control characters.')
    return '"'+value.replace('\\','\\\\').replace('"','\\"').replace('%','%%').replace('$','$$')+'"'


def unit_text(root:Path,command:list[str],description:str,path:str,extra:str='') -> str:
    if any(character in str(root) for character in '\n\r\x00'):
        raise ValueError('Invalid project path.')
    return f'''[Unit]
Description={description}
After=network.target

[Service]
Type=simple
WorkingDirectory={str(root).replace('%','%%')}
ExecStart={' '.join(quoted(part) for part in command)}
Environment={quoted('PATH='+path)}
Restart=on-failure
RestartSec=5
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
{extra}
[Install]
WantedBy=default.target
'''


def render(root:Path,address:str,port:int,path:str,caddy:str) -> dict[str,str]:
    address=private_address(address)
    if not 1024<=port<=65535 or port in {2019,3000,8000,11434}:
        raise ValueError('Choose a free HTTPS port from 1024–65535 (default 8443).')
    root=root.resolve()
    generated=root/'deploy/generated/lan'
    data=root/'data/lan-gateway'
    origin=f'https://{address}:{port}'
    config=f'''{{
    admin off
    auto_https disable_redirects
    skip_install_trust
}}
{origin} {{
    bind {address}
    tls internal
    encode zstd gzip
    reverse_proxy 127.0.0.1:3000 {{
        flush_interval -1
    }}
}}
'''
    backend=unit_text(root,[str(root/'scripts/backend.sh')],'Local LLM Studio API',path,
                      f'ProtectSystem=strict\nReadWritePaths={str(root / "data").replace("%","%%")}')
    web=unit_text(root,[str(root/'scripts/web.sh'),'--production'],'Local LLM Studio web',path)
    web=web.replace('After=network.target','After=local-llm-studio-backend.service\nWants=local-llm-studio-backend.service')
    gateway=unit_text(root,[caddy,'run','--config',str(generated/'Caddyfile'),'--adapter','caddyfile'],
                      'Local LLM Studio private HTTPS gateway',path,
                      'Environment='+quoted('XDG_DATA_HOME='+str(data))+'\nEnvironment='+quoted('XDG_CONFIG_HOME='+str(root/'data/lan-gateway-config')))
    gateway=gateway.replace('After=network.target','After=network.target local-llm-studio-web.service\nWants=local-llm-studio-web.service')
    return {'Caddyfile':config,'local-llm-studio-backend.service':backend,
            'local-llm-studio-web.service':web,'local-llm-studio-gateway.service':gateway}


def write_private(path:Path,content:str) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_symlink():
        raise ValueError(f'Refusing to replace a symlink: {path}')
    descriptor,temporary_name=tempfile.mkstemp(prefix='.'+path.name+'.',dir=path.parent)
    temporary=Path(temporary_name)
    try:
        with os.fdopen(descriptor,'w') as file:
            file.write(content)
        os.replace(temporary,path)
        path.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)


def update_env(content:str,values:dict[str,str]) -> str:
    lines=content.splitlines()
    for key,value in values.items():
        replacement=f'{key}={value}'
        pattern=re.compile(r'^\s*(?:export\s+)?'+re.escape(key)+r'\s*=')
        positions=[i for i,line in enumerate(lines) if pattern.match(line)]
        if positions:
            lines[positions[0]]=replacement
            for index in reversed(positions[1:]):
                lines.pop(index)
        else:
            lines.append(replacement)
    return '\n'.join(lines)+'\n'


def required_program(name:str) -> str:
    program=shutil.which(name)
    if not program:
        raise RuntimeError(f'{name} is not installed/in PATH. See docs/LAN_QUICKSTART.md.')
    return str(Path(program).absolute())


def check_local_ports(systemctl:str) -> None:
    for port,service in [(8000,'backend'),(3000,'web')]:
        with socket.socket() as connection:
            connection.settimeout(.5)
            listening=connection.connect_ex(('127.0.0.1',port))==0
        managed=subprocess.run([systemctl,'--user','is-active','--quiet',f'local-llm-studio-{service}.service'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
        if listening and not managed:
            raise RuntimeError(f'Port {port} is used by an unmanaged process. Stop the existing backend/web terminal with Ctrl+C, then rerun. No process was killed.')


def certificate_fingerprint(path:Path) -> str:
    der=ssl.PEM_cert_to_DER_cert(path.read_text())
    return ':'.join(f'{byte:02X}' for byte in hashlib.sha256(der).digest())


def export_ca(root:Path,generated:Path) -> Path:
    source=root/'data/lan-gateway/caddy/pki/authorities/local/root.crt'
    if not source.is_file():
        raise RuntimeError('Gateway CA not created yet; inspect the gateway service logs.')
    target=generated/'studio-lan-root.crt'
    write_private(target,source.read_text())
    print('Public CA certificate:',target)
    print('CA SHA-256 fingerprint (certificate DER):',certificate_fingerprint(target))
    print('CA file SHA-256:',hashlib.sha256(target.read_bytes()).hexdigest())
    return target


def verify_gateway(origin:str,ca:Path) -> None:
    context=ssl.create_default_context(cafile=str(ca))
    with urlopen(origin+'/api/auth/me',context=context,timeout=5) as response:
        status=json.load(response)
    if not status.get('lan_mode') or status.get('authenticated'):
        raise RuntimeError('Gateway did not report anonymous authenticated-LAN mode.')
    try:
        urlopen(origin+'/api/conversations',context=context,timeout=5)
    except HTTPError as error:
        if error.code!=401:
            raise
    else:
        raise RuntimeError('Unauthenticated conversation access was not denied.')
    with urlopen(origin+'/chat',context=context,timeout=5) as response:
        if not response.url.endswith('/login'):
            raise RuntimeError('Private page did not redirect to the login page.')
    print('PASS: TLS certificate verified; anonymous API denied; page redirects to login')


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--address',required=True,type=private_address)
    parser.add_argument('--port',type=int,default=8443)
    parser.add_argument('--apply',action='store_true',help='Build, update .env, install/start user services on this host')
    parser.add_argument('--check',action='store_true',help='Export public CA and verify the existing HTTPS gateway')
    args=parser.parse_args()
    if args.apply and os.geteuid()==0:
        raise RuntimeError('Run the installer as your normal desktop user, not with sudo.')
    os.chdir(ROOT)
    generated=ROOT/'deploy/generated/lan'
    origin=f'https://{args.address}:{args.port}'
    path=os.environ.get('PATH','/usr/local/bin:/usr/bin:/bin')
    caddy=shutil.which('caddy') or '/usr/bin/caddy'
    files=render(ROOT,args.address,args.port,path,caddy)
    if args.check:
        profile=json.loads((generated/'profile.json').read_text())
        if profile['origin']!=origin:
            raise RuntimeError('Address/port do not match the prepared deployment profile.')
        verify_gateway(origin,export_ca(ROOT,generated))
        return
    if args.apply:
        caddy=required_program('caddy')
        systemctl=required_program('systemctl')
        npm=required_program('npm')
        required_program('node')
        files=render(ROOT,args.address,args.port,path,caddy)
        for name in files:
            if name.endswith('.service') and (Path.home()/'.config/systemd/user'/name).is_symlink():
                raise ValueError('Existing service unit is a symlink; manage it manually instead of replacing it.')
        subprocess.run([systemctl,'--user','show-environment'],check=True,stdout=subprocess.DEVNULL)
        check_local_ports(systemctl)
        with socket.socket() as binding:
            try:
                binding.bind((args.address,args.port))
            except OSError as error:
                managed=subprocess.run([systemctl,'--user','is-active','--quiet','local-llm-studio-gateway.service'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
                if error.errno!=errno.EADDRINUSE or not managed:
                    raise RuntimeError('HTTPS address/port cannot be bound; check the IP and other listeners.')
        if (ROOT/'.env').is_symlink():
            raise ValueError('Manage the existing .env symlink manually before applying deployment.')
        from backend.core.config import settings
        previous=settings()
        password_hash=previous.admin_password_hash
        if not password_hash:
            from backend.services.auth import hash_password
            password=getpass.getpass('Administrator password (12+ characters; never sent to chat): ')
            if password!=getpass.getpass('Repeat administrator password: '):
                raise ValueError('Passwords do not match.')
            password_hash=hash_password(password)
        # Build before changing any running service/configuration.
        subprocess.run([npm,'run','build','--prefix',str(ROOT/'apps/web')],check=True)
    generated.mkdir(parents=True,exist_ok=True)
    generated.chmod(0o700)
    for name,content in files.items():
        write_private(generated/name,content)
    write_private(generated/'profile.json',json.dumps({'origin':origin,'address':args.address,'port':args.port},indent=2)+'\n')
    print('Prepared native production deployment:',generated)
    print('HTTPS browser address:',origin)
    if not args.apply:
        print('STAGED ONLY: no .env, systemd, firewall or trust-store changes. Rerun with --apply on the Linux host.')
        return
    data=ROOT/'data'
    data.mkdir(exist_ok=True)
    backups=data/'backups'
    backups.mkdir(exist_ok=True)
    backups.chmod(0o700)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    old_env=(ROOT/'.env').read_text() if (ROOT/'.env').exists() else ''
    write_private(backups/f'lan-before-{stamp}.env',old_env)
    from sqlalchemy.engine import make_url
    database=make_url(previous.database_url)
    if database.get_backend_name()!='sqlite' or not database.database or database.database==':memory:':
        raise RuntimeError('Native LAN installer supports a file-backed SQLite database only.')
    source=Path(database.database).resolve()
    if source.is_file():
        destination=backups/f'studio-before-lan-{stamp}.sqlite3'
        destination.touch(mode=0o600)
        with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as connection,sqlite3.connect(destination) as backup:
            connection.backup(backup)
    gateway_environment={**os.environ,'XDG_DATA_HOME':str(data/'lan-gateway'),'XDG_CONFIG_HOME':str(data/'lan-gateway-config')}
    subprocess.run([caddy,'validate','--config',str(generated/'Caddyfile'),'--adapter','caddyfile'],check=True,env=gateway_environment)
    unit_dir=Path.home()/'.config/systemd/user'
    unit_dir.mkdir(parents=True,exist_ok=True)
    for name,content in files.items():
        if name.endswith('.service'):
            target=unit_dir/name
            if target.exists():
                write_private(backups/f'{name}-{stamp}.bak',target.read_text())
            write_private(target,content)
    write_private(ROOT/'.env',update_env(old_env,{'STUDIO_LAN_MODE':'true','STUDIO_WEB_ORIGIN':origin,'STUDIO_ADMIN_PASSWORD_HASH':password_hash}))
    subprocess.run([systemctl,'--user','daemon-reload'],check=True)
    services=['local-llm-studio-backend','local-llm-studio-web','local-llm-studio-gateway']
    subprocess.run([systemctl,'--user','enable',*services],check=True)
    for service in services:
        subprocess.run([systemctl,'--user','restart',service],check=True)
    deadline=time.monotonic()+45
    while time.monotonic()<deadline:
        try:
            ca=ROOT/'data/lan-gateway/caddy/pki/authorities/local/root.crt'
            if ca.is_file():
                verify_gateway(origin,ca)
                export_ca(ROOT,generated)
                print('Started native user services. Complete client CA import and second-PC testing in docs/LAN_QUICKSTART.md.')
                return
        except (OSError,URLError,ValueError,RuntimeError):
            pass
        time.sleep(1)
    raise RuntimeError('Services were installed but HTTPS checks did not pass. Inspect journalctl --user -u local-llm-studio-gateway -u local-llm-studio-web -u local-llm-studio-backend. Config backups are in data/backups.')

if __name__=='__main__':
    try:
        main()
    except (Exception,KeyboardInterrupt) as error:
        print(f'Deployment not verified: {error}',file=sys.stderr)
        raise SystemExit(1)
