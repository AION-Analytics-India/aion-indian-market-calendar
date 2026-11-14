"""Disposable native Windows HTTPS fixture. Private TLS key stays in memory.

No certificate-store registration, persisted PFX, password, TLS bypass or
system HTTP binding. The fixed PowerShell process receives a synthetic PFX
through stdin and imports it with EphemeralKeySet. Loopback and filenames only.
"""
import base64
import json
import os
from pathlib import Path
import subprocess
import threading

SCRIPT = r'''
$ErrorActionPreference='Stop'
[Console]::InputEncoding=[System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$d=[Console]::In.ReadLine() | ConvertFrom-Json
Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Net.Security;
using System.Text;
using System.Security.Authentication;
using System.Security.Cryptography.X509Certificates;
public static class CalendarTestTLS {
 public static void Run(string root, byte[] pfx) {
  using(var cert=new X509Certificate2(pfx,(string)null,X509KeyStorageFlags.EphemeralKeySet)) {
   Array.Clear(pfx,0,pfx.Length);
   var listener=new TcpListener(IPAddress.Loopback,0);listener.Start();
   Console.WriteLine("PORT:"+((IPEndPoint)listener.LocalEndpoint).Port);Console.Out.Flush();
   try {while(true) {
    using(var client=listener.AcceptTcpClient()) {
     client.ReceiveTimeout=10000;client.SendTimeout=10000;
     try {using(var tls=new SslStream(client.GetStream(),false)) {
      tls.ReadTimeout=10000;tls.WriteTimeout=10000;
      tls.AuthenticateAsServer(cert,false,SslProtocols.Tls12,false);
      var bytes=new MemoryStream();int b;int size=0;
      while((b=tls.ReadByte())!=-1) {
       bytes.WriteByte((byte)b);if(++size>8192)throw new IOException("Request too large");
       var data=bytes.GetBuffer();
       if(size>=4 && data[size-4]==13 && data[size-3]==10 && data[size-2]==13 && data[size-1]==10)break;
      }
      var line=Encoding.ASCII.GetString(bytes.ToArray()).Split('\r')[0].Split(' ');
      var name=line.Length==3 ? line[1].TrimStart('/') : "";
      bool valid=line.Length==3 && line[0]=="GET" && name.Length>0 &&
       name==Path.GetFileName(name) && name.IndexOfAny(new char[]{'\\',':','?','%'})<0;
      var file=Path.Combine(root,valid?name:"missing");
      bool found=valid && File.Exists(file);
      byte[] body=found?File.ReadAllBytes(file):Encoding.ASCII.GetBytes("Unavailable");
      var header=Encoding.ASCII.GetBytes("HTTP/1.1 "+(found?"200 OK":"404 Not Found")+
        "\r\nContent-Length: "+body.Length+"\r\nConnection: close\r\n\r\n");
      tls.Write(header,0,header.Length);tls.Write(body,0,body.Length);tls.Flush();
      Console.WriteLine("REQUEST:"+Convert.ToBase64String(Encoding.UTF8.GetBytes(name)));Console.Out.Flush();
     }}catch(IOException){}catch(AuthenticationException){}
    }
   }}finally{listener.Stop();}
  }
 }
}
'@
$bytes=[Convert]::FromBase64String($d.pfx)
$d.pfx=$null
[CalendarTestTLS]::Run($d.root,$bytes)
'''


class FixtureServer:
    def __init__(self, root, key, cert, requests):
        if os.name!='nt':raise NotImplementedError('Native Windows fixture only')
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.serialization import pkcs12
        pfx=pkcs12.serialize_key_and_certificates(b'isolated-test',key,cert,None,serialization.NoEncryption())
        exe=Path(os.environ['SYSTEMROOT'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
        encoded=base64.b64encode(SCRIPT.encode('utf-16-le')).decode('ascii')
        self.process=subprocess.Popen([str(exe),'-NoLogo','-NoProfile','-NonInteractive','-EncodedCommand',encoded],
                                      stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.process.stdin.write(json.dumps({'root':str(root),'pfx':base64.b64encode(pfx).decode()}).encode()+b'\n')
        self.process.stdin.close();del pfx
        self.port=None;ready=threading.Event()
        def read():
            for line in iter(self.process.stdout.readline,b''):
                if line.startswith(b'PORT:'):
                    self.port=int(line[5:]);ready.set()
                elif line.startswith(b'REQUEST:'):
                    requests.append({'path':base64.b64decode(line[8:].strip()).decode('utf-8')})
            ready.set()
        self.reader=threading.Thread(target=read,daemon=True);self.reader.start()
        if not ready.wait(40) or self.port is None:
            self.close()
            raise RuntimeError('Native ephemeral TLS fixture could not initialize; no TLS policy was weakened')

    def close(self):
        if self.process.poll() is None:
            subprocess.run([str(Path(os.environ['SYSTEMROOT'])/'System32/taskkill.exe'),'/PID',str(self.process.pid),'/T','/F'],
                           capture_output=True,timeout=15)
        self.process.wait(timeout=15);self.reader.join(timeout=5)
        self.process.stdout.close();self.process.stderr.close()
