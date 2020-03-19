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
            return json.loads(api.cat(fl['Hash']))

@app.get('/getkeys')
def getKeys():
    keys = api.key.list()
    result = []
    for k in keys['Keys']:
        if k['Name'].startswith(conf['StorageSubPath'] + '_'):
            result.append(k)
    return {"api": conf['ipfsApi'], "keys": result}


@app.get('/newkey')
def newKey(keyname: str):
    if not keyname.isalnum():
        return 'keyname not allow'
    keys = api.key.list()
    for k in keys['Keys']:
        if k['Name'] == conf['StorageSubPath'] + '_' + keyname:
            return 'keyname Already.'
    key = api.key.gen(conf['StorageSubPath'] + '_' + keyname, type="rsa")
    return key


@app.get('/getupdate')
def getUpdate(ipns: str):
    red = redis.Redis(host=conf['redisCacheServer'][0]["host"],
                      port=conf['redisCacheServer'][0]["port"],
                      decode_responses=True)
    ipfs = red.get(ipns)
    if ipfs is None:
        update = {
            "title": conf['projectName'],
            "data": [],
        }
        return update
    else:
        return getupdatejson(ipfs)


@app.post('/newversion')
async def newVersion(ipns: str = Form(...),
                     title: str = Form(...),
                     version:str = Form(...),
                     bulid:str = Form(...),
                     log:str = Form(...),
                     apk: UploadFile = File(...)):
    apkname = "%s_%s_%s.apk" % (conf['projectName'].lower(), version, bulid)
    apkpath = os.path.join(conf['localStorage'], conf['StorageSubPath'])
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
            "title": conf['projectName'],
            "data": [],
        }
        ipfs = conf['uiTemplate']
    else:
        update = getupdatejson(ipfs)
    update['data'].append({
        "title": title,
        "version": version,
        "bulid": bulid,
        "log": log,
        "apk_file": os.path.join(conf['StorageSubPath'], apkname),
        "datetime": int(time.time())
    })
    update['last'] = bulid
    updatehash = api.add_json(update)

    files = api.object.links(ipfs)

    dirhash = api.object.new("unixfs-dir")
    for fl in files['Links']:
        if fl['Name'] == conf['StorageSubPath']:
            dirhash = fl

    # add apk file in hash
    dirhash = api.object.patch.add_link(dirhash['Hash'], apkname, apkhash['Hash'])

    hash = conf['uiTemplate']
    hash = api.object.patch.add_link(hash, conf['StorageSubPath'], dirhash['Hash'])
    hash = api.object.patch.add_link(hash['Hash'], 'update.json', updatehash)
    red.set(ipns, hash['Hash'])
    return {"newhash": hash['Hash']}


if __name__ == '__main__':
    import uvicorn
    runConf = conf['service']
    uvicorn.run(app=app,
                host=runConf['host'],
                port=runConf['port'],
                workers=runConf['workers'])