#!/usr/bin/python3
import json
import os
import sys
import time

import ipfshttpclient
import redis as redis
from fastapi import FastAPI, File, UploadFile, Form
from androguard.core.bytecodes import apk


def loadjson(jsonfile):
    with open(jsonfile) as json_file:
        data = json.load(json_file)
        return data


app = FastAPI()
api = None

uiTemplate = None


def getupdatejson(hash):
    stat = api.files.stat('/ipfs/' + hash)
    if not stat['Type'] == 'directory':
        return 'ERR: hash is not directory.'
    file = api.object.links('/ipfs/' + hash)
    for fl in file['Links']:
        if fl['Name'] == 'update.json':
            return json.loads(api.cat(fl['Hash']))


def publish(ipns, ipfs):
    from threading import Thread

    def setipns(ipns, ipfs):
        api.name.publish('/ipfs/%s' % ipfs, key=ipns, lifetime='8760h')

    redcfs = conf['redisCacheServer']
    for redcf in redcfs:
        red = redis.Redis(host=redcf["host"], port=redcf["port"], decode_responses=True)
        red.set("IPNSCACHE_%s" % ipns, ipfs)
    t = Thread(target=setipns, args=(ipns, ipfs))
    t.start()
    return


def get_android_info(package_file):
    try:
        apkobj = apk.APK(package_file)
    except Exception as err:
        print(err)
    else:
        if apkobj.is_valid_APK():
            package = apkobj.get_package()
            version = apkobj.get_androidversion_name()
            code = apkobj.get_androidversion_code()
            print(package)
            # labelname = apkobj.get_app_name()
            # sdk_version = apkobj.get_target_sdk_version()
            return package, version, code


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
    try:
        ipfs = api.files.stat("IPNSCACHE_%s" % ipns)['Hash']
    except ipfshttpclient.exceptions.ErrorResponse:
        ipfs = None
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
               log: str = Form(...),
               apk: UploadFile = File(...)):
    with open(os.path.join("/tmp/tmp.apk"), "wb") as f:
        f.write(apk.file.read())
    package, version, code = get_android_info("/tmp/tmp.apk")
    apkname = "%s_%s_%s.apk" % (package, version, code)
    apkpath = os.path.join(conf['localStorage'], conf['storageSubPath'])
    if not os.path.isdir(apkpath):
        os.mkdir(apkpath)
    with open(os.path.join(apkpath, apkname), "wb") as f:
        f.write(apk.file.read())
    apkhash = api.add(os.path.join(apkpath, apkname), chunker='size-1048576', nocopy=True)
    red = redis.Redis(host=conf['redisCacheServer'][0]["host"],
                      port=conf['redisCacheServer'][0]["port"],
                      decode_responses=True)
    try:
        ipfs = api.files.stat("IPNSCACHE_%s" % ipns)['Hash']
    except ipfshttpclient.exceptions.ErrorResponse:
        ipfs = None
    if ipfs is None:
        update = {
            "title": conf['projectName'],
            "data": [],
        }
        ipfs = uiTemplate
    else:
        update = getupdatejson(ipfs)
    update['data'].append({
        "title": title,
        "version": version,
        "build": code,
        "log": log,
        "apk_file": os.path.join(conf['storageSubPath'], apkname),
        "datetime": int(time.time())
    })
    update['last'] = code
    updatehash = api.add_json(update)

    files = api.object.links(ipfs)

    dirhash = api.object.new("unixfs-dir")
    for fl in files['Links']:
        if fl['Name'] == conf['storageSubPath']:
            dirhash = fl

    # add apk file in hash
    dirhash = api.object.patch.add_link(dirhash['Hash'], apkname, apkhash['Hash'])

    hash = uiTemplate
    hash = api.object.patch.add_link(hash, conf['storageSubPath'], dirhash['Hash'])
    hash = api.object.patch.add_link(hash['Hash'], 'update.json', updatehash)
    publish(ipns, hash['Hash'])
    api.files.cp('/ipfs/%s' % hash['Hash'], "/IPNSCACHE_%s" % ipns)
    return {"newhash": hash['Hash']}


@app.get('/delversion')
def delVersion(ipns, build):
    try:
        ipfs = api.files.stat("IPNSCACHE_%s" % ipns)['Hash']
    except ipfshttpclient.exceptions.ErrorResponse:
        ipfs = None
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
            apkname = apk_file.split("/")[1]

    if update['last'] == build:
        last = 0
        for i in range(len(newupdate['data'])):
            if newupdate['data'][i]['datetime'] > newupdate['data'][last]['datetime']:
                last = i
        newupdate['last'] = newupdate['data'][last]['build']
    else:
        newupdate['last'] = update['last']

    updatehash = api.add_json(newupdate)
    files = api.object.links(ipfs)

    dirhash = api.object.new("unixfs-dir")
    for fl in files['Links']:
        if fl['Name'] == conf['storageSubPath']:
            dirhash = fl

    # del apk file in hash
    dirhash = api.object.patch.rm_link(dirhash['Hash'], apkname)

    hash = uiTemplate
    hash = api.object.patch.add_link(hash, conf['storageSubPath'], dirhash['Hash'])
    hash = api.object.patch.add_link(hash['Hash'], 'update.json', updatehash)
    publish(ipns, hash['Hash'])
    api.files.rm("/IPNSCACHE_%s" % ipns, recursive=True)
    api.files.cp('/ipfs/%s' % hash['Hash'], "/IPNSCACHE_%s" % ipns)
    return {"newhash": hash['Hash']}


@app.post('/upversion')
def upVersion(ipns: str = Form(...),
              title: str = Form(...),
              build: str = Form(...),
              log: str = Form(...),
              apk: UploadFile = File(None)):
    try:
        ipfs = api.files.stat("IPNSCACHE_%s" % ipns)['Hash']
    except ipfshttpclient.exceptions.ErrorResponse:
        ipfs = None
    if ipfs is None:
        return 'no Version.'

    files = api.object.links(ipfs)
    dirhash = api.object.new("unixfs-dir")
    for fl in files['Links']:
        if fl['Name'] == conf['storageSubPath']:
            dirhash = fl

    if apk:
        with open(os.path.join("/tmp/tmp.apk"), "wb") as f:
            f.write(apk.file.read())
        package, version, code = get_android_info("/tmp/tmp.apk")
        apkname = "%s_%s_%s.apk" % (package, version, code)
        apkpath = os.path.join(conf['localStorage'], conf['storageSubPath'])
        if not os.path.isdir(apkpath):
            os.mkdir(apkpath)
        with open(os.path.join(apkpath, apkname), "wb") as f:
            f.write(apk.file.read())
        apkhash = api.add(os.path.join(apkpath, apkname), chunker='size-1048576', nocopy=True)
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

    hash = uiTemplate
    hash = api.object.patch.add_link(hash, conf['storageSubPath'], dirhash['Hash'])
    hash = api.object.patch.add_link(hash['Hash'], 'update.json', updatehash)
    publish(ipns, hash['Hash'])
    api.files.rm("/IPNSCACHE_%s" % ipns, recursive=True)
    api.files.cp('/ipfs/%s' % hash['Hash'], "/IPNSCACHE_%s" % ipns)
    return {"newhash": hash['Hash']}


if __name__ == '__main__':
    import uvicorn

    if len(sys.argv[1:]) < 1:
        print("can't read config file.")
        sys.exit(0)
    conf_path = (sys.argv[1])
    conf = loadjson(conf_path)
    api = ipfshttpclient.connect(conf['ipfsApi'], timeout=3600)
    uidir = os.path.abspath(os.path.join(os.path.dirname(conf_path), "ui_html"))
    if not os.path.isdir(uidir):
        print("can't find ui html dir.")
        sys.exit(0)
    hash = api.add(uidir)
    uiTemplate = hash[-1]['Hash']

    runConf = conf['service']
    uvicorn.run(app=app,
                host=runConf['host'],
                port=runConf['port'],
                workers=runConf['workers'])
