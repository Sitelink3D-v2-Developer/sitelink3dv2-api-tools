#!/usr/bin/env bash

site_source_url=https://qa-api.sitelink.topcon.com:443
site_source_identifier= 
site_source_token=

site_dest_url=https://qa-api.sitelink.topcon.com:443
site_dest_identifier=
site_dest_token=

echo "Copying data from source site $site_source_identifier to destination site $site_dest_identifier"

python ../site-tool/site-tool.py --token $site_source_token --url $site_source_url $site_source_identifier copyto $site_dest_url $site_dest_identifier $site_dest_token

echo;echo "Done."
