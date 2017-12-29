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

import numpy
import os
import re
import scipy.spatial.distance
import sys
import time

import cv2
import PIL
import PIL.ImageEnhance
import PIL.ImageOps
import pytesseract

BASE_WIDTH = 1280
BASE_HEIGHT = 720

MATCH_LABEL_RECTS = [(164, 555, 625, 596)]

FMS_BASE_X = BASE_WIDTH / 2
FMS_BASE_Y = 555

TIMEOUT_RECT = (543-FMS_BASE_X, 644-FMS_BASE_Y, 43+543-FMS_BASE_X, 52+644-FMS_BASE_Y)
TIMEOUT_COLOR = (217, 174, 125)
TIMEOUT_THRESHOLD = 10

LEFT_COLOR_RECT = (623-FMS_BASE_X, 647-FMS_BASE_Y, 12+623-FMS_BASE_X, 55+647-FMS_BASE_Y)
RED_COLOR = (184, 39, 2)
BLUE_COLOR = (59, 133, 220)

LEFT_SCORE_RECT = (497-FMS_BASE_X, 643-FMS_BASE_Y, 136+497-FMS_BASE_X, 64+643-FMS_BASE_Y)
RIGHT_SCORE_RECT = (647-FMS_BASE_X, 643-FMS_BASE_Y, 136+647-FMS_BASE_X, 64+643-FMS_BASE_Y)

LEFT_HANGS_RECT = (98-FMS_BASE_X, 673-FMS_BASE_Y, 23+98-FMS_BASE_X, 26+673-FMS_BASE_Y)
LEFT_ROTORS_RECT = (210-FMS_BASE_X, 674-FMS_BASE_Y, 20+210-FMS_BASE_X, 26+674-FMS_BASE_Y)
LEFT_KPA_RECT = (317-FMS_BASE_X, 674-FMS_BASE_Y, 47+317-FMS_BASE_X, 27+674-FMS_BASE_Y)

RIGHT_HANGS_RECT = (1160-FMS_BASE_X, 673-FMS_BASE_Y, 19+1160-FMS_BASE_X, 26+673-FMS_BASE_Y)
RIGHT_ROTORS_RECT = (1049-FMS_BASE_X, 672-FMS_BASE_Y, 21+1049-FMS_BASE_X, 27+672-FMS_BASE_Y)
RIGHT_KPA_RECT = (917-FMS_BASE_X, 674-FMS_BASE_Y, 47+917-FMS_BASE_X, 27+674-FMS_BASE_Y)

MATCH_TIME_RECT = (614-FMS_BASE_X, 606-FMS_BASE_Y, 52+614-FMS_BASE_X, 27+606-FMS_BASE_Y)
MATCH_TIME_CONTRAST = 127
MATCH_TIME_THRESHOLD = 72

MODE_DISTINGUISH_RECT = (580-FMS_BASE_X, 604-FMS_BASE_Y, 21+580-FMS_BASE_X, 31+604-FMS_BASE_Y)

FIRST_PORTION_COLOR = (222, 188, 146)
FIRST_PORTION_THRESHOLD = 10

MATCH_ENDED_COLOR = (236, 54, 11)
MATCH_ENDED_THRESHOLD = 100

AUTON_TIME = 15
TELEOP_TIME = 135

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

NUMBER_TESSERACT_CONFIG = '-psm 6 digits'
MATCH_LABEL_TESSERACT_CONFIG = \
    '-psm 7 --tessdata-dir {}/matchlabel_tessdata matchlabel'.format(SCRIPT_DIR)

FIRST_LOGO_SCAN_RATIO = 1 / 4
FIRST_LOGO_TEMPLATE_PATH = '{}/first-logo.bmp'.format(SCRIPT_DIR)
FIRST_LOGO_FLANN_PARAMS = ({'algorithm': 0, 'trees': 5}, {'checks': 50})
FIRST_LOGO_MATCH_RATIO = 0.7
FIRST_LOGO_MIN_MATCH_COUNT = 10

MATCH_LABEL_LEFT_PADDING = 15
MATCH_LABEL_RIGHT_PADDING = 15

NUMBER_PATTERN = '0-9ZSO'
def np(r):
    return r.replace('@', NUMBER_PATTERN)

MATCH_ID_FORMATS = [
    (re.compile(np(r'^Qualif[^@]+([@\s]+)of')), '#Qualification Match {}'),

    (re.compile(np(r'^Quart[^T]+Tieb[^@]+([@\s]+)$')), '#Quarterfinal Tiebreaker {}'),
    (re.compile(np(r'^Quart[^@]+([@\s]+)of')), '#Quarterfinal Match {}'),
    (re.compile(np(r'^Quart[^@]+([@\s]+)$')), '#Quarterfinal Match {}'),

    (re.compile(np(r'^Semi[^T]+Tieb[^@]+([@\s]+)')), '#Semifinal Tiebreaker {}'),
    (re.compile(np(r'^Semi[^@]+([@\s]+)of')), '#Semifinal Match {}'),
    (re.compile(np(r'^Semi[^@]+([@\s]+)$')), '#Semifinal Match {}'),

    (re.compile(np(r'^Fin[^T]+Tieb[^@]+([@\s]+)')), '#Final Tiebreaker {}'),
    (re.compile(np(r'^Fin[^@]+([@\s]+)of')), '#Final Match {}'),
    (re.compile(np(r'^Fin[^@]+([@\s]+)$')), '#Final Match {}'),

    (re.compile(np(r'^Practice[^@]+([@\s]+)of')), '#Practice Match {}'),

    (re.compile(np(r'^Einst[^F]+Fin[^T]+Tieb[^@]+([@\s]+)')), '#Final Tiebreaker {}'),
    (re.compile(np(r'^Einst[^F]+Fin[^@]+([@\s]+)of')), '#Final Match {}'),
    (re.compile(np(r'^Einst[^F]+Fin[^@]+([@\s]+)$')), '#Final Match {}'),

    (re.compile(np(r'^Einst[^T]+Tieb[^@]+([@\s]+)')), '#Playoff Tiebreaker {}'),
    (re.compile(np(r'^Einst[^@]+([@\s]+)of')), '#Playoff Match {}'),
    (re.compile(np(r'^Einst[^@]+([@\s]+)$')), '#Playoff Match {}')
]

WHITESPACE_RE = re.compile(r'\s+')
NOT_DIGIT_RE = re.compile(r'[^0-9]')

def fix_digits(text):
    return WHITESPACE_RE.sub('', text).replace('Z', '2').replace('S', '5').replace('O', '0')

def interpret_as_number(text):
    text = NOT_DIGIT_RE.sub('', fix_digits(text))
    if len(text) == 0:
        return None
    return int(text)

def read_number(img):
    return interpret_as_number(pytesseract.image_to_string(img, config=NUMBER_TESSERACT_CONFIG))

def read_match_id(label):
    #return 'Test Match'

    text = pytesseract.image_to_string(label)
    print(text)

    for regex, fmt in MATCH_ID_FORMATS:
        match = regex.match(text.strip())
        if match:
            match_number = fix_digits(match.group(1))
            if len(match_number) == 0:
                return ''
            else:
                return fmt.format(match_number)
    return None

def mean_color(img):
    return cv2.mean(numpy.array(img))[:3]

def color_dist(color1, color2):
    return scipy.spatial.distance.euclidean(color1, color2)

class FRC2017VisionCore:
    def __init__(self, video_width, video_height, advanced_scraping=False):
        self._advanced_scraping = advanced_scraping

        self._x_scale = video_width / BASE_WIDTH
        self._y_scale = video_height / BASE_HEIGHT
        self._scaled_label_rects = \
            [(x1 * self._x_scale, y1 * self._y_scale, x2 * self._x_scale, y2 * self._y_scale)
                for x1, y1, x2, y2 in MATCH_LABEL_RECTS]

        self._half_video_width = video_width / 2
        self._label_x2 = self._half_video_width - MATCH_LABEL_RIGHT_PADDING

        template = cv2.cvtColor(cv2.imread(FIRST_LOGO_TEMPLATE_PATH), cv2.COLOR_BGR2RGB)
        self._template_height, self._template_width = template.shape[:2]
        self._feature_detector = cv2.xfeatures2d.SURF_create()
        self._flann_matcher = cv2.FlannBasedMatcher(*FIRST_LOGO_FLANN_PARAMS)
        self._template_keypoints, self._template_descriptors = \
            self._feature_detector.detectAndCompute(template, None)

    def process_frame(self, frame):
        candidate_label_rects = self._scaled_label_rects

        found_rect = self._find_label_rect(frame)
        print('found_rect = {}'.format(found_rect))
        if found_rect is not None:
            candidate_label_rects = [found_rect] + candidate_label_rects

        candidate_match_ids = \
            ((read_match_id(frame.crop(rect)), rect) for rect in candidate_label_rects)

        match_id = None
        label_rect = None
        for candidate_match_id, candidate_label_rect in candidate_match_ids:
            match_id = candidate_match_id
            label_rect = candidate_label_rect
            if match_id is not None and len(match_id) > 0:
                break

        if match_id is not None:
            timeout_dist = color_dist(mean_color(self._crop_rel(frame, label_rect, TIMEOUT_RECT)),
                                      TIMEOUT_COLOR)
            if timeout_dist < TIMEOUT_THRESHOLD:
                print('timeout detected')
                match_id = None

        match_info = {}
        if self._advanced_scraping and match_id is not None:
            left_color_img = self._crop_rel(frame, label_rect, LEFT_COLOR_RECT)
            left_mean_color = mean_color(left_color_img)
            left_red_dist = color_dist(left_mean_color, RED_COLOR)
            left_blue_dist = color_dist(left_mean_color, BLUE_COLOR)

            left_team = 'red' if left_red_dist < left_blue_dist else 'blue'
            right_team = 'blue' if left_team == 'red' else 'red'

            left_score_img = \
                PIL.ImageOps.invert(self._crop_rel(frame, label_rect, LEFT_SCORE_RECT).convert('L'))
            right_score_img = \
                PIL.ImageOps.invert(self._crop_rel(frame, label_rect, RIGHT_SCORE_RECT).convert('L'))

            match_info['{}_score'.format(left_team)] = read_number(left_score_img)
            match_info['{}_score'.format(right_team)] = read_number(right_score_img)

            match_info['{}_hangs'.format(left_team)] = \
                read_number(self._crop_rel(frame, label_rect, LEFT_HANGS_RECT))
            match_info['{}_rotors'.format(left_team)] = \
                read_number(self._crop_rel(frame, label_rect, LEFT_ROTORS_RECT))
            match_info['{}_kpa'.format(left_team)] = \
                read_number(self._crop_rel(frame, label_rect, LEFT_KPA_RECT))

            match_info['{}_hangs'.format(right_team)] = \
                read_number(self._crop_rel(frame, label_rect, RIGHT_HANGS_RECT))
            match_info['{}_rotors'.format(right_team)] = \
                read_number(self._crop_rel(frame, label_rect, RIGHT_ROTORS_RECT))
            match_info['{}_kpa'.format(right_team)] = \
                read_number(self._crop_rel(frame, label_rect, RIGHT_KPA_RECT))

            mode_distinguish_color = \
                mean_color(self._crop_rel(frame, label_rect, MODE_DISTINGUISH_RECT))

            first_portion_dist = color_dist(mode_distinguish_color, FIRST_PORTION_COLOR)
            first_portion = first_portion_dist < FIRST_PORTION_THRESHOLD

            match_ended_dist = color_dist(mode_distinguish_color, MATCH_ENDED_COLOR)
            match_ended = match_ended_dist < MATCH_ENDED_THRESHOLD

            if match_ended:
                match_info['match_period'] = 'ended'
                match_info['match_time'] = 0
            else:
                match_time_img = self._crop_rel(frame, label_rect, MATCH_TIME_RECT)
                #match_time_img.save('a.png')

                match_time_enhanced = \
                    PIL.ImageEnhance.Contrast(match_time_img).enhance(MATCH_TIME_CONTRAST)
                #match_time_enhanced.save('b.png')

                match_time_thresholded = \
                    match_time_enhanced \
                        .convert('L') \
                        .point(lambda x: 0 if x < MATCH_TIME_THRESHOLD else 255, '1')
                #match_time_thresholded.save('c.png')

                match_period = 'teleop'
                match_time = read_number(match_time_thresholded)
                if match_time is None:
                    match_time = read_number(match_time_enhanced)
                if match_time is None:
                    match_time = read_number(match_time_img)

                if match_time == 0:
                    match_info['match_period'] = None
                    match_info['match_time'] = None
                else:
                    if match_time is not None and first_portion and match_time <= AUTON_TIME:
                        match_period = 'auton'
                        match_time += TELEOP_TIME
                    match_info['match_period'] = match_period
                    match_info['match_time'] = match_time

        return (match_id, match_info)

    def _crop_rel(self, frame, origin_rect, rel_rect):
        ox1, oy1, ox2, oy2 = origin_rect
        rx1, ry1, rx2, ry2 = rel_rect

        x1 = rx1 * self._x_scale + self._half_video_width
        y1 = ry1 * self._y_scale + oy1
        x2 = rx2 * self._x_scale + self._half_video_width
        y2 = ry2 * self._y_scale + oy1

        return frame.crop((x1, y1, x2, y2))

    def _find_label_rect(self, frame):
        frame_crop = (0, 0, frame.width * FIRST_LOGO_SCAN_RATIO, frame.height)
        frame_array = numpy.array(frame.crop(frame_crop))
        keypoints, descriptors = self._feature_detector.detectAndCompute(frame_array, None)

        if descriptors is None:
            print('no descriptors')
            return None

        matches = self._flann_matcher.knnMatch(self._template_descriptors, descriptors, k=2)

        # store all the good matches as per Lowe's ratio test.
        good_matches = []
        for m, n in matches:
            if m.distance < FIRST_LOGO_MATCH_RATIO * n.distance:
                good_matches.append(m)

        if len(good_matches) > FIRST_LOGO_MIN_MATCH_COUNT:
            src_pts = numpy.float32([self._template_keypoints[m.queryIdx].pt for m in good_matches]).reshape(-1,1,2)
            dst_pts = numpy.float32([keypoints[m.trainIdx].pt for m in good_matches]).reshape(-1,1,2)

            t = cv2.estimateRigidTransform(src_pts, dst_pts, False)
            if t is not None:
                scale = t[0, 0]
                x1 = t[0, 2]
                y1 = t[1, 2]
                x2 = x1 + self._template_width * scale
                y2 = y1 + self._template_height * scale
                return (x2 + MATCH_LABEL_LEFT_PADDING, y1, self._label_x2, y2)

        return None

if __name__ == '__main__':
    vision_core = FRC2017VisionCore(BASE_WIDTH, BASE_HEIGHT)

    frames_dir = os.path.join(SCRIPT_DIR, '../../samples/frc2017')
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
