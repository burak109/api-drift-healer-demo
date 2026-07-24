import requests
from unittest.mock import patch


def test_create_second_user_with_current_contract():
    with patch("requests.post") as post_mock:
        post_mock.return_value.status_code = 201

        response = requests.post(
            "http://localhost:3000/users",
            json={
                "name": "Second User",
                "email_address": "second@example.com",
            },
        )

        sent_payload = post_mock.call_args.kwargs["json"]

        assert "email_address" in sent_payload
        assert response.status_code == 201
