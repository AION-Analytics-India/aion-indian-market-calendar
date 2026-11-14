"""Loopback HTTPS fixture with in-memory OpenSSL keys, including Windows.

This is test-only infrastructure. It neither changes client TLS verification
nor uses a Windows certificate store. No private key is serialized to a file.
The production updater does not import or depend on this helper.
"""
from pathlib import Path
import select
import socket
import threading
import time


class FixtureServer:
    def __init__(self, root, key, cert, requests):
        from OpenSSL import SSL, crypto
        self.SSL=SSL;self.root=Path(root);self.requests=requests;self.stopped=threading.Event()
        self.context=SSL.Context(SSL.TLS_SERVER_METHOD)
        self.context.set_min_proto_version(SSL.TLS1_2_VERSION)
        self.context.use_certificate(crypto.X509.from_cryptography(cert))
        self.context.use_privatekey(crypto.PKey.from_cryptography_key(key))
        self.context.check_privatekey()
        self.socket=socket.socket();self.socket.bind(('127.0.0.1',0));self.socket.listen(8);self.socket.settimeout(.2)
        self.port=self.socket.getsockname()[1];self.client=None
        self.thread=threading.Thread(target=self.serve,daemon=True);self.thread.start()

    def wait(self, operation, raw, deadline):
        while not self.stopped.is_set():
            try:return operation()
            except self.SSL.WantReadError:read,write=[raw],[]
            except self.SSL.WantWriteError:read,write=[],[raw]
            remaining=deadline-time.monotonic()
            if remaining<=0:raise TimeoutError('Fixture TLS operation exceeded 10 seconds')
            select.select(read,write,[],min(.2,remaining))
        raise ConnectionAbortedError('Fixture closing')

    def serve(self):
        while not self.stopped.is_set():
            try:raw,_=self.socket.accept()
            except socket.timeout:continue
            except OSError:break
            self.client=raw;raw.setblocking(False)
            connection=self.SSL.Connection(self.context,raw);connection.set_accept_state()
            try:
                deadline=time.monotonic()+10
                self.wait(connection.do_handshake,raw,deadline)
                data=b''
                while b'\r\n\r\n' not in data:
                    part=self.wait(lambda:connection.recv(1024),raw,deadline)
                    if not part:raise ConnectionError('Fixture request ended early')
                    data+=part
                    if len(data)>8192:raise ValueError('Fixture request too large')
                method,name,_=data.split(b'\r\n',1)[0].decode('ascii').split(' ')
                name=name.removeprefix('/')
                valid=method=='GET' and name==Path(name).name and name and not any(c in name for c in '\\:%?')
                target=self.root/name if valid else self.root/'missing'
                found=valid and target.is_file();body=target.read_bytes() if found else b'Unavailable'
                header=('HTTP/1.1 '+('200 OK' if found else '404 Not Found')+'\r\nContent-Length: '+str(len(body))+'\r\nConnection: close\r\n\r\n').encode()
                output=memoryview(header+body);sent=0
                while sent<len(output):
                    sent+=self.wait(lambda:connection.send(output[sent:]),raw,deadline)
                self.requests.append({'path':name})
                try:self.wait(connection.shutdown,raw,deadline)
                except (OSError,self.SSL.Error):pass
            except (OSError,self.SSL.Error,ValueError) as exc:
                self.requests.append({'fixture_error':type(exc).__name__})
            finally:
                raw.close();self.client=None

    def close(self):
        self.stopped.set();self.socket.close()
        client=self.client
        if client:
            try:client.shutdown(socket.SHUT_RDWR)
            except OSError:pass
            client.close()
        self.thread.join(timeout=5)
        if self.thread.is_alive():raise RuntimeError('Fixture thread did not stop')
