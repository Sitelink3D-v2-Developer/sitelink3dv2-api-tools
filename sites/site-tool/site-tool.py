#!/usr/bin/python
import base64
import json
import logging
import requests
import time
import uuid
import hashlib
from framework import *
from tqdm import tqdm
from requests_toolbelt import MultipartEncoder
import math

logger = logging.getLogger(__name__)

SITELINK_MAX_FILE_PART_SIZE = 10485760

# Yield parts of data from file pointer until EOF. This avoids reading large files completely into memory.
# This function is used to chunk the data if its size exceeds the maximum part size accpeted by the 
# Sitelink3D v2 file and designfile services
def read_parts(a_file_ptr, a_part_size=SITELINK_MAX_FILE_PART_SIZE):
    while True:
        part = a_file_ptr.read(a_part_size)
        if not part:
            break
        yield part 

def upload_file_multipart(a_url, a_upload_uuid, a_file_location, a_file_name, a_media_type, a_encoding_type, a_jwt):
    file_path = a_file_location + os.path.sep + a_file_name
    part_index = 0
    part_generator = read_parts(a_file_ptr=open(file_path, "rb"), a_part_size=SITELINK_MAX_FILE_PART_SIZE)

    sha1 = hashlib.sha1()
    with open(file_path, "rb") as f:
        sha1.update(f.read())

    success = True

    for part in part_generator:
        file_size = os.stat(file_path).st_size
        part_total_count = math.ceil(file_size / SITELINK_MAX_FILE_PART_SIZE)

        print("Preparing data part index {} of size {} bytes. Total parts {} ".format(part_index, len(part), part_total_count))

        form_header = {
            "upload-uuid": str(a_upload_uuid),
            "upload-file-name": a_file_name,
            "upload-file-sha1": sha1.hexdigest(),
            "upload-file-size": str(file_size),
            "upload-part-index": str(part_index),
            "upload-total-parts": str(part_total_count),
            "upload-part-size": str(len(part)),
            "upload-file" : (a_file_name, part, "application/octet-stream")
        }

        multipartEncoder = MultipartEncoder(fields=form_header)
        headers = {
            "Content-Type": "multipart/form-data; media-type=\"%s\"; boundary=%s" % (a_media_type, multipartEncoder.boundary_value),
            "Authorization": "Bearer " + a_jwt,
            "Content-Encoding": a_encoding_type
        }
        response = requests.post(a_url, headers=headers, data=multipartEncoder)
        print_and_assert_http_reponse(a_response=response, a_print_text_on_success=True, a_optional_text="File part upload")
        if response.status_code != 200:
            success = False
            break
        part_index = part_index + 1

    return success

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
        headers = {'content-type':'application/json', "X-Topcon-Auth" : token}
        res = requests.post(url, data, headers=headers, verify=self.verify)
        print_and_assert_http_reponse(a_response=res, a_print_text_on_success=True, a_optional_text="Post object")

    def get_stats(self, token, site_identifier, domain):
        url = "%s/rdm/v1/site/%s/domain/%s/stats" % (self.api_url, site_identifier, domain)
        headers = {'content-type':'application/json', "X-Topcon-Auth" : token}
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
        headers = {'content-type':'application/json', "X-Topcon-Auth" : token}
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
        self.headers = {'content-type':'application/json', "X-Topcon-Auth" : token}

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

def post_rdm_payload(a_payload, a_rdm_accessor):
    a_payload["_at"] = int(round(time.time() * 1000))
    print("Posting payload to RDM {}".format(json.dumps(a_payload,indent=4)))
    a_rdm_accessor.post_object(a_payload) 

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

    def configure_log_projection(a_dest_url, a_verify, a_site, a_domain, a_dest_token):
        print("Projecting RDM '{}' domain log".format(a_domain))
        dest_rdm_accessor = RdmAccessor(RdmItf(api_url=a_dest_url, verify=a_verify), site=a_site, domain=a_domain, token=a_dest_token)
        
        source_rdm_log_projection_url = "{}/rdm_log/v1/site/{}/domain/{}/events".format(args.url, args.site, a_domain)
        params = {"timeout_ms": 0, "from_cursor_excl":0, "limit":400, "timeout_ms":0 }
        source_headers = {'content-type':'application/json', "X-Topcon-Auth" : args.token} 

        return dest_rdm_accessor, source_rdm_log_projection_url, params, source_headers

    def event_callback_filesystem(a_event, a_source_headers, a_dest_url, a_dest_site, a_dest_token, a_dest_rdm_accessor, a_status_dict):
        slug, decoded_event, object_type = process_log_event(a_event=a_event, a_status_dict=a_status_dict)

        if object_type.startswith("_"):
            ignore_object_type(a_slug=slug, a_object_type=object_type, a_object_id="_id={}".format(decoded_event["_id"]), a_status_dict=a_status_dict, a_additional_text="internal RDM type")

        elif object_type == "fs::file":
            # Download the file. Don't ignore archived files as they may be the origin of design file content.
            get_file_url = "{}/file/v1/sites/{}/files/{}/url".format(args.url, args.site, decoded_event["uuid"])
            res = requests.get(get_file_url, verify=not args.unverified, headers=a_source_headers)
            while res.status_code == 503:
                time.sleep(1)
                res = requests.get(get_file_url, verify=not args.unverified, headers=a_source_headers)
            print_and_assert_http_reponse(a_response=res, a_print_text_on_success=True, a_optional_text="Get file location")
            # get the content of the url
            output_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), args.site)
            print("{}: Processing file from {}".format(slug, get_file_url))
            download_file(a_source_url="{0}{1}".format(args.url, res.text), a_source_headers=a_source_headers, a_output_file_name=decoded_event["name"], a_output_dir=output_dir, a_source_site=args.site)

            # Now upload the file under the same parent (if specified) at the dest site.
            url = "{}/file/v1/sites/{}/upload".format(a_dest_url, a_dest_site)
            upload_success = upload_file_multipart(a_url=url, a_upload_uuid=decoded_event["uuid"], a_file_location=output_dir, a_file_name=decoded_event["name"], a_media_type="multipart/mixed", a_encoding_type="binary", a_jwt=a_dest_token)

            if upload_success:
                copy_object_type(a_slug=slug, a_object_type=object_type, a_object_id="uuid={}".format(decoded_event["uuid"]), a_decoded_event=decoded_event, a_rdm_accessor=a_dest_rdm_accessor, a_status_dict=a_status_dict)
            else:
                a_status_dict["errors"] += 1
                print("Upload failed.")

        elif object_type == "fs::folder":
            copy_object_type(a_slug=slug, a_object_type=object_type, a_object_id="_id={}".format(decoded_event["_id"]), a_decoded_event=decoded_event, a_rdm_accessor=a_dest_rdm_accessor, a_status_dict=a_status_dict)

    def event_callback_sitelink(a_event, a_source_headers, a_dest_url, a_dest_site, a_dest_token, a_dest_rdm_accessor, a_status_dict):

        particular_dict = {
            "Lines" : "LN3",
            "Points" : "PT3",
            "Surfaces" : "TN3",
            "Roads" : "RD3",
            "Planes" : "PL3"
        }

        media_type_dict = {
            "Lines" : "application/vnd.topcon.ln3",
            "Points" : "application/vnd.topcon.pt3",
            "Surfaces" : "application/vnd.topcon.tn3",
            "Roads" : "application/vnd.topcon.rd3",
            "Planes" : "application/vnd.topcon.pl3"
        }

        slug, decoded_event, object_type = process_log_event(a_event=a_event, a_status_dict=a_status_dict)

        if object_type.startswith("_"):
            ignored = ignore_object_type(a_slug=slug, a_object_type=object_type, a_object_id="_id={}".format(decoded_event["_id"]), a_status_dict=a_status_dict, a_additional_text="internal RDM type")

        elif object_type == "sl::list":
            ignored = ignore_object_type(a_slug=slug, a_object_type=object_type, a_object_id="_id={}".format(decoded_event["_id"]), a_status_dict=a_status_dict, a_additional_text="lists are special purpose objects")

        elif object_type == "sl::site":
            ignored = ignore_object_type(a_slug=slug, a_object_type=object_type, a_object_id="_id={}".format(decoded_event["_id"]), a_status_dict=a_status_dict, a_additional_text="the source site definition is not copied to the destination site")

        elif object_type == "sl::working_set":
            ignored = ignore_object_type(a_slug=slug, a_object_type=object_type, a_object_id="_id={}".format(decoded_event["_id"]), a_status_dict=a_status_dict, a_additional_text="working sets are obsolete")

        elif object_type == "sl::designObjectSet":

            # Design Object Sets look something like the following.
            # {
            #     "_id": "04585119-e2c2-4ed2-b336-5a30ca90c95f",
            #     "_type": "sl::designObjectSet",
            #     "name": "Default Design Set",
            #     "designObjects": [],
            #     "_rev": "d61cd5ec-54b2-4951-bfb6-3925028dacb6",
            #     "_at": 1662430394645
            # }
            
            # We have special handling that ignores Design Object Sets with a particular _id UUID. 
            # The Sitelink3D v2 website creates a default design set when a site is created. This 
            # assists with usability for web users and results in an RDM object that we don't want
            # to replicate at the destination site. Exclude it here based on the known UUID:
            if decoded_event["_id"] == "04585119-e2c2-4ed2-b336-5a30ca90c95f": # default_design_object_set
                return

            copy_object_type(a_slug=slug, a_object_type=object_type, a_object_id="_id={}".format(decoded_event["_id"]), a_decoded_event=decoded_event, a_rdm_accessor=a_dest_rdm_accessor, a_status_dict=a_status_dict)

        elif object_type == "sl::designObject" or object_type == "sl::deviceDesignObject":

            # Each design object is actually stored as a MAXML file that we must now download and upload at the destination site. We do this via the design_file service.
            get_file_url = "{}/designfile/v1/sites/{}/design_files/{}?design_type={}&particular={}".format(args.url, args.site, decoded_event["doFileUUID"], decoded_event["designType"], particular_dict[decoded_event["designType"]])
            output_name = "{}.{}".format(decoded_event["name"],particular_dict[decoded_event["designType"]])
            output_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), args.site)
            print("{}: Processing design file from {}".format(slug, get_file_url))
            download_file(a_source_url=get_file_url, a_source_headers=a_source_headers, a_output_file_name=output_name, a_output_dir=output_dir, a_source_site=args.site)

            # Now upload that MAXML to the destination site.
            upload_uuid = decoded_event["doFileUUID"]
            design_file_uuid = decoded_event["doFileUUID"]
            media_type = media_type_dict[decoded_event["designType"]]

            url = "{}/designfile/v1/sites/{}/design_files/{}/fineupload".format(a_dest_url, a_dest_site, design_file_uuid)
            upload_success = upload_file_multipart(a_url=url, a_upload_uuid=design_file_uuid, a_file_location=output_dir, a_file_name=output_name, a_media_type=media_type, a_encoding_type="identity", a_jwt=a_dest_token)
            
            if upload_success:
                # Ensure that the RDM payload contains a "createdAt" field.
                if not "createdAt" in decoded_event:
                    decoded_event["createdAt"] = decoded_event["_at"]
                copy_object_type(a_slug=slug, a_object_type=object_type, a_object_id="_id={}".format(decoded_event["_id"]), a_decoded_event=decoded_event, a_rdm_accessor=a_dest_rdm_accessor, a_status_dict=a_status_dict)
            else:
                a_status_dict["errors"] += 1
                print("Upload failed.")

        else:
            copy_object_type(a_slug=slug, a_object_type=object_type, a_object_id="_id={}".format(decoded_event["_id"]), a_decoded_event=decoded_event, a_rdm_accessor=a_dest_rdm_accessor, a_status_dict=a_status_dict)
            

    def process_rdm_domain_events(a_event_callback, a_dest_url, a_verify, a_dest_site, a_domain, a_dest_token, a_status_dict):
        dest_rdm_accessor, source_rdm_log_projection_url, params, source_headers = configure_log_projection(a_dest_url=a_dest_url, a_verify=a_verify, a_site=a_dest_site, a_domain=a_domain, a_dest_token=a_dest_token)

        more_data = True
        while more_data:
            
            response = requests.get(source_rdm_log_projection_url, verify=a_verify, headers=source_headers, params=params)
            print_and_assert_http_reponse(a_response=response, a_print_text_on_success=False, a_optional_text="Fetch event page")
            
            if response.status_code == 200:
                res_json = response.json()
                params["from_cursor_excl"] = res_json["cursor_incl"]
                for event in res_json["events"]:
                    a_event_callback(a_event=event, a_source_headers=source_headers, a_dest_url=a_dest_url, a_dest_site=a_dest_site, a_dest_token=a_dest_token, a_dest_rdm_accessor=dest_rdm_accessor, a_status_dict=a_status_dict)

            elif response.status_code == 204: # No data returned meaning the query has finalised. Treat this as distinct from an error.
                print("Query finished.")
                more_data = False
            else:
                print("An error occurred.")
                more_data = False

    def process_log_event(a_event, a_status_dict):
        a_status_dict["count"] += 1
        slug = "{}: log_id {}, seq {}".format(a_status_dict["count"], a_event["log_id"], a_event["seq"])
        decoded_event = json.loads(base64.b64decode(a_event["data_b64"]).decode('utf-8'))
        object_type = decoded_event.get("_type", "_")

        return slug, decoded_event, object_type

    def ignore_object_type(a_slug, a_object_type, a_object_id, a_status_dict, a_additional_text=""):
        log_string = "%s: Ignore %s object [%s]" % (a_slug, a_object_type, a_object_id)
        if len(a_additional_text) > 0:
            log_string += " ({})".format(a_additional_text)
        print(log_string)
        a_status_dict["ignored"] +=1

    def copy_object_type(a_slug, a_object_type, a_object_id, a_decoded_event, a_rdm_accessor, a_status_dict):
        try:
            print("%s: Copy %s object [%s]" % (a_slug, a_object_type, a_object_id))
            post_rdm_payload(a_payload=a_decoded_event, a_rdm_accessor=a_rdm_accessor)
            a_status_dict["copied"] += 1

        except requests.exceptions.HTTPError as e:
            if e.response.status_code >= 400: raise
            print("%s: Failed to copy %s object [%s]: error: %s" % (a_slug, a_object_type, a_object_id, e.response.content))
            a_status_dict["errors"] += 1

    def download_file(a_source_url, a_source_headers, a_output_file_name, a_output_dir, a_source_site):                        
        response = requests.get(a_source_url, headers=a_source_headers, stream=True)
        print_and_assert_http_reponse(a_response=response, a_print_text_on_success=False, a_optional_text="Get file")

        if not os.path.exists(a_output_dir):
            os.mkdir(a_output_dir)

        output_file_qualified_name = os.path.join(a_output_dir, a_output_file_name)
        with open(output_file_qualified_name, "wb") as handle:
            for data in tqdm(response.iter_content()):
                handle.write(data)
        return output_file_qualified_name

    def print_and_assert_http_reponse(a_response, a_print_text_on_success=True, a_optional_text=""):
        log_string = ""
        if len(a_optional_text) > 0:
            log_string += "{} ".format(a_optional_text)
        log_string += "response {}".format(a_response.status_code)
        if a_response.status_code != 200 or a_print_text_on_success:
            # we don't print success texts in some instances due to size
            log_string += ":{}".format(a_response.text)

        print(log_string)
        a_response.raise_for_status()

    def copy_action(a_dest_url, a_dest_site, a_dest_token):
        """ Use log projection to duplicate this RDM's log into a new site."""

        status_dict = {"count" : 0, "ignored" : 0, "copied" : 0, "errors" : 0, "skipped" : 0 }

        process_rdm_domain_events(a_event_callback=event_callback_filesystem, a_dest_url=a_dest_url, a_verify=not args.unverified, a_dest_site=a_dest_site, a_domain="file_system", a_dest_token=a_dest_token, a_status_dict=status_dict)
        
        process_rdm_domain_events(a_event_callback=event_callback_sitelink, a_dest_url=a_dest_url, a_verify=not args.unverified, a_dest_site=a_dest_site, a_domain="sitelink", a_dest_token=a_dest_token, a_status_dict=status_dict)
        
        print("entries: %d objects(s) copied, %d ignored, %d skipped, %d errors." % (status_dict["copied"], status_dict["ignored"], status_dict["skipped"], status_dict["errors"]))


    actions = {
        "copy"    : copy_action,
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
    logging.basicConfig(format=args.log_fmt, level=logging.INFO)
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
