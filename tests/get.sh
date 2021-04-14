#!/bin/sh

base=$(dirname "$(realpath "${0}")")

export THINCF_CA="$0"
export THINCF_CERT="$0"
export THINCF_KEY="$0"
export THINCF_URL=http://127.0.0.1:8000
export THINCF_ROOT=${base}/root

mkdir -p ${THINCF_ROOT}/var/db/thincf/client/states
mkdir -p ${THINCF_ROOT}/var/db/thincf/client/backups

curl () {
    local skipn=0
    for arg in "$@"; do
        shift
        if [ ${skipn} -eq 1 ]; then
            skipn=0
            continue
        fi
        case "${arg}" in
            --cacert|--cert|--key) skipn=1 ;;
            *) set -- "$@" "${arg}" ;;
        esac
    done
    { printf "thincf-client: client\n"; cat -; } | command curl "$@"
}

. "${base}/../client/thincf"
