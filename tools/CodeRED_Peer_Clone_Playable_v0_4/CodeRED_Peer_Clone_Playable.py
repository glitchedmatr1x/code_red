#!/usr/bin/env python3
"""Code RED Peer Clone Playable v0.4
Portable two-player sandbox plus bridge file outputs for the future in-game clone hook.
No third-party dependencies.
"""
import argparse, json, math, queue, random, socket, socketserver, sys, threading, time
from dataclasses import dataclass, asdict
from pathlib import Path
APP='Code RED Peer Clone Playable v0.4'; PROTO='codered.peer.clone.v1'; PORT=47666
ROOT=Path(__file__).resolve().parent; RUNTIME=ROOT/'runtime'; BRIDGE=ROOT/'bridge'
RUNTIME.mkdir(exist_ok=True); BRIDGE.mkdir(exist_ok=True)
def ms(): return int(time.time()*1000)
def send(f,o): f.write((json.dumps(o,separators=(',',':'))+'\n').encode()); f.flush()
def log(name,o): (RUNTIME/name).open('a',encoding='utf-8').write(json.dumps(o,separators=(',',':'))+'\n')
def atomic(path,o):
    path.parent.mkdir(exist_ok=True); tmp=path.with_suffix(path.suffix+'.tmp'); tmp.write_text(json.dumps(o,indent=2,sort_keys=True),encoding='utf-8'); tmp.replace(path)
class State:
    def __init__(s): s.lock=threading.RLock(); s.clients={}
class Server(socketserver.ThreadingTCPServer): allow_reuse_address=True; daemon_threads=True
class Handler(socketserver.BaseRequestHandler):
    def setup(s): s.cid=''; s.file=s.request.makefile('rwb')
    def roster(s):
        with s.server.state.lock:
            return [{'client_id':k,'name':v['name'],'actor':v['actor'],'color':v['color'],'addr':v['addr']} for k,v in s.server.state.clients.items()]
    def broadcast(s,o,self_too=False):
        with s.server.state.lock: vals=list(s.server.state.clients.values())
        for v in vals:
            if not self_too and v['id']==s.cid: continue
            try: send(v['file'],o)
            except Exception: pass
    def handle(s):
        try:
            line=s.file.readline()
            if not line: return
            h=json.loads(line.decode(errors='replace'))
            if h.get('type')!='hello' or h.get('protocol')!=PROTO:
                send(s.file,{'type':'error','error':'bad protocol','expected':PROTO}); return
            s.cid=str(h.get('client_id') or f'peer_{random.randint(1000,9999)}')[:64]
            name=str(h.get('name') or s.cid)[:64]; actor=str(h.get('actor') or 'ACTOR_player_jack')[:96]; color=str(h.get('color') or 'red')[:32]
            with s.server.state.lock:
                s.server.state.clients[s.cid]={'id':s.cid,'name':name,'actor':actor,'color':color,'addr':f'{s.client_address[0]}:{s.client_address[1]}','file':s.file}
                roster=s.roster()
            print(f'[relay] joined {s.cid} {name} from {s.client_address[0]}:{s.client_address[1]}',flush=True)
            send(s.file,{'type':'welcome','protocol':PROTO,'client_id':s.cid,'roster':roster,'server_ms':ms()})
            s.broadcast({'type':'peer_joined','peer':s.cid,'roster':roster,'server_ms':ms()})
            while True:
                line=s.file.readline()
                if not line: break
                m=json.loads(line.decode(errors='replace')); t=m.get('type')
                if t=='bye': break
                if t=='ping': send(s.file,{'type':'pong','roster':s.roster(),'server_ms':ms()}); continue
                if t not in {'state','event','chat'}: send(s.file,{'type':'error','error':f'unknown type {t}'}); continue
                m.update({'protocol':PROTO,'client_id':s.cid,'relay_ms':ms()}); log('relay_messages.jsonl',m); s.broadcast(m)
        except Exception as e: print(f'[relay] error {s.cid or s.client_address}: {e}',flush=True)
        finally:
            if s.cid:
                with s.server.state.lock:
                    s.server.state.clients.pop(s.cid,None); roster=s.roster()
                s.broadcast({'type':'peer_left','client_id':s.cid,'roster':roster,'server_ms':ms()}); print(f'[relay] left {s.cid}',flush=True)
def start_relay(bind,port):
    srv=Server((bind,port),Handler); srv.state=State(); th=threading.Thread(target=srv.serve_forever,kwargs={'poll_interval':.25},daemon=True); srv.th=th; th.start(); print(f'# {APP} Relay\nlistening={bind}:{port}\n',flush=True); return srv
def stop_relay(srv): srv.shutdown(); srv.server_close(); getattr(srv,'th',threading.Thread()).join(.5)
def host(bind,port):
    srv=start_relay(bind,port); print('Keep this window open. Press Ctrl+C to stop.',flush=True)
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt: print('\n[relay] stopping')
    finally: stop_relay(srv)
def ips():
    out=[]
    try:
        for x in socket.gethostbyname_ex(socket.gethostname())[2]:
            if x not in out: out.append(x)
    except Exception: pass
    try:
        s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.connect(('8.8.8.8',80)); x=s.getsockname()[0]; s.close()
        if x not in out: out.append(x)
    except Exception: pass
    if '127.0.0.1' not in out: out.append('127.0.0.1')
    return out
def doctor():
    print(f'# {APP} Doctor\npython={sys.version.split()[0]}\ndefault_port={PORT}/tcp\nlocal_ip_candidates:')
    for x in ips(): print(' -',x)
    print('\nGive tester your LAN/VPN IP, not 127.0.0.1. Allow Python through Firewall if needed.')
    print('\nBridge output folder:',BRIDGE)
    print('Future game hook files: bridge/local_player_state.json, bridge/remote_players_state.json, bridge/bridge_status.json')
@dataclass
class Peer:
    client_id:str; name:str='Remote'; actor:str='ACTOR_mpplayer01'; color:str='orange'; x:float=0; y:float=0; z:float=0; heading:float=0; action:str='idle'; health:int=100; last_ms:int=0; pulse_id:int=0
class Client:
    def __init__(s,host,port,cid,name,actor,color): s.host=host; s.port=port; s.cid=cid; s.name=name; s.actor=actor; s.color=color; s.sock=None; s.file=None; s.inbox=queue.Queue(); s.connected=False; s.stop=False
    def connect(s):
        s.sock=socket.create_connection((s.host,s.port),timeout=8); s.sock.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1); s.file=s.sock.makefile('rwb')
        send(s.file,{'type':'hello','protocol':PROTO,'client_id':s.cid,'name':s.name,'actor':s.actor,'color':s.color,'client_ms':ms()})
        deadline=time.time()+8; welcome=None
        while time.time()<deadline:
            line=s.file.readline()
            if not line: break
            m=json.loads(line.decode(errors='replace'))
            if m.get('type')=='welcome': welcome=m; break
            s.inbox.put(m)
        if not welcome: raise RuntimeError('Relay did not send welcome before timeout')
        s.connected=True; s.inbox.put(welcome); threading.Thread(target=s.rx,daemon=True).start()
    def rx(s):
        try:
            while not s.stop and s.file:
                line=s.file.readline()
                if not line: break
                s.inbox.put(json.loads(line.decode(errors='replace')))
        except Exception as e: s.inbox.put({'type':'local_error','error':str(e)})
        finally: s.connected=False
    def send_state(s,o):
        if s.file and s.connected: send(s.file,o)
    def send_event(s,o):
        if s.file and s.connected: send(s.file,o)
    def close(s):
        s.stop=True
        try:
            if s.file: send(s.file,{'type':'bye','client_ms':ms()})
        except Exception: pass
        try:
            if s.sock: s.sock.close()
        except Exception: pass
class Headless(Client):
    def __init__(s,*a,style='circle',**k): super().__init__(*a,**k); s.remote={}; s.style=style
    def state(s,n):
        a=time.time()*.9+math.radians(sum(map(ord,s.cid))%360); r=120 if s.style=='circle' else 80+40*math.sin(time.time())
        return {'type':'state','protocol':PROTO,'client_ms':ms(),'seq':n,'name':s.name,'actor':s.actor,'color':s.color,'x':round(math.cos(a)*r,2),'y':round(math.sin(a)*r,2),'z':0.0,'heading':round((math.degrees(a)+90)%360,2),'action':'walk','health':100,'pulse_id':0}
    def run(s,seconds=2,rate=12):
        s.connect(); start=time.time(); n=0
        while not s.stop and (seconds<=0 or time.time()-start<seconds):
            n+=1; s.send_state(s.state(n))
            while True:
                try: m=s.inbox.get_nowait()
                except queue.Empty: break
                if m.get('type')=='state' and m.get('client_id')!=s.cid: s.remote[m['client_id']]=m
            time.sleep(1/rate)
        s.close()
def selftest():
    port=random.randint(49100,59900); srv=start_relay('127.0.0.1',port); time.sleep(.2)
    a=Headless('127.0.0.1',port,'player_a','Player A','ACTOR_player_jack','red'); b=Headless('127.0.0.1',port,'player_b','Player B','ACTOR_mpplayer01','cyan')
    ta=threading.Thread(target=a.run); tb=threading.Thread(target=b.run); ta.start(); tb.start(); ta.join(5); tb.join(5); time.sleep(.2); stop_relay(srv)
    ok_a='player_b' in a.remote; ok_b='player_a' in b.remote; print(f'# Selftest result: {"PASS" if ok_a and ok_b else "FAIL"}\nplayer_a saw player_b: {ok_a}\nplayer_b saw player_a: {ok_b}'); return 0 if ok_a and ok_b else 1
def run_bot(args):
    bot=Headless(args.host,args.port,args.client_id,args.name,args.actor,args.color,style=args.style); print(f'# {APP} bot\nconnecting={args.host}:{args.port}\nclient_id={args.client_id}\nPress Ctrl+C to stop.')
    try: bot.run(seconds=0,rate=args.rate)
    except KeyboardInterrupt: bot.close()
def watch_bridge():
    print(f'# {APP} Bridge Watch\nfolder={BRIDGE}\nPress Ctrl+C to stop.\n'); last=''
    try:
        while True:
            data={}
            for n in ['bridge_status.json','local_player_state.json','remote_players_state.json']:
                p=BRIDGE/n; data[n]=json.loads(p.read_text('utf-8')) if p.exists() else {}
            txt=json.dumps(data,indent=2,sort_keys=True)
            if txt!=last: print(txt+'\n'+'-'*60); last=txt
            time.sleep(1)
    except KeyboardInterrupt: pass
def playable(args):
    try: import tkinter as tk
    except Exception as e: print('Tkinter is required:',e); return
    relay=None; bot=None
    if args.start_relay: relay=start_relay(args.bind,args.port); time.sleep(.25)
    if args.start_bot:
        bot=Headless('127.0.0.1' if args.start_relay else args.host,args.port,'bot_echo','Echo Bot','ACTOR_mpplayer02','orange'); threading.Thread(target=bot.run,kwargs={'seconds':0,'rate':12},daemon=True).start(); time.sleep(.25)
    c=Client(args.host,args.port,args.client_id,args.name,args.actor,args.color)
    try: c.connect()
    except Exception:
        if bot: bot.close()
        if relay: stop_relay(relay)
        raise
    root=tk.Tk(); root.title(f'{APP} - {args.name}'); root.geometry('960x720'); root.configure(bg='#111')
    canvas=tk.Canvas(root,width=920,height=620,bg='#141414',highlightthickness=1,highlightbackground='#660000'); canvas.pack(padx=10,pady=10)
    status=tk.Label(root,text='Connecting...',fg='#eee',bg='#111',anchor='w'); status.pack(fill='x',padx=12)
    tk.Label(root,text='WASD/arrows move | Shift boost | Space pulse | B bridge status | Q quit',fg='#ff5555',bg='#111',anchor='w').pack(fill='x',padx=12)
    player={'x':0.0,'y':0.0,'z':0.0,'heading':0.0,'health':100,'pulse_id':0,'action':'idle'}; keys=set(); rem={}; trail=[]; msgs=[]; last_send=0; seq=0; flash=0
    def w2s(x,y): return 460+x,310-y
    def bridge():
        atomic(BRIDGE/'local_player_state.json',{'schema':'codered.bridge.local_player.v1','client_id':c.cid,'name':c.name,'actor':c.actor,'color':c.color,'updated_ms':ms(),**player})
        atomic(BRIDGE/'remote_players_state.json',{'schema':'codered.bridge.remote_players.v1','updated_ms':ms(),'players':{k:asdict(v) for k,v in rem.items()}})
        atomic(BRIDGE/'bridge_status.json',{'schema':'codered.bridge.status.v1','app':APP,'connected':c.connected,'host':args.host,'port':args.port,'client_id':c.cid,'remote_count':len(rem),'updated_ms':ms()})
    def draw_grid():
        for gx in range(-400,401,100): canvas.create_line(w2s(gx,-300),w2s(gx,300),fill='#282828')
        for gy in range(-300,301,100): canvas.create_line(w2s(-400,gy),w2s(400,gy),fill='#282828')
        canvas.create_text(12,12,text='CODE RED PEER CLONE PLAYABLE v0.4',fill='#ff3333',anchor='nw',font=('Consolas',14,'bold'))
    def draw_actor(x,y,h,color,label,remote=False,pulse=0):
        sx,sy=w2s(x,y); r=12 if remote else 14; canvas.create_oval(sx-r,sy-r,sx+r,sy+r,fill=color,outline='#fff' if not remote else '#aaa',width=2)
        hx=sx+math.cos(math.radians(h-90))*24; hy=sy+math.sin(math.radians(h-90))*24; canvas.create_line(sx,sy,hx,hy,fill='#fff',width=2); canvas.create_text(sx,sy-25,text=label,fill='#fff',font=('Consolas',10,'bold'))
        if pulse:
            pr=24+((time.time()*8)%1)*36; canvas.create_oval(sx-pr,sy-pr,sx+pr,sy+pr,outline=color,width=2)
    def kd(e):
        nonlocal flash
        k=e.keysym.lower()
        if k=='q': close(); return
        if k=='space': player['pulse_id']+=1; player['action']='pulse'; c.send_event({'type':'event','event':'pulse','pulse_id':player['pulse_id'],'x':player['x'],'y':player['y'],'client_ms':ms()})
        if k=='b': bridge(); flash=time.time()+1.5
        keys.add(k)
    def ku(e): keys.discard(e.keysym.lower())
    def inbox():
        while True:
            try: m=c.inbox.get_nowait()
            except queue.Empty: break
            t=m.get('type')
            if t=='state' and m.get('client_id')!=c.cid:
                rid=m.get('client_id'); p=rem.get(rid) or Peer(rid)
                p.name=str(m.get('name') or rid); p.actor=str(m.get('actor') or p.actor); p.color=str(m.get('color') or p.color); p.x=float(m.get('x',p.x)); p.y=float(m.get('y',p.y)); p.z=float(m.get('z',p.z)); p.heading=float(m.get('heading',p.heading)); p.action=str(m.get('action') or 'idle'); p.health=int(m.get('health',100)); p.pulse_id=int(m.get('pulse_id',p.pulse_id)); p.last_ms=ms(); rem[rid]=p; log(f'{c.cid}_remote_playable.jsonl',m)
            elif t=='event' and m.get('client_id')!=c.cid: msgs.append((time.time(),f"{m.get('client_id')} {m.get('event')}"))
            elif t in {'welcome','peer_joined','peer_left','local_error','error'}: msgs.append((time.time(),json.dumps(m)[:120]))
    def tick():
        nonlocal last_send,seq
        inbox(); speed=4.5 if any(k in keys for k in ['shift_l','shift_r','shift']) else 2.5; dx=dy=0
        if 'w' in keys or 'up' in keys: dy+=speed
        if 's' in keys or 'down' in keys: dy-=speed
        if 'a' in keys or 'left' in keys: dx-=speed
        if 'd' in keys or 'right' in keys: dx+=speed
        if dx or dy:
            player['x']=max(-420,min(420,player['x']+dx)); player['y']=max(-280,min(280,player['y']+dy)); player['heading']=(math.degrees(math.atan2(dx,dy))+360)%360; player['action']='boost' if speed>3 else 'walk'; trail.append((player['x'],player['y'],time.time()))
        else:
            if player['action']!='pulse': player['action']='idle'
        if player['action']=='pulse' and random.random()<.15: player['action']='idle'
        trail[:]=[p for p in trail if time.time()-p[2]<1.5]
        if time.time()-last_send>=1/max(1,args.rate):
            seq+=1; last_send=time.time(); c.send_state({'type':'state','protocol':PROTO,'client_ms':ms(),'seq':seq,'name':c.name,'actor':c.actor,'color':c.color,'x':round(player['x'],2),'y':round(player['y'],2),'z':0.0,'heading':round(player['heading'],2),'action':player['action'],'health':player['health'],'pulse_id':player['pulse_id']}); bridge()
        canvas.delete('all'); draw_grid()
        for x,y,_ in trail:
            sx,sy=w2s(x,y); canvas.create_oval(sx-3,sy-3,sx+3,sy+3,fill='#772222',outline='')
        draw_actor(player['x'],player['y'],player['heading'],c.color,f'YOU {c.name}',False,player['pulse_id'] if player['action']=='pulse' else 0)
        for rid,p in list(rem.items()):
            stale=ms()-p.last_ms>2500; draw_actor(p.x,p.y,p.heading,p.color if not stale else '#555',f"{p.name}{' (stale)' if stale else ''}",True,p.pulse_id if p.action=='pulse' else 0)
        y=40
        for ts,msg in msgs[-6:]:
            if time.time()-ts<8: canvas.create_text(12,y,text=msg,fill='#ddd',anchor='nw',font=('Consolas',9)); y+=16
        if time.time()<flash: canvas.create_text(908,12,text='BRIDGE FILES UPDATED',fill='#66ff66',anchor='ne',font=('Consolas',11,'bold'))
        status.config(text=f"Connected to {args.host}:{args.port} as {c.cid} | remotes={len(rem)} | bridge=bridge/ | pos=({player['x']:.0f},{player['y']:.0f}) action={player['action']}")
        root.after(16,tick)
    def close():
        bridge(); c.close();
        if bot: bot.close()
        if relay: stop_relay(relay)
        root.destroy()
    root.bind('<KeyPress>',kd); root.bind('<KeyRelease>',ku); root.protocol('WM_DELETE_WINDOW',close); tick(); root.mainloop()
def main():
    p=argparse.ArgumentParser(description=APP); sub=p.add_subparsers(dest='cmd',required=True)
    h=sub.add_parser('host'); h.add_argument('--bind',default='0.0.0.0'); h.add_argument('--port',type=int,default=PORT)
    pl=sub.add_parser('play'); pl.add_argument('--host',default='127.0.0.1'); pl.add_argument('--bind',default='0.0.0.0'); pl.add_argument('--port',type=int,default=PORT); pl.add_argument('--client-id',default='player_a'); pl.add_argument('--name',default='Player A'); pl.add_argument('--actor',default='ACTOR_player_jack'); pl.add_argument('--color',default='red'); pl.add_argument('--rate',type=float,default=20); pl.add_argument('--start-relay',action='store_true'); pl.add_argument('--start-bot',action='store_true')
    b=sub.add_parser('bot'); b.add_argument('--host',default='127.0.0.1'); b.add_argument('--port',type=int,default=PORT); b.add_argument('--client-id',default='bot_echo'); b.add_argument('--name',default='Echo Bot'); b.add_argument('--actor',default='ACTOR_mpplayer02'); b.add_argument('--color',default='orange'); b.add_argument('--style',default='circle',choices=['circle','wave']); b.add_argument('--rate',type=float,default=12)
    sub.add_parser('doctor'); sub.add_parser('selftest'); sub.add_parser('watch-bridge'); a=p.parse_args()
    if a.cmd=='host': host(a.bind,a.port)
    elif a.cmd=='play': playable(a)
    elif a.cmd=='bot': run_bot(a)
    elif a.cmd=='doctor': doctor()
    elif a.cmd=='selftest': return selftest()
    elif a.cmd=='watch-bridge': watch_bridge()
    return 0
if __name__=='__main__': raise SystemExit(main())
