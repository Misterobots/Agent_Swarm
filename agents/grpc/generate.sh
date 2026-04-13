#!/usr/bin/env bash
# Generate Python gRPC stubs from openclaude.proto
# Run from the agents/grpc/ directory or provide the path.
#
# Prerequisites: pip install grpcio-tools
#
# Usage:
#   cd agents/grpc && bash generate.sh
#   OR: bash agents/grpc/generate.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Generating Python gRPC stubs from openclaude.proto..."
python -m grpc_tools.protoc \
    -I"${SCRIPT_DIR}" \
    --python_out="${SCRIPT_DIR}" \
    --grpc_python_out="${SCRIPT_DIR}" \
    "${SCRIPT_DIR}/openclaude.proto"

echo "Generated:"
echo "  ${SCRIPT_DIR}/openclaude_pb2.py"
echo "  ${SCRIPT_DIR}/openclaude_pb2_grpc.py"
