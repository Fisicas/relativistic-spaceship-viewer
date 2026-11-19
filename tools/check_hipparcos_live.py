"""Explicit live service check; preserve the response diagnostic and catalog.

This contacts public VizieR endpoints. It does not establish catalog measurement
accuracy, completeness, or uncertainty estimates.
"""
from pathlib import Path
import argparse
from dataclasses import asdict
import hashlib
import json
import sys
import time
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',required=True,type=Path)
    parser.add_argument('--limit',type=float,default=8.)
    args=parser.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=False)
    from astroquery.vizier import Vizier
    from spaceship_viewer.catalog import fetch_hipparcos
    from spaceship_viewer.session import save_document,load_document
    from spaceship_viewer.state import ViewState
    from spaceship_viewer.presentation import Presentation
    main_site={}
    try:
        client=Vizier(columns=['HIP'],row_limit=3,vizier_server='vizier.cds.unistra.fr',timeout=8.)
        response=client.query_constraints_async(catalog='I/239/hip_main',Vmag='<2.',cache=False)
        raw=args.output_dir/'main_site_response.bin'
        raw.write_bytes(response.content)
        main_site={'status_code':response.status_code,'url':response.url,
                   'response_sha256':hashlib.sha256(response.content).hexdigest(),'raw_response':str(raw)}
    except Exception as exc:
        main_site={'exception':type(exc).__name__,'message':str(exc)}
    (args.output_dir/'main_site_diagnostic.json').write_text(json.dumps(main_site,indent=2),encoding='utf-8')
    started=time.perf_counter()
    catalog=fetch_hipparcos(args.limit)
    assert catalog.n and np.all(catalog.vmag<args.limit)
    snapshot=args.output_dir/'hipparcos_scene.json'
    save_document(snapshot,catalog,ViewState(rest_mag_limit=args.limit),Presentation(),f'Live Hipparcos V < {args.limit:g}')
    reopened,_,_,_=load_document(snapshot)
    np.testing.assert_array_equal(catalog.ra_deg,reopened.ra_deg)
    np.testing.assert_array_equal(catalog.bv,reopened.bv)
    result={'status':'passed','main_site_diagnostic':main_site,'rows':catalog.n,
            'rows_received':catalog.import_report.total_rows,'rows_rejected':len(catalog.import_report.rejected),
            'seconds':time.perf_counter()-started,'rest_vmag_limit_exclusive':args.limit,
            'metadata':asdict(catalog.metadata),'unknown_bv':int(np.isnan(catalog.bv).sum()),
            'unknown_distance':int(np.isnan(catalog.distance_pc).sum()),'snapshot':str(snapshot),
            'snapshot_sha256':hashlib.sha256(snapshot.read_bytes()).hexdigest(),
            'scientific_scope':'service and serialization check; not observational validation'}
    (args.output_dir/'live_check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
