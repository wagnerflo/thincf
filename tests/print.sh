#!/bin/sh
THINCF_PRINT=1 exec $(dirname "$(realpath "${0}")")/get.sh "$@"
