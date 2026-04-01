#!/bin/bash
# Compatibility wrapper.
# Run: ./framework.sh start

DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$DIR/framework.sh" start
