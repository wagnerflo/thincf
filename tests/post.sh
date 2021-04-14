#!/bin/sh

tar -C "$(dirname "$(realpath "${0}")")/state" -cf - . | \
    curl -X POST -H "thincf-client: client" \
         --data-binary @- \
         http://127.0.0.1:8000/
