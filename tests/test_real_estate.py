import sqlite3
import unittest
import app, real_estate, commerce

class RealEstateTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(':memory:')
        self.c.row_factory = sqlite3.Row
        self.c.executescript(app.SCHEMA)
        self.c.execute("INSERT INTO companies(id,name) VALUES(1,'Inmobiliaria Test')")
        self.c.execute("INSERT INTO users(id,username,name,password) VALUES(1,'admin','Admin Inmobiliaria','!')")
        self.c.execute("INSERT INTO memberships(user_id,company_id,role,role_name) VALUES(1,1,'admin','Admin')")
        self.c.execute("INSERT INTO departments(id,company_id,name) VALUES(1,1,'Ventas y Alquileres')")
        self.c.execute("INSERT INTO employees(id,company_id,name,position,basis,rate,department_id) VALUES(1,1,'Laura Agente','Asesora Senior','monthly',3000000,1)")
        self.c.commit()

    def tearDown(self):
        self.c.close()

    def save(self, action, **data):
        with self.c:
            return app.mutate(self.c, 1, 1, action, data)

    def test_property_crud_and_status(self):
        # Create property
        res = self.save('create_re_property',
            title='Apartamento 4A Piantini',
            code='PROP-001',
            property_type='apartment',
            listing_type='rent',
            status='available',
            address='Calle Fantino Falco #22',
            city='Santo Domingo',
            price_rent='35000',
            price_sale='0',
            area_sqm=85.5,
            bedrooms=2,
            bathrooms=2,
            parking_spots=1,
            owner_name='Pedro Propietario',
            owner_phone='809-555-1234',
            agent_id=1
        )
        self.assertTrue(res['ok'])
        prop_id = res['id']

        # Verify property in state
        st = app.state(self.c, 1, 1)
        self.assertEqual(len(st['re_properties']), 1)
        self.assertEqual(st['re_properties'][0]['title'], 'Apartamento 4A Piantini')
        self.assertEqual(st['re_properties'][0]['price_rent'], 3500000)

        # Edit property
        edit_res = self.save('edit_re_property',
            id=prop_id,
            title='Apartamento 4A Piantini Amueblado',
            code='PROP-001',
            property_type='apartment',
            listing_type='rent',
            status='available',
            price_rent='40000'
        )
        self.assertTrue(edit_res['ok'])
        st = app.state(self.c, 1, 1)
        self.assertEqual(st['re_properties'][0]['title'], 'Apartamento 4A Piantini Amueblado')
        self.assertEqual(st['re_properties'][0]['price_rent'], 4000000)

        # Delete property
        del_res = self.save('delete_re_property', id=prop_id)
        self.assertTrue(del_res['ok'])
        st = app.state(self.c, 1, 1)
        self.assertEqual(len(st['re_properties']), 0)

    def test_lease_workflow_and_rent_charge(self):
        prop_id = self.save('create_re_property',
            title='Casa Residencial Alameda',
            price_rent='50000',
            listing_type='rent',
            status='available'
        )['id']

        # Create lease
        lease_res = self.save('create_re_lease',
            property_id=prop_id,
            tenant_name='María Inquilina',
            tenant_phone='809-444-5555',
            start_date=app.today().isoformat(),
            end_date=(app.today().replace(year=app.today().year + 1)).isoformat(),
            monthly_rent='50000',
            deposit_amount='100000',
            payment_day=5,
            agent_id=1
        )
        self.assertTrue(lease_res['ok'])
        lease_id = lease_res['id']

        # Property should automatically become rented
        st = app.state(self.c, 1, 1)
        prop = next(p for p in st['re_properties'] if p['id'] == prop_id)
        self.assertEqual(prop['status'], 'rented')

        # Cannot delete property while lease is active
        with self.assertRaises(ValueError):
            self.save('delete_re_property', id=prop_id)

        # Generate rent charge (accounts receivable integration)
        ch_res = self.save('generate_re_lease_charge', lease_id=lease_id)
        self.assertTrue(ch_res['ok'])
        ch_id = ch_res['charge_id']

        # Verify charge in system
        charges = app.charge_list(self.c, 1)
        charge_row = next(ch for ch in charges if ch['id'] == ch_id)
        self.assertEqual(charge_row['customer'], 'María Inquilina')
        self.assertEqual(charge_row['amount'], 5000000)

        # Terminate lease
        term_res = self.save('terminate_re_lease', id=lease_id)
        self.assertTrue(term_res['ok'])

        # Property should now be available again
        st = app.state(self.c, 1, 1)
        prop = next(p for p in st['re_properties'] if p['id'] == prop_id)
        self.assertEqual(prop['status'], 'available')

    def test_sale_and_visit_and_maintenance(self):
        prop_id = self.save('create_re_property',
            title='Local Bella Vista Mall',
            price_sale='10000000',
            listing_type='sale',
            status='available'
        )['id']

        # Visit
        visit_res = self.save('create_re_visit',
            property_id=prop_id,
            client_name='Dr. Roberto Gómez',
            client_phone='809-888-7777',
            visit_date=app.today().isoformat(),
            agent_id=1,
            interest_level='high',
            feedback='Le gustó la ubicación para consultorio médico'
        )
        self.assertTrue(visit_res['ok'])

        # Maintenance
        maint_res = self.save('create_re_maintenance',
            property_id=prop_id,
            title='Pintura interior general',
            cost_estimate='15000',
            reported_date=app.today().isoformat(),
            contractor_technician='Pinturas Express'
        )
        self.assertTrue(maint_res['ok'])
        m_id = maint_res['id']
        self.save('resolve_re_maintenance', id=m_id)

        # Sale
        sale_res = self.save('create_re_sale',
            property_id=prop_id,
            buyer_name='Dr. Roberto Gómez',
            buyer_phone='809-888-7777',
            sale_price='9800000',
            commission_rate=5.0,
            closing_date=app.today().isoformat(),
            status='closed',
            agent_id=1
        )
        self.assertTrue(sale_res['ok'])

        # Property is now sold
        st = app.state(self.c, 1, 1)
        prop = next(p for p in st['re_properties'] if p['id'] == prop_id)
        self.assertEqual(prop['status'], 'sold')
        self.assertEqual(len(st['re_sales']), 1)
        self.assertEqual(st['re_sales'][0]['commission_amount'], 49000000) # 5% of 9,800,000 * 100

    def test_demo_real_estate_seeding(self):
        res = self.save('seed_demo_real_estate')
        self.assertTrue(res['ok'])

        st = app.state(self.c, 1, 1)
        self.assertGreaterEqual(len(st['re_properties']), 4)
        self.assertGreaterEqual(len(st['re_leases']), 1)
        self.assertGreaterEqual(len(st['re_sales']), 1)
        self.assertGreaterEqual(len(st['re_visits']), 1)
        self.assertGreaterEqual(len(st['re_maintenances']), 1)
        self.assertEqual(st['company_profile']['business_vertical'], 'real_estate')
        self.assertEqual(st['company_profile']['unit_singular'], 'Propiedad')
        self.assertEqual(st['company_profile']['unit_plural'], 'Propiedades')

if __name__ == '__main__':
    unittest.main()
