#!/usr/bin/python
import base64
import json
import logging
import requests
import time
import uuid
from framework import *

logger = logging.getLogger("site-tool")
AUTH_HEADER_KEY = "X-Topcon-Auth"

class RdmItf(object):
    """ bare-bones RDM access """
    def __init__(self, api_url, verify=True):
        self.api_url = api_url
        self.verify = verify

    def safe_b64(self, x):
        if not x: return ""
        if not isinstance(x, str): 
            x = json.dumps(x)
        return base64.urlsafe_b64encode(x.encode("utf-8")).decode("utf-8").rstrip("=")

    def fetch_object(self, token, site_identifier, domain, _id):
        start = self.safe_b64([_id])
        end =  self.safe_b64([_id, None])
        result = self.fetch_view_subset(token, site_identifier, domain, "_head", start, end, 1)
        items = result.get("items",[])
        if len(items) != 1: return None
        if "value" not in items[0]: return None
        value = items[0]["value"]
        if value.get("_id") == _id:
            return value
        return None

    def post_object(self, token, site_identifier, domain, obj):
        if "_type" in obj and not "_v" in obj:
            type = self.fetch_object(token, site_identifier, domain, obj["_type"])
            if type is not None:
                obj["_v"] = type.get("_v", 0)

        url = "%s/rdm_log/v1/site/%s/domain/%s/events" % (self.api_url, site_identifier, domain)
        data = json.dumps({ "data_b64" : base64.b64encode(json.dumps(obj).encode("utf-8")).decode("utf-8") })
        headers = {'content-type':'application/json', ApiAccess.AUTH_HEADER_KEY : token}
        res = requests.post(url, data, headers=headers, verify=self.verify)
        res.raise_for_status()

    def get_stats(self, token, site_identifier, domain):
        url = "%s/rdm/v1/site/%s/domain/%s/stats" % (self.api_url, site_identifier, domain)
        headers = {'content-type':'application/json', ApiAccess.AUTH_HEADER_KEY : token}
        res = requests.get(url, verify=self.verify, headers = headers)
        while res.status_code == 503:
            time.sleep(1)
            res = requests.get(url, verify=self.verify, headers = headers)
        res.raise_for_status()
        jj = res.json()
        return jj

    def fetch_view_subset(self, token, site_identifier, domain, view, start="", end="", limit=500):
        if start and not isinstance(start, str):
            start = self.safe_b64(json.dumps(start))
        url = "%s/rdm/v1/site/%s/domain/%s/view/%s?limit=%d&start=%s&end=%s" % (self.api_url, site_identifier, domain, view, limit, start, end)
        headers = {'content-type':'application/json', ApiAccess.AUTH_HEADER_KEY : token}
        res = requests.get(url, verify=self.verify, headers = headers)
        while res.status_code == 503:
            time.sleep(1)
            res = requests.get(url, verify=self.verify, headers = headers)
        res.raise_for_status()
        jj = res.json()
        return jj

class RdmAccessor(object):
    """ RDM access for a specific site/domain """

    def __init__(self, itf, site, domain, token):
        if not token: raise ValueError("you must supply a JWT!")
        self.itf = itf
        self.site = site
        self.domain = domain or "sitelink"
        self.token = token
        self.headers = {'content-type':'application/json', AUTH_HEADER_KEY : token}

    def safe_b64(self, x): return self.itf.safe_b64(x)

    def post_objects(self,  objects):
        if isinstance(objects, list):
            return [self.post_object(event) for event in objects]
        else:
            return [self.post_object(objects)]

    def post_object(self,  obj):
        if not "_id"  in obj: obj["_id"] = str(uuid.uuid1())
        if not "_rev" in obj: obj["_rev"] = str(uuid.uuid4())
        if not "_at"  in obj: obj["_at"] = int(round(time.time() * 1000))
        self.itf.post_object(self.token, self.site, self.domain, obj)
        return self.fetch_object(obj["_id"])

    def get_stats(self):
        return self.itf.get_stats(self.token, self.site, self.domain)

    def fetch_object(self, _id):
        return self.itf.fetch_object(self.token, self.site, self.domain, _id)

    def fetch_view_all(self, view):
        result = self.fetch_view_subset(view, "")
        last_excl = result["last_excl"]
        while last_excl:
            res2 = self.fetch_view_subset(view, self.safe_b64(json.dumps(last_excl)))
            result["items"] += res2["items"]
            last_excl = res2["last_excl"]
        return result["items"]

    def fetch_view_subset(self, view, start="", end="", limit=500):
        return self.itf.fetch_view_subset(self.token, self.site, self.domain, view, start, end, limit)

    def fetch_view_entry_by_key(self, view_name, key):
        items = self.fetch_view_subset(view_name, key, 1)["items"]
        if len(items) == 0: return None
        if items[0]["key"] != key: return None
        return items[0]

if __name__ == "__main__":
    # -- >> Available verbs ----------------------------------------------------
    def stats_action():
        """ Get stats """
        print(json_dumps(rdm_accessor.get_stats()))

    def get_action(object_id):
        """ Get an object with the given ID """
        print(json_dumps(rdm_accessor.fetch_object(object_id)))

    def download_regions_action():
        """ Download all active regions and represent them each in a vertex json file """
        lines = rdm_accessor.fetch_view_all("v_sl_region_by_name")
        current_dir = os.getcwd()
        region_dir = current_dir + os.path.sep + "regions"

        os.makedirs(region_dir, exist_ok=True)

        if not os.path.exists(region_dir):
            os.mkdir(region_dir)
        for line in lines:
            try:
                output_list = []
                if line["value"]["_type"] == "sl::region":
                    for point in line["value"]["vertices"]["data"]:
                        point = {"point" : point,"action":""}
                        output_list.append(point)
                        file_name = line["value"]["name"] + ".json"
                        file_name = file_name.replace("/", "")
                    with open(region_dir + os.path.sep + file_name, "w") as file:
                            file.write(json.dumps(output_list))

            except KeyError:
                print("KeyError")
                pass
            except FileNotFoundError:
                print("FileNotFoundError")
                pass


    def view_action(view_name):
        """ Fetch the entries in the given view """
        lines = rdm_accessor.fetch_view_all(view_name)
        print(json_dumps(lines))

    def load_action(file_name):
        """ Load a file that contains a JSON object or an array of JSON objects """
        with open(file_name) as f:
            event = json.load(f)
        if isinstance(event, list):
            for e in event:
                print(rdm_accessor.post_object(e))
        else:
            print(rdm_accessor.post_object(event))

    def load_lines_action(file_name):
        """ Load a file that contains JSON objects, one per line """
        with open(file_name) as f:
            for line in f:
                print(rdm_accessor.post_object(args.site, args.domain, json.loads(line)))

    def hist_action(id):
        """ get the history for an object """
        start = rdm_accessor.itf.safe_b64([id])
        end =  rdm_accessor.itf.safe_b64([id, None])
        sset = rdm_accessor.fetch_view_subset("_hist", start, end, 10)
        history = []
        for item in sset["items"]:
            if item["id"] == id:
                history.append(item["value"])
            else:
                break
        print(json_dumps(history))

    def copyto_action(url, site, token):
        """ Copy this RDM's heads into a new site. Use a blank 'url' to copy to the same server."""
        if not url: url = RDM_URL
        rdm_to = RdmAccessor(RdmItf(api_url=url, verify=not args.unverified), site=site, domain=args.domain, token=token)
        heads = rdm_accessor.fetch_view_all("_head")
        head2 = rdm_to.fetch_view_all("_head")
        id2rev = {}
        for h2 in head2:
            v = h2["value"]
            id2rev[v["_id"]] = v["_rev"]

        count, ignored, copied, errors, skipped = 0, 0, 0, 0, 0
        logger.info("copying %d entries", len(heads))
        total, totallen = len(heads), len(str(len(heads)))
        for head in heads:
            count += 1
            slug = "%*d of %*d" % (totallen, count, totallen, total)
            v = head["value"]
            t = v.get("_type", "_")
            if v.get("_archived") == True:
                print("%s: Ignored archived %s object %s" % (slug, t, v["_id"]))
                ignored += 1
            elif t.startswith("_"):
                ignored +=1
            elif t == "sl::list":
                print("%s: Ignored list %s object %s" % (slug, t, v["_id"]))
                ignored += 1
            elif t == "sl::file":
                print("%s: Ignored file %s object %s. This tool does not copy files." % (slug, t, v["_id"]))
                ignored += 1
            elif t == "sl::task":
                print("%s: Ignored task %s object %s. Tasks cannot be copied because referenced design sets are not copied." % (slug, t, v["_id"]))
                ignored += 1
            elif t == "sl::designObjectSet":
                print("%s: Ignored design set %s object %s. Design sets cannot be copied because referenced design objects are not copied." % (slug, t, v["_id"]))
                ignored += 1
            elif t == "sl::designObject":
                print("%s: Ignored design object %s object %s. This tool does not copy design objects." % (slug, t, v["_id"]))
                ignored += 1
            elif id2rev.get(v["_id"], "") == v["_rev"]:
                print("%s: skip %s object %s" % (slug, t, v["_id"]))
                skipped += 1
            else:
                try:
                    rdm_to.post_object(v)
                    copied += 1
                    print("%s: Copied %s object %s" % (slug, t, v["_id"]))
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code >= 400: raise
                    print("%s: Failed %s object %s: error: %s" % (slug, t, v["_id"], e.response.content))
                    errors += 1

        print("%d entries: %d head(s) copied, %d ignored, %d skipped, %d errors" % (total, copied, ignored, skipped, errors))

    actions = {
        "copyto"  : copyto_action,
        "get"     : get_action,
        "stats"   : stats_action,
        "view"    : view_action,
        "load"    : load_action,
        "lines"   : load_lines_action,
        "hist"    : hist_action,
        "regions" : download_regions_action
    }

    # -- >> Argument parsing ---------------------------------------------------
    import argparse
    arg_parser = argparse.ArgumentParser(description="Simple access to RDM")
    add_default_arguments(arg_parser)
    arg_parser.add_argument("--url"    , help="RDM URL (dflt: $RDM_SCHEME://$RDM_HOST:$RDM_PORT)")
    arg_parser.add_argument("--domain" , help="RDM domain")
    arg_parser.add_argument("--jsonl", action="store_true", default=False, help="Output results in json-lines format")
    arg_parser.add_argument("site", help="Site identifier")
    arg_parser.add_argument("verb", help="Action, one of " + json.dumps(sorted([a for a in actions])))
    arg_parser.add_argument("args", nargs="*", help="Arguments for verb (see below)")
    args = arg_parser.parse_args()
    # -- << Argument parsing ---------------------------------------------------

    # -- >> Set up logging -----------------------------------------------------
    logging.basicConfig(format=args.log_fmt, level=args.log_lvl)
    logger = logging.getLogger(__name__)
    # -- << Set up logging -----------------------------------------------------

    # -- >> Set up json dumping ------------------------------------------------
    if args.jsonl:
        json_dumps = lambda x: "\n".join([json.dumps(y, sort_keys=True) for y in (x if isinstance(x, list) else [x])])
    else:
        json_dumps = lambda x: json.dumps(x, sort_keys=True, indent=4)
    # -- << Set up json dumping ------------------------------------------------

    rdm_accessor = RdmAccessor(RdmItf(api_url=args.url, verify=not args.unverified), site=args.site, domain=args.domain, token=args.token)
    verb = args.verb.lower()
    run_action(actions, verb, args.args)
""" done """
