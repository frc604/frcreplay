# FRC Replay

> *Videos of FIRST Robotics matches, recorded automatically &amp; uploaded in
> minutes*

Live at [**@FRC_replay**](https://twitter.com/frc_replay) and
[**@FTC_replay**](https://twitter.com/ftc_replay)

## Code Outline

The `matchobserver/` subsystem handles detecting match start/stop and extracting information from
the FIRST match overlay when present. `matchobserver/__init__.py` sets up a framework for
game-specific plugins like `matchobserver/frc2017/` and `matchobserver/ftc2017.py` to hook into.

`streamconnector.py` manages the connection to an event's Twitch video stream.

`videohandler.py` takes care of uploading recorded match videos to
[Streamable](https://streamable.com/) and posting the corresponding links to
[Twitter](https://twitter.com/frc_replay).

`matchrecorder.py` brings all of these parts together and tracks the current match state.

`matchrecorder.service` contains a template
[systemd](https://www.freedesktop.org/wiki/Software/systemd/) unit file for supervising an instance
of the FRC Replay software.

`tessdata` directories contain pre-trained
[Tesseract OCR](https://github.com/tesseract-ocr/tesseract) configurations for scraping text from
the FIRST match overlay in the video stream frames.

## Deployment

Deployment-related scripts live in the `scripts/` directory.

[`docker-machine`](https://docs.docker.com/machine/) is used to provision, manage, and tear down
server infrastructure running the FRC Replay software, though Docker itself is not used. You'll
also need the [`docker-machine-vultr`](https://github.com/janeczku/docker-machine-vultr) plugin for
deploying to [Vultr](https://vultr.com).

Before deploying, you'll need to create a `credentials.json` file in the following format for
posting to Twitter:

```json
{
  "twitter": {
    "<username>": {
      "consumer_key": "<consumer key>",
      "consumer_secret": "<consumer secret>",
      "access_token_key": "<access token key>",
      "access_token_secret": "<access token secret>"
    }
  }
}
```

You'll also need to sign up for a [Vultr](https://vultr.com) account and obtain your API key from
the control panel. Then create a `scripts/credentials.sh` file in the following format:

```bash
VULTR_API_KEY='<vultr api key>'
```

Finally, you'll want to set up a `scripts/events.sh` file with a configuration line for each event
you'll be covering. A separate server will be provisioned for each of these, at $0.007/hour at the
time of writing (check the [Vultr pricing page](https://www.vultr.com/pricing/) for up-to-date
information). The configuration format is as follows:

```bash
event '<event hashtag>' '<Twitch username for livestream>' '<Twitter account username to post to>' '<game type such as FRC-2017>' "$1"
```

`scripts/provision` builds the server infrastructure for all configured events.

`scripts/teardown` destroys said infrastructure. Note this will **only** destroy servers which were
created from configuration lines still in your `events.sh`!

`scripts/deploy` updates the copy of the code on the provisioned server(s) and (re)starts the
service.

`scripts/tail` streams the log output of the FRC Replay instance(s) running on your provisioned
server(s).

All of the above operate on all configured events by default, but can also take an event hashtag parameter to operate just on that event (eg. `scripts/deploy ArchimedesSTL`).

`scripts/log <event hashtag>` fetches a snapshot of the corresponding log output and prints it out.

`scripts/status <event hashtag>` prints the status of the corresponding FRC Replay instance.

## Runtime Dependencies

The following applies to the system *running* the FRC Replay software. The deployment scripts take
care of properly preparing the servers they provision.

Python 3 is required.

The `requirements.txt` file can be used with `pip install -r` to set up the required Python
dependencies.

The software will also expect a [Tesseract](https://github.com/tesseract-ocr/tesseract) binary at
`/usr/bin/tesseract` and an [FFmpeg](https://www.ffmpeg.org/) binary at `/usr/bin/ffmpeg`.

## License

Copyright (C) 2017 Michael Smith &lt;michael@spinda.net&gt;

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU Affero General Public License as published by the Free
Software Foundation, either version 3 of the License, or (at your option) any
later version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
details.

You should have received a copy of the GNU Affero General Public License along
with this program. If not, see <http://www.gnu.org/licenses/>.
