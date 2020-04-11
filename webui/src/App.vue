<template>
  <div id="app">
    <div>
      <img alt="Vue logo" src="./assets/logo.png" class="logo">
      <div id="apkqrCode" ref="apkqrCodeDiv" class="qr"></div>
    </div>
    <h2>Download IPFS APP<br>{{ title }}</h2>
    <b-form-select v-model="lastversion" :options="updates" @change="selectver"></b-form-select>
    <p>Version: {{item.version}}</p>
    <p>Release Date: {{item.datetime | dateT}}</p>
    <p>Release Notes: <br><span v-html="item.log" class="log"></span></p>
    <p>
      <b-button size="lg" variant="success" @click="download">DownLoad</b-button>
    </p>
    <p></p>
  </div>
</template>

<script>
  import Axios from 'axios';
  import QRCode from 'qrcodejs2';
export default {
  name: 'App',
  data(){
    return {
      updatejson:[],
      updates:[],
      lastversion:null,
      title:"",
      item:{
        "title": "",
        "version": "",
        "build": "",
        "apk_file": "",
        "log": "",
        "datetime": "",
      },
    }
  },
  methods:{
    init(){
      Axios.get('./update.json').then((res)=>{
        this.title = res.data.title;
        this.updatejson = res.data.data;
        for (let i = this.updatejson.length - 1; i >=0 ; i--) {
          let t =this.updatejson[i]['title'] + '['+ this.updatejson[i]['version']+']';
          if (this.updatejson[i]['build']===res.data.last){
            t+=' (new)';
            this.lastversion = i;
          }
          this.updates.push({
            text:t,
            value:i,
          })
        }
        this.selectver();
        this.$refs.apkqrCodeDiv.innerHTML = '';
        new QRCode(this.$refs.apkqrCodeDiv, {
          text: window.location.href,
          width: 120,
          height: 120,
          colorDark: "#333333",
          colorLight: "#ffffff",
          correctLevel: QRCode.CorrectLevel.L
        });
      });
    },
    selectver(){
      this.item = this.updatejson[this.lastversion];
      this.item.log = this.item.log.replace(/[\n\r]/g,'<br>')
    },
    download(){
      window.location.href = this.item.apk_file;
    }
  },
  filters:{
    dateT(timestamp){
      return new Date(timestamp * 1000).toLocaleString()
    }
  },
  created(){
    this.init();
  },
  watch: {
    title() {
      document.title = this.title !=="" ? this.title : "VideoShare";
    }
  }
}
</script>

<style>
#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #2c3e50;
  margin-top: 20px;
}
  .logo{
    display: inline-block;
    width: 120px;
  }
  .qr{
    display: inline-block;
    width: 120px;
    vertical-align: middle;
  }
  .log{
    display: inline-block;
    max-height: 3em;
    overflow: hidden;
  }
</style>
