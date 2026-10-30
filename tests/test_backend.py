import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi.testclient import TestClient
from backend.server import create_app


class CommerceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app(self.temp.name, secure_cookie=False)
        self.admin = TestClient(self.app)
        self.admin.__enter__()
        self.csrf(self.admin)
        token = (Path(self.temp.name) / 'bootstrap-token').read_text()
        response = self.post(self.admin, '/api/setup', {'bootstrap_token': token, 'name': 'Test Admin', 'email': 'admin@example.test', 'password': 'Administrator-test-123', 'accepted_terms': True, 'adult': True})
        self.assertEqual(response.status_code, 200, response.text)
        self.customer = TestClient(self.app)
        self.csrf(self.customer)
        response = self.post(self.customer, '/api/auth/register', {'name': 'Test Customer', 'email': 'customer@example.test', 'password': 'Customer-test-password-123', 'accepted_terms': True, 'adult': True})
        self.assertEqual(response.status_code, 200, response.text)

    def tearDown(self):
        self.customer.close()
        self.admin.__exit__(None, None, None)
        self.temp.cleanup()

    def csrf(self, client):
        token = client.get('/api/auth/session').json()['csrf']
        client.headers['X-CSRF-Token'] = token
        return token

    def post(self, client, path, body, method='post'):
        self.csrf(client)
        result = getattr(client, method)(path, json=body)
        if result.status_code < 300 and 'csrf' in result.json():
            client.headers['X-CSRF-Token'] = result.json()['csrf']
        return result

    def order(self, key='checkout-key-0000001', qty=1, size=42):
        return {'items': [{'id': 'aero-ice', 'size': size, 'qty': qty}], 'coupon': '', 'name': 'Test Customer', 'email': 'customer@example.test', 'phone': '0123456789', 'address': 'Example address for test', 'postcode': '50000', 'payment': 'manual', 'idempotency_key': key}

    def stock(self, size=42):
        products = self.customer.get('/api/products').json()['products']
        return next(p for p in products if p['id']=='aero-ice')['stock'][str(size)]

    def test_authentication_csrf_and_role_boundaries(self):
        anonymous = TestClient(self.app)
        self.assertEqual(anonymous.get('/api/admin/dashboard').status_code, 401)
        self.assertEqual(self.customer.get('/api/admin/dashboard').status_code, 403)
        self.assertEqual(anonymous.post('/api/auth/login', json={'email': 'admin@example.test', 'password': 'Administrator-test-123'}).status_code, 403)
        self.csrf(self.customer)
        self.assertEqual(self.customer.post('/api/auth/logout', json={}, headers={'Origin': 'https://evil.example'}).status_code, 403)
        cookie = self.customer.cookies.get('kenny_session')
        self.assertTrue(cookie)
        self.assertEqual(self.post(self.customer, '/api/auth/register', {'name': 'Bad User', 'email': 'new@example.test', 'password': 'long-enough-password', 'accepted_terms': True, 'adult': True, 'role': 'admin'}).status_code, 422)
        result = self.post(self.customer, '/api/auth/logout', {})
        self.assertIn('HttpOnly', result.headers['set-cookie'])
        self.assertIn('SameSite=lax', result.headers['set-cookie'])
        self.assertNotEqual(cookie, self.customer.cookies.get('kenny_session'))
        self.assertIsNone(result.json()['user'])
        self.assertEqual(self.customer.get('/api/orders').status_code, 401)
        self.assertEqual(self.post(self.customer, '/api/auth/login', {'email':'customer@example.test','password':'Customer-test-password-123'}).status_code,200)

    def test_server_price_idempotency_and_cancel_releases_stock(self):
        before = self.stock()
        payload = self.order(qty=2)
        payload['coupon'] = 'KENNY10'
        response = self.post(self.customer, '/api/orders', payload)
        self.assertEqual(response.status_code,200,response.text)
        order = response.json()
        self.assertEqual(order['subtotal_cents'],77800)
        self.assertEqual(order['discount_cents'],7780)
        self.assertEqual(order['shipping_cents'],0)
        self.assertEqual(order['total_cents'],70020)
        self.assertEqual(order['payment_status'],'unpaid')
        self.assertEqual(self.stock(),before-2)
        duplicate = self.post(self.customer, '/api/orders', payload)
        self.assertEqual(duplicate.json()['id'],order['id'])
        self.assertEqual(self.stock(),before-2)
        payload['items'][0]['qty']=1
        self.assertEqual(self.post(self.customer,'/api/orders',payload).status_code,409)
        self.assertEqual(self.post(self.customer,'/api/orders/'+order['id']+'/cancel',{}).status_code,200)
        self.assertEqual(self.stock(),before)
        self.assertEqual(self.post(self.customer,'/api/orders/'+order['id']+'/cancel',{}).status_code,409)
        self.assertEqual(self.admin.get('/api/admin/coupons').json()['coupons'][0]['uses'],0)
        tamper=self.order('price-injection-001');tamper['total_cents']=1
        self.assertEqual(self.post(self.customer,'/api/orders',tamper).status_code,422)

    def test_ownership_stock_race_and_duplicate_lines(self):
        self.assertEqual(self.post(self.admin,'/api/admin/products/aero-ice/stock',{'size':42,'quantity':1,'note':'Race test'},'put').status_code,200)
        self.csrf(self.customer)
        headers={'X-CSRF-Token':self.customer.headers['X-CSRF-Token']}
        cookie=self.customer.cookies.get('kenny_session')
        def buy(index):
            with TestClient(self.app) as client:
                client.cookies.set('kenny_session',cookie)
                return client.post('/api/orders',json=self.order('concurrent-checkout-'+str(index)),headers=headers)
        with ThreadPoolExecutor(max_workers=3) as executor:
            responses=list(executor.map(buy,range(3)))
        self.assertEqual(sorted(r.status_code for r in responses),[200,409,409])
        self.assertEqual(self.stock(),0)
        oid=next(r.json()['id'] for r in responses if r.status_code==200)
        other=TestClient(self.app);self.csrf(other)
        self.post(other,'/api/auth/register',{'name':'Another Customer','email':'another@example.test','password':'Another-password-123','accepted_terms':True,'adult':True})
        self.assertEqual(other.get('/api/orders/'+oid).status_code,404)
        self.assertEqual(self.post(other,'/api/orders/'+oid+'/cancel',{}).status_code,404)
        payload=self.order('duplicate-line-test');payload['items']*=2
        self.assertIn(self.post(other,'/api/orders',payload).status_code,[400,409])

    def test_fulfilment_manual_payments_refund_and_audit(self):
        order=self.post(self.customer,'/api/orders',self.order()).json();oid=order['id']
        def action(name,**extra):
            return self.post(self.admin,'/api/admin/orders/'+oid+'/action',{'action':name,'note':'Test offline proof',**extra})
        self.assertEqual(action('ship',carrier='Carrier',tracking_number='TEST123').status_code,409)
        self.assertEqual(action('mark_paid').status_code,200)
        self.assertEqual(action('mark_paid').status_code,409)
        self.assertEqual(action('process').status_code,200)
        self.assertEqual(action('ship').status_code,400)
        self.assertEqual(action('ship',carrier='Test Carrier',tracking_number='TEST123').status_code,200)
        self.assertEqual(action('complete').status_code,200)
        self.assertEqual(self.customer.get('/api/orders/'+oid).json()['tracking_number'],'TEST123')
        self.assertEqual(self.post(self.customer,'/api/orders/'+oid+'/refund-request',{'reason':'Example refund request'}).status_code,200)
        self.assertEqual(action('approve_refund').status_code,200)
        result=self.customer.get('/api/orders/'+oid).json()
        self.assertEqual(result['payment_status'],'refunded')
        self.assertEqual(result['status'],'refunded')
        events=self.admin.get('/api/admin/audit').json()['events']
        self.assertTrue(any(e['action']=='approve_refund' for e in events))

    def test_product_stock_settings_reviews_and_messages(self):
        product=self.admin.get('/api/admin/products').json()['products'][0]
        allowed={'id','name','category','audience','color','price_cents','original_price_cents','description','badge','image','bg','active','outlet','translations'}
        payload={k:v for k,v in product.items() if k in allowed};payload['name']='Updated Shoe';payload['active']=False
        self.assertEqual(self.post(self.admin,'/api/admin/products/'+payload['id'],payload,'put').status_code,200)
        self.assertNotIn(payload['id'],[p['id'] for p in self.customer.get('/api/products').json()['products']])
        self.assertEqual(self.post(self.admin,'/api/admin/products/'+payload['id']+'/stock',{'size':42,'quantity':-1,'note':'Bad input'},'put').status_code,422)
        settings=self.admin.get('/api/settings').json();settings['social_links']={'instagram':'javascript:alert(1)'}
        self.assertEqual(self.post(self.admin,'/api/admin/settings',settings,'put').status_code,422)
        result=self.post(self.customer,'/api/contact',{'name':'Test User','email':'test@example.test','message':'Test support message'})
        self.assertEqual(result.status_code,200)
        self.assertEqual(len(self.admin.get('/api/admin/messages').json()['messages']),1)
        self.assertEqual(self.post(self.customer,'/api/products/aero-ice/reviews',{'rating':5,'text':'Test product review'}).status_code,200)
        self.assertEqual(self.customer.get('/api/products/aero-ice/reviews').json()['reviews'],[])
        rid=self.admin.get('/api/admin/reviews').json()['reviews'][0]['id']
        self.assertEqual(self.post(self.admin,'/api/admin/reviews/'+rid,{'status':'published'},'put').status_code,200)
        self.assertEqual(len(self.customer.get('/api/products/aero-ice/reviews').json()['reviews']),1)

    def test_upload_newsletter_and_store_settings(self):
        import io
        from PIL import Image
        image = io.BytesIO()
        Image.new('RGB', (12, 12), 'purple').save(image, 'PNG')
        self.csrf(self.admin)
        response = self.admin.post('/api/admin/uploads', content=image.getvalue(), headers={'Content-Type': 'image/png'})
        self.assertEqual(response.status_code, 200, response.text)
        saved = self.customer.get('/' + response.json()['path'])
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.headers['content-type'], 'image/webp')
        self.csrf(self.customer)
        self.assertEqual(self.customer.post('/api/admin/uploads', content=image.getvalue(), headers={'Content-Type':'image/png'}).status_code, 403)
        self.assertEqual(self.admin.post('/api/admin/uploads', content=b'<svg/>', headers={'Content-Type':'image/svg+xml'}).status_code, 400)
        for _ in range(2):
            self.assertEqual(self.post(self.customer, '/api/newsletter', {'email':'Subscriber@Example.test'}).status_code, 200)
        self.assertEqual(len(self.admin.get('/api/admin/subscribers').json()['subscribers']), 1)
        self.assertEqual(self.customer.get('/api/admin/subscribers').status_code, 403)
        settings = self.admin.get('/api/settings').json()
        settings['stores'] = [{'id':'test-store','name':'Test showroom','city':'Test city','address':'Example address','hours':'10–18','map_url':'https://maps.example.test','active':True}]
        self.assertEqual(self.post(self.admin, '/api/admin/settings', settings, 'put').status_code, 200)
        self.assertEqual(self.customer.get('/api/settings').json()['stores'][0]['name'], 'Test showroom')
        settings['stores'][0]['map_url'] = 'javascript:alert(1)'
        self.assertEqual(self.post(self.admin, '/api/admin/settings', settings, 'put').status_code, 422)

    def test_expiry_persistence_customer_block_and_static_boundaries(self):
        before=self.stock();order=self.post(self.customer,'/api/orders',self.order()).json()
        with sqlite3.connect(self.app.state.database) as conn:
            old=(datetime.now(timezone.utc)-timedelta(minutes=31)).isoformat(timespec='seconds')
            conn.execute('UPDATE orders SET created_at=? WHERE id=?',(old,order['id']))
        self.assertEqual(self.customer.get('/api/orders/'+order['id']).json()['status'],'expired')
        self.assertEqual(self.stock(),before)
        account=self.customer.get('/api/auth/session').json()['user']
        self.assertEqual(self.post(self.admin,'/api/admin/customers/'+account['id'],{'active':False},'put').status_code,200)
        self.assertEqual(self.customer.get('/api/orders').status_code,401)
        reopened=create_app(self.temp.name,secure_cookie=False)
        with TestClient(reopened) as client:
            self.assertFalse(client.get('/api/setup/status').json()['required'])
            for path in ['/.data/kenny.sqlite3','/backend/server.py','/.git/config','/requirements.txt','/admin/../backend/server.py']:
                self.assertEqual(client.get(path).status_code,404,path)
            self.assertEqual(client.get('/admin/').status_code,200)
            self.assertEqual(client.get('/api/products').status_code,200)


if __name__=='__main__':
    unittest.main()
