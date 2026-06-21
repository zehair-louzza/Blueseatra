"""Blueseatra backend API test suite — comprehensive testing of all endpoints + multi-tenancy isolation."""
import requests
import sys
import time
import io
from datetime import datetime

BASE_URL = "https://language-bridge-421.preview.emergentagent.com/api"

class APITester:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tenant1_token = None
        self.tenant1_id = None
        self.tenant2_token = None
        self.tenant2_id = None

    def test(self, name, method, endpoint, expected_status, data=None, files=None, token=None, params=None):
        """Run a single API test."""
        url = f"{BASE_URL}{endpoint}"
        headers = {'Content-Type': 'application/json'} if files is None else {}
        if token:
            headers['Authorization'] = f'Bearer {token}'

        self.tests_run += 1
        print(f"\n🔍 [{self.tests_run}] Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == 'POST':
                if files is not None:
                    headers.pop('Content-Type', None)
                    response = requests.post(url, data=data, files=files if files else None, headers=headers, timeout=30)
                else:
                    response = requests.post(url, json=data, headers=headers, timeout=30)
            elif method == 'PATCH':
                response = requests.patch(url, json=data, headers=headers, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ PASSED - Status: {response.status_code}")
                try:
                    return True, response.json()
                except:
                    return True, response.content
            else:
                print(f"❌ FAILED - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return False, {}

        except Exception as e:
            print(f"❌ FAILED - Error: {str(e)}")
            return False, {}

    def poll_request(self, request_id, token, max_wait=30):
        """Poll a request until it's done/needs_review/failed."""
        print(f"⏳ Polling request {request_id} (max {max_wait}s)...")
        start = time.time()
        while time.time() - start < max_wait:
            success, data = self.test(
                f"Poll request {request_id}",
                "GET",
                f"/requests/{request_id}",
                200,
                token=token
            )
            if success:
                status = data.get("status")
                print(f"   Status: {status}")
                if status in ("done", "needs_review", "failed"):
                    return success, data
            time.sleep(3)
        print(f"⚠️  Timeout waiting for request processing")
        return False, {}

    def run_all_tests(self):
        print("=" * 80)
        print("BLUESEATRA BACKEND API TEST SUITE")
        print("=" * 80)

        # ===================================================================
        # 1. AUTH - TENANT 1
        # ===================================================================
        print("\n" + "=" * 80)
        print("1. AUTH - TENANT 1 (Signup + Login)")
        print("=" * 80)
        
        ts = datetime.now().strftime('%H%M%S')
        tenant1_email = f"tenant1_{ts}@example.com"
        tenant1_password = "secret123"
        
        success, data = self.test(
            "Signup Tenant 1",
            "POST",
            "/auth/signup",
            200,
            data={
                "email": tenant1_email,
                "password": tenant1_password,
                "name": "Tenant One",
                "company": "ACME Corp"
            }
        )
        if success:
            self.tenant1_token = data.get("token")
            self.tenant1_id = data.get("tenant", {}).get("id")
            print(f"   Tenant 1 ID: {self.tenant1_id}")
        else:
            print("❌ CRITICAL: Tenant 1 signup failed, stopping tests")
            return

        # Test login
        success, data = self.test(
            "Login Tenant 1",
            "POST",
            "/auth/login",
            200,
            data={"email": tenant1_email, "password": tenant1_password}
        )
        if success:
            print(f"   Login successful, token matches: {data.get('token') == self.tenant1_token}")

        # Test /auth/me
        success, data = self.test(
            "GET /auth/me (Tenant 1)",
            "GET",
            "/auth/me",
            200,
            token=self.tenant1_token
        )
        if success:
            print(f"   User: {data.get('user', {}).get('email')}, Tenant: {data.get('tenant', {}).get('name')}")

        # ===================================================================
        # 2. AUTH - TENANT 2 (for multi-tenancy isolation testing)
        # ===================================================================
        print("\n" + "=" * 80)
        print("2. AUTH - TENANT 2 (for isolation testing)")
        print("=" * 80)
        
        tenant2_email = f"tenant2_{ts}@example.com"
        tenant2_password = "secret456"
        
        success, data = self.test(
            "Signup Tenant 2",
            "POST",
            "/auth/signup",
            200,
            data={
                "email": tenant2_email,
                "password": tenant2_password,
                "name": "Tenant Two",
                "company": "Beta Inc"
            }
        )
        if success:
            self.tenant2_token = data.get("token")
            self.tenant2_id = data.get("tenant", {}).get("id")
            print(f"   Tenant 2 ID: {self.tenant2_id}")

        # ===================================================================
        # 3. CATALOG - Check demo catalog seeded on signup
        # ===================================================================
        print("\n" + "=" * 80)
        print("3. CATALOG - Demo catalog auto-seeded")
        print("=" * 80)
        
        success, data = self.test(
            "GET /catalogs (Tenant 1)",
            "GET",
            "/catalogs",
            200,
            token=self.tenant1_token
        )
        if success:
            catalogs = data if isinstance(data, list) else []
            print(f"   Catalogs found: {len(catalogs)}")
            if catalogs:
                demo = catalogs[0]
                print(f"   Demo catalog: {demo.get('name')}, active_version: {demo.get('active_version_id')}")
                print(f"   Versions: {len(demo.get('versions', []))}")

        # Download catalog template
        success, _ = self.test(
            "GET /catalog-template.csv",
            "GET",
            "/catalog-template.csv",
            200,
            token=self.tenant1_token
        )

        # ===================================================================
        # 4. REQUESTS - Multilingual extraction (French)
        # ===================================================================
        print("\n" + "=" * 80)
        print("4. REQUESTS - Create request with French text (async processing)")
        print("=" * 80)
        
        french_text = """Devis pour renovation bureau
Client: Société Dupont
Site: 15 rue de la Paix, Paris

Travaux demandés:
- Peinture murale deux couches: 45 m2
- Pose placo BA13: 30 m2
- Main d'oeuvre qualifiée: 8 heures
- Déplacement technicien: 1 unité
- Protection chantier: 1 ensemble

Urgent - délai 2 semaines"""

        success, data = self.test(
            "POST /requests (French text)",
            "POST",
            "/requests",
            200,
            data={"title": "Renovation bureau Paris", "text": french_text},
            files={},  # Empty files dict to trigger multipart/form-data
            token=self.tenant1_token
        )
        
        request1_id = None
        if success:
            request1_id = data.get("id")
            print(f"   Request ID: {request1_id}, Status: {data.get('status')}")
            
            # Poll until processed
            success, req_data = self.poll_request(request1_id, self.tenant1_token, max_wait=30)
            if success:
                extracted = req_data.get("extracted", {})
                print(f"   Language detected: {req_data.get('language')}")
                print(f"   Confidence: {req_data.get('confidence')}")
                print(f"   Line items: {len(extracted.get('line_items', []))}")
                print(f"   Client: {extracted.get('client')}")
                print(f"   Description: {extracted.get('description', '')[:80]}")

        # ===================================================================
        # 5. REQUESTS - Second language (English)
        # ===================================================================
        print("\n" + "=" * 80)
        print("5. REQUESTS - Create request with English text")
        print("=" * 80)
        
        english_text = """Quote request for office renovation
Client: Smith & Co
Site: 123 Main Street, London

Required work:
- Wall painting two coats: 50 m2
- Plasterboard installation: 25 m2
- Skilled labor: 10 hours
- Technician travel: 1 unit

Urgency: normal"""

        success, data = self.test(
            "POST /requests (English text)",
            "POST",
            "/requests",
            200,
            data={"title": "Office renovation London", "text": english_text},
            files={},  # Empty files dict to trigger multipart/form-data
            token=self.tenant1_token
        )
        
        request2_id = None
        if success:
            request2_id = data.get("id")
            success, req_data = self.poll_request(request2_id, self.tenant1_token, max_wait=30)
            if success:
                print(f"   Language detected: {req_data.get('language')}")
                print(f"   Line items: {len(req_data.get('extracted', {}).get('line_items', []))}")

        # Test reprocess
        if request1_id:
            self.test(
                "POST /requests/{id}/process (reprocess)",
                "POST",
                f"/requests/{request1_id}/process",
                200,
                token=self.tenant1_token
            )

        # List requests
        success, data = self.test(
            "GET /requests (list)",
            "GET",
            "/requests",
            200,
            token=self.tenant1_token
        )
        if success:
            print(f"   Total requests: {len(data)}")

        # ===================================================================
        # 6. QUOTES - Generate draft from request
        # ===================================================================
        print("\n" + "=" * 80)
        print("6. QUOTES - Generate draft from processed request")
        print("=" * 80)
        
        quote1_id = None
        if request1_id:
            success, data = self.test(
                "POST /quotes/draft",
                "POST",
                "/quotes/draft",
                200,
                data={"request_id": request1_id},
                token=self.tenant1_token
            )
            if success:
                quote1_id = data.get("id")
                print(f"   Quote ID: {quote1_id}")
                print(f"   Number: {data.get('number')}")
                print(f"   Lines: {len(data.get('lines', []))}")
                print(f"   Total HT: {data.get('total_ht')} {data.get('currency')}")
                print(f"   Total TTC: {data.get('total_ttc')} {data.get('currency')}")

        # Get quote
        if quote1_id:
            success, data = self.test(
                "GET /quotes/{id}",
                "GET",
                f"/quotes/{quote1_id}",
                200,
                token=self.tenant1_token
            )

        # Update quote (edit lines)
        if quote1_id:
            success, quote_data = self.test(
                "GET /quotes/{id} (for editing)",
                "GET",
                f"/quotes/{quote1_id}",
                200,
                token=self.tenant1_token
            )
            if success:
                lines = quote_data.get("lines", [])
                if lines:
                    # Modify first line qty
                    lines[0]["qty"] = 50
                    lines[0]["description"] = "Peinture murale premium"
                    
                    success, updated = self.test(
                        "PATCH /quotes/{id} (edit lines)",
                        "PATCH",
                        f"/quotes/{quote1_id}",
                        200,
                        data={"lines": lines, "client": "Société Dupont SARL"},
                        token=self.tenant1_token
                    )
                    if success:
                        print(f"   Updated total HT: {updated.get('total_ht')}")

        # Validate quote
        if quote1_id:
            success, data = self.test(
                "POST /quotes/{id}/validate",
                "POST",
                f"/quotes/{quote1_id}/validate",
                200,
                token=self.tenant1_token
            )

        # Send quote
        if quote1_id:
            success, data = self.test(
                "POST /quotes/{id}/send",
                "POST",
                f"/quotes/{quote1_id}/send",
                200,
                token=self.tenant1_token
            )

        # Download PDF (test with token param)
        if quote1_id:
            success, pdf_data = self.test(
                "GET /quotes/{id}/pdf (with token param)",
                "GET",
                f"/quotes/{quote1_id}/pdf",
                200,
                params={"token": self.tenant1_token}
            )
            if success and isinstance(pdf_data, bytes):
                print(f"   PDF size: {len(pdf_data)} bytes")
                if pdf_data.startswith(b'%PDF'):
                    print(f"   ✅ Valid PDF header")

        # List quotes
        success, data = self.test(
            "GET /quotes (list)",
            "GET",
            "/quotes",
            200,
            token=self.tenant1_token
        )
        if success:
            print(f"   Total quotes: {len(data)}")

        # ===================================================================
        # 7. DASHBOARD
        # ===================================================================
        print("\n" + "=" * 80)
        print("7. DASHBOARD - KPIs and recent items")
        print("=" * 80)
        
        success, data = self.test(
            "GET /dashboard",
            "GET",
            "/dashboard",
            200,
            token=self.tenant1_token
        )
        if success:
            kpis = data.get("kpis", {})
            print(f"   Requests: {kpis.get('requests')}")
            print(f"   Drafts: {kpis.get('drafts')}")
            print(f"   Validated: {kpis.get('validated')}")
            print(f"   Active catalog items: {kpis.get('active_catalog_items')}")
            print(f"   Recent requests: {len(data.get('recent_requests', []))}")
            print(f"   Recent quotes: {len(data.get('recent_quotes', []))}")

        # ===================================================================
        # 8. MEMBERS - List, Add, Update
        # ===================================================================
        print("\n" + "=" * 80)
        print("8. MEMBERS - Team management")
        print("=" * 80)
        
        success, data = self.test(
            "GET /members",
            "GET",
            "/members",
            200,
            token=self.tenant1_token
        )
        if success:
            print(f"   Members: {len(data)}")

        # Add member (owner can add)
        new_member_email = f"operator_{ts}@example.com"
        success, data = self.test(
            "POST /members (add operator)",
            "POST",
            "/members",
            200,
            data={
                "email": new_member_email,
                "name": "Operator User",
                "password": "secret789",
                "role": "operator"
            },
            token=self.tenant1_token
        )
        
        new_member_id = None
        if success:
            new_member_id = data.get("user_id")
            print(f"   New member ID: {new_member_id}")

        # Update member role
        if new_member_id:
            success, data = self.test(
                "PATCH /members/{user_id} (update role)",
                "PATCH",
                f"/members/{new_member_id}",
                200,
                data={"role": "admin"},
                token=self.tenant1_token
            )

        # Test role enforcement: create viewer and try to validate quote (should fail)
        viewer_email = f"viewer_{ts}@example.com"
        success, data = self.test(
            "POST /members (add viewer)",
            "POST",
            "/members",
            200,
            data={
                "email": viewer_email,
                "name": "Viewer User",
                "password": "secret999",
                "role": "viewer"
            },
            token=self.tenant1_token
        )
        
        if success:
            # Login as viewer
            success, viewer_data = self.test(
                "Login as viewer",
                "POST",
                "/auth/login",
                200,
                data={"email": viewer_email, "password": "secret999"}
            )
            if success:
                viewer_token = viewer_data.get("token")
                
                # Try to validate quote (should fail with 403)
                if quote1_id:
                    self.test(
                        "POST /quotes/{id}/validate (as viewer - should fail)",
                        "POST",
                        f"/quotes/{quote1_id}/validate",
                        403,
                        token=viewer_token
                    )

        # ===================================================================
        # 9. SETTINGS - Integrations
        # ===================================================================
        print("\n" + "=" * 80)
        print("9. SETTINGS - AI provider configuration")
        print("=" * 80)
        
        success, data = self.test(
            "GET /settings/integrations",
            "GET",
            "/settings/integrations",
            200,
            token=self.tenant1_token
        )
        if success:
            settings = data.get("settings", {})
            print(f"   AI provider: {settings.get('ai_provider')}")
            print(f"   AI model: {settings.get('ai_model')}")
            print(f"   AI key set: {settings.get('ai_key_set')}")
            print(f"   Provider models available: {list(data.get('provider_models', {}).keys())}")

        # Update settings
        success, data = self.test(
            "PUT /settings/integrations",
            "PUT",
            "/settings/integrations",
            200,
            data={
                "ai_provider": "emergent",
                "ai_model": "gpt-5.4",
                "n8n_webhook_url": "https://n8n.example.com/webhook/test"
            },
            token=self.tenant1_token
        )

        # ===================================================================
        # 10. AUDIT LOGS
        # ===================================================================
        print("\n" + "=" * 80)
        print("10. AUDIT - Activity logs")
        print("=" * 80)
        
        success, data = self.test(
            "GET /audit",
            "GET",
            "/audit",
            200,
            token=self.tenant1_token
        )
        if success:
            print(f"   Audit entries: {len(data)}")
            if data:
                recent = data[0]
                print(f"   Most recent: {recent.get('action')} by {recent.get('actor')}")

        # ===================================================================
        # 11. CATALOG IMPORT - CSV upload
        # ===================================================================
        print("\n" + "=" * 80)
        print("11. CATALOG - CSV import flow")
        print("=" * 80)
        
        # Create test CSV
        csv_content = """client_code,item_code,item_label,category,unit,unit_price_ht,currency,vat_rate,min_qty,is_active,notes
TEST,TEST-001,Test item one,test_cat,u,100.00,EUR,20,1,true,Test note
TEST,TEST-002,Test item two,test_cat,m2,25.50,EUR,10,5,true,Another test"""

        # Preview
        success, data = self.test(
            "POST /catalogs/import/preview",
            "POST",
            "/catalogs/import/preview",
            200,
            files={"file": ("test_catalog.csv", io.BytesIO(csv_content.encode()), "text/csv")},
            token=self.tenant1_token
        )
        if success:
            print(f"   Columns: {data.get('columns')}")
            print(f"   Total rows: {data.get('total_rows')}")
            print(f"   Missing required: {data.get('missing_required')}")

        # Import
        success, data = self.test(
            "POST /catalogs/import",
            "POST",
            "/catalogs/import",
            200,
            data={"catalog_name": f"Test Catalog {ts}", "activate": "true"},
            files={"file": ("test_catalog.csv", io.BytesIO(csv_content.encode()), "text/csv")},
            token=self.tenant1_token
        )
        
        new_catalog_id = None
        new_version_id = None
        if success:
            new_catalog_id = data.get("catalog_id")
            new_version_id = data.get("version_id")
            print(f"   Catalog ID: {new_catalog_id}")
            print(f"   Version: {data.get('version_number')}")
            print(f"   Success rows: {data.get('success_rows')}")
            print(f"   Error rows: {data.get('error_rows')}")
            print(f"   Activated: {data.get('activated')}")

        # Activate version (test manual activation)
        if new_catalog_id and new_version_id:
            self.test(
                "POST /catalogs/{id}/activate/{version_id}",
                "POST",
                f"/catalogs/{new_catalog_id}/activate/{new_version_id}",
                200,
                token=self.tenant1_token
            )

        # ===================================================================
        # 12. MULTI-TENANCY ISOLATION - CRITICAL TEST
        # ===================================================================
        print("\n" + "=" * 80)
        print("12. MULTI-TENANCY ISOLATION - Cross-tenant data access")
        print("=" * 80)
        
        if self.tenant2_token and request1_id:
            # Tenant 2 tries to access Tenant 1's request (should fail or return 404)
            success, data = self.test(
                "GET /requests/{id} (Tenant 2 accessing Tenant 1 request - should fail)",
                "GET",
                f"/requests/{request1_id}",
                404,
                token=self.tenant2_token
            )
            
        if self.tenant2_token and quote1_id:
            # Tenant 2 tries to access Tenant 1's quote (should fail)
            success, data = self.test(
                "GET /quotes/{id} (Tenant 2 accessing Tenant 1 quote - should fail)",
                "GET",
                f"/quotes/{quote1_id}",
                404,
                token=self.tenant2_token
            )

        # Tenant 2 should see empty lists
        success, data = self.test(
            "GET /requests (Tenant 2 - should be empty)",
            "GET",
            "/requests",
            200,
            token=self.tenant2_token
        )
        if success:
            print(f"   Tenant 2 requests: {len(data)} (should be 0)")

        success, data = self.test(
            "GET /quotes (Tenant 2 - should be empty)",
            "GET",
            "/quotes",
            200,
            token=self.tenant2_token
        )
        if success:
            print(f"   Tenant 2 quotes: {len(data)} (should be 0)")

        # Tenant 2 should have its own demo catalog
        success, data = self.test(
            "GET /catalogs (Tenant 2 - should have demo catalog)",
            "GET",
            "/catalogs",
            200,
            token=self.tenant2_token
        )
        if success:
            print(f"   Tenant 2 catalogs: {len(data)} (should be 1 - demo)")

        # ===================================================================
        # SUMMARY
        # ===================================================================
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"Total tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        print(f"Success rate: {(self.tests_passed / self.tests_run * 100):.1f}%")
        
        return 0 if self.tests_passed == self.tests_run else 1


if __name__ == "__main__":
    tester = APITester()
    sys.exit(tester.run_all_tests())
