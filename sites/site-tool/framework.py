#!/usr/bin/python

""" This is a set of utility functions for the site-tool file. """

import argparse
import inspect
import logging
import os
import requests

logger = logging.getLogger(__name__)

class ApiAccess(object):
    AUTH_HEADER_KEY = "X-Topcon-Auth"
    def __init__(self, api_url, site, token, verify=True):
        self.api_url = api_url
        self.token = token
        self.site = site
        self.verify = verify

    def post(self, uri, params=None, headers=None, files=None):
        url = self.api_url + uri
        if not headers: headers = {ApiAccess.AUTH_HEADER_KEY:self.token}
        elif not ApiAccess.AUTH_HEADER_KEY in headers: headers[ApiAccess.AUTH_HEADER_KEY] = self.token
        res = requests.post(url, params=params, files=files, headers=headers, verify=self.verify)
        res.raise_for_status()
        return res

def add_default_arguments(arg_parser, epilog=None):
    arg_parser.add_argument("--log-fmt", default="%(asctime)-15s %(module)s %(levelname)s %(funcName)s %(message)s", help="format of log messages")
    arg_parser.add_argument("--log-lvl", default=logging.INFO,  help="log messages at or above this level")
    arg_parser.add_argument("--token"  , help="JWT to authorize requests")
    arg_parser.add_argument("--unverified", action="store_true", default=False, help="Do not verify https requests")
    if epilog is not None:
        arg_parser.epilog = epilog
        arg_parser.formatter_class = argparse.RawDescriptionHelpFormatter

def pretty_dict_to_list(d, indent=2, sep=2):
    l = []
    lmax = max([len(s) for s in d])
    for key in sorted([key for key in d]):
        l.append("%s%-*s%s%s" % (' ' * indent, lmax, key, ' ' * sep, d[key]))
    return l

def make_epilogue(settings, actions):
    epi = []
    epi.append("environment variables:")
    aDict = {}
    for s in settings:
        d = s.lower().replace("_", " ")
        setting, dflt = settings[s], str(settings[s])
        if type(setting) in [list,tuple]:
            dflt = setting[0]
            if len(setting) > 1: d = setting[1]
        aDict[s] = d
        if dflt and s != "LOG_FORMAT":
            aDict[s] += " (dflt:%s)" % (dflt)
    epi = epi + pretty_dict_to_list(aDict)

    if actions is not None and len(actions)>0:
        epi.append(" ")
        epi.append("supported actions:")

        def addDict(epi, actions, indent=2):
            aDict = {}
            for verb in actions:
                if type(actions[verb]) == dict:
                    epi.append("%s%s:" % (' '*indent, verb))
                    epi = addDict(epi, actions[verb], indent+2)
                else:
                    argstr = inspect.formatargspec(inspect.getargspec(actions[verb]).args)
                    aDict[verb+argstr] = inspect.getdoc(actions[verb])
            epi = epi + pretty_dict_to_list(aDict)
            return epi

        epi = addDict(epi, actions)
    return '\n'.join(epi)

def set_globals(glob, settings):
    for key,val in settings.items():
        if type(val) in [list,tuple]: val = val[0]
        glob[key] = os.getenv(key, val)
        globals()[key] = glob[key]

def print_table(data, fields):
    def s(n, x):
        if n <= len(x): return x[0:n]
        return "-" * ((n - len(x))/2) + x + "-" * ((n - len(x)+1)/2)

    def fmt_field(f):
        if f[0] == "-": return "-", f[1:]
        return "", f

    f2, fmts, lens,tags = [], {}, {}, []
    for f in fields:
        fmt, field = fmt_field(f)
        lens[field] = max([len(str(e.get(field,"n/a"))) for e in data])
        f2.append(field)
        tags.append("%%%s%ds" % (fmt, lens[field]))
    fields = f2
    tag = " ".join(tags)
    print(tag % tuple([s(lens[f],f) for f in fields]))
    for e in data: print(tag % tuple([str(e.get(f,"n/a")) for f in fields]))

def run_action(actions, verb, args):
    verb = verb.lower()
    action = actions.get(verb)
    if action is None:
        logger.warn("unexpected verb %s", verb)
        return
    argspec = inspect.getargspec(action)
    param_len = len(argspec.args)
    if param_len > len(args):
        if len(argspec.defaults or []) < param_len - len(args):
            logger.warn("action %s: no value given for arg '%s' which has no default value", verb, argspec.args[len(args)])
            return
        args = args + list(argspec.defaults[len(argspec.defaults)-len(args):])
    def trnc(s): return s if len(s)<12 else s[0:10]+".."
    logger.info("%s%s calls %s%s ..", verb, [trnc(str(a)) for a in args], action.__name__, inspect.formatargspec(argspec.args))
    action(*args)
    logger.info(".. %s%s call done", verb, [trnc(str(a)) for a in args])
