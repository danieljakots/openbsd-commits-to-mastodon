#!/usr/bin/env python3

# Copyright (c) 2018, 2020 Daniel Jakots
#
# Licensed under the MIT license.

import os
import subprocess
import time

from mastodon import Mastodon

import psycopg2


INSTANCE = "https://botsin.space"
WORK_DIR = "/home/obsdcommits/"
MIRROR = "anoncvs.spacehopper.org/OpenBSD-CVS/CVSROOT/ChangeLog"
CHANGELOG_DIR = WORK_DIR + "/tmp"
TIME_BETWEEN = 60


def awoo(account, message):
    access_token = get_credentials(account)
    print(account, access_token, message)
    # mastodon = Mastodon(access_token=access_token, api_base_url=INSTANCE)
    # mastodon.toot(message)


def awooifneeded():
    database = db_connect()
    cursor = database.cursor()
    cursor.execute("SELECT account, message FROM obsdcommits WHERE status_specific = 0")
    toots_specific = cursor.fetchall()
    for toot in toots_specific:
        account = toot[0]
        message = toot[1]
        awoo(account, message)
        cursor.execute(
            "UPDATE obsdcommits SET status_specific = 1 "
            "WHERE account = %s AND message = %s",
            (account, message),
        )
        database.commit()
        time.sleep(TIME_BETWEEN)
        # check this commit wasn't tooted by openbsd_cvs
        cursor.execute(
            "SELECT status_cvs FROM obsdcommits WHERE account = %s AND message = %s",
            (account, message),
        )
        if cursor.fetchone()[0] == 0:
            awoo("openbsd_cvs", message)
            cursor.execute(
                "UPDATE obsdcommits SET status_cvs = 1 "
                "WHERE account = %s AND message = %s",
                (account, message),
            )
            database.commit()
            time.sleep(TIME_BETWEEN)
    database.commit()
    # check if anything needs to be tooted by @openbsd_cvs
    cursor.execute("SELECT account, message FROM obsdcommits WHERE status_cvs = 0")
    toots_cvs = cursor.fetchall()
    for toot in toots_cvs:
        account = toot[0]
        message = toot[1]
        awoo(account, message)
        cursor.execute(
            "UPDATE obsdcommits SET status_cvs = 1 "
            "WHERE account = %s AND message = %s",
            (account, message),
        )
        database.commit()
        time.sleep(TIME_BETWEEN)
    database.close()


def update_changelog(mirror, changelog_dir):
    if not os.path.exists(changelog_dir):
        os.makedirs(changelog_dir)
    subprocess.run(
        ["/usr/bin/rsync", "-a", f"rsync://{mirror}", changelog_dir],
        stdout=subprocess.PIPE,
        encoding="utf-8",
    )


def parse_commits(work_dir, changelog_dir):
    print("Begin parsing commits (with the perl script)")
    parsed = subprocess.run(
        [f"{work_dir}/parse-commits.pl", f"{changelog_dir}/ChangeLog"],
        stdout=subprocess.PIPE,
        encoding="utf-8",
    )
    print("Finish parsing commits (with the perl script)")
    return parsed.stdout


def pgsql_init():
    """Initialize database."""
    database = db_connect()
    cursor = database.cursor()
    create_obsdcommits = (
        "CREATE TABLE IF NOT EXISTS obsdcommits (account TEXT, message "
        "TEXT, status_specific INTEGER, status_cvs INTEGER, CONSTRAINT "
        "commit_unique UNIQUE (account, message));"
    )
    create_credentials = (
        "CREATE TABLE IF NOT EXISTS credentials (account TEXT, client_id "
        "TEXT, client_secret TEXT, access_token TEXT);"
    )
    cursor.execute(create_obsdcommits)
    cursor.execute(create_credentials)
    database.commit()
    cursor.close()
    database.close()


def add_commit_to_pgsql(account, message):
    database = db_connect()
    cursor = database.cursor()
    cursor.execute(
        "INSERT INTO obsdcommits (account, message, "
        "status_specific, status_cvs) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING;",
        (account, message, 0, 0),
    )
    database.commit()
    cursor.close()
    database.close()


def db_connect():
    host = os.getenv("PG_HOST", "127.0.0.1")
    database = os.getenv("PG_DB", "obsdcommits")
    user = os.getenv("PG_USER", "obsdcommits")
    password = os.getenv("PG_PASSWORD")
    port = os.getenv("PG_PORT", "5432")
    database = psycopg2.connect(
        host=host, database=database, user=user, password=password, port=port
    )
    return database


def get_credentials(account):
    database = db_connect()
    cursor = database.cursor()
    cursor.execute(
        "SELECT client_id, client_secret, access_token FROM credentials WHERE account=%s;",
        (account,),
    )
    client_id, client_secret, access_token = cursor.fetchone()
    cursor.close()
    database.close()
    return client_id, client_secret, access_token


def main():
    update_changelog(MIRROR, CHANGELOG_DIR)
    pgsql_init()
    commits = parse_commits(WORK_DIR, CHANGELOG_DIR)
    for line in commits.split("\n"):
        if not line:
            continue
        if line.split()[0] != "nostabletag":
            account = "openbsd_stable"
        else:
            account = line.split()[1]
        message = " ".join(line.split()[2:])
        add_commit_to_pgsql(account, message)
    awooifneeded()


if __name__ == "__main__":
    main()
