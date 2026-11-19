import sys
import json
from types import ModuleType
from unittest.mock import Mock, patch
import unittest
import numpy as np
from spaceship_viewer.catalog_network import fetch_hipparcos, HIPPARCOS_SERVERS


def table():
    return {'HIP':[1,2], 'RAICRS':[1.,2.], 'DEICRS':[0.,1.], 'Vmag':[1.,1.5],
            'B-V':np.ma.array([.4,999.],mask=[False,True]), 'Plx':[100.,-1.]}


class CatalogNetworkTests(unittest.TestCase):
    def factory(self, clients):
        module = ModuleType('astroquery.vizier')
        module.Vizier = Mock(side_effect=clients)
        return module

    def test_http_failure_falls_back_and_records_successful_mirror(self):
        first = Mock()
        first.query_constraints.side_effect = RuntimeError('HTTP 404 controlled fixture')
        second = Mock()
        second.query_constraints.return_value = [table()]
        module = self.factory([first,second])
        with patch.dict(sys.modules, {'astroquery.vizier':module}):
            result = fetch_hipparcos(2.)
        self.assertIn(HIPPARCOS_SERVERS[1], result.metadata.source)
        self.assertIn('HTTP 404', result.metadata.notes[-1])
        self.assertTrue(np.isnan(result.bv[1]) and np.isnan(result.distance_pc[1]))
        self.assertEqual(result.distance_pc[0],10.)
        second.query_constraints.assert_called_once_with(catalog='I/239/hip_main',Vmag='<2.0',cache=False)
        self.assertEqual(first.TIMEOUT,15.)

    def test_all_failures_report_each_server(self):
        clients = [Mock() for _ in HIPPARCOS_SERVERS]
        for client in clients:
            client.query_constraints.side_effect = RuntimeError('controlled offline fixture')
        module = self.factory(clients)
        with patch.dict(sys.modules, {'astroquery.vizier':module}), self.assertRaises(RuntimeError) as error:
            fetch_hipparcos()
        for host in HIPPARCOS_SERVERS:
            self.assertIn(host,str(error.exception))
        self.assertIn('current catalog is unchanged',str(error.exception))

    def test_rejected_live_rows_remain_json_serializable(self):
        from spaceship_viewer.session import make_document,decode_document
        from spaceship_viewer.state import ViewState
        from spaceship_viewer.presentation import Presentation
        data = table()
        data['DEICRS'] = [0.,float('nan')]
        client = Mock()
        client.query_constraints.return_value = [data]
        module = self.factory([client])
        with patch.dict(sys.modules, {'astroquery.vizier':module}):
            catalog = fetch_hipparcos()
        document = json.loads(json.dumps(make_document(catalog,ViewState(),Presentation()),allow_nan=False))
        reopened,_,_,_ = decode_document(document)
        self.assertEqual(reopened.n,1)
        self.assertEqual(reopened.import_report.rejected[0].line,2)
        self.assertEqual(reopened.import_report.total_rows,2)

    def test_empty_response_retries_and_unsupported_server_is_rejected(self):
        first,second = Mock(),Mock()
        first.query_constraints.return_value = []
        second.query_constraints.return_value = [table()]
        module = self.factory([first,second])
        with patch.dict(sys.modules, {'astroquery.vizier':module}):
            self.assertEqual(fetch_hipparcos().n,2)
            with self.assertRaises(ValueError):
                fetch_hipparcos(servers=('unknown.example',))
