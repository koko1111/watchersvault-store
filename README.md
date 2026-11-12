# Watchers Vault

Community app store for umbrelOS.

## Add this store

1. Open the App Store.
2. Click the three dots in the top-right and select Community App Stores.
3. Paste this URL and click Add:

https://github.com/koko1111/watchersvault-store

## Apps

- **YT Cut and Splice** downloads only the YouTube range you select.
- **OmniRoute** is an OpenAI-compatible gateway. The dashboard stays behind Umbrel login. `/v1` requires an OmniRoute API key, which you create in the dashboard. The first launch asks for a dashboard password and stores generated signing secrets in the app data directory. `OMNIROUTE_MEMORY_MB` defaults to 4096.
- **LiveSync** is CouchDB for the Self-hosted LiveSync Obsidian plugin. The first database is `test`, for `documents/obsidian/test`. Open the app for the username and password. Obsidian uses the Tailscale HTTPS address, not the Umbrel address.

## Optional OmniRoute Tailscale HTTPS

Leave the public address blank, and leave `TS_AUTHKEY` empty in the app data `.env`, to keep the Umbrel address. This does not open ports 80 or 443, and it does not replace the Umbrel Tailscale app.

1. In the Tailscale admin console, enable HTTPS certificates and MagicDNS.
2. Create a reusable auth key.
3. In the OmniRoute app settings, set `NEXT_PUBLIC_BASE_URL` to `https://omniroute.your-tailnet.ts.net`, `AUTH_COOKIE_SECURE` to `true`, and leave `TS_HOSTNAME` as `omniroute` unless you want another name.
4. Put the key in `.env` in the OmniRoute app data folder, beside `settings.yml`: `TS_AUTHKEY=tskey-auth-...`. The file is mode 600. It is not stored in Umbrel settings. On update, a key already saved in `settings.yml` is moved into this file and removed from settings.
5. Restart the app. Tailnet peers open that https address directly. It uses OmniRoute's own password and API key.

## Optional LiveSync Tailscale HTTPS

Leave `LIVESYNC_URL` blank, and leave `TS_AUTHKEY` empty in the app data `.env`, to keep CouchDB off the network. This does not open ports 80 or 443, and it does not replace the Umbrel Tailscale app. Umbrel does not need the auth key in `settings.yml`.

1. In the Tailscale admin console, enable HTTPS certificates and MagicDNS.
2. Create a reusable auth key.
3. In the LiveSync app settings, set `LIVESYNC_URL` to `https://livesync.your-tailnet.ts.net`. Leave `TS_HOSTNAME` as `livesync` unless you want another name.
4. Put `TS_AUTHKEY=tskey-auth-...` in `.env` beside `settings.yml`. The file is mode 600.
5. Restart the app. In the `test` vault, run Self-hosted LiveSync Quick Setup with database name `test`. The username is `livesync`. The password is the one Umbrel shows for the app.
