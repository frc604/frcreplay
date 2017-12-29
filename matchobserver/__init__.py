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
import multiprocessing
import io
import os
import re
import subprocess
import time
import traceback

import PIL

MATCH_DETECTOR_FPS = 1 / 3
FFMPEG_BINARY = '/usr/bin/ffmpeg'
FFMPEG_COMMAND = [
    FFMPEG_BINARY, '-i', '-', '-vf',
    'fps={}'.format(MATCH_DETECTOR_FPS),
    '-an', '-sn', '-c:v', 'rawvideo', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'
]

MATCH_ID_TEMPLATE = '#{} {}'

MATCH_END_TIMEOUT = 60

VIDEO_CHANNELS = 3

VIDEO_RESOLUTION_RE = re.compile('rgb24, ([0-9]+)x([0-9]+)[, ]')

def background_process(event_id, vision_core_class, info_stream, frame_stream, match_id_queue):
    match_id = None
    match_id_counter = collections.Counter()

    change_timestamp = -1
    end_timestamp = -1

    video_width = None
    video_height = None

    while False:
        info_line = info_stream.readline().decode('utf-8')
        if len(info_line) == 0:
            break

        print(info_line)

        match = VIDEO_RESOLUTION_RE.search(info_line)
        if match:
            video_width = int(match.group(1))
            video_height = int(match.group(2))
            break

    video_width=1920
    video_height=1080

    if video_width is None:
        raise Exception('Failed to identify video resolution')
    #info_stream.close()
    print('******** identified {}x{} resolution'.format(video_width, video_height))

    vision_core = vision_core_class(video_width, video_height)

    frame_size = video_width * video_height * VIDEO_CHANNELS
    frame_reader = io.BufferedReader(frame_stream)

    while True:
        try:
            print('reading frame data')
            data = frame_reader.read(frame_size)
            if len(data) < frame_size:
                break

            print('decoding frame data')
            frame = PIL.Image.frombuffer('RGB', (video_width, video_height), data, 'raw', 'RGB',
                                         0, 1)

            print('start processing frame')
            process_start_time = time.time()
            new_match_id, match_info = vision_core.process_frame(frame)
            print('frame_process_time = {}'.format(time.time() - process_start_time))

            if new_match_id is None:
                if match_id is not None:
                    if end_timestamp == -1:
                        end_timestamp = time.time()
                    elif time.time() - end_timestamp >= MATCH_END_TIMEOUT:
                        end_timestamp = -1
                        match_id_counter.clear()
                        match_id = None
                        match_id_queue.put(None)
            elif len(new_match_id) > 0:
                new_match_id = MATCH_ID_TEMPLATE.format(event_id, new_match_id)
                match_id_counter[new_match_id] += 1
                match_id = match_id_counter.most_common(1)[0][0]
                match_id_queue.put(match_id)

            if match_id is not None:
                print('{} {}'.format(match_id, match_info))
        except KeyboardInterrupt:
            raise
        except:
            traceback.print_exc()

class MatchObserver:
    def __init__(self, event_id, game_id):
        self._event_id = event_id
        self._frame_extractor = None

        if game_id == 'FTC-2017':
            import matchobserver.ftc2017
            self._vision_core_class = ftc2017.FTC2017VisionCore
        elif game_id == 'FRC-2017':
            import matchobserver.frc2017
            self._vision_core_class = frc2017.FRC2017VisionCore
        else:
            raise Exception('Unrecognized game id: ' + game_id)
        print('***** ready for game_id ' + game_id)

    def start(self):
        self._match_id_queue = multiprocessing.Queue()
        self._frame_extractor = subprocess.Popen(FFMPEG_COMMAND,
                                                 stdin=subprocess.PIPE,
                                                 stdout=subprocess.PIPE,
                                                 #stderr=subprocess.PIPE,
                                                 preexec_fn=os.setpgrp)

        multiprocessing.Process(
                target=background_process,
                args=(self._event_id,
                      self._vision_core_class,
                      self._frame_extractor.stderr,
                      self._frame_extractor.stdout,
                      self._match_id_queue)
        ).start()

    def stop(self):
        if self._frame_extractor is not None:
            self._frame_extractor.terminate()
            self._frame_extractor = None
        self._match_id_queue = None

    def feed(self, data):
        self._frame_extractor.stdin.write(data)

    def has_update(self):
        return not self._match_id_queue.empty()

    def get_latest(self):
        new_match_id = None
        while not self._match_id_queue.empty():
            new_match_id = self._match_id_queue.get_nowait()
        return new_match_id
