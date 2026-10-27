#!/bin/sh
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo=$(CDPATH= cd -- "$here/../../../../.." && pwd)
exec bash "$repo/build_fpk1/run.sh" --glhost "$here/glhost-with-gear" "$@"
