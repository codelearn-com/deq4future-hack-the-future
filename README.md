# Hack-The-Future Server

This is the server hosted at [hackathon.deq4future.org](https://hackathon.deq4future.org),
which serves some request for the **Hack The Future** hackathon, that took
place in Gavà (Barcelona) on June 14th.

The server can be easily set up using docker and uses a Flask application with
a MariaDB database.

## Endpoints

There are 4 endpoints available:
- `/game/new` creates a game row and returns `{game_id: 12345, seed: 12345}`.
- `/game/store_progress` stores a game progress, sent as POST body.
- `/game/finalize` marks the game as finished. This is also a POST request.
- `/game/get_progress?game_id=12345` retrieves the latest update.

## Set up

Simply build and run the docker image(s):

```sh
docker compose up -d
```

Then you will be able to access the server on `http://localhost:3555`.

## Access logs

Also a single command:

```sh
docker compose logs -t
```
