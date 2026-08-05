#!/bin/sh
# Step 5 of the pipeline: extract/augment features (if not already done), then run
# microWakeWord's actual training + quantized-TFLite export.
#
# CLI invocation below is copied verbatim from microWakeWord's own training notebook
# (cell 10, cross-checked line-by-line against the current model_train_eval.py and
# mixednet.py argparse definitions at the pinned commit — every flag name confirmed
# to still exist) — the task brief's abbreviated version only mentioned
# --pointwise_filters/--stride; this uses the full, actually-correct set of mixednet
# hyperparameters the notebook itself uses.
set -e

DATA_DIR="${DATA_DIR:-/data}"
cd "$DATA_DIR"

CONFIG_PATH="$DATA_DIR/training_parameters.yaml"
if [ ! -f "$CONFIG_PATH" ]; then
    echo "[train] No training_parameters.yaml in $DATA_DIR yet — copying the image's default template."
    echo "[train] Edit $CONFIG_PATH directly to change hyperparameters; re-running train.sh will pick up edits without a rebuild."
    cp /opt/wakeword/training_parameters.yaml.template "$CONFIG_PATH"
fi

START_TS=$(date +%s)

echo "[train] --- Feature extraction ---"
python3 /opt/wakeword/extract_features.py

echo "[train] --- Model training + quantized TFLite export ---"
echo "[train] TensorFlow device visibility:"
python3 -c "import tensorflow as tf; print('  GPUs:', tf.config.list_physical_devices('GPU') or 'none (CPU-only run)')"

python3 -m microwakeword.model_train_eval \
    --training_config="$CONFIG_PATH" \
    --train 1 \
    --restore_checkpoint 1 \
    --test_tf_nonstreaming 0 \
    --test_tflite_nonstreaming 0 \
    --test_tflite_nonstreaming_quantized 0 \
    --test_tflite_streaming 0 \
    --test_tflite_streaming_quantized 1 \
    --use_weights "best_weights" \
    mixednet \
    --pointwise_filters "64,64,64,64" \
    --repeat_in_block "1, 1, 1, 1" \
    --mixconv_kernel_sizes '[5], [7,11], [9,15], [23]' \
    --residual_connection "0,0,0,0" \
    --first_conv_filters 32 \
    --first_conv_kernel_size 5 \
    --stride 3

END_TS=$(date +%s)
TFLITE_OUT="$DATA_DIR/trained_models/wakeword/tflite_stream_state_internal_quant/stream_state_internal_quant.tflite"
if [ -f "$TFLITE_OUT" ]; then
    echo "[train] Done. Output: $TFLITE_OUT ($(wc -c < "$TFLITE_OUT") bytes). Elapsed: $((END_TS - START_TS))s."
else
    echo "[train] WARNING: training finished but expected output not found at $TFLITE_OUT — check the log above for errors." >&2
fi
