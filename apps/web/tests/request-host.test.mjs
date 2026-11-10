import {test} from 'node:test';
import assert from 'node:assert/strict';
import {allowedRequestHost,lanModeEnabled} from '../lib/request-host.ts';
test('only configured or loopback hosts can reach the same-origin proxy',()=>{
 const origin='https://studio.home.arpa';
 for(const host of ['studio.home.arpa','studio.home.arpa:443','127.0.0.1:3000','localhost:3000','[::1]:3000'])assert.equal(allowedRequestHost(host,origin),true,host);
 for(const host of [null,'evil.invalid','localhost.evil.invalid','studio.home.arpa.evil.invalid','user@localhost:3000','localhost:3000/path'])assert.equal(allowedRequestHost(host,origin),false,String(host));
});

test('LAN activation matches backend boolean spellings',()=>{
 for(const value of ['true','TRUE','1','yes','on','y','t'])assert.equal(lanModeEnabled(value),true);
 for(const value of [undefined,'false','0','off','no'])assert.equal(lanModeEnabled(value),false);
});
