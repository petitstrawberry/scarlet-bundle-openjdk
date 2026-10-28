#!/bin/sh
set -eu
bundle_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$bundle_dir/../../producer/bundle.py" --jdk 25 --destination "${1:?image stage is required}"
