#!/usr/bin/env bash
# Create the Mongo root user ONCE on an existing (pre-auth) data volume so that --auth can be
# enabled without locking everyone out. On a FRESH volume the compose entrypoint creates this
# user automatically and this script is unnecessary. Idempotent: no-ops if the user exists.
# Run with the mongodb container up (auth may already be on -- localhost exception allows the
# first user creation; if a user already exists this just reports it).
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; [ -f .env ] && . ./.env; set +a
: "${MONGO_USER:?set MONGO_USER in .env}"; : "${MONGO_PASS:?set MONGO_PASS in .env}"
# Pass creds as ENV into the container (never interpolated into the JS string), so passwords
# containing quotes/backslashes/$/backticks can't break the eval or inject JS -> avoids the
# "auth enabled but no user created => full lockout" failure mode.
docker exec -e MU="$MONGO_USER" -e MP="$MONGO_PASS" -i mongodb mongosh --quiet admin --eval '
  const u = process.env.MU, p = process.env.MP;
  try { if (db.getUser(u)) { print("user already exists"); quit(0); } } catch (e) {}
  db.createUser({user: u, pwd: p, roles: [{role: "root", db: "admin"}]});
  print("root user " + u + " created");
'
