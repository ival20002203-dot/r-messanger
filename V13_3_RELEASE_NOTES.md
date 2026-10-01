# Artel Link 13.3.0 — Presentation build

## What changed

### Artel Link notifications
Desktop notifications are now rendered by the Artel Link Electron process itself as a branded popup. The popup contains the Artel Link icon, sender/avatar, sender name and preview according to the user's notification privacy settings. It is independent of Windows Action Center notifications.

### Unread counters
Every chat has an exact unread badge. Realtime events increment it immediately and a server resync corrects counters after sleep, reconnect or background operation. The **Непрочитанные** tab also shows the total unread count.

### Calls
Call signaling moved to the global `/ws/app/` connection, so the callee does not need to have the same conversation open. Incoming calls can be received from the home screen or settings; accepting navigates to the direct chat and continues the same pending call. Audio/video calls include busy/reject/end/timeout states, ICE buffering, microphone/camera toggles and connection-state handling.

The default Docker Compose now starts a coturn service. If `RTC_ICE_SERVERS_JSON=[]`, Django automatically builds TURN settings from `TURN_HOST`, `TURN_USERNAME` and `TURN_PASSWORD`.

For the current test server the default host is `10.10.10.130`. Change `TURN_PASSWORD` before production exposure.

## Presentation test
1. Open Artel Link on two Windows PCs using two different users.
2. Minimize the receiver to tray, send a message and confirm the branded Artel Link popup appears.
3. Send multiple messages and verify the unread badge increments immediately.
4. Open the chat: the badge should clear after read/resync.
5. From one PC start an audio call while the other user is on the home/settings screen.
6. Accept the incoming call and confirm two-way audio.
7. Repeat with video and test microphone/camera toggles.
8. Check `docker compose ps` and confirm `coturn` is running.

## Production note
For production, change at least:

```env
TURN_HOST=<stable DNS/IP>
TURN_USERNAME=artellink
TURN_PASSWORD=<strong random password>
```

If clients are split across VLANs, make sure UDP/TCP 3478 and the relay UDP range 49160-49200 reach the Artel Link server.
