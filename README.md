# openbsd-commits-to-mastodon

A script that toots each and every OpenBSD commits. It's based on the work and
idea of afresh1 for [twitter](https://github.com/afresh1/openbsd-commits-to-twitter)

You can follow these accounts:
 * [openbsd_cvs](https://botsin.space/@openbsd_cvs): All commits
 * [openbsd_src](https://botsin.space/@openbsd_src): Commits to the src module
 * [openbsd_ports](https://botsin.space/@openbsd_ports): Commits to the ports module
 * [openbsd_www](https://botsin.space/@openbsd_www): Commits to the www module
 * [openbsd_xenocara](https://botsin.space/@openbsd_xenocara): Commits to the xenocara module
 * [openbsd_stable](https://botsin.space/@openbsd_stable): Commits to a stable branch (broken for now)
 * [openbsd_sets](https://botsin.space/@openbsd_sets): New snapshots (still to be done)

See each script for their authors and licenses.

## Maintenance

Create a docker image

~~~
$ docker build . -t obsdcommits:XXX && DOCKER_UPLOAD obsdcommits:XXX
~~~

In a docker-compose file

~~~
  obsdcommits:
    image: r.chown.me/obsdcommits:XXX
    restart: always
    env_file: .env.obsdcommits
    security_opt:
      - "no-new-privileges:true"
    cap_drop:
      - ALL
~~~

The .env.obsdcommits file is something like

~~~
PG_HOST=10.10.10.42
PG_PASSWORD=hunter2
~~~

To fill the `credentials` sql table, use

~~~
$ docker-compose run --rm obsdcommits python createsecret.py
# or
$ docker run -it --rm obsdcommits:16 python createsecret.py
~~~
