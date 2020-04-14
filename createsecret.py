#!/usr/bin/env python3

import getpass

from mastodon import Mastodon

INSTANCE = "https://botsin.space"


def create_app_secret():
    client_id, client_secret = Mastodon.create_app(
        "openbsd-commits-to-mastodon", api_base_url=INSTANCE
    )
    return client_id, client_secret


def create_login_secret(client_id, client_secret, email, password):
    mastodon = Mastodon(
        client_id=client_id, client_secret=client_secret, api_base_url=INSTANCE
    )
    access_token = mastodon.log_in(email, password)
    return access_token


def main():
    email = input("email address: ")
    password = getpass.getpass()
    client_id, client_secret = create_app_secret()
    access_token = create_login_secret(client_id, client_secret, email, password)
    print(
        "INSERT INTO credentials (account, client_id, client_secret, access_token) "
        f"VALUES ('{email}', '{client_id}', '{client_secret}', '{access_token}');"
    )


if __name__ == "__main__":
    main()
