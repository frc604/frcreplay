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

import json
import os
import traceback

import requests
import requests_toolbelt.multipart.encoder
import retrying
import twitter

VIDEOS_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'videos')

RETRY_DELAY = 60000

STREAMABLE_UPLOAD_ENDPOINT = 'https://api.streamable.com/upload'
STREAMABLE_LINK_FORMAT = 'https://streamable.com/{}'

with open('credentials.json', 'r', encoding='utf-8') as credentials_file:
    CREDENTIALS = json.load(credentials_file)

TWEET_FORMAT = '{} {}'
STREAMABLE_TITLE_FORMAT = '{} (twitter.com/{})'

@retrying.retry(wait_fixed=RETRY_DELAY)
def upload_to_streamable(title, path):
    try:
        print('******** uploading video for {} to streamable'.format(title))
        traceback.print_stack()

        encoder = requests_toolbelt.multipart.encoder.MultipartEncoder(
                fields={'title':title, 'files[]': ('video.mp4', open(path, 'rb'), 'video/mp4')})
        r = requests.post(STREAMABLE_UPLOAD_ENDPOINT,
                          data=encoder, headers={'Content-Type': encoder.content_type})
        print('******** streamable response for {}: {}'.format(title, r.text))
        r.raise_for_status()

        data = json.loads(r.text)
        link = STREAMABLE_LINK_FORMAT.format(data['shortcode'])
        print('******** streamable link for {}: {}'.format(title, link))
        return link
    except:
        traceback.print_exc()
        raise

@retrying.retry(wait_fixed=RETRY_DELAY)
def post_video_to_twitter(title, link, twitter_user):
    try:
        tweet = TWEET_FORMAT.format(title, link)
        status = twitter.Api(**CREDENTIALS['twitter'][twitter_user]).PostUpdate(tweet)
        print('******** posted tweet: {}'.format(status.text))
    except:
        traceback.print_exc()
        raise

def upload_to_streamable_and_post_to_twitter(title, path, twitter_user):
    link = upload_to_streamable(STREAMABLE_TITLE_FORMAT.format(title, twitter_user), path)
    post_video_to_twitter(title, link, twitter_user)
    try:
        os.unlink(path)
    except:
        traceback.print_exc()

if __name__ == '__main__':
    upload_to_streamable('Hello World', 'test.mp4')
