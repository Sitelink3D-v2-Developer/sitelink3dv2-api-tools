#!/usr/bin/env bash

site_url=https://qa-api.sitelink.topcon.com:443
site_identifier=
site_token=

echo "Downloading regions as vertex files from site $site_identifier"

python ../site-tool/site-tool.py --token $site_token --url $site_url $site_identifier regions

echo;echo "Done."