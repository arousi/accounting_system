import os
import tempfile
import unittest
import uuid

from app import create_app


class ApiRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = os.path.join(cls._tmpdir.name, "test_accounting_web.db")
        os.environ["ACCOUNTING_DATABASE_URL"] = f"sqlite:///{db_path.replace('\\', '/')}"
        cls.app = create_app()
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls._tmpdir.cleanup()

    def login(self, email, password):
        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        return {"Authorization": f"Bearer {payload['token']}"}

    def test_admin_core_flows_and_exports(self):
        headers = self.login("admin@example.com", "Admin@12345")

        session_response = self.client.get("/api/v1/auth/session", headers=headers)
        self.assertEqual(session_response.status_code, 200)

        projects_response = self.client.get("/api/v1/projects", headers=headers)
        self.assertEqual(projects_response.status_code, 200)
        projects = projects_response.get_json()["items"]
        self.assertGreaterEqual(len(projects), 1)

        main_project = next(project for project in projects if project["code"] == "MAIN")
        project_id = main_project["id"]

        fiscal_years_response = self.client.get(
            f"/api/v1/projects/{project_id}/fiscal-years",
            headers=headers,
        )
        self.assertEqual(fiscal_years_response.status_code, 200)
        fiscal_year_id = fiscal_years_response.get_json()["items"][0]["id"]

        accounts_response = self.client.get(
            f"/api/v1/projects/{project_id}/accounts",
            headers=headers,
        )
        self.assertEqual(accounts_response.status_code, 200)
        account_id = accounts_response.get_json()["items"][0]["id"]

        for route in [
            f"/api/v1/projects/{project_id}",
            f"/api/v1/projects/{project_id}/readiness",
            f"/api/v1/projects/{project_id}/dashboard",
            f"/api/v1/projects/{project_id}/journals?fiscal_year_id={fiscal_year_id}",
            f"/api/v1/projects/{project_id}/ledger?fiscal_year_id={fiscal_year_id}&account_id={account_id}",
            f"/api/v1/projects/{project_id}/trial-balance?fiscal_year_id={fiscal_year_id}",
            f"/api/v1/projects/{project_id}/transfers?fiscal_year_id={fiscal_year_id}",
        ]:
            response = self.client.get(route, headers=headers)
            self.assertEqual(response.status_code, 200, msg=route)

        project_xlsx = self.client.get(
            f"/api/v1/projects/{project_id}/exports/finance.xlsx?fiscal_year_id={fiscal_year_id}",
            headers=headers,
        )
        self.assertEqual(project_xlsx.status_code, 200)
        self.assertIn(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            project_xlsx.headers.get("Content-Type", ""),
        )

        project_pdf = self.client.get(
            f"/api/v1/projects/{project_id}/exports/finance.pdf?fiscal_year_id={fiscal_year_id}",
            headers=headers,
        )
        self.assertEqual(project_pdf.status_code, 200)
        self.assertIn("application/pdf", project_pdf.headers.get("Content-Type", ""))

    def test_project_scope_isolated_for_field_manager(self):
        headers = self.login("field.manager@example.com", "Manager@12345")
        response = self.client.get("/api/v1/projects", headers=headers)
        self.assertEqual(response.status_code, 200)
        codes = [item["code"] for item in response.get_json()["items"]]
        self.assertEqual(codes, ["FIELD-SVC"])

    def test_registration_and_onboarding_company_and_project(self):
        suffix = uuid.uuid4().hex[:8]
        email = f"new.user.{suffix}@example.com"
        company_code = f"NC{suffix[:6].upper()}"
        project_code = f"NCP{suffix[:4].upper()}"
        register_response = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "full_name": "New User",
                "password": "StrongPass123!",
                "preferred_locale": "en",
            },
        )
        self.assertEqual(register_response.status_code, 201)
        payload = register_response.get_json()
        headers = {"Authorization": f"Bearer {payload['token']}"}

        onboarding_before = self.client.get("/api/v1/onboarding/status", headers=headers)
        self.assertEqual(onboarding_before.status_code, 200)
        self.assertFalse(onboarding_before.get_json()["onboarding_complete"])

        company_response = self.client.post(
            "/api/v1/companies",
            json={"code": company_code, "name": "New Company"},
            headers=headers,
        )
        self.assertEqual(company_response.status_code, 201)

        project_response = self.client.post(
            "/api/v1/projects",
            json={
                "code": project_code,
                "name_ar": "مشروع جديد",
                "name_en": "New Company Project",
                "currency_code": "USD",
                "fiscal_year": {
                    "code": "2026",
                    "name": "Fiscal Year 2026",
                    "start_date": "2026-01-01",
                    "end_date": "2026-12-31",
                },
            },
            headers=headers,
        )
        self.assertEqual(project_response.status_code, 201)

        onboarding_after = self.client.get("/api/v1/onboarding/status", headers=headers)
        self.assertEqual(onboarding_after.status_code, 200)
        self.assertTrue(onboarding_after.get_json()["onboarding_complete"])

    def test_rbac_blocks_employee_from_company_user_management(self):
        headers = self.login("field.manager@example.com", "Manager@12345")
        list_users_response = self.client.get("/api/v1/users", headers=headers)
        self.assertEqual(list_users_response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
