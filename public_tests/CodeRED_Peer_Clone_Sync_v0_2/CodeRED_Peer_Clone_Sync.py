#!/usr/bin/env python3
"""Code RED Peer Clone Sync v0.2 public test.
No dependencies. Proves two PCs can exchange clone/player state through one relay.
"""
import argparse, json, math, random, socket, socketserver, sys, threading, time
from pathlib import Path
APP="Code RED Peer Clone Sync v0.2"; PROTO="codered.peer.clone.v1"; PORT=47666
ROOT=Path(__file__).resolve().parent; RUNTIME=ROOT/"runtime"; RUNTIME.mkdir(exist_ok=True)
def ms(): return int(time.time()*1000)
def send(f,o): f.write((json.dumps(o,separators=(",",":"))+"\n").encode()); f.flush()
def log(name,o): (RUNTIME/name).open("a",encoding="utf-8").write(json.dumps(o,separators=(",",":"))+"\n")
class State:
    def __init__(s): s.lock=threading.RLock(); s.clients={}
class Server(socketserver.ThreadingTCPServer): allow_reuse_address=True; daemon_threads=True
class Handler(socketserver.BaseRequestHandler):
    def setup(s): s.cid=""; s.name=""; s.actor=""; s.file=s.request.makefile("rwb")
    def peers(s):
        with s.server.state.lock:
            return [{"client_id":k,"name":v["name"],"actor":v["actor"],"addr":v["addr"]} for k,v in s.server.state.clients.items()]
    def broadcast(s,o,self_too=False):
        with s.server.state.lock: vals=list(s.server.state.clients.values())
        for v in vals:
            if not self_too and v["id"]==s.cid: continue
            try: send(v["file"],o)
            except Exception: pass
    def handle(s):
        try:
            line=s.file.readline()
            if not line: return
            hello=json.loads(line.decode(errors="replace"))
            if hello.get("type")!="hello" or hello.get("protocol")!=PROTO:
                send(s.file,{"type":"error","error":"bad_hello_or_protocol","expected":PROTO}); return
            s.cid=str(hello.get("client_id") or f"peer_{random.randint(1000,9999)}")[:64]
            s.name=str(hello.get("name") or s.cid)[:64]; s.actor=str(hello.get("actor") or "ACTOR_player_jack")[:96]
            with s.server.state.lock:
                s.server.state.clients[s.cid]={"id":s.cid,"name":s.name,"actor":s.actor,"addr":f"{s.client_address[0]}:{s.client_address[1]}","file":s.file}
                roster=s.peers()
            print(f"[relay] joined {s.cid} {s.name} from {s.client_address[0]}:{s.client_address[1]}",flush=True)
            send(s.file,{"type":"welcome","protocol":PROTO,"client_id":s.cid,"roster":roster,"server_ms":ms()})
            s.broadcast({"type":"peer_joined","peer":s.cid,"roster":roster,"server_ms":ms()})
            while True:
                line=s.file.readline()
                if not line: break
                m=json.loads(line.decode(errors="replace")); t=m.get("type")
                if t=="bye": break
                if t=="ping": send(s.file,{"type":"pong","roster":s.peers(),"server_ms":ms()}); continue
                if t!="state": send(s.file,{"type":"error","error":f"unknown_type:{t}"}); continue
                m.update({"type":"state","protocol":PROTO,"client_id":s.cid,"name":s.name,"actor":s.actor,"relay_ms":ms()})
                log("relay_states.jsonl",m); s.broadcast(m)
        except Exception as e: print(f"[relay] error {s.cid}: {e}",flush=True)
        finally:
            with s.server.state.lock:
                if s.cid in s.server.state.clients: del s.server.state.clients[s.cid]
                roster=s.peers()
            if s.cid: s.broadcast({"type":"peer_left","client_id":s.cid,"roster":roster,"server_ms":ms()}); print(f"[relay] left {s.cid}",flush=True)
def host(bind="0.0.0.0",port=PORT):
    srv=Server((bind,port),Handler); srv.state=State(); print(f"# {APP} Relay\nlistening={bind}:{port}\nPress Ctrl+C to stop.",flush=True)
    try: srv.serve_forever(.25)
    except KeyboardInterrupt: print("\n[relay] stopping")
    finally: srv.shutdown(); srv.server_close()
class Client:
    def __init__(s,host,port,cid,name,actor,rate): s.host=host; s.port=port; s.cid=cid; s.name=name; s.actor=actor; s.rate=max(1,min(30,rate)); s.remote={}; s.stop=False; s.t0=time.time()
    def connect(s):
        s.sock=socket.create_connection((s.host,s.port),timeout=8); s.sock.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1); s.file=s.sock.makefile("rwb")
        send(s.file,{"type":"hello","protocol":PROTO,"client_id":s.cid,"name":s.name,"actor":s.actor,"client_ms":ms()})
        w=json.loads(s.file.readline().decode()); print(f"[{s.cid}] connected roster={len(w.get('roster',[]))}",flush=True); threading.Thread(target=s.rx,daemon=True).start()
    def rx(s):
        while not s.stop:
            line=s.file.readline()
            if not line: break
            m=json.loads(line.decode(errors="replace")); t=m.get("type")
            if t=="state" and m.get("client_id")!=s.cid:
                rid=m.get("client_id"); s.remote[rid]=m; log(f"{s.cid}_remote_states.jsonl",m)
                print(f"[{s.cid}] remote {rid}: pos=({m.get('x'):.2f},{m.get('y'):.2f},{m.get('z'):.2f}) heading={m.get('heading'):.1f} action={m.get('action')}",flush=True)
            elif t in ("peer_joined","peer_left"): print(f"[{s.cid}] {t}: roster={len(m.get('roster',[]))}",flush=True)
            elif t=="error": print(f"[{s.cid}] relay error: {m}",flush=True)
    def state(s,n):
        a=(time.time()-s.t0)*.8+math.radians(sum(map(ord,s.cid))%360); r=8+(sum(map(ord,s.cid))%5)
        act="walk" if n%40<30 else "idle"
        return {"type":"state","protocol":PROTO,"client_ms":ms(),"seq":n,"x":round(math.cos(a)*r,3),"y":round(math.sin(a)*r,3),"z":0.0,"heading":round((math.degrees(a)+90)%360,2),"speed":1.6 if act=="walk" else 0,"health":100,"weapon":"WEAPON_REVOLVER","action":act}
    def run(s,seconds=0):
        s.connect(); end=time.time()+seconds if seconds else 0; n=0
        try:
            while not s.stop and (not end or time.time()<end): n+=1; send(s.file,s.state(n)); time.sleep(1/s.rate)
        except KeyboardInterrupt: pass
        finally:
            s.stop=True
            try: send(s.file,{"type":"bye","client_ms":ms()}); s.sock.close()
            except Exception: pass
def ips():
    out=[]
    try:
        for x in socket.gethostbyname_ex(socket.gethostname())[2]:
            if x not in out: out.append(x)
    except Exception: pass
    try:
        s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.connect(("8.8.8.8",80)); x=s.getsockname()[0]; s.close()
        if x not in out: out.append(x)
    except Exception: pass
    if "127.0.0.1" not in out: out.append("127.0.0.1")
    return out
def doctor():
    print(f"# {APP} Doctor\npython={sys.version.split()[0]}\nport={PORT}/tcp\nlocal_ip_candidates:")
    for x in ips(): print(" -",x)
    print("Give tester your LAN/VPN IP, not 127.0.0.1. Allow Python through Firewall if needed.")
def selftest():
    port=random.randint(49100,59900); srv=Server(("127.0.0.1",port),Handler); srv.state=State(); threading.Thread(target=srv.serve_forever,daemon=True).start(); time.sleep(.2)
    a=Client("127.0.0.1",port,"player_a","Player A","ACTOR_player_jack",12); b=Client("127.0.0.1",port,"player_b","Player B","ACTOR_mpplayer01",12)
    ta=threading.Thread(target=a.run,args=(2,),daemon=True); tb=threading.Thread(target=b.run,args=(2,),daemon=True); ta.start(); tb.start(); ta.join(4); tb.join(4); time.sleep(.4)
    ok=bool(a.remote.get("player_b")) and bool(b.remote.get("player_a")); print(f"# Selftest result: {'PASS' if ok else 'FAIL'}\nplayer_a saw player_b: {bool(a.remote.get('player_b'))}\nplayer_b saw player_a: {bool(b.remote.get('player_a'))}")
    srv.shutdown(); srv.server_close(); return 0 if ok else 1
def main():
    p=argparse.ArgumentParser(description=APP); sub=p.add_subparsers(dest="cmd",required=True)
    h=sub.add_parser("host"); h.add_argument("--bind",default="0.0.0.0"); h.add_argument("--port",type=int,default=PORT)
    c=sub.add_parser("client"); c.add_argument("--host",default="127.0.0.1"); c.add_argument("--port",type=int,default=PORT); c.add_argument("--client-id",default="player_a"); c.add_argument("--name",default="CodeRED Player"); c.add_argument("--actor",default="ACTOR_player_jack"); c.add_argument("--rate",type=float,default=15); c.add_argument("--seconds",type=float,default=0)
    sub.add_parser("doctor"); sub.add_parser("selftest"); a=p.parse_args()
    if a.cmd=="host": host(a.bind,a.port)
    elif a.cmd=="client": Client(a.host,a.port,a.client_id,a.name,a.actor,a.rate).run(a.seconds)
    elif a.cmd=="doctor": doctor()
    elif a.cmd=="selftest": return selftest()
    return 0
if __name__=="__main__": raise SystemExit(main())
