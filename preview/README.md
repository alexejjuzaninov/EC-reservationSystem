# Public EC preview

The public site is a **view-only demo**. The source project remains fully functional locally. The preview runs as an independent Compose project (`ec_preview`) with its own primary PostgreSQL database, streaming read replica, Redis cache, application, Nginx edge, and optional Cloudflare Tunnel connector. No application, database, or cache port is published on the host.

## Current deployment

The dedicated Linux project directory has its own database volumes, credentials, and Cloudflare Tunnel connector. Git does not track local credentials or connector tokens. One-time archive creation and transfer helpers have been removed from this repository. The running server keeps its own deployed copy.

The app uses `preview_reader`, which has `SELECT` only. The servlet filter and Nginx both reject API methods that change data. The sole POST exception is `/api/stations/availability-batch`, which only checks open slots. Background event dispatch and Flyway are disabled in the running preview app. Redis only caches derived map clusters and is nonpersistent. All demo roles and existing records remain present; the public copy marks most old seeded notifications as read to give the sample inboxes plausible counts. Role selection does not authenticate a real user.

## Cloudflare

The dedicated tunnel routes `ec.vezem1r.com` to `http://edge:8080`. Its connector token lives only in `preview/secrets/tunnel-token` on the server (`chmod 600`), never in Git. The connector runs as non-root UID 1000. To start an already configured connector from the server project directory:

```sh
docker compose --env-file preview/.env -f compose.preview.yaml -f compose.preview.tunnel.yaml up -d tunnel
```

The tunnel token alone can run a connector, so keep it private and rotate it if exposed. The connector joins the internal `edge` network to reach Nginx and a separate `tunnel_egress` network for outbound Cloudflare traffic. Nginx, the app, and the databases have only internal networks. The tunnel needs no inbound port forwarding. Cloudflare Access may be added later if the audience should be restricted.

## Verify

Use `docker compose --env-file preview/.env -f compose.preview.yaml ps` and `curl https://ec.vezem1r.com/api/system`. `readOnly` must be `true`. A direct `POST /api/bookings`, `PATCH /api/notifications/{id}/read`, or `DELETE` request must return 403. The safe batch availability POST should return data. Compare row counts with the source after restore. The site should be checked on desktop and mobile in every role.

## Remove

The local, Git-ignored `preview/remove-server.sh` is a narrowly scoped teardown helper. Copy it to the server and run it with `sh`; it stops the dedicated `ec_preview` Compose stack, removes its database volumes and custom app image, and deletes its project directory. It checks the exact target path and project name before deleting anything. Delete the dedicated tunnel and DNS route separately in Cloudflare. The helper does not touch other Compose projects. Docker isolation reduces exposure, but sharing a kernel with other services is not an absolute security boundary; a separate VPS gives stronger separation.
