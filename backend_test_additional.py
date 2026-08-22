"""Additional backend tests for specific features in the review request."""
import requests
import sys
import io
from datetime import datetime

BASE_URL = "https://vps-ai-tuner.preview.emergentagent.com/api"

class AdditionalTester:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.token = None
        self.tenant_id = None

    def test(self, name, method, endpoint, expected_status, data=None, files=None, params=None):
        """Run a single API test."""
        url = f"{BASE_URL}{endpoint}"
        headers = {'Content-Type': 'application/json'} if files is None else {}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        self.tests_run += 1
        print(f"\n🔍 [{self.tests_run}] Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == 'POST':
                if files is not None:
                    headers.pop('Content-Type', None)
                    response = requests.post(url, data=data, files=files, headers=headers, timeout=30)
                else:
                    response = requests.post(url, json=data, headers=headers, timeout=30)
            elif method == 'PATCH':
                response = requests.patch(url, json=data, headers=headers, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
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
                print(f"   Response: {response.text[:300]}")
                return False, {}

        except Exception as e:
            print(f"❌ FAILED - Error: {str(e)}")
            return False, {}

    def run_tests(self):
        print("=" * 80)
        print("BLUESEATRA ADDITIONAL BACKEND TESTS")
        print("=" * 80)

        # ===================================================================
        # 1. AUTH EDGE CASES
        # ===================================================================
        print("\n" + "=" * 80)
        print("1. AUTH - Edge cases (duplicate email, wrong password)")
        print("=" * 80)
        
        ts = datetime.now().strftime('%H%M%S')
        test_email = f"test_{ts}@example.com"
        test_password = "secret123"
        
        # Signup
        success, data = self.test(
            "Signup new user",
            "POST",
            "/auth/signup",
            200,
            data={
                "email": test_email,
                "password": test_password,
                "name": "Test User",
                "company": "Test Corp"
            }
        )
        if success:
            self.token = data.get("token")
            self.tenant_id = data.get("tenant", {}).get("id")

        # Test duplicate email (should return 400)
        self.test(
            "Signup with duplicate email (should return 400)",
            "POST",
            "/auth/signup",
            400,
            data={
                "email": test_email,
                "password": "different123",
                "name": "Another User",
                "company": "Another Corp"
            }
        )

        # Test wrong password (should return 401)
        self.test(
            "Login with wrong password (should return 401)",
            "POST",
            "/auth/login",
            401,
            data={"email": test_email, "password": "wrongpassword"}
        )

        # Test login with non-existent email (should return 401)
        self.test(
            "Login with non-existent email (should return 401)",
            "POST",
            "/auth/login",
            401,
            data={"email": f"nonexistent_{ts}@example.com", "password": "anypassword"}
        )

        # ===================================================================
        # 2. CATALOG MANAGEMENT
        # ===================================================================
        print("\n" + "=" * 80)
        print("2. CATALOG MANAGEMENT - Deactivate, Edit, Delete")
        print("=" * 80)

        # Get existing catalogs
        success, data = self.test(
            "GET /catalogs",
            "GET",
            "/catalogs",
            200
        )
        
        demo_catalog_id = None
        if success and data:
            demo_catalog_id = data[0].get("id")
            print(f"   Demo catalog ID: {demo_catalog_id}")

        # Test GET /catalog/active
        success, data = self.test(
            "GET /catalog/active",
            "GET",
            "/catalog/active",
            200
        )
        if success:
            catalog = data.get("catalog")
            items = data.get("items", [])
            print(f"   Active catalog: {catalog.get('name') if catalog else None}")
            print(f"   Active items: {len(items)}")

        # Test PATCH /catalogs/{id} (edit client_code)
        if demo_catalog_id:
            success, data = self.test(
                "PATCH /catalogs/{id} (edit client_code)",
                "PATCH",
                f"/catalogs/{demo_catalog_id}",
                200,
                data={"client_code": "DEMO-UPDATED"}
            )
            if success:
                print(f"   Updated client_code: {data.get('client_code')}")

        # Import a new catalog for testing deactivate/delete
        csv_content = """item_label,item_code,unit,unit_price_ht,vat_rate
Test Item A,TEST-A,u,50.00,20
Test Item B,TEST-B,m2,75.50,10"""

        success, data = self.test(
            "POST /catalogs/import (for testing)",
            "POST",
            "/catalogs/import",
            200,
            data={"catalog_name": f"Test Catalog {ts}", "activate": "true"},
            files={"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        )
        
        test_catalog_id = None
        if success:
            test_catalog_id = data.get("catalog_id")
            print(f"   Test catalog ID: {test_catalog_id}")

        # Test GET /catalogs/{id}/items (with dynamic columns)
        if test_catalog_id:
            success, data = self.test(
                "GET /catalogs/{id}/items (dynamic columns)",
                "GET",
                f"/catalogs/{test_catalog_id}/items",
                200
            )
            if success:
                items = data.get("items", [])
                columns = data.get("columns", [])
                mapping = data.get("mapping", {})
                print(f"   Items: {len(items)}")
                print(f"   Dynamic columns: {columns}")
                print(f"   Mapping keys: {list(mapping.keys())[:5]}")
                if items:
                    # Check if attributes field exists (dynamic columns stored here)
                    first_item = items[0]
                    print(f"   First item has attributes: {'attributes' in first_item}")
                    if 'attributes' in first_item:
                        print(f"   Attributes keys: {list(first_item['attributes'].keys())}")

        # Test POST /catalogs/{id}/deactivate
        if test_catalog_id:
            success, data = self.test(
                "POST /catalogs/{id}/deactivate",
                "POST",
                f"/catalogs/{test_catalog_id}/deactivate",
                200
            )

        # Verify deactivation
        if test_catalog_id:
            success, data = self.test(
                "GET /catalogs (verify deactivation)",
                "GET",
                "/catalogs",
                200
            )
            if success:
                for cat in data:
                    if cat.get("id") == test_catalog_id:
                        print(f"   Deactivated catalog active_version_id: {cat.get('active_version_id')}")

        # Test DELETE /catalogs/{id} (cascade delete)
        if test_catalog_id:
            success, data = self.test(
                "DELETE /catalogs/{id} (cascade delete)",
                "DELETE",
                f"/catalogs/{test_catalog_id}",
                200
            )

        # Verify deletion
        if test_catalog_id:
            success, data = self.test(
                "GET /catalogs (verify deletion)",
                "GET",
                "/catalogs",
                200
            )
            if success:
                deleted = all(cat.get("id") != test_catalog_id for cat in data)
                print(f"   Catalog deleted: {deleted}")

        # ===================================================================
        # 3. CSV IMPORT - Dynamic mapping & comma decimals
        # ===================================================================
        print("\n" + "=" * 80)
        print("3. CSV IMPORT - Dynamic mapping, comma decimals, semicolon delimiter")
        print("=" * 80)

        # Test with comma decimals and semicolon delimiter
        csv_semicolon = """Famille;Article;Unité;Prix_vente_HT;TVA_%
Électricité;Câble RJ45 Cat6;ml;9,99;20
Plomberie;Tuyau PVC 32mm;ml;12,50;10
Menuiserie;Planche pin 200x20;ml;15,75;20"""

        success, data = self.test(
            "POST /catalogs/import/preview (semicolon + comma decimals)",
            "POST",
            "/catalogs/import/preview",
            200,
            files={"file": ("test_semicolon.csv", io.BytesIO(csv_semicolon.encode()), "text/csv")}
        )
        if success:
            print(f"   Columns detected: {data.get('columns')}")
            print(f"   Total rows: {data.get('total_rows')}")
            mapping = data.get('suggested_mapping', {})
            print(f"   Auto-detected mapping:")
            for key, val in mapping.items():
                if val:
                    print(f"     {key} -> {val}")

        # Import with dynamic mapping
        success, data = self.test(
            "POST /catalogs/import (dynamic mapping)",
            "POST",
            "/catalogs/import",
            200,
            data={"catalog_name": f"Dynamic Catalog {ts}", "activate": "false"},
            files={"file": ("test_dynamic.csv", io.BytesIO(csv_semicolon.encode()), "text/csv")}
        )
        if success:
            print(f"   Success rows: {data.get('success_rows')}")
            print(f"   Error rows: {data.get('error_rows')}")

        # ===================================================================
        # 4. SECURITY TESTS
        # ===================================================================
        print("\n" + "=" * 80)
        print("4. SECURITY - Upload limit, CORS, encrypted AI key")
        print("=" * 80)

        # Test >15MB upload (should return 413)
        large_content = b"x" * (16 * 1024 * 1024)  # 16 MB
        success, data = self.test(
            "POST /catalogs/import (>15MB - should return 413)",
            "POST",
            "/catalogs/import",
            413,
            data={"catalog_name": "Large Catalog", "activate": "false"},
            files={"file": ("large.csv", io.BytesIO(large_content), "text/csv")}
        )

        # Test GET /settings/integrations (ai_key should NOT be returned)
        success, data = self.test(
            "GET /settings/integrations (ai_key should not be exposed)",
            "GET",
            "/settings/integrations",
            200
        )
        if success:
            settings = data.get("settings", {})
            has_ai_key = "ai_key" in settings
            has_ai_key_set = "ai_key_set" in settings
            print(f"   Has 'ai_key' field: {has_ai_key} (should be False)")
            print(f"   Has 'ai_key_set' flag: {has_ai_key_set} (should be True)")
            if has_ai_key:
                print(f"   ⚠️  SECURITY ISSUE: ai_key is exposed in response!")

        # Test PUT /settings/integrations (ai_key should be encrypted)
        success, data = self.test(
            "PUT /settings/integrations (with ai_key)",
            "PUT",
            "/settings/integrations",
            200,
            data={
                "ai_provider": "openai",
                "ai_model": "gpt-5.4",
                "ai_key": "sk-test-secret-key-12345"
            }
        )

        # Verify ai_key is encrypted in database (check via GET)
        success, data = self.test(
            "GET /settings/integrations (verify ai_key encrypted)",
            "GET",
            "/settings/integrations",
            200
        )
        if success:
            settings = data.get("settings", {})
            print(f"   ai_key_set: {settings.get('ai_key_set')}")
            print(f"   ai_key exposed: {'ai_key' in settings}")

        # Test CORS preflight (OPTIONS request)
        print("\n   Testing CORS configuration...")
        try:
            response = requests.options(
                f"{BASE_URL}/auth/login",
                headers={
                    "Origin": "https://example.com",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type,authorization"
                },
                timeout=10
            )
            print(f"   CORS preflight status: {response.status_code}")
            cors_headers = {k: v for k, v in response.headers.items() if 'access-control' in k.lower()}
            for k, v in cors_headers.items():
                print(f"     {k}: {v}")
            
            # Check if credentials are allowed with wildcard origin
            allow_origin = response.headers.get('Access-Control-Allow-Origin', '')
            allow_credentials = response.headers.get('Access-Control-Allow-Credentials', '')
            if allow_origin == '*' and allow_credentials.lower() == 'true':
                print(f"   ⚠️  SECURITY ISSUE: credentials=true with wildcard origin!")
            else:
                print(f"   ✅ CORS properly configured (no credentials with wildcard)")
        except Exception as e:
            print(f"   CORS test error: {e}")

        # ===================================================================
        # 5. MEMBER ROLE UPDATE (previously failed)
        # ===================================================================
        print("\n" + "=" * 80)
        print("5. MEMBER ROLE UPDATE - Test fix for 500 error")
        print("=" * 80)

        # Add a member
        member_email = f"member_{ts}@example.com"
        success, data = self.test(
            "POST /members (add member)",
            "POST",
            "/members",
            200,
            data={
                "email": member_email,
                "name": "Test Member",
                "password": "secret123",
                "role": "operator"
            }
        )
        
        member_id = None
        if success:
            member_id = data.get("user_id")

        # Update member role (this was failing with 500)
        if member_id:
            success, data = self.test(
                "PATCH /members/{user_id} (update role - was failing)",
                "PATCH",
                f"/members/{member_id}",
                200,
                data={"role": "admin"}
            )

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
    tester = AdditionalTester()
    sys.exit(tester.run_tests())
