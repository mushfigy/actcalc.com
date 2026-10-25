"""Non-mutating deployment smoke test, to run AFTER domain and secrets are configured.

This script checks public endpoints without submitting contact messages.
Usage: python deploy/verify_live.py https://actcalc.com
"""
from __future__ import annotations
import json, ssl, sys, urllib.request
from urllib.parse import urlparse


def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'ACTCalcLaunchAudit/1.0','Accept':'*/*'})
    with urllib.request.urlopen(req,timeout=12,context=ssl.create_default_context()) as response:
        return response.status,response.headers, response.read(4_000_000)


def main(url):
    u=urlparse(url)
    if u.scheme!='https' or u.netloc not in ('actcalc.com','www.actcalc.com'):
        raise SystemExit('Use the exact verified public ACTCalc HTTPS host.')
    expected={'/':'data-product-build="rev3-production-candidate"','/api/health':'public_access_enabled','/privacy':'Privacy information','/terms':'engineering limitations','/sw.js':'actcalc-','/manifest.webmanifest':'ACTCalc'}
    all_pass=True
    for path,needle in expected.items():
        try:
            status,headers,body=get(url.rstrip('/')+path)
            ok=status==200 and needle.encode() in body
            if path=='/api/health':
                state=json.loads(body)
                ok &= (state.get('public_access_enabled') is True and state.get('public_release_configuration_ready') is True)
            print(('PASS' if ok else 'FAIL'),path,status,headers.get('Content-Type'))
            all_pass &=ok
        except Exception as ex:
            all_pass=False
            print('FAIL',path,type(ex).__name__,str(ex)[:150])
    if not all_pass:raise SystemExit('NO-GO: live launch checks did not pass.')
    print('Basic live checks passed. Still verify real SMTP, data persistence/restore, operator/legal details and actual mobile browsers.')

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Usage: python deploy/verify_live.py https://actcalc.com')
    main(sys.argv[1])
