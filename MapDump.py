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
requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += ':HIGH:!DH:!aNULL'
try:
    requests.packages.urllib3.contrib.pyopenssl.util.ssl_.DEFAULT_CIPHERS += ':HIGH:!DH:!aNULL'
except AttributeError:
    # no pyopenssl support used / needed / available
    pass

#About wkid or latestwkid, for now, lets use wkid, I'll suppose it recovers the orginal coords

def dumpjson(ifile, data):
    with open(ifile, 'w') as f:
        json.dump(data, f, indent=4, sort_keys=True)

def request2json(url, itry = 3):
    #print(url)
    ret = requests.get(url, verify=False)
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
    elif (ret.status_code == 500) and (itry > 0):
        time.sleep(5)
        return request2json(url, itry=(itry-1))
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

class Arcgis:
    def __init__(self, url, path, proxy = None, timeout = 30):
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
        if os.path.exists(path):
            shutil.rmtree(path)
        os.makedirs(path)
    def dumpjson(self, start = ""):
        data = request2json(self.link_generator(start, {'f': 'json'}))
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
                os.makedirs(dpath)
                self.read_Map(upath, dpath)
            else:
                print("Unsupported service type: {}".format(services[i]["type"]))
    def read_folder(self, folders):
        for i in folders:
            os.makedirs(os.path.join(self.path, i))
            self.dumpjson(i)
    def read_Map(self, link, path):
        data = request2json(self.link_generator(link, {'f':'json'}))
        dumpjson(os.path.join(path, "data.json"), data)
        with open(os.path.join(path, "map.service"), "w") as url:
            url.write(link)
        for layer in data['layers']:
                upath = "{}/{}".format(link, layer['id'])
                dpath = url2path(upath)
                os.makedirs(url2path(link, spaths=[self.path], epaths=[str(layer['id'])]))
                self.read_Layer(upath, dpath, link, layer['id'], data)
    def read_Layer(self, link, path, maplink, layer, mapdata):
        print("Requesting:")
        print("{}/{}".format(self.url, link))
        data = request2json(self.link_generator(link, {'f':'json'}))
        if 'error' in data:
            print("No se pudo obtner esta capa")
            print(data)
            return
        wkid = None
        wkid_txt = 'wkid'
        if 'sourceSpatialReference' in data:
            wkid = data['sourceSpatialReference'][wkid_txt]
        else:
            if 'spatialReference' in mapdata:
                wkid = mapdata['spatialReference'][wkid_txt]
            else:
                print("No se pudo recuperar el wkid")
                return
        dumpjson(os.path.join(self.path, path, "data.json"), data)
        tmp_file = os.path.join(self.path, path, "tmp.geojson")
        tmp = open(tmp_file, "w")
        tmp.write('{"type":"FeatureCollection","features":[')
        try:
            iterator = EsriDumper("{}/{}".format(self.url, link),
                                        proxy=self.proxy,
                                        outSR=wkid,
                                        timeout=self.timeout)
            if iterator == None:
                print("This is a layer constructed with other ones")
                print(link)
                return
            for feature in iterator:
                tmp.write(json.dumps(feature, indent=4))
                tmp.write(",")
            tmp.seek(tmp.tell()-1)
            tmp.truncate()
            tmp.write(']}')
            tmp.close()
            geo = geopandas.read_file(tmp_file)
            geo.set_crs(wkid, allow_override=True, inplace=True)
            geo.to_file(os.path.join(self.path, path, "{}.gpkg".format(layer)))
            os.remove(tmp_file)
        except Exception as e:
            tmp.close()
            os.remove(tmp_file)
            print(e)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description = 'Dump Map Server')
    parser.add_argument('url', help='url map server')
    parser.add_argument('folder', help='output folder')
    parser.add_argument('--proxy', nargs="?", help='proxy url')
    parser.add_argument('--timeout', nargs="?", default=30, help='Timeout to get response from the server in seconds')
    parser.add_argument('--start_folder', nargs="?", default="", help='From what folder start reading')
    args = parser.parse_args()
    full = Arcgis(args.url, args.folder, args.proxy, timeout=int(args.timeout))
    if args.start_folder != "":
        os.makedirs(os.path.join(args.folder, *args.start_folder.split("/")))
    full.dumpjson(args.start_folder)