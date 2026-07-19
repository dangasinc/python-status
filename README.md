# WhatsApp Status Auto View & Like Bot

A Python worker that logs into WhatsApp via a **pairing code** (no QR
scanning) and automatically **views** and **reacts to ("likes")** the
Status updates posted by your contacts.

Built on [neonize](https://github.com/krypton-byte/neonize), a Python
binding for the Go library `whatsmeow`, which implements WhatsApp's
multi-device web protocol. Every method this project calls
(`PairPhone`, `mark_read`, `build_reaction`, `send_message`, event
handlers) was verified against neonize `0.4.3.post0` installed and
imported in a real Python 3.12 environment before being shipped here —
see "What was and wasn't verified" below for the one thing that
couldn't be tested end-to-end.

## How it works

- WhatsApp statuses arrive over the same protocol channel as normal
  messages, addressed to the special chat `status@broadcast`, with the
  real poster in the sender field. The bot listens to the normal
  message event stream and filters for that chat.
- "Viewing" a status = sending a read receipt for it.
- "Liking" a status = sending an emoji reaction targeted at that same
  broadcast chat, with the original poster as the reaction's sender
  reference.
- A small random delay (2–8s by default) is added before reacting so
  it doesn't fire mechanically the instant a status appears.

## Project layout

```
whatsapp-status-bot/
├── app/
│   ├── config.py         # all settings, read from environment variables
│   ├── health_server.py  # tiny stdlib-only HTTP health/status endpoint
│   └── status_bot.py     # neonize client, pairing, status detection/actions
├── main.py                # entrypoint
├── requirements.txt
├── Procfile
├── railway.json
├── .python-version
├── .env.example
└── .gitignore
```

## Deploying to Railway

1. Push this project to a GitHub repo (or use Railway's CLI to deploy
   the folder directly).
2. In Railway, create a new project from that repo.
3. **Attach a Volume** to the service, mounted at `/data`. This is the
   most important step — without it, the container's filesystem is
   wiped on every redeploy, the WhatsApp session is lost, and you'll
   have to re-pair the device each time.
4. Set environment variables (Railway → your service → Variables):
   - `PHONE_NUMBER` — your WhatsApp number, digits only, country code,
     no `+` (e.g. `15551234567`)
   - `SESSION_DB_PATH=/data/session.db3` (matches the volume mount)
   - Optionally: `VIEW_STATUSES`, `LIKE_STATUSES`, `REACTION_EMOJI`,
     `MIN_REACT_DELAY_SECONDS`, `MAX_REACT_DELAY_SECONDS`,
     `ALLOWED_STATUS_SENDERS`, `LOG_LEVEL`
5. Deploy. Railway will build with Nixpacks using `requirements.txt`
   and start the process with `python main.py` (from `Procfile` /
   `railway.json`).
6. **Watch the deploy logs.** On first run (no existing session) the
   app will print:
   ```
   ================================================================
   WHATSAPP PAIRING CODE: ABCD-1234
   On your phone: WhatsApp > Settings > Linked Devices >
   Link a Device > 'Link with phone number instead' > enter this code
   ================================================================
   ```
   Enter that code on your phone within the app's time limit. Once
   paired, the `Paired successfully as ...` log line confirms it, and
   the session is saved to `/data/session.db3` for future restarts.
7. A minimal JSON health endpoint is exposed on the Railway-assigned
   `$PORT` at `/`, showing `connected`, `logged_in`, and running
   counters for statuses viewed/liked — useful for a quick sanity
   check without digging through logs.

## Running it

```
python main.py
```

That's it. On first run it installs its own dependencies from
`requirements.txt` and restarts itself automatically. If there's no
existing session, it'll ask you right in the terminal:

```
================================================================
No existing WhatsApp session found — pairing is required.
================================================================
Enter the WhatsApp number to pair (digits only, country code, no '+' or spaces, e.g. 15551234567):
```

Enter your number, then watch for:

```
WHATSAPP PAIRING CODE: ABCD-1234
```

Enter that code on your phone: **WhatsApp > Settings > Linked Devices >
Link a Device > "Link with phone number instead"**. Once it's accepted
you'll see:

```
✅ Bot connected successfully — now watching for statuses.
```

...and it starts viewing/liking statuses from then on. It also sends a
confirmation message to your own WhatsApp inbox ("Message Yourself"):
`ESSENCE AUTO Like connected succeful` (configurable via
`STARTUP_NOTIFICATION_MESSAGE`, or disable with `NOTIFY_ON_STARTUP=false`).

The session is saved to `SESSION_DB_PATH` — by default a stable
`data/session.db3` folder next to this project, resolved the same way
no matter what directory you launch `python main.py` from. **Restarting
the terminal and running `python main.py` again reuses that saved
session automatically: no re-pairing and no reinstalling dependencies**
(the dependency check at the top of `main.py` is a no-op once packages
are already present). You'll only see the pairing prompt again if that
session file is deleted, moved, or the device gets unlinked from your
phone.

If you'd rather not be prompted (e.g. running headlessly, or on
Railway where there's no interactive terminal), set `PHONE_NUMBER` as
an environment variable or in `.env` beforehand — the prompt is
skipped automatically whenever that's already set.

## What was and wasn't verified

Before writing this, I installed neonize `0.4.3.post0` in a real
Python 3.12 sandbox and confirmed directly against the library source:

- The exact signatures of `PairPhone`, `mark_read`, `build_reaction`,
  `send_message`, `is_logged_in`, `connect`, and `disconnect`.
- The exact protobuf field layout for incoming messages
  (`Info.MessageSource.Chat/Sender/IsFromMe`, `Info.ID`).
- That `NewClient(path)` takes the sqlite path as its first positional
  argument (the library's own README shows a different, non-existent
  `database=` kwarg for one older example — the actual installed
  source doesn't have it, so this project uses what's real).
- I fed the code above a synthetic "status@broadcast" message and
  confirmed the full pipeline — filtering, dedup, `mark_read`, and
  `build_reaction` + `send_message` — executes with correct argument
  types, failing only with a "client is nil" error, which is the
  expected result of not being connected to a real account in a
  sandbox with no network access to WhatsApp's servers.

As a final check, running `main.py` for real (with a fake phone number,
since I have no test WhatsApp account) confirmed `client.connect()`
correctly attempts a genuine WebSocket handshake to
`web.whatsapp.com` — it failed only with a `403` from the sandbox's
own outbound network allowlist (which blocks arbitrary domains
including WhatsApp's). Railway has normal outbound internet access, so
this step will proceed past that point there.

What I could **not** test end-to-end, for the obvious reason that
doing so requires a live, paired WhatsApp account: whether WhatsApp's
servers accept a reaction addressed to `status@broadcast` in exactly
this shape. This mirrors the one concrete reaction example in
neonize's own official example file, just applied to a message whose
chat happens to be the status broadcast JID instead of a regular chat.
If a status reaction gets silently rejected in practice, the fix is
almost certainly a one-line adjustment to the `chat`/`sender` JIDs
passed into `build_reaction` — worth an issue on the
[neonize GitHub Discussions](https://github.com/krypton-byte/neonize/discussions)
if you hit it, since this is a genuinely underdocumented protocol
corner.

## Known limitation: reacting to statuses can still return a server error

Viewing statuses (`mark_read`) works reliably. Reacting to them
(`build_reaction` + `send_message`, both addressed to
`status@broadcast`) can still fail with a `400`/"participant list
hash" style error from WhatsApp's servers, depending on your account.

This was investigated in depth, not guessed at:
- whatsmeow's own godoc and a real, actively maintained production
  whatsmeow-based project both confirm the correct pattern is
  `send_message(chat, ...)` where `chat` matches `build_reaction`'s
  first argument (`status@broadcast` for a status) — this is what the
  code does.
- There's a still-open whatsmeow GitHub issue (#668) with this exact
  symptom for anything sent to `status@broadcast`, describing a
  participant-list-hash mismatch at the protocol level.
- Tellingly, that same production project reads/filters
  `status@broadcast` messages extensively but has never implemented
  *sending* anything to it — a strong signal this is a genuine rough
  edge in whatsmeow itself, not something fixable purely from calling
  code.

The bot calls `get_status_privacy()` before reacting as a best-effort
attempt to keep that internal cache fresh, but this isn't guaranteed
to resolve it. If you still hit the error: Baileys (Node.js) exposes
an explicit `statusJidList` option specifically for this case and is
the one place this is confirmed to work end-to-end. The most reliable
fix at that point would be a small Baileys side-service handling just
the "react to a status" call, invoked from this Python app over HTTP
— happy to build that out if you hit this wall.

## A few things worth knowing before you run this continuously

- This uses WhatsApp's unofficial, reverse-engineered protocol, not an
  approved Business API. WhatsApp's terms don't sanction third-party
  automation on a personal account, and bot-like behavior (reacting to
  every single status) does occasionally get accounts flagged or
  banned. The randomized delay reduces but doesn't eliminate that risk.
- If you get logged out (`LoggedOutEv` in the logs), the phone unlinked
  the device — you'll need to delete the session file and re-pair.
- `ALLOWED_STATUS_SENDERS` is there if you'd rather only auto-react to
  a specific subset of contacts instead of everyone.
