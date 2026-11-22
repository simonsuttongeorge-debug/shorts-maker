#!/usr/bin/env bash
# One-time setup per session: Python deps + segmentation model.
set -e
cd "$(dirname "$0")"
pip install --break-system-packages -q faster-whisper mediapipe opencv-python-headless pillow numpy
mkdir -p models
[ -f models/selfie_multiclass.tflite ] || curl -sSfLo models/selfie_multiclass.tflite \
  https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/latest/selfie_multiclass_256x256.tflite
echo "shorts-maker ready"
