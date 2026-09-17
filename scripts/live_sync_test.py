#!/usr/bin/env python3
"""Opt-in integration test against a configured Syncplay server and real Roku.
This moves playback, ends paused, and does not send chat messages.
"""
import asyncio
import json
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from bridge.config import Store
from bridge.syncplay import Syncplay

async def main():
    store = Store()
    with tempfile.TemporaryDirectory() as directory:
        peer_store = Store(Path(directory))
        peer_store.config.server = store.config.server.model_copy(update={'username': 'Roku-validation'})
        peer = Syncplay(peer_store)
        await peer.start()
        async def update_peer():
            while True:
                target = peer.target()
                peer.telemetry(target['position'], target['paused'], True)
                await asyncio.sleep(.1)
        ticker = asyncio.create_task(update_peer())
        try:
            for _ in range(100):
                if peer.connected: break
                await asyncio.sleep(.1)
            assert peer.connected, peer.error
            async with httpx.AsyncClient(headers={'X-Access-Token': store.config.token}, timeout=10) as client:
                async def check(label, position, paused):
                    await asyncio.sleep(6)
                    state = (await client.get(store.config.public_url+'/api/state')).json()['sync']
                    xml = ET.fromstring((await client.get('http://'+sys.argv[1]+':8060/query/media-player')).text)
                    actual = float(xml.findtext('position').split()[0]) / 1000
                    expected = 'pause' if paused else 'play'
                    assert xml.attrib['state'] == expected, (label, xml.attrib)
                    assert abs(actual-position) < 9, (label, actual, position)
                    assert state['target']['paused'] == paused, (label, state['target'])
                    result = {'test': label, 'roku_seconds': actual, 'server_seconds': state['target']['position'], 'state': expected}
                    print(json.dumps(result), flush=True)
                await peer.action(200, True, True)
                await check('peer seek + pause -> Roku', 200, True)
                await peer.action(200, False)
                await check('peer play -> Roku', 206, False)
                await client.post('http://'+sys.argv[1]+':8060/keypress/Play')
                await asyncio.sleep(6)
                assert peer.target()['paused'] is True
                print(json.dumps({'test':'Roku pause -> peer', 'paused':peer.target()['paused']}), flush=True)
                await client.post('http://'+sys.argv[1]+':8060/keypress/Right')
                await asyncio.sleep(6)
                xml = ET.fromstring((await client.get('http://'+sys.argv[1]+':8060/query/media-player')).text)
                actual = float(xml.findtext('position').split()[0])/1000
                assert abs(peer.target()['position']-actual)<4
                assert actual > 210
                print(json.dumps({'test':'Roku seek -> peer','roku_seconds':actual,'peer_seconds':peer.target()['position']}),flush=True)
        finally:
            ticker.cancel()
            await peer.stop()

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Uso: live_sync_test.py IP_ROKU')
    asyncio.run(main())
