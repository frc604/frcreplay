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

import os
import re
import sys
import time

import PIL
import pytesseract

BASE_WIDTH = 1280
BASE_HEIGHT = 720

MATCH_LABEL_RECTS = [(351, 577, 351+247, 577+108)]

MATCH_LABEL_TESSERACT_CONFIG = '-psm 7'

NUMBER_PATTERN = '0-9ZSO'
def np(r):
    return r.replace('@', NUMBER_PATTERN)

match_id_formats = [
    (re.compile(np(r'^[Q|0]\s*-\s*([@\s]+)$')), '#Qualifier Match {}'),
    (re.compile(np(r'^[Q|0]F\s*-\s*([@\s]+\s*-\s*[@\s]+)$')), '#Quarterfinal Match {}'),
    (re.compile(np(r'^[S|5]F\s*-\s*([@\s]+\s*-\s*[@\s]+)$')), '#Semifinal Match {}'),
    (re.compile(np(r'^F\s*-\s*([@\s]+\s*-\s*[@\s]+)$')), '#Final Match {}'),
]

WHITESPACE_RE = re.compile(r'\s+')

def fix_digits(text):
    return WHITESPACE_RE.sub('', text).replace('Z', '2').replace('S', '5').replace('O', '0')

def read_match_id(label):
    #return 'Test Match'

    text = pytesseract.image_to_string(label, config=MATCH_LABEL_TESSERACT_CONFIG)
    print(text)

    for regex, fmt in match_id_formats:
        match = regex.match(text.strip().replace('—', '-'))
        if match:
            match_number = fix_digits(match.group(1))
            if len(match_number) == 0:
                return ''
            else:
                return fmt.format(match_number)
    return None

class FTC2017VisionCore:
    def __init__(self, video_width, video_height):
        x_scale = video_width / BASE_WIDTH
        y_scale = video_height / BASE_HEIGHT
        self._scaled_label_rects = \
            [(x1 * x_scale, y1 * y_scale, x2 * x_scale, y2 * y_scale)
                for x1, y1, x2, y2 in MATCH_LABEL_RECTS]

    def process_frame(self, frame):
        candidate_match_ids = \
            (read_match_id(frame.crop(rect)) for rect in self._scaled_label_rects)

        match_id = None
        for candidate_match_id in candidate_match_ids:
            match_id = candidate_match_id
            if match_id is not None and len(match_id) > 0:
                break

        return (match_id, {})


if __name__ == '__main__':
    vision_core = FTC2017VisionCore(BASE_WIDTH, BASE_HEIGHT)

    frames_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), '../samples/ftc2017')
    frames_files = []
    if len(sys.argv) > 1:
        frames_files = sys.argv[1:]
    else:
        frames_files = sorted(os.listdir(frames_dir))

    for frame_file in frames_files:
        frame_path = frame_file
        if not os.path.isfile(frame_path):
            frame_path = os.path.join(frames_dir, frame_file)

        frame = PIL.Image.open(frame_path)
        start_time = time.time()
        match_id, match_info = vision_core.process_frame(frame)
        print('({}) {} = {}: {}'.format(time.time() - start_time, frame_file, match_id, match_info))
