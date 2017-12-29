# vim: set tw=99:

# This file is part of FRC Replay, a system for automatically recording match
# videos from live streams of FIRST games.

# Copyright (C) 2017 Michael Smith <michael@spinda.net>

# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.

# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
# details.

# You should have received a copy of the GNU Affero General Public License along
# with this program. If not, see <http://www.gnu.org/licenses/>.

import io
import time
import traceback

import requests
import streamlink

RECONNECT_OFFLINE_DELAY = 5
RECONNECT_DC_DELAY = 1

TWITCH_URL_TEMPLATE = 'https://www.twitch.tv/{}'
TWITCH_ONLINE_ENDPOINT = 'https://api.twitch.tv/kraken/streams/{}?client_id=5j0r5b7qb7kro03fvka3o8kbq262wwm&callback=badge.drawStream'

STREAM_QUALITY = 'best'

class StreamConnector:
    def __init__(self, event_id, twitch_id):
        self.event_id = event_id
        self.twitch_id = twitch_id

    def on_connecting(self):
        pass

    def on_connected(self):
        pass

    def on_disconnected(self):
        pass

    def on_data(self, data):
        pass

    def run(self):
        twitch_url = TWITCH_URL_TEMPLATE.format(self.twitch_id)
        print('******** starting loop for event {}, stream {}'.format(self.event_id, twitch_url))

        while True:
            try:
                self.on_connecting()

                r = requests.get(TWITCH_ONLINE_ENDPOINT.format(self.twitch_id))
                r.raise_for_status()
                if '"stream":null,' in r.text:
                    time.sleep(RECONNECT_OFFLINE_DELAY)
                    continue

                streams = streamlink.streams(twitch_url)
                if STREAM_QUALITY not in streams:
                    time.sleep(RECONNECT_DC_DELAY)
                    continue
                stream = streams[STREAM_QUALITY]

                with stream.open() as s:
                    self.on_connected()
                    print('******** connected to stream {} for event {}'.format(twitch_url,
                                                                                self.event_id))

                    try:
                        while True:
                            data = s.read(io.DEFAULT_BUFFER_SIZE)
                            if len(data) == 0:
                                break
                            self.on_data(data)
                    finally:
                        self.on_disconnected()
                        print('******** disconnected from stream {} for event {}'.format(twitch_url,
                                                                                self.event_id))
            except KeyboardInterrupt:
                raise
            except:
                traceback.print_exc()

            time.sleep(RECONNECT_DC_DELAY)
