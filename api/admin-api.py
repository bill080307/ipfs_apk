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
conf = loadjson(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"))
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
        if k['Name'].startswith(conf['storageSubPath'] + '_'):
            result.append(k)
    return {"api": conf['ipfsApi'], "gw": conf['ipfsGW'], "keys": result}


@app.get('/newkey')
def newKey(keyname: str):
    if not keyname.isalnum():
        return 'keyname not allow'
    keys = api.key.list()
    for k in keys['Keys']:
        if k['Name'] == conf['storageSubPath'] + '_' + keyname:
            return 'keyname Already.'
    key = api.key.gen(conf['storageSubPath'] + '_' + keyname, type="rsa")
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
        result = getupdatejson(ipfs)
        result['ipfs'] = ipfs
        return result


@app.post('/newversion')
def newVersion(ipns: str = Form(...),
                     title: str = Form(...),
                     version:str = Form(...),
                     build:str = Form(...),
                     log:str = Form(...),
                     apk: UploadFile = File(...)):
    apkname = "%s_%s_%s.apk" % (conf['projectName'].lower(), version, build)
    apkpath = os.path.join(conf['localStorage'], conf['storageSubPath'])
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
        "build": build,
        "log": log,
        "apk_file": os.path.join(conf['storageSubPath'], apkname),
        "datetime": int(time.time())
    })
    update['last'] = build
    updatehash = api.add_json(update)

    files = api.object.links(ipfs)

    dirhash = api.object.new("unixfs-dir")
    for fl in files['Links']:
        if fl['Name'] == conf['storageSubPath']:
            dirhash = fl

    # add apk file in hash
    dirhash = api.object.patch.add_link(dirhash['Hash'], apkname, apkhash['Hash'])

    hash = conf['uiTemplate']
    hash = api.object.patch.add_link(hash, conf['storageSubPath'], dirhash['Hash'])
    hash = api.object.patch.add_link(hash['Hash'], 'update.json', updatehash)
    red.set(ipns, hash['Hash'])
    return {"newhash": hash['Hash']}


@app.get('/delversion')
def delVersion(ipns, build):
    red = redis.Redis(host=conf['redisCacheServer'][0]["host"],
                      port=conf['redisCacheServer'][0]["port"],
                      decode_responses=True)
    ipfs = red.get(ipns)
    if ipfs is None:
        return 'no Version.'
    update = getupdatejson(ipfs)
    newupdate = {
        "title": conf['projectName'],
        "data": [],
    }
    for item in update['data']:
        if not item['build'] == build:
            newupdate['data'].append(item)
        else:
            apkname = "%s_%s_%s.apk" % (conf['projectName'].lower(), item['version'], build)

    if update['last'] == build:
        last = 0
        for i in range(len(newupdate['data'])):
            if newupdate['data'][i]['datetime'] > newupdate['data'][last]['datetime']:
                last = i
        newupdate['last'] = newupdate['data'][last]['build']

    updatehash = api.add_json(newupdate)
    files = api.object.links(ipfs)

    dirhash = api.object.new("unixfs-dir")
    for fl in files['Links']:
        if fl['Name'] == conf['storageSubPath']:
            dirhash = fl

    # del apk file in hash
    dirhash = api.object.patch.rm_link(dirhash['Hash'], apkname)

    hash = conf['uiTemplate']
    hash = api.object.patch.add_link(hash, conf['storageSubPath'], dirhash['Hash'])
    hash = api.object.patch.add_link(hash['Hash'], 'update.json', updatehash)
    red.set(ipns, hash['Hash'])
    return {"newhash": hash['Hash']}


@app.post('/upversion')
def upVersion(ipns: str = Form(...),
                     title: str = Form(...),
                     version:str = Form(...),
                     build:str = Form(...),
                     log:str = Form(...),
                     apk: UploadFile = File(None)):
    red = redis.Redis(host=conf['redisCacheServer'][0]["host"],
                      port=conf['redisCacheServer'][0]["port"],
                      decode_responses=True)
    ipfs = red.get(ipns)
    if ipfs is None:
        return 'no Version.'

    files = api.object.links(ipfs)
    dirhash = api.object.new("unixfs-dir")
    for fl in files['Links']:
        if fl['Name'] == conf['storageSubPath']:
            dirhash = fl

    if apk:
        apkname = "%s_%s_%s.apk" % (conf['projectName'].lower(), version, build)
        apkpath = os.path.join(conf['localStorage'], conf['storageSubPath'])
        if not os.path.isdir(apkpath):
            os.mkdir(apkpath)
        with open(os.path.join(apkpath, apkname), "wb") as f:
            f.write(apk.file.read())
        apkhash = api.add(os.path.join(apkpath, apkname))
    update = getupdatejson(ipfs)
    newupdate = {
        "title": conf['projectName'],
        "data": [],
    }
    for item in update['data']:
        if not item['build'] == build:
            newupdate['data'].append(item)
        else:
            if apk:
                apk_file = os.path.join(conf['storageSubPath'], apkname)
                dirhash = api.object.patch.rm_link(dirhash['Hash'], item['apk_file'].split('/')[1])
                dirhash = api.object.patch.add_link(dirhash['Hash'], apkname, apkhash['Hash'])
            else:
                apk_file = item['apk_file']
            newupdate['data'].append({
                "title": title,
                "version": version,
                "build": build,
                "log": log,
                "apk_file": apk_file,
                "datetime": int(time.time())
            })
    newupdate['last'] = build
    updatehash = api.add_json(newupdate)

    hash = conf['uiTemplate']
    hash = api.object.patch.add_link(hash, conf['storageSubPath'], dirhash['Hash'])
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
