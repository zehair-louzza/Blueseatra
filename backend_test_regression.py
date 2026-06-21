"""Blueseatra REGRESSION TEST — validates NEW fields added for real maintenance broker PDFs.
Tests: doc_type, request_number, di_number, response_deadline, donneur_d_ordre, client_final,
       line_items with dimensions/location/specs, quote meta, company profile tva_intra, PDF generation.
"""
import requests
import sys
import time
from datetime import datetime

BASE_URL = "https://language-bridge-421.preview.emergentagent.com/api"

# Real French maintenance request text from PRESTA MAINTENANCE for SFR
FRENCH_MAINTENANCE_TEXT = """Demande de devis N° 26061000
Date: 10/06/2026
Date limite de réponse: 15/06/2026

Donneur d'ordre: PRESTA MAINTENANCE
Client final: SFR
Dossier DI: 26060951

Lieu d'intervention: CC Carrefour Belle Epine - Thiais (94)
Adresse: Centre Commercial Belle Epine, 94320 Thiais

Description des travaux:
- Mise en place serrure + mécanisme porte magasin
- Dimensions: H 2m10 x L 1m20
- Matériau: Acier galvanisé
- Finition: RAL 7016 (gris anthracite)

Contraintes:
- Intervention en horaires d'ouverture uniquement (9h-19h)
- Accès par entrée livraison

Livrables attendus:
- Durée d'intervention
- Nombre de techniciens
- Fournitures avec références
- Délai d'exécution
- Fiches techniques produits

Contact: Jean Dupont - j.dupont@prestamaintenance.fr - 06 12 34 56 78
"""

# English maintenance request
ENGLISH_MAINTENANCE_TEXT = """Maintenance Request #ENG-2026-001
Issue Date: 2026-06-10
Response Deadline: 2026-06-15

Broker: GMS MAINTENANCE
End Client: PROMOD

Intervention Site: PROMOD Store - Lyon Part-Dieu
Address: Centre Commercial Part-Dieu, 69003 Lyon

Work Description:
- Replace automatic door motor
- Install new access control system
- Electrical wiring upgrade

Required Deliverables:
- Intervention duration
- Number of technicians
- Equipment specifications
- Execution timeline

Contact: Sarah Martin - s.martin@gmsmaintenance.com - +33 6 98 76 54 32
"""

class RegressionTester:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.token = None
        self.tenant_id = None

    def test(self, name, method, endpoint, expected_status, data=None, token=None, params=None, form_data=None):
        """Run a single API test."""
        url = f"{BASE_URL}{endpoint}"
        headers = {}
        if not form_data:
            headers['Content-Type'] = 'application/json'
        if token:
            headers['Authorization'] = f'Bearer {token}'

        self.tests_run += 1
        print(f"\n🔍 [{self.tests_run}] {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == 'POST':
                if form_data:
                    response = requests.post(url, data=form_data, headers=headers, timeout=30)
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
                print(f"   Response: {response.text[:300]}")
                return False, {}

        except Exception as e:
            print(f"❌ FAILED - Error: {str(e)}")
            return False, {}

    def poll_request(self, request_id, max_wait=35):
        """Poll a request until processing is done."""
        print(f"⏳ Polling request {request_id} (max {max_wait}s)...")
        start = time.time()
        while time.time() - start < max_wait:
            success, data = self.test(
                f"Poll request {request_id}",
                "GET",
                f"/requests/{request_id}",
                200,
                token=self.token
            )
            if success:
                status = data.get("status")
                print(f"   Status: {status}")
                if status in ("done", "needs_review", "failed"):
                    return success, data
            time.sleep(3)
        print(f"⚠️  Timeout waiting for request processing")
        return False, {}

    def validate_new_fields(self, extracted, expected_fields):
        """Validate that new fields are present in extracted data."""
        missing = []
        for field in expected_fields:
            if "." in field:  # nested field like contact.name
                parts = field.split(".")
                val = extracted
                for p in parts:
                    val = val.get(p) if isinstance(val, dict) else None
                if val is None:
                    missing.append(field)
            else:
                if field not in extracted or extracted[field] is None:
                    missing.append(field)
        return missing

    def run_all_tests(self):
        print("=" * 80)
        print("BLUESEATRA REGRESSION TEST — NEW FIELDS VALIDATION")
        print("=" * 80)

        # ===================================================================
        # 1. AUTH
        # ===================================================================
        print("\n" + "=" * 80)
        print("1. AUTH - Signup & Login")
        print("=" * 80)
        
        ts = datetime.now().strftime('%H%M%S')
        email = f"regression_{ts}@blueseatra.com"
        password = "secret123"
        
        success, data = self.test(
            "Signup",
            "POST",
            "/auth/signup",
            200,
            data={"email": email, "password": password, "name": "Regression Tester", "company": "Test Corp"}
        )
        if not success:
            print("❌ Signup failed, cannot continue")
            return 1
        
        self.token = data["token"]
        self.tenant_id = data["tenant"]["id"]
        print(f"✓ Token obtained, tenant_id: {self.tenant_id}")

        success, data = self.test(
            "GET /auth/me",
            "GET",
            "/auth/me",
            200,
            token=self.token
        )
        if not success:
            print("❌ /auth/me failed")
            return 1

        # ===================================================================
        # 2. FRENCH MAINTENANCE REQUEST - NEW FIELDS
        # ===================================================================
        print("\n" + "=" * 80)
        print("2. FRENCH MAINTENANCE REQUEST - Validate NEW Fields")
        print("=" * 80)

        success, data = self.test(
            "POST /requests (French maintenance text)",
            "POST",
            "/requests",
            200,
            form_data={"title": "Demande PRESTA MAINTENANCE - SFR", "text": FRENCH_MAINTENANCE_TEXT},
            token=self.token
        )
        if not success:
            print("❌ Request creation failed")
            return 1
        
        fr_request_id = data["id"]
        print(f"✓ Request created: {fr_request_id}")

        # Poll until done
        success, req_data = self.poll_request(fr_request_id, max_wait=35)
        if not success or req_data.get("status") not in ("done", "needs_review"):
            print(f"❌ Request processing failed or timed out. Status: {req_data.get('status')}")
            return 1

        extracted = req_data.get("extracted", {})
        print(f"\n📋 Extracted data preview:")
        print(f"   Language: {extracted.get('language')}")
        print(f"   Doc type: {extracted.get('doc_type')}")
        print(f"   Request number: {extracted.get('request_number')}")
        print(f"   DI number: {extracted.get('di_number')}")
        print(f"   Response deadline: {extracted.get('response_deadline')}")
        print(f"   Donneur d'ordre: {extracted.get('donneur_d_ordre')}")
        print(f"   Client final: {extracted.get('client_final')}")
        print(f"   Intervention site: {extracted.get('intervention_site')}")
        print(f"   Intervention address: {extracted.get('intervention_address')}")
        print(f"   Contact: {extracted.get('contact')}")
        print(f"   Required deliverables: {extracted.get('required_deliverables')}")
        print(f"   Constraints: {extracted.get('constraints')}")
        print(f"   Line items count: {len(extracted.get('line_items', []))}")

        # Validate NEW fields are present
        expected_new_fields = [
            "doc_type", "request_number", "response_deadline",
            "donneur_d_ordre", "client_final", "di_number",
            "intervention_site", "intervention_address",
            "required_deliverables", "constraints", "keywords"
        ]
        
        missing = self.validate_new_fields(extracted, expected_new_fields)
        if missing:
            print(f"⚠️  WARNING: Missing new fields: {missing}")
        else:
            print(f"✅ All NEW top-level fields present")
            self.tests_passed += 1
        self.tests_run += 1

        # Validate line_items have NEW fields (dimensions, location, specs)
        line_items = extracted.get("line_items", [])
        if line_items:
            first_item = line_items[0]
            print(f"\n📦 First line item:")
            print(f"   Label: {first_item.get('label')}")
            print(f"   Category: {first_item.get('category')}")
            print(f"   Qty: {first_item.get('qty')}")
            print(f"   Unit: {first_item.get('unit')}")
            print(f"   Dimensions: {first_item.get('dimensions')}")
            print(f"   Location: {first_item.get('location')}")
            print(f"   Specs: {first_item.get('specs')}")
            
            # Check if dimensions/location/specs are present (at least one should be)
            has_new_line_fields = any([
                first_item.get('dimensions'),
                first_item.get('location'),
                first_item.get('specs')
            ])
            if has_new_line_fields:
                print(f"✅ Line items contain NEW fields (dimensions/location/specs)")
                self.tests_passed += 1
            else:
                print(f"⚠️  WARNING: Line items missing dimensions/location/specs")
            self.tests_run += 1

        # ===================================================================
        # 3. ENGLISH MAINTENANCE REQUEST - Multilingual
        # ===================================================================
        print("\n" + "=" * 80)
        print("3. ENGLISH MAINTENANCE REQUEST - Multilingual Test")
        print("=" * 80)

        success, data = self.test(
            "POST /requests (English text)",
            "POST",
            "/requests",
            200,
            form_data={"title": "GMS MAINTENANCE - PROMOD", "text": ENGLISH_MAINTENANCE_TEXT},
            token=self.token
        )
        if not success:
            print("❌ English request creation failed")
            return 1
        
        en_request_id = data["id"]
        success, en_req_data = self.poll_request(en_request_id, max_wait=35)
        if not success or en_req_data.get("status") not in ("done", "needs_review"):
            print(f"❌ English request processing failed")
            return 1

        en_extracted = en_req_data.get("extracted", {})
        if en_extracted.get("language") == "en":
            print(f"✅ Language detected: en")
            print(f"   Donneur d'ordre: {en_extracted.get('donneur_d_ordre')}")
            print(f"   Client final: {en_extracted.get('client_final')}")
            print(f"   Line items: {len(en_extracted.get('line_items', []))}")
            self.tests_passed += 1
        else:
            print(f"⚠️  Expected language 'en', got '{en_extracted.get('language')}'")
        self.tests_run += 1

        # ===================================================================
        # 4. QUOTE DRAFT - Validate META fields
        # ===================================================================
        print("\n" + "=" * 80)
        print("4. QUOTE DRAFT - Validate META Fields")
        print("=" * 80)

        success, quote_data = self.test(
            "POST /quotes/draft",
            "POST",
            "/quotes/draft",
            200,
            data={"request_id": fr_request_id},
            token=self.token
        )
        if not success:
            print("❌ Quote draft creation failed")
            return 1

        quote_id = quote_data["id"]
        meta = quote_data.get("meta", {})
        print(f"\n📄 Quote meta:")
        print(f"   Request number: {meta.get('request_number')}")
        print(f"   DI number: {meta.get('di_number')}")
        print(f"   Response deadline: {meta.get('response_deadline')}")
        print(f"   Donneur d'ordre: {meta.get('donneur_d_ordre')}")
        print(f"   Client final: {meta.get('client_final')}")
        print(f"   Required deliverables: {meta.get('required_deliverables')}")

        # Validate meta fields
        expected_meta_fields = [
            "request_number", "di_number", "response_deadline",
            "donneur_d_ordre", "client_final", "required_deliverables"
        ]
        meta_missing = []
        for field in expected_meta_fields:
            if field not in meta:
                meta_missing.append(field)
        
        if not meta_missing:
            print(f"✅ All META fields present in quote")
            self.tests_passed += 1
        else:
            print(f"⚠️  WARNING: Missing meta fields: {meta_missing}")
        self.tests_run += 1

        # Check that client is set to donneur_d_ordre
        if quote_data.get("client") == extracted.get("donneur_d_ordre"):
            print(f"✅ Quote client correctly set to donneur_d_ordre: {quote_data.get('client')}")
            self.tests_passed += 1
        else:
            print(f"⚠️  Quote client: {quote_data.get('client')}, expected: {extracted.get('donneur_d_ordre')}")
        self.tests_run += 1

        # ===================================================================
        # 5. COMPANY PROFILE - tva_intra field
        # ===================================================================
        print("\n" + "=" * 80)
        print("5. COMPANY PROFILE - tva_intra Field")
        print("=" * 80)

        success, profile_data = self.test(
            "GET /company-profile",
            "GET",
            "/company-profile",
            200,
            token=self.token
        )
        if not success:
            print("❌ GET company profile failed")
            return 1

        # Update with tva_intra
        success, _ = self.test(
            "PUT /company-profile (with tva_intra)",
            "PUT",
            "/company-profile",
            200,
            data={
                "company_name": "Test Corp",
                "tva_intra": "FR12345678901",
                "siret": "12345678901234",
                "address_line1": "123 Test Street",
                "country": "France"
            },
            token=self.token
        )
        if not success:
            print("❌ PUT company profile failed")
            return 1

        # Verify tva_intra was saved
        success, profile_data = self.test(
            "GET /company-profile (verify tva_intra)",
            "GET",
            "/company-profile",
            200,
            token=self.token
        )
        if success and profile_data.get("tva_intra") == "FR12345678901":
            print(f"✅ tva_intra field saved: {profile_data.get('tva_intra')}")
            self.tests_passed += 1
        else:
            print(f"⚠️  tva_intra not saved correctly: {profile_data.get('tva_intra')}")
        self.tests_run += 1

        # ===================================================================
        # 6. QUOTE PDF - Verify PDF generation
        # ===================================================================
        print("\n" + "=" * 80)
        print("6. QUOTE PDF - Verify PDF Generation")
        print("=" * 80)

        success, pdf_content = self.test(
            "GET /quotes/{id}/pdf",
            "GET",
            f"/quotes/{quote_id}/pdf",
            200,
            token=self.token,
            params={"token": self.token}
        )
        if success and isinstance(pdf_content, bytes):
            if pdf_content.startswith(b'%PDF'):
                print(f"✅ PDF generated successfully ({len(pdf_content)} bytes)")
                self.tests_passed += 1
            else:
                print(f"⚠️  Response is not a valid PDF")
        else:
            print(f"❌ PDF generation failed")
        self.tests_run += 1

        # ===================================================================
        # 7. QUOTE OPERATIONS - edit/validate/send
        # ===================================================================
        print("\n" + "=" * 80)
        print("7. QUOTE OPERATIONS - Edit/Validate/Send")
        print("=" * 80)

        # Edit quote
        success, _ = self.test(
            "PATCH /quotes/{id} (edit)",
            "PATCH",
            f"/quotes/{quote_id}",
            200,
            data={"object": "Updated: Serrurerie + mécanisme"},
            token=self.token
        )
        if not success:
            print("❌ Quote edit failed")

        # Validate quote
        success, _ = self.test(
            "POST /quotes/{id}/validate",
            "POST",
            f"/quotes/{quote_id}/validate",
            200,
            token=self.token
        )
        if not success:
            print("❌ Quote validation failed")

        # Send quote
        success, _ = self.test(
            "POST /quotes/{id}/send",
            "POST",
            f"/quotes/{quote_id}/send",
            200,
            token=self.token
        )
        if not success:
            print("❌ Quote send failed")

        # ===================================================================
        # 8. CATALOG IMPORT - Price matching
        # ===================================================================
        print("\n" + "=" * 80)
        print("8. CATALOG IMPORT - CSV Import & Price Matching")
        print("=" * 80)

        # Create a CSV with serrurerie item
        csv_content = """client_code,item_code,item_label,category,unit,unit_price_ht,currency,vat_rate,min_qty,is_active,notes
TEST,SERR-001,Serrure + mécanisme porte,serrurerie,u,250.00,EUR,20,1,true,Acier galvanisé
TEST,SERR-002,Pose serrure,serrurerie,u,120.00,EUR,20,1,true,Main d'oeuvre"""

        files = {'file': ('catalog_serrurerie.csv', csv_content, 'text/csv')}
        headers = {'Authorization': f'Bearer {self.token}'}
        
        print(f"   Uploading catalog CSV...")
        try:
            response = requests.post(
                f"{BASE_URL}/catalogs/import",
                files=files,
                data={'catalog_name': 'Catalogue Serrurerie', 'activate': 'true'},
                headers=headers,
                timeout=30
            )
            if response.status_code == 200:
                print(f"✅ Catalog imported and activated")
                self.tests_passed += 1
                import_result = response.json()
                print(f"   Success rows: {import_result.get('success_rows')}")
                print(f"   Error rows: {import_result.get('error_rows')}")
            else:
                print(f"❌ Catalog import failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Catalog import error: {e}")
        self.tests_run += 1

        # ===================================================================
        # 9. DASHBOARD, MEMBERS, AUDIT, SETTINGS
        # ===================================================================
        print("\n" + "=" * 80)
        print("9. OTHER ENDPOINTS - Dashboard/Members/Audit/Settings")
        print("=" * 80)

        self.test("GET /dashboard", "GET", "/dashboard", 200, token=self.token)
        self.test("GET /members", "GET", "/members", 200, token=self.token)
        self.test("GET /audit", "GET", "/audit", 200, token=self.token)
        self.test("GET /settings/integrations", "GET", "/settings/integrations", 200, token=self.token)

        # ===================================================================
        # SUMMARY
        # ===================================================================
        print("\n" + "=" * 80)
        print("REGRESSION TEST SUMMARY")
        print("=" * 80)
        print(f"Tests run: {self.tests_run}")
        print(f"Tests passed: {self.tests_passed}")
        print(f"Success rate: {self.tests_passed}/{self.tests_run} ({100*self.tests_passed//self.tests_run if self.tests_run else 0}%)")
        
        if self.tests_passed == self.tests_run:
            print("\n✅ ALL REGRESSION TESTS PASSED")
            return 0
        else:
            print(f"\n⚠️  {self.tests_run - self.tests_passed} tests failed")
            return 1

def main():
    tester = RegressionTester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())
