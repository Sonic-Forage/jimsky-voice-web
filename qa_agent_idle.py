"""Join the room as a plain silent participant and confirm the AGENT hangs itself up.

This is the server-side half of the failsafe: the client never disconnects and never speaks, so
only the agent's watchdog can end the session. Run while watching the worker log.
"""
import asyncio
import json
import os
import sys
import time

from livekit import rtc
from livekit import api

VOICE = "/home/ubuntu/apps/voice"
URL = "wss://vex.15-204-82-198.nip.io"
ROOM = "vex-voice"
LINGER = float(sys.argv[1]) if len(sys.argv) > 1 else 75.0


def creds():
    import yaml
    cfg = yaml.safe_load(open(f"{VOICE}/livekit.yaml"))
    key = list(cfg["keys"])[0]
    return key, cfg["keys"][key]


async def main() -> int:
    key, secret = creds()
    token = (
        api.AccessToken(key, secret)
        .with_identity("silent-probe")
        .with_name("silent probe")
        .with_grants(api.VideoGrants(room_join=True, room=ROOM))
        .with_room_config(api.RoomConfiguration(
            agents=[api.RoomAgentDispatch(agent_name="vex")]))
        .to_jwt()
    )

    room = rtc.Room()
    events = []
    room.on("participant_connected", lambda p: events.append(f"connected:{p.identity}"))
    room.on("participant_disconnected", lambda p: events.append(f"left:{p.identity}"))
    room.on("disconnected", lambda *a: events.append("room-disconnected"))

    await room.connect(URL, token)
    print(f"  joined {ROOM} as silent-probe; deliberately saying nothing for {int(LINGER)}s")

    start = time.time()
    agent_saw = None
    while time.time() - start < LINGER:
        await asyncio.sleep(2)
        remotes = [p.identity for p in room.remote_participants.values()]
        if remotes and agent_saw is None and any(r.startswith("agent") for r in remotes):
            agent_saw = time.time() - start
            print(f"  [t+{int(agent_saw)}s] agent present: {remotes}")
        if not any(r.startswith("agent") for r in remotes) and agent_saw is not None:
            print(f"  [t+{int(time.time()-start)}s] AGENT LEFT after ~{int(time.time()-start)}s of silence")
            print("  events:", events)
            await room.disconnect()
            return 0

    print(f"  [t+{int(LINGER)}s] agent still present after {int(LINGER)}s of silence - watchdog did NOT fire")
    print("  events:", events)
    await room.disconnect()
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
