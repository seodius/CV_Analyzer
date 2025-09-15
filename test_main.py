from fastapi.testclient import TestClient
from main import app
from unittest.mock import patch
import os

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"Hello": "World"}

@patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "BUCKET_NAME": "test-bucket"})
@patch("main.save_to_firestore")
@patch("main.upload_to_gcs")
@patch("main.parse_resume_with_gemini")
@patch("main.extract_text_from_pdf")
def test_upload_resume(mock_extract_text, mock_parse_gemini, mock_upload_to_gcs, mock_save_to_firestore):
    # Mock the return values of the external services
    mock_extract_text.return_value = "This is a dummy resume."
    mock_parse_gemini.return_value = {
        "basics": {
            "name": "John Doe",
            "email": "john.doe@example.com"
        },
        "skills": [
            {"name": "Python"},
            {"name": "FastAPI"}
        ]
    }
    mock_upload_to_gcs.return_value = "gs://test-bucket/dummy_resume.pdf"
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
    assert data["basics"]["name"] == "John Doe"
    assert data["basics"]["email"] == "john.doe@example.com"
    assert data["skills"][0]["name"] == "Python"
    assert "resume_uri" in data
    assert "firestore_id" in data
