import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest.mock import patch
import store
import server

SAMPLE = {'prompt':'Return the first even number.', 'category':'Python', 'model_a':'model-one',
          'response_a':'next(x for x in values if x % 2 == 0)', 'model_b':'model-two',
          'response_b':'next(x for x in values if x % 2 == 1)'}
REVIEW = {'preference':'a','reason':'A checks parity correctly.',
          'scores':{'a':dict.fromkeys(store.CRITERIA,5),'b':dict.fromkeys(store.CRITERIA,2)}}


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name)/'test.sqlite3')
        store.initialize(self.path)
        with patch('store.secrets.randbelow', return_value=0):
            store.ingest(self.path,[SAMPLE])

    def tearDown(self):
        self.temp.cleanup()

    def test_blind_until_review_and_export_excludes_pending(self):
        before = store.comparison(self.path,1)
        self.assertNotIn('model_a',before)
        self.assertNotIn('model_b',before)
        self.assertEqual(store.export(self.path),[])
        after = store.review(self.path,1,REVIEW)
        self.assertEqual(after['model_a'],'model-one')
        self.assertEqual(len(store.export(self.path)),1)

    def test_randomization_swaps_response_and_identity_together(self):
        with patch('store.secrets.randbelow', return_value=1):
            store.ingest(self.path,[SAMPLE])
        self.assertEqual(store.comparison(self.path,2)['response_a'], SAMPLE['response_b'])
        after=store.review(self.path,2,REVIEW)
        self.assertEqual(after['model_a'],SAMPLE['model_b'])
        self.assertEqual(store.comparison(self.path,2),after)

    def test_atomic_import(self):
        with self.assertRaises(ValueError):
            store.ingest(self.path,[SAMPLE,{'prompt':'incomplete'}])
        self.assertEqual(len(store.queue(self.path)),1)

    def test_scores_reject_bool_float_missing_and_out_of_range(self):
        for value in (True, 2.5, 0, 6, '3', None):
            item=json.loads(json.dumps(REVIEW))
            item['scores']['a']['clarity']=value
            with self.assertRaises(ValueError): store.review(self.path,1,item)
        item=json.loads(json.dumps(REVIEW)); del item['scores']['b']['clarity']
        with self.assertRaises(ValueError): store.review(self.path,1,item)

    def test_review_is_immutable(self):
        store.review(self.path,1,REVIEW)
        with self.assertRaises(FileExistsError): store.review(self.path,1,{**REVIEW,'preference':'b'})
        self.assertEqual(store.comparison(self.path,1)['review']['preference'],'a')

    def test_unknown_id(self):
        with self.assertRaises(LookupError): store.review(self.path,999,REVIEW)

    def test_summary_accounts_for_tie_neither_and_side_mapping(self):
        store.ingest(self.path,[SAMPLE,SAMPLE])
        store.review(self.path,1,REVIEW)
        store.review(self.path,2,{**REVIEW,'preference':'tie'})
        store.review(self.path,3,{**REVIEW,'preference':'neither'})
        stats=store.summary(self.path)
        self.assertEqual(stats['reviewed'],3)
        self.assertEqual(stats['models']['model-one']['wins'],1)
        for result in stats['models'].values():
            self.assertEqual(result['appearances'],3)
            self.assertEqual(result['ties'],1)
            self.assertEqual(result['neither'],1)


class HTTPTests(StoreTests):
    # Inherit persistence checks against the same real database used by HTTP.
    def setUp(self):
        super().setUp()
        self.server=ThreadingHTTPServer(('127.0.0.1',0),server.handler(self.path))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        super().tearDown()

    def request(self,method,path,body=None,headers=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
        connection.request(method,path,body,headers or {})
        response=connection.getresponse(); data=response.read(); status=response.status
        connection.close(); return status,data

    def test_http_save_reveal_conflict_export(self):
        status,body=self.request('GET','/api/comparisons/1')
        self.assertEqual(status,200); self.assertNotIn('model_a',json.loads(body))
        headers={'Content-Type':'application/json'}
        self.assertEqual(self.request('POST','/api/reviews/1',json.dumps(REVIEW),headers)[0],201)
        self.assertEqual(self.request('POST','/api/reviews/1',json.dumps(REVIEW),headers)[0],409)
        status,body=self.request('GET','/api/export')
        self.assertEqual(json.loads(body)['reviews'][0]['model_a'],'model-one')

    def test_http_invalid_json_and_cross_origin(self):
        self.assertEqual(self.request('POST','/api/import','{',{'Content-Type':'application/json'})[0],400)
        self.assertEqual(self.request('POST','/api/import','[]',{'Content-Type':'application/json','Origin':'https://evil.example'})[0],403)
        self.assertEqual(self.request('POST','/api/import','[]',{'Content-Type':'text/plain'})[0],415)
        self.assertEqual(self.request('POST','/api/import','[]',{'Content-Type':'application/json','Host':'evil.example'})[0],403)

    def test_static_allowlist_and_missing_comparison(self):
        self.assertEqual(self.request('GET','/api/export', headers={'Host':'evil.example'})[0],403)
        self.assertEqual(self.request('GET','/')[0],200)
        self.assertEqual(self.request('GET','/../store.py')[0],404)
        self.assertEqual(self.request('GET','/api/comparisons/999')[0],404)


if __name__=='__main__': unittest.main()
