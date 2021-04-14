#!/bin/sh

base=$(dirname "$(realpath "${0}")")

export PYTHONUSERBASE=${base}/../.pyenv
export PYTHONPATH=${base}/../server
export PIP_USER=true

export THINCF_SERVER_STATEDIR=${base}/server/states
export THINCF_SERVER_CLIENT_NAME_HEADER=thincf-client

mkdir -p ${THINCF_SERVER_STATEDIR}
${base}/../.pyenv/bin/uvicorn thincf.server:app --reload
