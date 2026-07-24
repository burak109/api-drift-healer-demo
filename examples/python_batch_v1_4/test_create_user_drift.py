import requests
from unittest.mock import patch


def test_create_user_with_stale_email_field():
    with patch("requests.post") as post_mock:
        post_mock.return_value.status_code = 201

        response = requests.post(
            "http://localhost:3000/users",
            json={
                "name": "Drift User",
                "userEmail": "drift@example.com",
            },
        )

        sent_payload = post_mock.call_args.kwargs["json"]

        assert "email_address" in sent_payload
        assert "userEmail" not in sent_payload
        assert response.status_code == 201
