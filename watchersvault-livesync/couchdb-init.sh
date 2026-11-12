#!/bin/sh
# Configure CouchDB for Self-hosted LiveSync and create one database per vault.
# Safe to run again after a restart.

set -eu

hostname="${COUCHDB_INTERNAL_URL:-http://couchdb:5984}"
username="${COUCHDB_USER:?COUCHDB_USER is required}"
password="${COUCHDB_PASSWORD:?COUCHDB_PASSWORD is required}"
node="${COUCHDB_NODE:-_local}"
envfile="${LIVESYNC_ENV:-/mnt/app/.env}"

json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

url_encode() {
  printf '%s' "$1" | sed 's/%/%25/g; s/+/%2B/g; s/(/%28/g; s/)/%29/g; s/\$/%24/g'
}

read_databases() {
  found=
  if [ -f "$envfile" ]; then
    while IFS= read -r line || [ -n "$line" ]; do
      line=$(printf '%s' "$line" | tr -d '\r')
      trim=$line
      while :; do
        case $trim in
          [[:space:]]*) trim=${trim#?} ;;
          *) break ;;
        esac
      done
      case $trim in
        COUCHDB_DATABASES=*)
          found=${trim#COUCHDB_DATABASES=}
          case $found in
            \"*\") found=${found#\"}; found=${found%\"} ;;
            \'*\') found=${found#\'}; found=${found%\'} ;;
          esac
          ;;
      esac
    done < "$envfile"
  fi
  if [ -z "$found" ]; then
    found=${COUCHDB_DATABASES:-test}
  fi
  printf '%s' "$found"
}

put_config() {
  section=$1
  key=$2
  value=$3
  curl -fsS -X PUT "${hostname}/_node/${node}/_config/${section}/${key}" \
    -H "Content-Type: application/json" \
    --netrc-file "$netrc" \
    -d "$value" >/dev/null
  echo "[OK] ${section}/${key}"
}

valid_database() {
  case $1 in
    _*) return 1 ;;
  esac
  printf '%s' "$1" | grep -Eq '^[a-z][a-z0-9_$()+/-]*$'
}

hostonly=${hostname#*://}
hostonly=${hostonly%%/*}
hostonly=${hostonly%%:*}
netrc=$(mktemp)
trap 'rm -f "$netrc"' EXIT
umask 077
cat > "$netrc" << EOF
machine ${hostonly}
login ${username}
password ${password}
EOF

echo "==> Waiting for CouchDB at ${hostname}"
until curl -sf "${hostname}/_up" 2>/dev/null | grep -q '"status":"ok"'; do
  sleep 2
done
echo "==> CouchDB is up"

user_json=$(json_escape "$username")
pass_json=$(json_escape "$password")
if curl -fsS -X POST "${hostname}/_cluster_setup" \
  -H "Content-Type: application/json" \
  --netrc-file "$netrc" \
  -d "{\"action\":\"enable_single_node\",\"username\":\"${user_json}\",\"password\":\"${pass_json}\",\"bind_address\":\"0.0.0.0\",\"port\":5984,\"singlenode\":true}" \
  >/dev/null
then
  echo "[OK] cluster_setup"
else
  echo "[OK] cluster already set up"
fi

put_config chttpd require_valid_user '"true"'
put_config chttpd_auth require_valid_user '"true"'
put_config httpd WWW-Authenticate '"Basic realm=\"couchdb\""'
put_config httpd enable_cors '"true"'
put_config chttpd enable_cors '"true"'
put_config chttpd max_http_request_size '"4294967296"'
put_config couchdb max_document_size '"50000000"'
put_config cors credentials '"true"'
put_config cors origins '"app://obsidian.md,capacitor://localhost,http://localhost"'
put_config cors headers '"accept, authorization, content-type, origin, referer"'
put_config cors methods '"GET, PUT, POST, HEAD, DELETE"'
put_config cors max_age '"3600"'

databases=$(read_databases)
old_ifs=$IFS
IFS=,
for raw in $databases; do
  db=$(printf '%s' "$raw" | tr -d '[:space:]')
  if [ -z "$db" ]; then
    continue
  fi
  if ! valid_database "$db"; then
    echo "Invalid database name: ${db}" >&2
    exit 1
  fi
  encoded=$(url_encode "$db")
  code=$(curl -sS -o /tmp/livesync-db-body -w "%{http_code}" \
    -X PUT "${hostname}/${encoded}" \
    --netrc-file "$netrc" || true)
  case $code in
    200|201|202)
      echo "[OK] database ${db} created"
      ;;
    412)
      echo "[OK] database ${db} already exists"
      ;;
    *)
      echo "Database ${db} was not created (HTTP ${code})" >&2
      cat /tmp/livesync-db-body >&2 || true
      exit 1
      ;;
  esac
done
IFS=$old_ifs

echo "==> CouchDB initialization complete"
echo "    Username : ${username}"
echo "    Databases: ${databases}"
