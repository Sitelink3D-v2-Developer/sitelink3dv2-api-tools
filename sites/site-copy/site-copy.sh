#!/usr/bin/env bash

# The base path to the Sitelink3D v2 instance that the source site exists at. Options are:
# QA: 
#    site_source_url=https://qa-api.sitelink.topcon.com:443
# Production US data center:
#    site_source_url=https://us-api.sitelink.topcon.com:443
# Production EU data center:
#    site_source_url=https://eu-api.sitelink.topcon.com:443
site_source_url=

# The identifier of the site to copy from in the form:
# site_source_identifier=7b33e65157675b33e6861b98588b51c743165b0ce13a965f30a0d3c8d1b4ef5c
site_source_identifier=
# A JWT that authorizes access to the source site in the form:
# site_source_token=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY3QiOnsiKiI6WyIqIl19LCJzY3AiOiIqIiwic3ViIjoidXJuOlgtdG9wY29uOmxlOmIzNjY4NzI4LWJkZTAtNGY1Zi04MzIxLTg0Mjk5Y2FhZDNhNTpvd25lcjpjZTIzNWU1ZS02ZDg3LTRhODQtODBmMi0wZTU2YjEzN2ExMzIiLCJpc3MiOiIzMjg4MWQ1My0yMTE1LTQyZGMtOWFhMC1kZTQzNDgxNzFjNWQiLCJleHAiOjE2Njc2MTQ2NTd9.LOusctze4KI9cRgiNPxxceojVjSOvdJifUOJ9ubDehAVgXx7O_qpyGSQyly_Fqk0mUFgQf70vu2Sme5nWTSqLg
site_source_token=

# The base path to the Sitelink3D v2 instance that the destination site exists at. Options are as specified above for the site_source_url
site_dest_url=

# The identifier of the site to copy to in the form:
# site_dest_identifier=7b33e65157675333e6861b98588b51c743165b0ce13a965f30a0d3c8d1b4ef5c
site_dest_identifier=

# A JWT that authorizes access to the destination site in the form:
# site_dest_token=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY3QiOnsiKiI6WyIqIl19LCJzY3AiOiIqIiwic3ViIjoidXJuOlgtdG9wY29uOmxlOmIzNjY4NzI4LWJkZTAtNGY1Zi04MzIxLTg0Mjk5Y2FhZDNhNTpvd25lcjpjZTIzNWU1ZS02ZDg3LTRhODQtODBmMi0wZTU2YjEzN2ExMzIiLCJpc3MiOiIzMjg4MWQ1My0yMTE1LTQyZGMtOWFhMC1kZTQzNDgxNzFjNWQiLCJleHAiOjE2Njc2MTQ2NTd9.LOusctze4KI9cRgiNPxxceojVjSOvdJifUOJ9ubDehAVgXx7O_qpyGSQyly_Fqk0mUFgQf70vu2Sme5nWTSqLg
site_dest_token=

echo "Copying data from source site $site_source_identifier to destination site $site_dest_identifier"

python ../site-tool/site-tool.py --token $site_source_token --url $site_source_url $site_source_identifier copy $site_dest_url $site_dest_identifier $site_dest_token

echo;echo "Done."
