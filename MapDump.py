import os
import shutil
import time
import pickle
import requests
import json
import geopandas

from esridump.dumper import EsriDumper

#requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += 'HIGH:!DH:!aNULL'
#There is a lot of problems with SSL and the severs, we want to scrap them anyway
import urllib3

requests.packages.urllib3.disable_warnings()
#requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += ':HIGH:!DH:!aNULL'
#try:
#    requests.packages.urllib3.contrib.pyopenssl.util.ssl_.DEFAULT_CIPHERS += ':HIGH:!DH:!aNULL'
#except AttributeError:
#    # no pyopenssl support used / needed / available
#    pass

#Due to some upgrades on urllib2 now SSL1 and SSL2 are disabled, so we can't fix with above solution
import urllib.parse 
from urllib3.util import create_urllib3_context
from urllib3 import PoolManager
from requests.adapters import HTTPAdapter
from requests import Session

class AddedCipherAdapter(HTTPAdapter):
  def init_poolmanager(self, conntections, maxsize, block=False):
    ctx = create_urllib3_context(ciphers=":HIGH:!DH:!aNULL")
    ctx.check_hostname = False
    self.poolmanager = PoolManager(
      #num_pools=connections,
      #maxsize=maxsize,
      #block=block,
      ssl_context=ctx,
    )

def unsafe_req(url, timeout = 30):
    s = Session()
    parse = urllib.parse.urlparse(url)
    s.mount("{scheme}://{netloc}".format(scheme = parse.scheme, netloc = parse.netloc), AddedCipherAdapter())
    ret = s.get(url, verify = False, timeout = timeout)
    s.close()
    return ret

#About wkid or latestwkid, for now, lets use wkid, I'll suppose it recovers the orginal coords

def dumpjson(ifile, data):
    with open(ifile, 'w') as f:
        json.dump(data, f, indent=4, sort_keys=True)

def request2json(url, itry = 3, timeout = 30):
    #print(url)
    ret = unsafe_req(url, timeout = timeout)
    #ret = requests.get(url, verify=False)
    #ret = requests.get(url)
    #print(ret.content)
    if ret.status_code == 200:
        data = json.loads(ret.content.decode("utf-8"))
        #if ('error' in data) and len(data.keys()) == 1:
        #    print(url)
        #    print(data)
        #    #Check this later
        #    raise ErrorPerformingOp
        return data
    elif (
          (ret.status_code == 500) or
          (ret.status_code == 403)
         ) and (itry > 0):
        time.sleep(5)
        return request2json(url, itry=(itry-1), timeout = timeout)
    else:
        print(url, flush=True)
        ret.raise_for_status()

def url2path(url, spaths=[], epaths=[]):
    url = url.split("/")
    return os.path.join(*spaths, *url, *epaths)

def params2html(params):
    data = ""
    for i in params:
        data += i + "=" + requests.utils.quote(params[i]) + "&"
    return data

def use_proxy(proxy, url, params):
    return "{}{}".format(proxy, requests.utils.quote("{}?{}".format(url, params2html(params))))

def DumpArcgis(url, path, proxy):
    pass

from pathlib import Path

class Arcgis:
    def __init__(self, url, path, proxy = None, timeout = 30, catalog = True, overwrite = False, paginate_oid = False):
        #linkgenerator(link, params)
        #some access to arcgis use custom ways to contruct the links
        #so, the link param is the link to the server
        #and params is the GET/Post parameters we want to send
        #The link need to start in the "server"
        if proxy is None:
            self.link_generator = lambda iurl, iparams: "{}/{}?{}".format(self.url, iurl, params2html(iparams))
        else:
            self.link_generator = lambda iurl, iparams: use_proxy(self.proxy, "{}/{}".format(self.url, iurl), iparams)
        self.proxy = proxy
        if url[-1] == "/":
            url = url[:-1]
        self.url = url
        self.path = path
        self.timeout = timeout
        self.catalog = catalog
        self.overwrite = overwrite
        self.paginate_oid = paginate_oid
        #if os.path.exists(path):
        #    shutil.rmtree(path)
        os.makedirs(path, exist_ok=True)
    def dumpjson(self, start = ""):
        try:
            data = request2json(self.link_generator(start, {'f': 'json'}), timeout = self.timeout)
        except:
          print("Fail dumpjson!")
          return
        dumpjson(url2path(start, [self.path], ["data.json"]), data)
        if 'services' in data:
            self.read_services(data['services'])
        if 'folders' in data:
            self.read_folder(data['folders'])
    def read_services(self, services):
        for i in range(len(services)):
            if services[i]["type"] == "MapServer" or services[i]["type"] == "FeatureServer":
                upath = services[i]["name"] + "/" + services[i]["type"]
                dpath = url2path(upath, spaths=[self.path])
                os.makedirs(dpath, exist_ok=True)
                self.read_Map(upath, dpath)
            else:
                print("Unsupported service type: {}".format(services[i]["type"]))
    def read_folder(self, folders):
        for i in folders:
            os.makedirs(os.path.join(self.path, i), exist_ok=True)
            self.dumpjson(i)
    def read_Map(self, link, path):
        try:
          data = request2json(self.link_generator(link, {'f':'json'}), timeout = self.timeout)
        except:
          print("Not able to get map data!")
          return
        dumpjson(os.path.join(path, "data.json"), data)
        with open(os.path.join(path, "map.service"), "w") as url:
            url.write(link)
        if 'layers' not in data:
          print("No Layers accesable from here! check the map!")
          return
        for layer in data['layers']:
                upath = "{}/{}".format(link, layer['id'])
                dpath = url2path(upath)
                os.makedirs(url2path(link, spaths=[self.path], epaths=[str(layer['id'])]), exist_ok=True)
                self.read_Layer(upath, dpath, link, layer['id'], data)
    def read_Layer(self, link, path, maplink, layer, mapdata):
        out_file = os.path.join(self.path, path, "{}.gpkg".format(layer))
        #Virtual layers are the ones are composed by others, should not be downloaded
        virtual_layer = os.path.join(self.path, path, "virtual_layer")
        if (not self.overwrite) and (os.path.exists(virtual_layer) or os.path.exists(out_file)): return
        print("Requesting:")
        print("{}/{}".format(self.url, link))
        try:
          data = request2json(self.link_generator(link, {'f':'json'}), timeout = self.timeout)
        except:
          print("Error downloading the data!")
          return
        if 'error' in data:
            print("No se pudo obtner esta capa")
            print(data)
            return
        dumpjson(os.path.join(self.path, path, "data.json"), data)
        dumpjson(os.path.join(self.path, path, "layer.url"), {
          'url': "{}/{}".format(self.url, link),
          'proxy': self.proxy
        })
        wkid = None
        wkid_txt = 'wkid'
        if 'sourceSpatialReference' in data:
            if wkid_txt not in data['sourceSpatialReference']:
              print("can't read wkid!")
              return
            wkid = data['sourceSpatialReference'][wkid_txt]
        else:
            if 'spatialReference' in mapdata:
                if wkid_txt in mapdata['spatialReference']:
                    wkid = mapdata['spatialReference'][wkid_txt]
        if wkid is None:
            wkid = 4326
        if self.catalog: return
        tmp_file = os.path.join(self.path, path, "tmp.geojson")
        try:
            tmp = open(tmp_file, "w")
            tmp.write('{"type":"FeatureCollection","features":[')
            try:
                iterator = EsriDumper("{}/{}".format(self.url, link),
                                            proxy=self.proxy,
                                            outSR=wkid,
                                            timeout=self.timeout,
                                            paginate_oid = self.paginate_oid)
                for feature in iterator:
                    tmp.write(json.dumps(feature, indent=4))
                    tmp.write(",")
                tmp.seek(tmp.tell()-1)
                tmp.truncate()
                tmp.write(']}')
                tmp.close()
            except TypeError as e:
                tmp.close()
                os.remove(tmp_file)
                if e.args == ("'NoneType' object is not iterable",):
                    print("This is a layer constructed with other ones")
                    Path(virtual_layer).touch()
                    return
                raise(e)
            geo = geopandas.read_file(tmp_file)
            geo.set_crs(wkid, allow_override=True, inplace=True)
            geo.to_file(out_file)
            os.remove(tmp_file)
        except Exception as e:
            print(e)
            return

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description = 'Dump Map Server')
    parser.add_argument('url', help='url map server')
    parser.add_argument('folder', help='output folder')
    parser.add_argument('--proxy', nargs="?", help='proxy url')
    parser.add_argument('--timeout', nargs="?", default=30, help='Timeout to get response from the server in seconds')
    parser.add_argument('--start_folder', nargs="?", default="", help='From what folder start reading')
    parser.add_argument('--catalog', action='store_true', help='We will only download map structures and info, not the map it self, good to know what can be inside')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing file')
    parser.add_argument('--paginate_oid', action='store_true', help='Use paginate_oid from Dumper to scrap')
    args = parser.parse_args()
    full = Arcgis(
        args.url,
        args.folder,
        args.proxy,
        timeout=int(args.timeout),
        catalog=args.catalog,
        overwrite = args.overwrite,
        paginate_oid = args.paginate_oid
    )
    if args.start_folder != "":
        os.makedirs(os.path.join(args.folder, *args.start_folder.split("/")), exist_ok=True)
    full.dumpjson(args.start_folder)
