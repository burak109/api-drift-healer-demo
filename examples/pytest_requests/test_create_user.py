import requests


def test_create_user() -> None:
    payload = {
        "name": "Test User",
        "userEmail": "qa_user@example.com",
    }

    response = requests.post(
        "http://localhost:3000/users",
        json=payload,
    )

    assert response.status_code == 201