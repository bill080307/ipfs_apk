<template>
  <div id="app">
    <b-container>
      <b-row>
        <b-col>
          ipfs API: {{ipfsApi}}<br>
          ipfs GW: {{ipfsGW}}
        </b-col>
        <b-col>key:
          <b-button variant="info" @click="init">refresh</b-button>
          <b-button variant="success" @click="newkey">new</b-button>
          <b-form-select v-model="keyselected" :options="keys" @change="selectkey"></b-form-select>
        </b-col>
      </b-row>
      <b-row>
        <b-col cols="3">
          <b-form-select v-model="updateed" :options="updates" :select-size="10" @change="selectver"></b-form-select>
          IPNS: {{ keyselected }}<br>
          IPNS QR (ipns gateway)<br>
          <div id="ipnsqrCode" ref="ipnsqrCodeDiv"></div>
          IPFS QR (ipfs path)<br>
          <div id="ipfsqrCode" ref="ipfsqrCodeDiv"></div>
        </b-col>
        <b-col cols="9">
          <b-form-group label="title:" label-for="title">
            <b-form-input id="title" v-model="item.title"></b-form-input>
          </b-form-group>
          <b-form-group label="version:" label-for="version">
            <b-form-input id="version" v-model="item.version"></b-form-input>
          </b-form-group>
          <b-form-group label="build:" label-for="build">
            <b-form-input id="build" v-model="item.build"></b-form-input>
          </b-form-group>
          <b-form-group label="update_log:" label-for="update_log">
            <b-form-textarea
                    id="update_log"
                    v-model="item.log"
                    rows="3"
                    max-rows="6"
            ></b-form-textarea>
          </b-form-group>
          <b-form-group label="apkfile:" label-for="apkfile">
            <b-form-file id="apkfile" v-model="apkfile" accept=".apk"></b-form-file>
          </b-form-group>
          <p>download: <a :href="item.apk_url">{{item.apk_file}}</a></p>
          <p>datetime: {{ item.datetime | dateT}}</p>
          <b-button-group>
            <b-button variant="success" @click="newversion">new</b-button>
            <b-button variant="info" @click="upversion">update</b-button>
            <b-button variant="warning" @click="delversion">delete</b-button>
          </b-button-group>
        </b-col>
      </b-row>
    </b-container>
  </div>
</template>

<script>
  import Axios from 'axios';
  import QRCode from 'qrcodejs2';
  export default {
    name: 'App',
    data(){
      return {
        ipfsApi:"",
        ipfsGW:"",
        keys:[],
        keyselected:"",
        item:{
          "title": "",
          "version": "",
          "build": "",
          "apk_file": "",
          "apk_url": "",
          "log": "",
          "datetime": "",
        },
        updatejson:[],
        updates:[],
        updateed:"",
        apkfile:null
      }
    },
    methods:{
      init(){
        Axios.get('/api/getkeys').then((res)=>{
          this.ipfsApi = res.data.api;
          this.ipfsGW = res.data.gw;
          this.keys = [];
          for (let i = 0; i < res.data.keys.length; i++) {
            this.keys.push({
              value: res.data.keys[i].Id,
              text: res.data.keys[i].Name
            })
          }
        });
      },
      newkey(){
        let name = prompt("input key name","");
        if(!name)return;
        Axios.get('/api/newkey?keyname='+name).then((res)=>{
          console.log(res);
          this.init()
        })
      },
      selectkey(){
        Axios.get('/api/getupdate?ipns='+this.keyselected).then((res)=>{
          this.updatejson = res.data.data;
          this.updates = [];
          for (let i = 0; i < this.updatejson.length; i++) {
            this.updates.push({
              value: i,
              text: this.updatejson[i].title
            })
          }
          this.$refs.ipnsqrCodeDiv.innerHTML = '';
          this.$refs.ipfsqrCodeDiv.innerHTML = '';
          if(this.updatejson.length > 0){
            new QRCode(this.$refs.ipnsqrCodeDiv, {
              text: this.ipfsGW.replace(/ipfs\/:hash/,'ipns/'+this.keyselected+'/'),
              width: 200,
              height: 200,
              colorDark: "#333333",
              colorLight: "#ffffff",
              correctLevel: QRCode.CorrectLevel.L
            });
            new QRCode(this.$refs.ipfsqrCodeDiv, {
              text: '/ipfs/'+res.data.ipfs,
              width: 200,
              height: 200,
              colorDark: "#333333",
              colorLight: "#ffffff",
              correctLevel: QRCode.CorrectLevel.L
            });
          }
        })
      },
      selectver(){
        this.item = this.updatejson[this.updateed];
        this.item.apk_url = this.ipfsGW.replace(/ipfs\/:hash/,'ipns/'+this.keyselected) + '/' +this.item.apk_file;
      },
      newversion(){
        const formdata = new FormData();
        formdata.append('apk',this.apkfile);
        formdata.append('ipns',this.keyselected);
        formdata.append('title',this.item.title);
        formdata.append('version',this.item.version);
        formdata.append('build',this.item.build);
        formdata.append('log',this.item.log);
        Axios.post('/api/newversion',formdata,{
          headers:{'Content-Type':'multipart/form-data'}
        }).then((res)=>{
          this.item = {};
          this.apkfile = null;
          this.selectkey();
          console.log(res)
        })
      },
      upversion(){
        const formdata = new FormData();
        if (this.apkfile){
          formdata.append('apk',this.apkfile);
        }
        formdata.append('ipns',this.keyselected);
        formdata.append('title',this.item.title);
        formdata.append('version',this.item.version);
        formdata.append('build',this.item.build);
        formdata.append('log',this.item.log);
        Axios.post('/api/upversion',formdata,{
          headers:{'Content-Type':'multipart/form-data'}
        }).then((res)=>{
          this.item = {};
          this.apkfile = null;
          this.selectkey();
          this.updateed = "";
          console.log(res)
        })
      },
      delversion(){
        Axios.get('/api/delversion?ipns='+this.keyselected+'&build='+this.item.build).then((res)=>{
          this.item = {};
          this.apkfile = null;
          this.selectkey();
          console.log(res)
        })
      },
    },
    filters:{
      dateT(timestamp){
        return new Date(timestamp * 1000).toLocaleString()
      }
    },
    created(){
      this.init();
      console.log()
    }
  }
</script>

<style>
</style>
