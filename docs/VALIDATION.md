# Validation and limitations

Tested on a physical Philips C408X-class Roku TV with Roku OS 15.3.4, Linux Docker bridge, an existing Syncplay server and Windows SMB. This is not Roku Store certification.

Physically checked: SMB/ranges, direct MKV/HEVC 4K, H.264/AAC prepared MP4, bidirectional pause/seek, remote controls, timed information bar, settings after repeated relaunch, browser pairing, overlapping Unicode subtitles, ASS text/burn-in, Windows CRLF normalization, Gotham and Google Fonts CSS import, live rounded backgrounds/colors/spacing/position and fonts after container recreation.

Automated tests cover protocol behavior, FTP/ranges, authentication, pairing, persistence, FFmpeg, Unicode/font rendering and cache cleanup. Fixtures use no private media or credentials. Run README commands for current results. Hardware checks are historical observations; CI does not control a TV.

Limits: one Roku per bridge; seek-based sync correction; generic ZIP requires initial connection; text mode omits ASS animation; adaptation completes before playback; installed fonts mean bridge-host fonts. Styling adapts Noir parameters, not a full browser CSS engine. Codec support depends on the Roku model.
