import os
import shutil
import time
import pickle
import requests
import json

from esridump.dumper import EsriDumper

def dumpjson(ifile, data):
    with open(ifile, 'w') as f:
        json.dump(data, f)

def request2json(url, itry = 3):
    ret = requests.get(url)
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

class Arcgis:
    def __init__(self, link_generator, path):
        #linkgenerator(link, params)
        #some access to arcgis use custom ways to contruct the links
        #so, the link param is the link to the server
        #and params is the GET/Post parameters we want to send
        #The link need to start in the "server"
        self.link_generator = link_generator
        self.path = path
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
            if services[i]["type"] == "MapServer":
                upath = services[i]["name"] + "/MapServer"
                dpath = url2path(upath, spaths=[self.path])
                os.makedirs(dpath)
                self.read_Map(upath, dpath)
    def read_folder(self, folders):
        for i in folders:
            os.makedirs(os.path.join(self.path, i))
            self.dumpjson(i)
    def read_Map(self, link, path):
        data = request2json(self.link_generator(link, {'f':'json'}))
        dumpjson(os.path.join(path, "data.json"), data)
        pickle.dump(link, open(os.path.join(path, "map.service"), "wb"))
        for layer in data['layers']:
                upath = "{}/{}".format(link, layer['id'])
                dpath = url2path(upath)
                os.makedirs(url2path(link, spaths=[self.path], epaths=[str(layer['id'])]))
                self.read_Layer(upath, dpath, link, layer['id'])
    def read_Layer(self, link, path, maplink, layer):
        #data = request2json(self.link_generator(link, {'f':'json'}))
        print(link)
        #dumpjson(os.path.join(self.path, path, "data.json"), data)

#def __name__ == "__main__":
#    pass