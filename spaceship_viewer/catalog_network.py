"""Explicit HTTPS VizieR mirror fallback; no global Astroquery configuration.

CDS lists these mirrors at https://vizier.cds.unistra.fr/. The main endpoint
was degraded in November 2026; keep it as the last fallback. A failed query
never substitutes the demo or a partial table for a successfully fetched one.
"""
from dataclasses import replace
from .geometry import finite_scalar

HIPPARCOS_SERVERS = ('vizier.cfa.harvard.edu', 'vizier.idia.ac.za', 'vizier.cds.unistra.fr')


def fetch_hipparcos(max_vmag=8., *, servers=HIPPARCOS_SERVERS, timeout=15.):
    from astroquery.vizier import Vizier
    from .catalog import catalog_from_hipparcos_table
    limit = finite_scalar(max_vmag, 'Hipparcos rest V magnitude limit')
    timeout = finite_scalar(timeout, 'VizieR timeout')
    if timeout <= 0 or not servers or any(host not in HIPPARCOS_SERVERS for host in servers):
        raise ValueError('Use a listed VizieR HTTPS mirror and a positive timeout.')
    failures = []
    for host in servers:
        try:
            query = Vizier(columns=['HIP', 'RAICRS', 'DEICRS', 'Vmag', 'B-V', 'Plx'],
                           row_limit=-1, vizier_server=host)
            query.TIMEOUT = timeout
            result = query.query_constraints(catalog='I/239/hip_main', Vmag=f'<{limit}', cache=False)
            if not result:
                raise RuntimeError('No Hipparcos table returned.')
            catalog = catalog_from_hipparcos_table(result[0], limit)
            notes = catalog.metadata.notes + (
                f'VizieR HTTPS server: {host}; table I/239/hip_main; no response cache used.',
                f'Mirror attempts before success: {len(failures)}; ' + ('; '.join(failures) or 'none failed.'))
            return replace(catalog, metadata=replace(catalog.metadata,
                source=f'VizieR I/239/hip_main (ESA 1997), https://{host}/viz-bin/votable', notes=notes))
        except Exception as exc:
            failures.append(f'{host}: {type(exc).__name__}: {exc}')
    raise RuntimeError('Hipparcos could not be retrieved from the VizieR HTTPS mirrors. '
                       'The current catalog is unchanged. CDS service status: https://vizier.cds.unistra.fr/\n\n'
                       + '\n'.join(failures))
