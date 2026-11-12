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
- **LiveSync** is CouchDB for the Self-hosted LiveSync Obsidian plugin. The first database is `test`, for `documents/obsidian/test`. Obsidian uses this app's Umbrel port over the existing Tailscale connection. The username is `livesync`. The password is the one Umbrel shows for the app.
- **Fast Note Sync** is the server for the Obsidian Fast Note Sync plugin. Notes are stored in the app data folder and are not end-to-end encrypted. Open the app at `http://<umbrel-tailscale-ip>:19000`, register, and paste **Copy API Config** into the plugin.

## Optional OmniRoute Tailscale HTTPS

Leave the public address blank, and leave `TS_AUTHKEY` empty in the app data `.env`, to keep the Umbrel address. This does not open ports 80 or 443, and it does not replace the Umbrel Tailscale app.

1. In the Tailscale admin console, enable HTTPS certificates and MagicDNS.
2. Create a reusable auth key.
3. In the OmniRoute app settings, set `NEXT_PUBLIC_BASE_URL` to `https://omniroute.your-tailnet.ts.net`, `AUTH_COOKIE_SECURE` to `true`, and leave `TS_HOSTNAME` as `omniroute` unless you want another name.
4. Put the key in `.env` in the OmniRoute app data folder, beside `settings.yml`: `TS_AUTHKEY=tskey-auth-...`. The file is mode 600. It is not stored in Umbrel settings. On update, a key already saved in `settings.yml` is moved into this file and removed from settings.
5. Restart the app. Tailnet peers open that https address directly. It uses OmniRoute's own password and API key.

## LiveSync over the existing Tailscale

LiveSync uses the Umbrel Tailscale app that is already installed. It does not add a second tailnet node, a certificate, or an auth key.

1. Update LiveSync from this store and restart it.
2. In the `test` vault, install Self-hosted LiveSync and choose manual CouchDB setup.
3. Use `http://<umbrel-tailscale-ip>:25984`, username `livesync`, database `test`, and the password Umbrel shows for the app. On the local network the Umbrel address for that same port works too.
4. Turn on end-to-end encryption. A phone may reject `http://umbrel.<tailnet>.ts.net`. Use the tailnet IP.

## Fast Note Sync over the existing Tailscale

Fast Note Sync uses the Umbrel Tailscale app that is already installed. It does not add a second tailnet node or a certificate. Notes stored by this server are not end-to-end encrypted.

1. Install Fast Note Sync from this store.
2. Open `http://<umbrel-tailscale-ip>:19000` and register.
3. Click **Copy API Config** and paste it into the Fast Note Sync plugin in the vault you want to sync.
4. Open that page from the tailnet IP before copying. A copy made from `umbrel.local` stores that name. A phone may reject `http://umbrel.<tailnet>.ts.net`.
5. After the first account exists, turn registration off in the admin settings.
