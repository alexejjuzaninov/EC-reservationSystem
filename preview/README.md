# Public EC preview

The public site is a **view-only demo**. The source project remains fully functional locally. The preview runs as an independent Compose project (`ec_preview`) with its own primary PostgreSQL database, streaming read replica, Redis cache, application, Nginx edge, and optional Cloudflare Tunnel connector. No application, database, or cache port is published on the host.

## Prepare the snapshot

On the Windows development machine, run `./preview/package.ps1`. It compiles the Spring Boot JAR, exports `preview/artifacts/source-data.dump` from the current local database, and creates `preview/artifacts/ec-preview-source.tar.gz`. Keep the dump private; it includes demo account and reservation data. The archive excludes Flyway history so the target database can run its own migrations.

Use an x86-64 Linux Docker Compose host with at least 2 vCPUs, 4 GB RAM, and 30 GB free disk. On the target host, unpack `ec-preview-source.tar.gz` into its own directory, `/home/ivan/ec-preview` on the current host. Do not copy the local `preview/.env` or any existing tunnel token. Copy `source-data.dump` to `preview/artifacts/`, then run `sh preview/setup-remote.sh` and `sh preview/deploy.sh` from that directory. The first script generates three different, random 48-character passwords on the server in a mode-0600 file. The Java image is built from the precompiled JAR; Maven is not required on the server. The deployment script migrates a new database, restores the snapshot, disables the normal write-capable database logins, sets the preview reader password, and starts the site. It does not start Cloudflare.

The app uses `preview_reader`, which has `SELECT` only. The servlet filter and Nginx both reject API methods that change data. The sole POST exception is `/api/stations/availability-batch`, which only checks open slots. Background event dispatch and Flyway are disabled in the running preview app. Redis only caches derived map clusters and is nonpersistent. All demo roles and existing records remain present; the public copy marks most old seeded notifications as read to give the sample inboxes plausible counts. Role selection does not authenticate a real user.

## Cloudflare

Create a **new, remotely managed tunnel** dedicated to this site in the Cloudflare dashboard under Networking > Tunnels. After its connector is online, use Routes > Add route > Published application. Set subdomain `ec`, domain `vezem1r.com`, service type `HTTP`, URL `http://edge:8080`, and leave the path empty. Save only this tunnel's connector token in `preview/secrets/tunnel-token` on the target host (`chmod 600`); do not use a Global API key. The dedicated connector runs as the host's non-root UID 1000 to read that file. Start it with:

```sh
docker compose --env-file preview/.env -f compose.preview.yaml -f compose.preview.tunnel.yaml up -d tunnel
```

The tunnel token alone can run a connector, so keep it private and rotate it if exposed. The connector joins the internal `edge` network to reach Nginx and a separate `tunnel_egress` network for outbound Cloudflare traffic. Nginx, the app, and the databases have only internal networks. The tunnel needs no inbound port forwarding. Cloudflare Access may be added later if the audience should be restricted.

## Verify

Use `docker compose --env-file preview/.env -f compose.preview.yaml ps` and `curl https://ec.vezem1r.com/api/system`. `readOnly` must be `true`. A direct `POST /api/bookings`, `PATCH /api/notifications/{id}/read`, or `DELETE` request must return 403. The safe batch availability POST should return data. Compare row counts with the source after restore. The site should be checked on desktop and mobile in every role.

## Remove

From the dedicated project directory, run:

```sh
docker compose --env-file preview/.env -f compose.preview.yaml down -v --remove-orphans
```

Then delete the dedicated Cloudflare tunnel and DNS route in Cloudflare, and delete the dedicated project directory and snapshot archive. This removes the preview containers, private networks, and its two PostgreSQL volumes. It does not touch the local development stack or other Compose projects. Docker isolation reduces exposure, but sharing a kernel with other services is not an absolute security boundary; a separate VPS gives stronger separation.
