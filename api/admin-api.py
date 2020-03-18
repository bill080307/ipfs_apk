#!/usr/bin/python3
import json
import os
import time

import ipfshttpclient
import redis as redis
from fastapi import FastAPI, File, UploadFile, Form


def loadjson(jsonfile):
    with open(jsonfile) as json_file:
        data = json.load(json_file)
        return data


app = FastAPI()
conf = loadjson("config.json")
api = ipfshttpclient.connect(conf['ipfsApi'], timeout=3600)


def getupdatejson(hash):
    stat = api.files.stat('/ipfs/' + hash)
    if not stat['Type'] == 'directory':
        return 'ERR: hash is not directory.'
    file = api.object.links('/ipfs/' + hash)
    for fl in file['Links']:
        if fl['Name'] == 'update.json':
            return fl['Hash']

@app.get('/getkeys')
def getKeys():
    keys = api.key.list()
    result = []
    for k in keys['Keys']:
        if k['Name'].startswith(conf['project'] + '_'):
            result.append(k)
    return {"api": conf['ipfsApi'], "keys": result}


@app.get('/newkey')
def newKey(keyname: str):
    if not keyname.isalnum():
        return 'keyname not allow'
    keys = api.key.list()
    for k in keys['Keys']:
        if k['Name'] == conf['project'] + '_' + keyname:
            return 'keyname Already.'
    key = api.key.gen(conf['project'] + '_' + keyname, type="rsa")
    return key


@app.get('/getupdate')
def getUpdate(ipns: str):
    red = redis.Redis(host=conf['redisCacheServer'][0]["host"],
                      port=conf['redisCacheServer'][0]["port"],
                      decode_responses=True)
    ipfs = red.get(ipns)
    if ipfs is None:
        # TODO: new key
        pass
    else:
        return json.loads(api.cat(getupdatejson(ipfs)))


@app.post('/newversion')
async def newVersion(ipns: str = Form(...),
                     title: str = Form(...),
                     version:str = Form(...),
                     bulid:str = Form(...),
                     log:str = Form(...),
                     apk: UploadFile = File(...)):
    apkname = "videoshare_%s_%s.apk" % (version, bulid)
    apkpath = os.path.join(conf['localStorage'], conf['project'])
    if not os.path.isdir(apkpath):
        os.mkdir(apkpath)
    with open(os.path.join(apkpath, apkname), "wb") as f:
        f.write(apk.file.read())
    apkhash = api.add(os.path.join(apkpath, apkname))
    red = redis.Redis(host=conf['redisCacheServer'][0]["host"],
                      port=conf['redisCacheServer'][0]["port"],
                      decode_responses=True)
    ipfs = red.get(ipns)
    if ipfs is None:
        update = {
            "title": "VideoShare",
            "data": [],
        }
        ipfs = conf['uiTemplate']
    else:
        update = json.loads(api.cat(getupdatejson(ipfs)))
    update['data'].append({
        "title": title,
        "version": version,
        "bulid_num": bulid,
        "update_log": log,
        "apk_file": os.path.join(conf['ipfsApkPath'], apkname),
        "datetime": int(time.time())
    })
    update['last'] = bulid
    updatehash = api.add_json(update)
    hash = ipfs

    files = api.object.links(hash)
    updatejson = False
    apkpath = False

    for fl in files['Links']:
        if fl['Name'] == 'update.json':
            updatejson = True
        elif fl['Name'] == conf['ipfsApkPath']:
            apkpath = True
            dirhash = fl['Hash']

    # add apk file in hash
    if not apkpath:
        dirhash = api.object.new("unixfs-dir")
        dirhash = api.object.patch.add_link(dirhash['Hash'], apkname, apkhash['Hash'])
        hash = api.object.patch.add_link(hash, conf['ipfsApkPath'], dirhash['Hash'])
    else:
        dirhash = api.object.patch.add_link(dirhash, apkname, apkhash['Hash'])
        hash = api.object.patch.rm_link(hash, conf['ipfsApkPath'])
        hash = api.object.patch.add_link(hash['Hash'], conf['ipfsApkPath'], dirhash['Hash'])

    if updatejson:
        hash = api.object.patch.rm_link(hash['Hash'], 'update.json')
    hash = api.object.patch.add_link(hash['Hash'], 'update.json', updatehash)
    return {"newhash": hash['Hash']}


if __name__ == '__main__':
    import uvicorn
    runConf = conf['service']
    uvicorn.run(app=app,
                host=runConf['host'],
                port=runConf['port'],
                workers=runConf['workers'])
