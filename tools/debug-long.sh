#!/bin/bash
source /opt/parakeet/scripts/env.sh
W=/tmp/long16k.wav
[ -f $W ] || ffmpeg -nostdin -loglevel error -y -i /opt/parakeet/samples/long-12min.mp3 -ac 1 -ar 16000 -c:a pcm_s16le $W
W2=/tmp/long29.wav
[ -f $W2 ] || ffmpeg -nostdin -loglevel error -y -i $W -i $W -filter_complex "[0:a][1:a]concat=n=2:v=0:a=1" -ac 1 -ar 16000 -c:a pcm_s16le $W2
W8=/tmp/long8.wav
[ -f $W8 ] || ffmpeg -nostdin -loglevel error -y -i $W -t 480 -c:a pcm_s16le $W8
W10=/tmp/long10.wav
[ -f $W10 ] || ffmpeg -nostdin -loglevel error -y -i $W -t 600 -c:a pcm_s16le $W10
W4=/tmp/long4.wav
[ -f $W4 ] || ffmpeg -nostdin -loglevel error -y -i $W -t 240 -c:a pcm_s16le $W4
W5=/tmp/long5.wav
[ -f $W5 ] || ffmpeg -nostdin -loglevel error -y -i $W -t 300 -c:a pcm_s16le $W5
for mode in "$@"; do
  f=$W; [[ $mode == *long29* ]] && f=$W2; [[ $mode == *m8* ]] && f=$W8; [[ $mode == *m10* ]] && f=$W10; [[ $mode == *m4* ]] && f=$W4; [[ $mode == *m5* ]] && f=$W5
  /opt/parakeet/venv/bin/python /mnt/r/repos/EagleEar/tools/debug-long.py "$mode" $f 2>&1 | grep -E " OK | FAIL "
done
