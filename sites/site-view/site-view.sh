#!/usr/bin/env bash

site_url=https://qa-api.sitelink.topcon.com:443
site_identifier=
site_token=

echo "Downloading data from site $site_identifier"

python ../site-tool/site-tool.py --token $site_token --url $site_url $site_identifier --jsonl view _head | sort > site.jsonl

echo;echo "Done."