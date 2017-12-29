#!/usr/bin/env python

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

import collections
import datetime
import multiprocessing
import os
import tempfile
import time
import traceback

import matchobserver
import streamconnector
import videohandler

PREMATCH_BUFFER_CHUNKS = 2048
SPLIT_AT_TIME = 60 * 8

VIDEOS_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'videos')
RECORDING_DIR = os.path.join(VIDEOS_DIR, 'recording')
READY_DIR = os.path.join(VIDEOS_DIR, 'ready')
READY_FORMAT = os.path.join(READY_DIR, '{}---{}')

os.makedirs(RECORDING_DIR, exist_ok=True)
os.makedirs(READY_DIR, exist_ok=True)

TITLE_FORMAT = '[{}] {}'

class MatchRecorderStreamConnector(streamconnector.StreamConnector):
    def __init__(self, event_id, twitch_id, twitter_user, game_id):
        super().__init__(event_id, twitch_id)
        self._twitter_user = twitter_user
        self._game_id = game_id
        self._match_observer = matchobserver.MatchObserver(event_id, game_id)

    def on_connecting(self):
        self._match_id = None
        self._match_video = None

        self._last_timestamp = 0
        self._recording_timestamp = -1

        self._prematch_buffer = collections.deque(maxlen=PREMATCH_BUFFER_CHUNKS)

        for recording_filename in os.listdir(RECORDING_DIR):
            try:
                os.unlink(os.path.join(RECORDING_DIR, recording_filename))
            except:
                traceback.print_exc()

        for ready_filename in sorted(os.listdir(READY_DIR)):
            self._upload_in_background(os.path.join(READY_DIR, ready_filename))

    def on_connected(self):
        self._match_observer.start()

    def on_disconnected(self):
        self._match_observer.stop()
        self._handle_match_video()

        self._match_id = None
        self._match_video = None
        self._recording_timestamp = -1

    def on_data(self, data):
        self._match_observer.feed(data)

        update_recording_state = False

        new_match_id = None
        if self._match_observer.has_update():
            new_match_id = self._match_observer.get_latest()
            update_recording_state = new_match_id != self._match_id

        needs_split = self._match_id and \
                      (not update_recording_state or self._match_id == new_match_id) and \
                      self._recording_timestamp != -1 and \
                      time.time() - self._recording_timestamp >= SPLIT_AT_TIME
        if needs_split:
            update_recording_state = True
            new_match_id = self._match_id

        if update_recording_state:
            if self._match_id is not None:
                if needs_split:
                    print('******** splitting video for match {}'.format(self._match_id))
                else:
                    print('******** stopped recording video for match {}'.format(self._match_id))

                self._handle_match_video()

                self._match_id = None
                self._match_video = None
                self._recording_timestamp = -1

            if new_match_id is not None:
                self._match_id = new_match_id
                self._match_video = tempfile.NamedTemporaryFile(suffix='.mp4', dir=RECORDING_DIR,
                                                                delete=False)
                self._recording_timestamp = time.time()

                for chunk in self._prematch_buffer:
                    self._match_video.write(chunk)
                self._prematch_buffer.clear()

                print('******** started recording video for match {}'.format(self._match_id))

        if self._match_video:
            self._match_video.write(data)
        self._prematch_buffer.append(data)

    def _handle_match_video(self):
        if self._match_id is None or self._match_video is None:
            return

        self._match_video.close()

        title = TITLE_FORMAT.format(datetime.date.today().isoformat(), self._match_id)
        ready_path = READY_FORMAT.format(int(time.time()), title)
        os.rename(self._match_video.name, ready_path)

        self._upload_in_background(ready_path)

    def _upload_in_background(self, ready_path):
        multiprocessing.Process(
                target=videohandler.upload_to_streamable_and_post_to_twitter,
                args=(ready_path.split('---')[1], ready_path, self._twitter_user)
        ).start()

if __name__ == '__main__':
    MatchRecorderStreamConnector(os.environ['EVENT_ID'], os.environ['TWITCH_ID'],
                                 os.environ['TWITTER_USER'], os.environ['GAME_ID']).run()
