"""Independently inspect populated engineering images and bind boot inventory."""
import argparse
import hashlib
import json
from pathlib import Path
from check_pi_fat import inspect

ROOT=Path(__file__).resolve().parents[1]
LOCK_SHA='537d7d3b991369db5ec4bb3475ddf37b41dd2217b56b53e44d69c163b356e850'
CONFIG=b'[all]\narm_64bit=1\nkernel=kernel8.img\nkernel_address=0x200000\ndevice_tree=bcm2710-rpi-zero-2-w.dtb\n'


def check(path):
    report=json.loads(path.read_text())
    lock_bytes=(ROOT/'assets/locks/rpi-zero2w-boot-assets.lock.json').read_bytes()
    if hashlib.sha256(lock_bytes).hexdigest()!=LOCK_SHA or report['asset_lock_sha256']!=LOCK_SHA:
        raise ValueError('Unapproved asset lock')
    lock=json.loads(lock_bytes)
    expected={asset['path']:asset['sha256'] for asset in lock['assets']}
    expected['config.txt']=hashlib.sha256(CONFIG).hexdigest()
    variants=report['variants']
    if [v['variant'] for v in variants]!=['normal','panic-test']:
        raise ValueError('Wrong variants')
    results=[]
    for variant in variants:
        flat=Path(variant['flat_kernel']).read_bytes()
        digest=hashlib.sha256(flat).hexdigest()
        if digest!=variant['flat_sha256'] or len(flat)!=variant['flat_bytes']:
            raise ValueError('Wrong flat kernel identity')
        wanted={**expected,'kernel8.img':digest}
        if variant['inventory']!=wanted:
            raise ValueError('Declared boot inventory differs from lock/config/kernel')
        image=Path(variant['sd_image']).read_bytes()
        result=inspect(image,wanted)
        if result['image_sha256']!=variant['image_sha256'] or len(image)!=variant['image_bytes']:
            raise ValueError('Wrong image identity')
        results.append({'variant':variant['variant'],**result})
    if results[0]['image_sha256']==results[1]['image_sha256']:
        raise ValueError('Normal and panic images confused')
    return {'passed':True,'asset_lock_sha256':LOCK_SHA,'compiler_report_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'images':results,'scope':'Engineering images only; source archive and complete bundle publication not covered. Inspection does not establish firmware or physical boot success.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-report',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    result=check(args.compiler_report)
    with args.report.open('x') as output:json.dump(result,output,indent=2);output.write('\n')
    print(json.dumps({'passed':True,'images':[{k:r[k] for k in ['variant','image_sha256','allocated_clusters']} for r in result['images']]}))
