from fastapi.testclient import TestClient
from main import app
from unittest.mock import patch
import os

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"Hello": "World"}

@patch("main.save_to_firestore")
@patch("main.upload_to_gcs")
@patch("main.parse_resume")
def test_upload_resume(mock_parse_resume, mock_upload_to_gcs, mock_save_to_firestore):
    # Mock the return values of the external services
    mock_parse_resume.return_value = {
        "name": "John Doe",
        "email": "john.doe@example.com",
        "skills": ["Python", "FastAPI"]
    }
    mock_upload_to_gcs.return_value = "gs://cvanalyzer_resumes/dummy_resume.pdf"
    mock_save_to_firestore.return_value = "some-firestore-id"

    # Create a dummy pdf file
    if not os.path.exists("resumes"):
        os.makedirs("resumes")
    with open("dummy_resume.pdf", "w") as f:
        f.write("This is a dummy resume.")

    with open("dummy_resume.pdf", "rb") as f:
        response = client.post("/resume/", files={"file": ("dummy_resume.pdf", f, "application/pdf")})

    # Clean up the dummy file
    os.remove("dummy_resume.pdf")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "John Doe"
    assert data["email"] == "john.doe@example.com"
    assert data["skills"] == ["Python", "FastAPI"]
    assert "resume_uri" in data
    assert "firestore_id" in data
