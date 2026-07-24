"""Tests for subject CRUD with user isolation."""


class TestSubjects:
    def test_create_and_list(self, client, auth_headers):
        """Create a subject and verify it appears in the list."""
        resp = client.post("/api/v1/subjects", json={
            "name": "TestSubject", "description": "A test subject"
        }, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["name"] == "TestSubject"

        # List
        resp = client.get("/api/v1/subjects", headers=auth_headers)
        assert resp.status_code == 200
        subjects = resp.json()
        assert any(s["name"] == "TestSubject" for s in subjects)

    def test_update_subject(self, client, auth_headers):
        """Update subject name."""
        client.post("/api/v1/subjects", json={
            "name": "OldName"
        }, headers=auth_headers)
        resp = client.put("/api/v1/subjects/1", json={
            "name": "NewName"
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "NewName"

    def test_soft_delete(self, client, auth_headers):
        """Delete sets is_active=False."""
        create_resp = client.post("/api/v1/subjects", json={
            "name": "ToDelete"
        }, headers=auth_headers)
        subj_id = create_resp.json()["id"]
        resp = client.delete(f"/api/v1/subjects/{subj_id}", headers=auth_headers)
        assert resp.status_code == 204
        # Verify it's gone from the list
        resp = client.get("/api/v1/subjects", headers=auth_headers)
        assert not any(s["name"] == "ToDelete" for s in resp.json())

    def test_user_isolation(self, client):
        """User A's subjects are invisible to User B."""
        # User A creates
        client.post("/api/v1/auth/signup", json={"username": "userA", "password": "password123"})
        token_a = client.post("/api/v1/auth/login", json={"username": "userA", "password": "password123"}).json()["access_token"]
        client.post("/api/v1/subjects", json={"name": "A_Subject"}, headers={"Authorization": f"Bearer {token_a}"})

        # User B creates
        client.post("/api/v1/auth/signup", json={"username": "userB", "password": "password123"})
        token_b = client.post("/api/v1/auth/login", json={"username": "userB", "password": "password123"}).json()["access_token"]
        client.post("/api/v1/subjects", json={"name": "B_Subject"}, headers={"Authorization": f"Bearer {token_b}"})

        # User A should only see A_Subject
        resp = client.get("/api/v1/subjects", headers={"Authorization": f"Bearer {token_a}"})
        names = [s["name"] for s in resp.json()]
        assert "A_Subject" in names
        assert "B_Subject" not in names
