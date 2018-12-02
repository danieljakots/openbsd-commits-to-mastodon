#!/usr/bin/env python3

# Copyright (c) 2018 Daniel Jakots
#
# Licensed under the MIT license.

import json
import os
import sqlite3
import subprocess
import time

from mastodon import Mastodon


INSTANCE = "https://botsin.space"
WORK_DIR = "/home/danj/bots-OpenBSD/"
SQLITE_DB = WORK_DIR + "/db-commits.db"
CREDENTIALS = WORK_DIR + "credentials.json"
MIRROR = "anoncvs.spacehopper.org/OpenBSD-CVS/CVSROOT/ChangeLog"
CHANGELOG_DIR = WORK_DIR + "/tmp"
TIME_BETWEEN = 60


def regis_app():
    """Register app - only once!"""
    with open(CREDENTIALS, "r") as f:
        json_cfg = json.load(f)
    client_id, client_secret = Mastodon.create_app("cvstotoot", api_base_url=INSTANCE)
    json_cfg["client_cred"] = {"client_id": client_id, "client_secret": client_secret}
    with open(CREDENTIALS, "w") as f:
        json.dump(json_cfg, f)
    return client_id, client_secret


def log_bot_in(name, mail, passwd, client_id, client_secret):
    with open(CREDENTIALS, "r") as f:
        json_cfg = json.load(f)
    mastodon = Mastodon(
        client_id=client_id, client_secret=client_secret, api_base_url=INSTANCE
    )
    access_token = mastodon.log_in(mail, passwd)
    for bot in json_cfg["accounts"]:
        if bot["name"] != name:
            continue
        bot["usercred"] = access_token
        break
    with open(CREDENTIALS, "w") as f:
        json.dump(json_cfg, f)


def awoo(account, message):
    with open(CREDENTIALS, "r") as f:
        json_cfg = json.load(f)
    for bot in json_cfg["accounts"]:
        if bot["name"] != account:
            continue
        access_token = bot["usercred"]
        break
    mastodon = Mastodon(access_token=access_token, api_base_url=INSTANCE)
    mastodon.toot(message)


def tootifneeded(conn):
    c = conn.cursor()
    c.execute("SELECT account, message FROM obsdcommits WHERE status_specific = 0")
    toots_specific = c.fetchall()
    for toot in toots_specific:
        account = toot[0]
        message = toot[1]
        awoo(account, message)
        c.execute(
            "UPDATE obsdcommits SET status_specific = 1 "
            "WHERE account = ? AND message = ?",
            (account, message),
        )
        conn.commit()
        time.sleep(TIME_BETWEEN)
        # check this commit wasn't tooted by openbsd_cvs
        c.execute(
            "SELECT status_cvs FROM obsdcommits WHERE account = ? AND message = ?",
            (account, message),
        )
        if c.fetchone()[0] == 0:
            awoo("openbsd_cvs", message)
            c.execute(
                "UPDATE obsdcommits SET status_cvs = 1 "
                "WHERE account = ? AND message = ?",
                (account, message),
            )
            conn.commit()
            time.sleep(TIME_BETWEEN)
    conn.commit()
    # check if anything needs to be tooted by @openbsd_cvs
    c.execute("SELECT account, message FROM obsdcommits WHERE status_cvs = 0")
    toots_cvs = c.fetchall()
    for toot in toots_cvs:
        account = toot[0]
        message = toot[1]
        awoo(account, message)
        c.execute(
            "UPDATE obsdcommits SET status_cvs = 1 "
            "WHERE account = ? AND message = ?",
            (account, message),
        )
        conn.commit()
        time.sleep(TIME_BETWEEN)


def update_changelog(mirror, changelog_dir):
    if not os.path.exists(changelog_dir):
        os.makedirs(changelog_dir)
    subprocess.run(
        ["/usr/local/bin/rsync", "-a", f"rsync://{mirror}", changelog_dir],
        stdout=subprocess.PIPE,
        encoding="utf-8",
    )


def parse_commits(work_dir, changelog_dir):
    parsed = subprocess.run(
        [f"{work_dir}/parse-commits.pl", f"{changelog_dir}/ChangeLog"],
        stdout=subprocess.PIPE,
        encoding="utf-8",
    )
    return parsed.stdout


def sqlite_init(sqlite_file):
    """Initialize database."""
    conn = sqlite3.connect(sqlite_file)
    create_sql = (
        "CREATE TABLE IF NOT EXISTS obsdcommits (account TEXT, message "
        "TEXT, status_specific INTEGER, status_cvs INTEGER, CONSTRAINT "
        "commit_unique UNIQUE (account, message));"
    )
    with conn:
        conn.execute(create_sql)
    conn.close()


def add_sqlite(conn, account, message):
    try:
        conn.execute(
            "INSERT INTO obsdcommits (account, message,"
            "status_specific, status_cvs) VALUES (?, ?, ?, ?)",
            (account, message, 0, 0),
        )
    except sqlite3.IntegrityError:
        # sqlite unicity constraint kicking in
        pass


def masto_init(work_dir):
    with open(CREDENTIALS, "r") as f:
        json_cfg = json.load(f)
    try:
        client_id = json_cfg["client_cred"]
        client_secret = json_cfg["client_secret"]
    except KeyError:
        client_id, client_secret = regis_app()
    with open(CREDENTIALS, "r") as f:
        json_cfg = json.load(f)
    for bot in json_cfg["accounts"]:
        name = bot["name"]
        try:
            usercred = bot["usercred"]
        except KeyError:
            mail = bot["email"]
            password = bot["password"]
            log_bot_in(name, mail, password, client_id, client_secret)


def main():
    masto_init(WORK_DIR)
    update_changelog(MIRROR, CHANGELOG_DIR)
    sqlite_init(SQLITE_DB)
    commits = parse_commits(WORK_DIR, CHANGELOG_DIR)
    conn = sqlite3.connect(SQLITE_DB)
    for line in commits.split("\n"):
        if not line:
            continue
        if line.split()[0] != "nostabletag":
            account = "openbsd_stable"
        else:
            account = line.split()[1]
        message = " ".join(line.split()[2:])
        add_sqlite(conn, account, message)
    conn.commit()
    tootifneeded(conn)
    conn.close()


if __name__ == "__main__":
    main()
