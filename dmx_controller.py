"""
AZHYRIA - Live Light Board
Version : v22  |  2026-05-21 06:22
Driver  : ftd2xx (D2XX) — ENTTEC Open DMX USB
MIDI    : mido + LoopBe1
"""

import tkinter as tk
import math
from tkinter import ttk, messagebox, filedialog
import threading, time, traceback, json

try:
    import ftd2xx as ftd
    # Vérifie que les DLLs sont vraiment chargées
    ftd.createDeviceInfoList()
    FTD2XX_OK = True
except Exception:
    FTD2XX_OK = False
    ftd = None

try:
    import mido
    try:
        mido.get_input_names()
        MIDO_OK = True
    except Exception as _e:
        print(f"Backend MIDI non disponible : {_e}")
        MIDO_OK = False; mido = None
except ImportError:
    MIDO_OK = False; mido = None

BG        = "#0a0a0f"
CARD      = "#13131c"
ACC       = "#e8e0ff"
DIM_COLOR = "#8888aa"
BAR_W=5; BAR_MAXH=70; BAR_GAP=3; N_SPOTS=9
NOTE_NAMES = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]

def midi_note_name(n):
    return f"{NOTE_NAMES[n%12]}{(n//12)-1}"

def note_name_to_midi(s):
    s = s.strip().upper()
    for i in range(len(NOTE_NAMES)-1,-1,-1):
        nm = NOTE_NAMES[i]
        if s.startswith(nm):
            rest = s[len(nm):]
            try: return (int(rest)+1)*12+i
            except ValueError: return None
    return None


class EnttecOpenDMX:
    def __init__(self):
        self.dev=None; self.running=False
        self.universe=bytearray(513)
        self._lock=threading.Lock(); self._thread=None

    def list_devices(self):
        if not FTD2XX_OK: return []
        try:
            nb=ftd.createDeviceInfoList()
            return [(i, ftd.getDeviceInfoDetail(i).get('description',b'').decode(errors='ignore') or f"Device {i}") for i in range(nb)]
        except: return []

    def connect(self, idx):
        try:
            self.dev=ftd.open(idx)
            self.dev.resetDevice(); self.dev.setBaudRate(250000)
            self.dev.setDataCharacteristics(ftd.defines.BITS_8,ftd.defines.STOP_BITS_2,ftd.defines.PARITY_NONE)
            self.dev.setFlowControl(ftd.defines.FLOW_NONE,0,0)
            self.dev.setTimeouts(1000,1000)
            self.dev.purge(ftd.defines.PURGE_RX|ftd.defines.PURGE_TX)
            self.running=True
            self._thread=threading.Thread(target=self._loop,daemon=True); self._thread.start()
            return True
        except Exception as e: print(f"Erreur: {e}"); traceback.print_exc(); return False

    def disconnect(self):
        self.running=False
        if self._thread: self._thread.join(timeout=2)
        try:
            if self.dev: self.dev.close()
        except: pass
        self.dev=None

    def set_channels(self, ch, d, r, g, b, s=0, offsets=None):
        with self._lock:
            if offsets:
                vals=[d,r,g,b,s]
                for i,v in enumerate(vals):
                    c=ch+offsets[i]
                    if 1<=c<=512: self.universe[c]=max(0,min(255,v))
            else:
                self.universe[ch]=max(0,min(255,d)); self.universe[ch+1]=max(0,min(255,r))
                self.universe[ch+2]=max(0,min(255,g)); self.universe[ch+3]=max(0,min(255,b))
                self.universe[ch+4]=max(0,min(255,s))

    def _loop(self):
        while self.running and self.dev:
            try:
                self.dev.setBreakOn(); time.sleep(0.001)
                self.dev.setBreakOff(); time.sleep(0.0002)
                with self._lock: data=bytes(self.universe)
                self.dev.write(data); time.sleep(0.025)
            except Exception as e: print(f"Erreur envoi: {e}"); break


class SpotWidget:
    WIDGET_W=145

    def __init__(self, parent, index, default_ch):
        self.index=index; self._selected=False
        self.ch_var=tk.IntVar(value=default_ch)
        self.dim=255; self.r=0; self.g=0; self.b=0

        self.enabled=True
        # Offsets sous-canaux DMX : DIM, R, G, B (relatifs à ch_var)
        self.ch_offsets=[tk.IntVar(value=i) for i in range(5)]
        self.frame=tk.Frame(parent,bg=CARD,width=self.WIDGET_W)
        self.frame.pack_propagate(True); self.frame.pack(side="left",padx=5,pady=4)

        self.name_var=tk.StringVar(value=f"SPOT {index+1}")
        self.name_lbl=tk.Label(self.frame,textvariable=self.name_var,
                               font=("Courier New",8,"bold"),
                               fg="#ffffff",bg=CARD,cursor="hand2")
        self.name_lbl.pack(pady=(6,2))
        self._bind_click(self.name_lbl)

        self._bind_click(self.frame)

        viz=tk.Frame(self.frame,bg=CARD,width=self.WIDGET_W-10,height=80)
        viz.pack_propagate(False); viz.pack()
        self._bind_click(viz)
        self.canvas=tk.Canvas(viz,width=70,height=76,bg=CARD,highlightthickness=0)
        self.canvas.pack(side="left",padx=(4,4))
        self.bulb=self.canvas.create_oval(3,5,67,71,fill="#000000",outline="#555566",width=1)

        bar_canvas_w=5*BAR_W+4*BAR_GAP+14
        self.bar_canvas=tk.Canvas(viz,width=bar_canvas_w,height=76,bg=CARD,highlightthickness=0)
        self.bar_canvas.pack(side="left",padx=(0,4))
        self._bind_click(self.canvas)
        self._bind_click(self.bar_canvas)
        self.bars=[]; self.bar_xs=[]
        for i,(col,lbl) in enumerate(zip(["#ffffff","#ff2244","#22cc66","#4488ff","#ffcc44"],["D","R","G","B","S"])):
            x=4+i*(BAR_W+BAR_GAP); self.bar_xs.append(x)
            self.bar_canvas.create_rectangle(x,2,x+BAR_W,2+BAR_MAXH,fill="#1e1e2e",outline="")
            bar=self.bar_canvas.create_rectangle(x,2+BAR_MAXH,x+BAR_W,2+BAR_MAXH,fill=col,outline="")
            self.bars.append(bar)
            self.bar_canvas.create_text(x+BAR_W//2,2+BAR_MAXH+3,text=lbl,fill="#ffffff",font=("Courier New",7),anchor="n")

        # Canal DMX (affiché ici mais éditable dans config)
        # Canal DMX masqué dans LIVE (visible dans CONFIG)
        self._ch_row=tk.Frame(self.frame,bg=CARD)
        self._ch_row.pack(pady=(4,0))
        ch_lbl_txt=tk.Label(self._ch_row,text="CH:",font=("Courier New",8),fg=DIM_COLOR,bg=CARD)
        ch_lbl_txt.pack(side="left")
        self._bind_click(ch_lbl_txt)
        self.ch_lbl=tk.Label(self._ch_row,textvariable=self.ch_var,font=("Courier New",8,"bold"),fg=ACC,bg=CARD,width=4)
        self.ch_lbl.pack(side="left")
        self._bind_click(self.ch_lbl)
        self._ch_row.pack_forget()  # caché par défaut



    def _rename_popup(self):
        popup=tk.Toplevel()
        popup.title(""); popup.resizable(False,False)
        popup.configure(bg=CARD)
        popup.grab_set()
        popup.geometry("240x90")

        # Centrage sur le spot
        self.frame.update_idletasks()
        x=self.frame.winfo_rootx()
        y=self.frame.winfo_rooty()-95
        popup.geometry(f"+{x}+{y}")

        tk.Label(popup,text="Renommer le spot :",
                 font=("Courier New",8,"bold"),fg=ACC,bg=CARD).pack(pady=(10,4))

        entry=tk.Entry(popup,font=("Courier New",9),
                       bg="#1e1e2e",fg=ACC,insertbackground=ACC,
                       relief="flat",justify="center",width=20)
        entry.pack(padx=10)
        entry.insert(0,self.name_var.get())
        entry.select_range(0,"end")
        entry.focus_set()

        def confirm(e=None):
            val=entry.get().strip()
            if val: self.name_var.set(val.upper())
            popup.destroy()

        entry.bind("<Return>",confirm)
        entry.bind("<Escape>",lambda e:popup.destroy())

        btn_row=tk.Frame(popup,bg=CARD); btn_row.pack(pady=6)
        tk.Button(btn_row,text="  OK  ",font=("Courier New",8,"bold"),
                  fg="#0a0a0f",bg="#22cc55",relief="flat",cursor="hand2",
                  command=confirm).pack(side="left",padx=6)
        tk.Button(btn_row,text=" ANNULER ",font=("Courier New",8,"bold"),
                  fg=ACC,bg="#333344",relief="flat",cursor="hand2",
                  command=popup.destroy).pack(side="left",padx=6)

    def _bind_click(self, widget):
        """Rend un widget cliquable pour toggler le spot"""
        widget.bind("<Button-1>", lambda e: self._toggle())
        widget.config(cursor="hand2")

    def _toggle(self):
        self._selected=not self._selected; self._refresh_btn()
        # Sync sera fait au changement d'onglet

    def _refresh_btn(self):
        if self._selected:
            self.name_lbl.config(fg="#000000",bg="#22cc55")
            self.canvas.itemconfig(self.bulb,outline="#ffffff",width=2)
        else:
            self.name_lbl.config(fg="#ffffff",bg=CARD)
            self.canvas.itemconfig(self.bulb,outline="#555566",width=1)
        if hasattr(self,"_ctrl_twin"):
            self._ctrl_twin._selected=self._selected
            self._ctrl_twin._refresh_btn_only()

    def _refresh_btn_only(self):
        """Refresh visuel sans propager (évite récursion)"""
        if self._selected:
            self.name_lbl.config(fg="#000000",bg="#22cc55")
            self.canvas.itemconfig(self.bulb,outline="#ffffff",width=2)
        else:
            self.name_lbl.config(fg="#ffffff",bg=CARD)
            self.canvas.itemconfig(self.bulb,outline="#555566",width=1)

    def _toggle_and_sync(self, app):
        """Toggle sélection et propage au spot source ou twin"""
        self._selected = not self._selected
        self._refresh_btn_only()
        app._sync_selection(source="control")

    def set_selected(self,val): self._selected=val; self._refresh_btn()
    def is_selected(self): return self._selected

    def update(self,dim,r,g,b,s=0):
        self.dim=dim; self.r=r; self.g=g; self.b=b; self.s=s
        f=dim/255; rr=int(r*f); gg=int(g*f); bb=int(b*f)
        col=f"#{rr:02x}{gg:02x}{bb:02x}"
        self.canvas.itemconfig(self.bulb,fill=col)
        for i,(bar,v) in enumerate(zip(self.bars,[dim,r,g,b,s])):
            h=int(v/255*BAR_MAXH); x=self.bar_xs[i]
            self.bar_canvas.coords(bar,x,2+BAR_MAXH-h,x+BAR_W,2+BAR_MAXH)
        # Sync twin CONTROL
        if hasattr(self,"_ctrl_twin"):
            tw=self._ctrl_twin
            tw.dim=dim; tw.r=r; tw.g=g; tw.b=b; tw.s=s
            tw.canvas.itemconfig(tw.bulb,fill=col)
            for i,(bar,v) in enumerate(zip(tw.bars,[dim,r,g,b,s])):
                h=int(v/255*BAR_MAXH); x=tw.bar_xs[i]
                tw.bar_canvas.coords(bar,x,2+BAR_MAXH-h,x+BAR_W,2+BAR_MAXH)



class App:
    def __init__(self, root):
        self.root=root
        self.root.title("AZHYRIA - Live Light Board  |  v22  |  2026-05-21 06:22")
        self.root.configure(bg=BG); self.root.resizable(False,True)

        self.dmx=EnttecOpenDMX(); self.connected=False; self.simulation=False
        self.dev_idx=tk.IntVar(value=0); self._devices=[]

        self.dimmer=tk.IntVar(value=255); self.r=tk.IntVar(value=0)
        self.g=tk.IntVar(value=0); self.b=tk.IntVar(value=0)
        self.s=tk.IntVar(value=0)

        self.midi_port_var=tk.StringVar(); self.midi_running=False
        self.midi_thread=None; self.midi_in=None
        self.midi_last=tk.StringVar(value="—")
        self.bypass_dimmer=tk.BooleanVar(value=False)

        self.midi_map=[]
        for i in range(9):
            self.midi_map.append([tk.StringVar(value=midi_note_name(i*5+j)) for j in range(5)])

        for var in (self.dimmer,self.r,self.g,self.b,self.s):
            var.trace_add("write",self._send)

        # Rebuild MIDI lookup à chaque modification de la table de mapping
        def _on_midi_map_change(*_):
            if hasattr(self,"_midi_lookup"): self._build_midi_lookup()
        for spot_notes in self.midi_map:
            for note_var in spot_notes:
                note_var.trace_add("write", _on_midi_map_change)

        self._build()
        self._refresh_devices()
        self._refresh_midi_ports()

        # Si ftd2xx indisponible (DLL manquante en .exe), force simulation
        if not FTD2XX_OK:
            self.root.after(200, self._auto_simulation)

    def _build(self):
        style=ttk.Style(); style.theme_use("clam")
        for name,trough in [("DIM","#1a1a10"),("R","#2a0a0a"),("G","#0a2a0a"),("B","#0a0a2a"),("S","#1a1a10")]:
            style.configure(f"{name}.Horizontal.TScale",background=CARD,troughcolor=trough,sliderlength=22)
        style.configure("TNotebook",background=BG,borderwidth=0)
        style.configure("TNotebook.Tab",background="#1a1a28",foreground=DIM_COLOR,
                        font=("Courier New",9,"bold"),padding=[14,6])
        style.map("TNotebook.Tab",background=[("selected",CARD)],foreground=[("selected",ACC)])

        # Header
        hdr=tk.Frame(self.root,bg="#0d0d18",pady=10); hdr.pack(fill="x")
        tk.Label(hdr,text="AZHYRIA  —  LIVE LIGHT BOARD",
                 font=("Courier New",13,"bold"),fg=ACC,bg="#0d0d18").pack()


        self._nb=ttk.Notebook(self.root); self._nb.pack(fill="both",expand=True)
        tab_live=tk.Frame(self._nb,bg=BG)
        tab_ctrl=tk.Frame(self._nb,bg=BG)
        tab_cfg =tk.Frame(self._nb,bg=BG)
        self._nb.add(tab_live,text="  ◈ LIVE  ")
        self._nb.add(tab_ctrl,text="  ◉ CONTROL  ")
        self._nb.add(tab_cfg, text="  ⚙ CONFIG  ")

        self._build_live(tab_live)
        self._build_control(tab_ctrl)
        self._build_config(tab_cfg)

        tab_live.pack_propagate(True)
        tab_ctrl.pack_propagate(True)
        tab_cfg.pack_propagate(True)

        self._nb.bind("<<NotebookTabChanged>>", lambda e: (self._sync_selection(), self._fit_window()))
        self.root.after(300, self._do_fit)

    # ═══════════════════════════════════════════════════════════ ONGLET LIVE ══

    def _build_live(self, parent):
        main=tk.Frame(parent,bg=BG,padx=16,pady=10); main.pack(fill="both")

        # ── Barre de statut connexions ────────────────────────────────────────
        status=tk.Frame(main,bg="#0d0d18",padx=12,pady=6); status.pack(fill="x",pady=(0,8))

        # DMX — juste le label + voyant
        tk.Label(status,text="DMX",font=("Courier New",8,"bold"),fg=DIM_COLOR,bg="#0d0d18").pack(side="left",padx=(0,3))
        self.dot=tk.Label(status,text="●",font=("Courier New",14),fg="#ff3355",bg="#0d0d18")
        self.dot.pack(side="left",padx=(0,16))
        self.status_dmx=tk.Label(status,text="",font=("Courier New",8),fg=DIM_COLOR,bg="#0d0d18")  # inutilisé live

        # MIDI — juste le label + voyant
        tk.Label(status,text="MIDI",font=("Courier New",8,"bold"),fg=DIM_COLOR,bg="#0d0d18").pack(side="left",padx=(0,3))
        self.midi_dot=tk.Label(status,text="●",font=("Courier New",14),fg="#ff3355",bg="#0d0d18")
        self.midi_dot.pack(side="left",padx=(0,16))
        self.status_midi=tk.Label(status,text="",font=("Courier New",8),fg=DIM_COLOR,bg="#0d0d18")  # inutilisé live

        # DIM mode
        tk.Label(status,text="DIM",font=("Courier New",8,"bold"),fg=DIM_COLOR,bg="#0d0d18").pack(side="left",padx=(0,3))
        self.status_dim_mode=tk.Label(status,text="MIDI",font=("Courier New",8,"bold"),
                                      fg="#ffffff",bg="#0d0d18")
        self.status_dim_mode.pack(side="left",padx=(0,16))

        # Note MIDI en cours
        tk.Label(status,text="NOTE",font=("Courier New",8,"bold"),fg=DIM_COLOR,bg="#0d0d18").pack(side="left",padx=(0,3))
        tk.Label(status,textvariable=self.midi_last,font=("Courier New",8),fg="#22cc55",bg="#0d0d18").pack(side="left",padx=2)

        # ── Grille spots ──────────────────────────────────────────────────────
        self._spots_frame=tk.Frame(main,bg=CARD,padx=8,pady=8); self._spots_frame.pack()
        self.spots=[]; self._spot_row_frames=[]
        default_channels=[1,11,21,31,41,51,61,71,81]
        for row in range(3):
            rf=tk.Frame(self._spots_frame,bg=CARD); rf.pack(pady=2)
            self._spot_row_frames.append(rf)
            for col in range(3):
                idx=row*3+col
                sp=SpotWidget(rf,idx,default_channels[idx])
                self.spots.append(sp)

        # ── Accès rapide ──────────────────────────────────────────────────────
        self._presets=[
            [0,   0,   0,   0  ],[25,  255, 255, 255],[255, 255, 255, 255],
            [255, 255, 0,   0  ],[255, 0,   255, 0  ],[255, 0,   0,   255],
            [255, 255, 130, 0  ],[255, 180, 0,   255],[255, 0,   255, 255],
        ]
        self._pill_canvases=[]
        PILL=28
        pill_row=tk.Frame(main,bg=BG,pady=4); pill_row.pack()
        for idx in range(9):
            c=tk.Canvas(pill_row,width=PILL,height=PILL,bg=BG,
                        highlightthickness=0,cursor="hand2")
            c.pack(side="left",padx=4)
            fill=self._preset_color(idx)
            oval=c.create_oval(2,2,PILL-2,PILL-2,fill=fill,outline="#ffffff",width=1)
            self._pill_canvases.append((c,oval))
            c.bind("<Button-1>",lambda e,i=idx:self._apply_preset(i))

    # ═════════════════════════════════════════════════════ ONGLET CONTROL ══

    def _build_control(self, parent):
        main=tk.Frame(parent,bg=BG,padx=16,pady=10); main.pack(fill="both")

        def make_collapsible(parent2, title, build_fn):
            state={"open": True}
            wrapper=tk.Frame(parent2,bg=BG); wrapper.pack(fill="x",pady=(0,2))
            lbl=tk.Label(wrapper,text=f"▾ {title}",font=("Courier New",8),
                         fg=DIM_COLOR,bg=BG,anchor="w",cursor="hand2")
            lbl.pack(fill="x")
            content=tk.Frame(wrapper,bg=CARD,padx=8,pady=6)
            content.pack(fill="x")
            tk.Frame(content,bg="#2a2a40",height=1).pack(fill="x")
            inner=tk.Frame(content,bg=CARD); inner.pack(fill="x",pady=(4,0))
            build_fn(inner)
            def toggle(e=None):
                state["open"]=not state["open"]
                if state["open"]:
                    content.pack(fill="x")
                    lbl.config(text=f"▾ {title}")
                else:
                    content.pack_forget()
                    lbl.config(text=f"▸ {title}")
                self._fit_window()
            lbl.bind("<Button-1>",toggle)
            return inner

        top_row=tk.Frame(main,bg=BG); top_row.pack(fill="x")

        # Grille spots CONTROL — widgets indépendants liés aux mêmes données
        ctrl_sf=tk.Frame(top_row,bg=CARD,padx=8,pady=8); ctrl_sf.pack(side="left")
        self._ctrl_spot_row_frames=[]
        self._ctrl_spot_widgets=[]  # (canvas, bulb, bars, bar_xs)
        for row in range(3):
            rf=tk.Frame(ctrl_sf,bg=CARD); rf.pack(pady=2)
            self._ctrl_spot_row_frames.append(rf)
            for col in range(3):
                idx=row*3+col
                sp=self.spots[idx]
                # Crée un SpotWidget complet indépendant qui partage les données
                sp2=SpotWidget(rf,idx,sp.ch_var.get())
                sp2.ch_var=sp.ch_var        # partage le ch_var
                sp2.name_var=sp.name_var    # partage le nom
                sp2.name_lbl.config(textvariable=sp.name_var)
                sp2._selected=sp._selected
                sp2._refresh_btn()
                sp2._ch_row.pack(pady=(4,0))  # affiche le canal dans CONTROL
                sp2.name_lbl.bind("<Button-3>", lambda e,s=sp2: s._rename_popup())
                # Override toggle pour sync bidirectionnel
                sp2.frame.bind("<Button-1>", lambda e,s=sp2: s._toggle_and_sync(self))
                sp2.name_lbl.bind("<Button-1>", lambda e,s=sp2: s._toggle_and_sync(self))
                sp2.canvas.bind("<Button-1>", lambda e,s=sp2: s._toggle_and_sync(self))
                sp2.bar_canvas.bind("<Button-1>", lambda e,s=sp2: s._toggle_and_sync(self))
                # Lie sp2 à sp pour sync
                sp._ctrl_twin=sp2
                self._ctrl_spot_widgets.append(sp2)

        right=tk.Frame(top_row,bg=BG,padx=10); right.pack(side="left",fill="y",anchor="n")

        # SÉLECTION
        self._sel_row_btns=[]
        def build_sel(inner):
            for lbl2,cmd in [("TOUS",self._select_all),("AUCUN",self._select_none),
                            ("LIG 1",lambda:self._select_row(0)),
                            ("LIG 2",lambda:self._select_row(1)),
                            ("LIG 3",lambda:self._select_row(2))]:
                btn=tk.Button(inner,text=lbl2,font=("Courier New",7,"bold"),
                              fg=ACC,bg="#1e1e30",relief="flat",cursor="hand2",
                              padx=4,pady=3,command=cmd)
                btn.pack(fill="x",pady=1)
                if lbl2.startswith("LIG"):
                    self._sel_row_btns.append(btn)
        make_collapsible(right,"[ SÉLECTION ]",build_sel)

        # ACCÈS RAPIDE — pastilles séparées (les données _presets viennent de LIVE)
        self._ctrl_pill_canvases=[]
        PILL=28
        def build_pills(inner):
            for row_idx in range(3):
                pr=tk.Frame(inner,bg=CARD); pr.pack(pady=2)
                for col_idx in range(3):
                    idx=row_idx*3+col_idx
                    c=tk.Canvas(pr,width=PILL,height=PILL,bg=CARD,
                                highlightthickness=0,cursor="hand2")
                    c.pack(side="left",padx=3)
                    fill=self._preset_color(idx)
                    oval=c.create_oval(2,2,PILL-2,PILL-2,fill=fill,outline="#ffffff",width=1)
                    self._ctrl_pill_canvases.append((c,oval))
                    c.bind("<Button-1>",lambda e,i=idx:self._apply_preset(i))
                    c.bind("<Button-3>",lambda e,i=idx:self._update_preset_both(i))
        make_collapsible(right,"[ ACCÈS RAPIDE ]",build_pills)

        # COULEUR
        WHEEL=100
        def build_wheel(inner):
            self.wheel_canvas=tk.Canvas(inner,width=WHEEL,height=WHEEL,
                                        bg=CARD,highlightthickness=0,cursor="hand2")
            self.wheel_canvas.pack(pady=4)
            self._draw_wheel(WHEEL)
            self.wheel_canvas.bind("<Button-1>",self._on_wheel_click)
            self.wheel_canvas.bind("<B1-Motion>",self._on_wheel_click)
        make_collapsible(right,"[ COULEUR ]",build_wheel)

        # CONTRÔLE sliders
        self.val_labels={}
        def build_sliders(inner):
            for name,var,color,tag in [
                ("CH1  DIMMER", self.dimmer,"#ffffff","DIM"),
                ("CH2  ROUGE",  self.r,    "#ff2244","R"),
                ("CH3  VERT",   self.g,    "#22ff77","G"),
                ("CH4  BLEU",   self.b,    "#4488ff","B"),
                ("CH5  SPECIAL", self.s,    "#ffcc44","S"),
            ]:
                self._row(inner,name,var,color,tag)
        make_collapsible(main,"[ CONTRÔLE  —  spots actifs ]",build_sliders)

    # ════════════════════════════════════════════════════════ ONGLET CONFIG ══

    def _build_config(self, parent):
        main=tk.Frame(parent,bg=BG,padx=16,pady=10); main.pack(fill="both")

        # ── Connexions empilées, boutons alignés via grid ─────────────────────
        conn_outer=tk.Frame(main,bg=BG); conn_outer.pack(fill="x",pady=(0,6))
        tk.Label(conn_outer,text="[ CONNEXIONS ]",font=("Courier New",8),
                 fg=DIM_COLOR,bg=BG,anchor="w").pack(anchor="w")
        conn_card=tk.Frame(conn_outer,bg=CARD,padx=12,pady=10); conn_card.pack(fill="x")
        tk.Frame(conn_card,bg="#2a2a40",height=1).pack(fill="x")
        g=tk.Frame(conn_card,bg=CARD); g.pack(fill="x",pady=(8,0))

        # Largeurs colonnes fixes pour alignement parfait
        g.columnconfigure(1,minsize=180)  # combo
        g.columnconfigure(2,minsize=28)   # ⟳
        g.columnconfigure(3,minsize=130)  # bouton
        g.columnconfigure(4,minsize=24)   # voyant

        # Ligne DMX
        tk.Label(g,text="DMX :",font=("Courier New",9,"bold"),fg=DIM_COLOR,bg=CARD,
                 width=6,anchor="e").grid(row=0,column=0,padx=(0,6),pady=5,sticky="e")
        self.dev_combo=ttk.Combobox(g,width=22,font=("Courier New",9),state="readonly")
        self.dev_combo.grid(row=0,column=1,padx=4,sticky="w")
        self.dev_combo.bind("<<ComboboxSelected>>",self._on_dev_select)
        tk.Button(g,text="⟳",fg=ACC,bg="#1e1e30",relief="flat",font=("Courier New",9),
                  cursor="hand2",command=self._refresh_devices).grid(row=0,column=2,padx=2)
        self.btn=tk.Button(g,text="  CONNECTER  ",font=("Courier New",9,"bold"),
                           fg="#0a0a0f",bg=ACC,relief="flat",cursor="hand2",command=self._toggle)
        self.btn.grid(row=0,column=3,padx=(8,4),sticky="ew")
        self._dot_cfg=tk.Label(g,text="●",font=("Courier New",16),fg="#ff3355",bg=CARD)
        self._dot_cfg.grid(row=0,column=4,padx=4)

        # Séparateur
        tk.Frame(g,bg="#1e1e2e",height=1).grid(row=1,column=0,columnspan=5,sticky="ew",pady=3)

        # Ligne MIDI
        tk.Label(g,text="MIDI :",font=("Courier New",9,"bold"),fg=DIM_COLOR,bg=CARD,
                 width=6,anchor="e").grid(row=2,column=0,padx=(0,6),pady=5,sticky="e")
        self.midi_combo=ttk.Combobox(g,textvariable=self.midi_port_var,width=22,
                                     font=("Courier New",9),state="readonly")
        self.midi_combo.grid(row=2,column=1,padx=4,sticky="w")
        tk.Button(g,text="⟳",fg=ACC,bg="#1e1e30",relief="flat",font=("Courier New",9),
                  cursor="hand2",command=self._refresh_midi_ports).grid(row=2,column=2,padx=2)
        self.midi_btn=tk.Button(g,text="  ÉCOUTER  ",font=("Courier New",9,"bold"),
                                fg="#0a0a0f",bg=ACC,relief="flat",cursor="hand2",
                                command=self._toggle_midi)
        self.midi_btn.grid(row=2,column=3,padx=(8,4),sticky="ew")
        self._midi_dot_cfg=tk.Label(g,text="●",font=("Courier New",16),fg="#ff3355",bg=CARD)
        self._midi_dot_cfg.grid(row=2,column=4,padx=4)

        # ── Tableau unique : SPOT | CH | DIM | R | G | B ─────────────────────
        tbl_outer=tk.Frame(main,bg=BG); tbl_outer.pack(fill="x",pady=4)
        tk.Label(tbl_outer,text="[ SPOT  —  ADRESSE DMX  &  MAPPING NOTES MIDI ]",
                 font=("Courier New",8),fg=DIM_COLOR,bg=BG,anchor="w").pack(anchor="w")
        tbl_card=tk.Frame(tbl_outer,bg=CARD,padx=12,pady=8); tbl_card.pack(fill="x")
        tk.Frame(tbl_card,bg="#2a2a40",height=1).pack(fill="x")
        tbl=tk.Frame(tbl_card,bg=CARD); tbl.pack(pady=(6,0),anchor="w")

        # En-têtes : ✓ | SPOT | CH | DIM | +d | R | +r | G | +g | B | +b
        hdrs=[("",DIM_COLOR),("SPOT",DIM_COLOR),("CH",ACC),
              ("DIM","#ffffff"),("↳","#886600"),
              ("R","#ff2244"),  ("↳","#880011"),
              ("G","#22cc66"),  ("↳","#116633"),
              ("B","#4488ff"),  ("↳","#224488"),
              ("S","#ffcc44"),  ("↳","#886600")]
        for c,(txt,col) in enumerate(hdrs):
            w=3 if c==0 else (3 if txt=="↳" else 5)
            tk.Label(tbl,text=txt,font=("Courier New",8,"bold"),fg=col,bg=CARD,
                     width=w,anchor="center").grid(row=0,column=c,padx=2,pady=(0,3))
        tk.Frame(tbl,bg="#2a2a40",height=1).grid(row=1,column=0,columnspan=13,sticky="ew",pady=(0,3))

        self._addr_tbl=tbl  # pour _finish_config

        # Bouton bypass dimmer
        bypass_row=tk.Frame(tbl_card,bg=CARD); bypass_row.pack(anchor="w",pady=(8,2))
        self._bypass_btn=tk.Button(bypass_row,text="  Dimmer MIDI  ",
                                   font=("Courier New",8,"bold"),
                                   fg="#ffffff",bg="#222233",
                                   activebackground="#222233",
                                   relief="flat",cursor="hand2",
                                   command=self._toggle_bypass)
        self._bypass_btn.pack(side="left",padx=0)
        tk.Label(bypass_row,text="  (notes DIM ignorées quand actif)",
                 font=("Courier New",7),fg=DIM_COLOR,bg=CARD).pack(side="left")

        # Légende compacte sous le tableau
        leg_card=tk.Frame(main,bg=CARD,padx=12,pady=6); leg_card.pack(fill="x",pady=(6,0))
        tk.Frame(leg_card,bg="#2a2a40",height=1).pack(fill="x")
        leg_inner=tk.Frame(leg_card,bg=CARD); leg_inner.pack(fill="x",pady=(4,0))
        for label,val in [("VELOCITY 0–127","→ DMX 0–255  (vel × 2)"),
                           ("NOTE ON vel=0", "→ canal à 0"),
                           ("CANAL MIDI",    "→ ignoré, seule la note compte")]:
            r=tk.Frame(leg_inner,bg=CARD); r.pack(side="left",padx=16)
            tk.Label(r,text=label,font=("Courier New",7,"bold"),fg=ACC,bg=CARD).pack()
            tk.Label(r,text=val,font=("Courier New",7),fg=DIM_COLOR,bg=CARD).pack()

        # Boutons Save / Load
        io_row=tk.Frame(main,bg=BG); io_row.pack(pady=(10,4))
        tk.Button(io_row,text="  SAUVEGARDER  ",
                  font=("Courier New",9,"bold"),fg="#0a0a0f",bg="#22cc55",
                  relief="flat",cursor="hand2",
                  command=self._save_config).pack(side="left",padx=8)
        tk.Button(io_row,text="  CHARGER  ",
                  font=("Courier New",9,"bold"),fg="#0a0a0f",bg="#4488ff",
                  relief="flat",cursor="hand2",
                  command=self._load_config).pack(side="left",padx=8)
        tk.Button(io_row,text="  DÉFAUT  ",
                  font=("Courier New",9,"bold"),fg="#0a0a0f",bg="#ffffff",
                  relief="flat",cursor="hand2",
                  command=self._reset_defaults).pack(side="left",padx=8)

        # Ligne technique en bas
        tk.Label(main,text="ENTTEC Open DMX USB  ·  D2XX  ·  DMX512  ·  MIDI via LoopBe1",
                 font=("Courier New",7),fg=DIM_COLOR,bg=BG).pack(pady=(6,2))

    def _update_preset_both(self, idx):
        """Clic droit : met à jour le preset et rafraîchit les deux séries de pastilles"""
        self._update_preset(idx)

    def _preset_color(self, idx):
        """Calcule la couleur RGB affichée pour une pastille à partir des valeurs dim/r/g/b"""
        d,r,g,b=self._presets[idx][:4]
        f=d/255; rr=int(r*f); gg=int(g*f); bb=int(b*f)
        return f"#{rr:02x}{gg:02x}{bb:02x}" if (rr+gg+bb)>10 else "#111122"

    def _apply_preset(self, idx):
        p=self._presets[idx]
        d,r,g,b=p[:4]; s=p[4] if len(p)>4 else 0
        self.dimmer.set(d); self.r.set(r); self.g.set(g); self.b.set(b); self.s.set(s)

    def _update_preset(self, idx):
        """Clic droit : popup pour mettre à jour la pastille avec les valeurs actuelles"""
        d=self.dimmer.get(); r=self.r.get(); g=self.g.get(); b=self.b.get(); s=self.s.get()

        # Popup confirmation
        popup=tk.Toplevel(self.root)
        popup.title(""); popup.resizable(False,False)
        popup.configure(bg=CARD)
        popup.grab_set()

        # Centrage
        popup.geometry("260x100")
        self.root.update_idletasks()
        x=self.root.winfo_x()+self.root.winfo_width()//2-130
        y=self.root.winfo_y()+self.root.winfo_height()//2-50
        popup.geometry(f"+{x}+{y}")

        tk.Label(popup,text="Mettre à jour ce preset ?",
                 font=("Courier New",9,"bold"),fg=ACC,bg=CARD).pack(pady=(14,4))

        # Aperçu couleur
        f2=d/255; rr=int(r*f2); gg=int(g*f2); bb=int(b*f2)
        col=f"#{rr:02x}{gg:02x}{bb:02x}" if (rr+gg+bb)>10 else "#111122"
        preview=tk.Canvas(popup,width=20,height=20,bg=CARD,highlightthickness=0)
        preview.pack()
        preview.create_oval(2,2,18,18,fill=col,outline="#ffffff",width=1)

        btn_row=tk.Frame(popup,bg=CARD); btn_row.pack(pady=8)

        def confirm():
            self._presets[idx]=[d,r,g,b,s]
            fill=self._preset_color(idx)
            # Live pills
            if idx<len(self._pill_canvases):
                c,oval=self._pill_canvases[idx]
                c.itemconfig(oval,fill=fill,outline="#ffffff")
            # Control pills
            if hasattr(self,"_ctrl_pill_canvases") and idx<len(self._ctrl_pill_canvases):
                c2,oval2=self._ctrl_pill_canvases[idx]
                c2.itemconfig(oval2,fill=fill,outline="#ffffff")
            popup.destroy()

        tk.Button(btn_row,text="  OUI  ",font=("Courier New",8,"bold"),
                  fg="#0a0a0f",bg="#22cc55",relief="flat",cursor="hand2",
                  command=confirm).pack(side="left",padx=6)
        tk.Button(btn_row,text="  NON  ",font=("Courier New",8,"bold"),
                  fg=ACC,bg="#333344",relief="flat",cursor="hand2",
                  command=popup.destroy).pack(side="left",padx=6)

    def _reset_defaults(self):
        if not messagebox.askyesno("Réinitialiser",
            "Remettre toutes les valeurs par défaut ?"):
            return

        # Noms des spots
        for i,sp in enumerate(self.spots):
            sp.name_var.set(f"SPOT {i+1}")

        # Adresses DMX (1, 11, 21, ...)
        for i,sp in enumerate(self.spots):
            sp.ch_var.set(1 + i*10)

        # Mapping MIDI
        for i in range(len(self.spots)):
            for j in range(5):
                self.midi_map[i][j].set(midi_note_name(i*5+j))

        # Presets couleurs
        defaults=[
            [0,   0,   0,   0  ],
            [25,  255, 255, 255],
            [255, 255, 255, 255],
            [255, 255, 0,   0  ],
            [255, 0,   255, 0  ],
            [255, 0,   0,   255],
            [255, 255, 130, 0  ],
            [255, 180, 0,   255],
            [255, 0,   255, 255],
        ]
        for i,preset in enumerate(defaults):
            if i<len(self._presets):
                self._presets[i]=preset
                fill=self._preset_color(i)
                if i<len(self._pill_canvases):
                    c,oval=self._pill_canvases[i]
                    c.itemconfig(oval,fill=fill,outline="#ffffff")
                if hasattr(self,"_ctrl_pill_canvases") and i<len(self._ctrl_pill_canvases):
                    c2,oval2=self._ctrl_pill_canvases[i]
                    c2.itemconfig(oval2,fill=fill,outline="#ffffff")

        for sp in self.spots:
            sp.enabled=True
            if hasattr(sp,"_enabled_var"): sp._enabled_var.set(True)
            for j,v in enumerate(sp.ch_offsets): v.set(j)
        self._rebuild_spot_grid()
        if self.bypass_dimmer.get():
            self._toggle_bypass()

        # Sliders à zéro
        for v in (self.dimmer,self.r,self.g,self.b): v.set(0)
        self.dimmer.set(255)

        messagebox.showinfo("Réinitialisation","Valeurs par défaut restaurées !")

    def _save_config(self):
        path=filedialog.asksaveasfilename(
            title="Sauvegarder la configuration",
            defaultextension=".txt",
            filetypes=[("Fichier texte","*.txt"),("Tous les fichiers","*.*")],
            initialfile="azhyria_config.txt")
        if not path: return
        cfg={
            "spot_names":   [sp.name_var.get() for sp in self.spots],
            "spot_channels":[sp.ch_var.get() for sp in self.spots],
            "spot_enabled":  [sp.enabled for sp in self.spots],
            "ch_offsets":    [[v.get() for v in sp.ch_offsets] for sp in self.spots],
            "midi_map":    [[self.midi_map[i][j].get() for j in range(5)]
                            for i in range(len(self.spots))],
            "presets":     self._presets,
            "bypass_dimmer":self.bypass_dimmer.get(),
        }
        try:
            with open(path,"w",encoding="utf-8") as f:
                json.dump(cfg,f,indent=2,ensure_ascii=False)
            messagebox.showinfo("Sauvegarde","Configuration sauvegardée !")
        except Exception as e:
            messagebox.showerror("Erreur","Impossible de sauvegarder :\n"+str(e))

    def _load_config(self):
        path=filedialog.askopenfilename(
            title="Charger une configuration",
            filetypes=[("Fichier texte","*.txt"),("Tous les fichiers","*.*")])
        if not path: return
        try:
            with open(path,"r",encoding="utf-8") as f:
                cfg=json.load(f)
        except Exception as e:
            messagebox.showerror("Erreur","Impossible de lire le fichier :\n"+str(e)); return

        for i,name in enumerate(cfg.get("spot_names",[])):
            if i<len(self.spots): self.spots[i].name_var.set(name)
        for i,en in enumerate(cfg.get("spot_enabled",[])):
            if i<len(self.spots) and i>=3:
                self.spots[i].enabled=en
                if hasattr(self.spots[i],"_enabled_var"): self.spots[i]._enabled_var.set(en)
        for i,offs in enumerate(cfg.get("ch_offsets",[])):
            if i<len(self.spots):
                for j,v in enumerate(offs):
                    if j<4: self.spots[i].ch_offsets[j].set(v)
        self._rebuild_spot_grid()

        for i,ch in enumerate(cfg.get("spot_channels",[])):
            if i<len(self.spots): self.spots[i].ch_var.set(ch)

        for i,row in enumerate(cfg.get("midi_map",[])):
            if i<len(self.midi_map):
                for j,note in enumerate(row):
                    if j<5: self.midi_map[i][j].set(note)

        for i,preset in enumerate(cfg.get("presets",[])):
            if i<len(self._presets):
                self._presets[i]=preset
                fill=self._preset_color(i)
                if i<len(self._pill_canvases):
                    c,oval=self._pill_canvases[i]
                    c.itemconfig(oval,fill=fill,outline="#ffffff")
                if hasattr(self,"_ctrl_pill_canvases") and i<len(self._ctrl_pill_canvases):
                    c2,oval2=self._ctrl_pill_canvases[i]
                    c2.itemconfig(oval2,fill=fill,outline="#ffffff")

        if "bypass_dimmer" in cfg:
            current=self.bypass_dimmer.get()
            if cfg["bypass_dimmer"]!=current:
                self._toggle_bypass()
            self._refresh_dim_entries()

        messagebox.showinfo("Chargement","Configuration chargée !")

    def _toggle_bypass(self):
        self.bypass_dimmer.set(not self.bypass_dimmer.get())
        if self.bypass_dimmer.get():
            self._bypass_btn.config(text="  Dimmer Manuel  ",
                                    fg="#0a0a0f",bg="#ff8822",
                                    activebackground="#ff8822")
            if hasattr(self,"status_dim_mode"):
                self.status_dim_mode.config(text="Manuel",fg="#ff8822")
        else:
            self._bypass_btn.config(text="  Dimmer MIDI  ",
                                    fg="#ffffff",bg="#222233",
                                    activebackground="#222233")
            if hasattr(self,"status_dim_mode"):
                self.status_dim_mode.config(text="MIDI",fg="#ffffff")
        self._refresh_dim_entries()

    def _refresh_dim_entries(self):
        """Grise les entrées DIM de la table quand bypass actif"""
        if not hasattr(self,'_dim_entries'): return
        bypassed=self.bypass_dimmer.get()
        for e in self._dim_entries:
            e.config(fg="#333344" if bypassed else "#ffffff",
                     state="disabled" if bypassed else "normal")

    def _addr_row(self, tbl, i, sp, row_idx):
        """Ligne : ✓ | NOM | CH | DIM | R | G | B"""
        if not hasattr(self,'_dim_entries'): self._dim_entries=[]
        if not hasattr(self,'_addr_row_frames'): self._addr_row_frames=[]
        sp._enabled_var=tk.BooleanVar(value=getattr(sp,'enabled',True))

        if i < 3:
            tk.Label(tbl,text="■",font=("Courier New",9),
                     fg="#444455",bg=CARD).grid(row=row_idx,column=0,padx=4,pady=3)
        else:
            cb=tk.Checkbutton(tbl,variable=sp._enabled_var,bg=CARD,
                           activebackground=CARD,selectcolor=CARD,
                           fg="#ffffff",activeforeground="#ffffff",
                           font=("Courier New",10,"bold"),
                           relief="flat",cursor="hand2",
                           command=lambda s=sp:self._on_spot_enabled_change(s))
            cb.grid(row=row_idx,column=0,padx=4,pady=3)

        name_lbl=tk.Label(tbl,textvariable=sp.name_var,font=("Courier New",8,"bold"),
                          fg=ACC,bg=CARD,width=7,anchor="center",cursor="hand2")
        name_lbl.grid(row=row_idx,column=1,padx=4,pady=3)
        name_lbl.bind("<Button-3>",lambda e,s=sp:s._rename_popup())
        tk.Spinbox(tbl,from_=1,to=509,textvariable=sp.ch_var,width=4,
                   font=("Courier New",9),bg="#1e1e2e",fg=ACC,relief="flat",
                   buttonbackground="#2a2a40").grid(row=row_idx,column=2,padx=2,pady=3)
        # Colonnes note MIDI + offset sous-canal (DIM,R,G,B)
        note_colors=["#ffffff","#ff2244","#22cc66","#4488ff","#ffcc44"]
        off_colors= ["#886600","#880011","#116633","#224488","#886600"]
        for j in range(5):
            col_note=note_colors[j]; col_off=off_colors[j]
            # Note MIDI
            e=tk.Entry(tbl,textvariable=self.midi_map[i][j],width=4,font=("Courier New",8),
                       bg="#1e1e2e",fg=col_note,insertbackground=col_note,
                       relief="flat",justify="center")
            e.grid(row=row_idx,column=3+j*2,padx=2,pady=3)
            if j==0: self._dim_entries.append(e)
            # Offset sous-canal DMX
            tk.Spinbox(tbl,from_=0,to=15,textvariable=sp.ch_offsets[j],width=2,
                       font=("Courier New",8),bg="#1a1a1a",fg=col_off,relief="flat",
                       buttonbackground="#2a2a40").grid(row=row_idx,column=4+j*2,padx=2,pady=3)

        # Stocke les widgets de la ligne pour toggle visibilité
        if not hasattr(self,'_addr_row_widgets'): self._addr_row_widgets={}
        row_widgets=[]
        for widget in tbl.grid_slaves(row=row_idx):
            info=widget.grid_info()
            row_widgets.append((widget, {k:v for k,v in info.items()
                                if k in ('row','column','padx','pady',
                                         'sticky','columnspan','rowspan','ipadx','ipady')}))
        self._addr_row_widgets[row_idx]=row_widgets
        self._addr_row_frames.append((row_idx, sp))

    def _on_spot_enabled_change(self, sp):
        sp.enabled=sp._enabled_var.get()
        self._rebuild_spot_grid()

    def _rebuild_spot_grid(self):
        ctrl_twins=getattr(self,"_ctrl_spot_widgets",[])
        for row_frames in [self._spot_row_frames,
                           getattr(self,"_ctrl_spot_row_frames",[])]:
            for row_idx,rf in enumerate(row_frames):
                if row_idx==0:
                    rf.pack(pady=2)
                else:
                    spots_in_row=self.spots[row_idx*3:row_idx*3+3]
                    if any(s.enabled for s in spots_in_row):
                        rf.pack(pady=2)
                    else:
                        rf.pack_forget()
        for row_idx in range(3):
            for col_idx in range(3):
                idx=row_idx*3+col_idx
                if idx>=len(self.spots): break
                sp=self.spots[idx]
                show=row_idx==0 or sp.enabled
                if show:
                    sp.frame.pack(side="left",padx=5,pady=4)
                else:
                    sp.frame.pack_forget()
                if idx<len(ctrl_twins):
                    if show:
                        ctrl_twins[idx].frame.pack(side="left",padx=5,pady=4)
                    else:
                        ctrl_twins[idx].frame.pack_forget()
        self._refresh_sel_buttons()
        self._fit_window()

    def _refresh_sel_buttons(self):
        """Grise les boutons LIG x si la ligne n'a aucun spot actif"""
        if not hasattr(self,"_sel_row_btns"): return
        for row_idx,btn in enumerate(self._sel_row_btns):
            row_spots=self.spots[row_idx*3:row_idx*3+3]
            active=any(sp.enabled for sp in row_spots)
            btn.config(fg=ACC if active else "#333344",
                       cursor="hand2" if active else "arrow",
                       state="normal" if active else "disabled")

    def _finish_config(self):
        if not hasattr(self,'_dim_entries'): self._dim_entries=[]
        for i,sp in enumerate(self.spots):
            self._addr_row(self._addr_tbl,i,sp,i+2)

    # ── Helpers UI ────────────────────────────────────────────────────────────

    def _card(self, parent, title):
        outer=tk.Frame(parent,bg=BG,pady=5); outer.pack(fill="x")
        tk.Label(outer,text=title,font=("Courier New",8),fg=DIM_COLOR,bg=BG,anchor="w").pack(anchor="w")
        card=tk.Frame(outer,bg=CARD,padx=12,pady=8); card.pack(fill="x")
        tk.Frame(card,bg="#2a2a40",height=1).pack(fill="x")
        inner=tk.Frame(card,bg=CARD); inner.pack(fill="x",pady=(6,0))
        return inner

    def _row(self, parent, name, var, color, tag):
        row=tk.Frame(parent,bg=CARD); row.pack(fill="x",pady=4)
        tk.Label(row,text=name,font=("Courier New",9),fg=color,bg=CARD,width=14,anchor="w").pack(side="left")
        ttk.Scale(row,from_=0,to=255,orient="horizontal",variable=var,
                  style=f"{tag}.Horizontal.TScale",length=230).pack(side="left",padx=6)
        lbl=tk.Label(row,text="255" if tag=="DIM" else "000",font=("Courier New",10,"bold"),
                     fg=color,bg=CARD,width=4)
        lbl.pack(side="left")
        self.val_labels[tag]=lbl
        tk.Button(row,text="0",font=("Courier New",8),fg="#555577",bg="#1a1a28",relief="flat",
                  cursor="hand2",command=lambda v=var:v.set(0)).pack(side="left",padx=2)
        tk.Button(row,text="MAX",font=("Courier New",8),fg=color,bg="#1a1a28",relief="flat",
                  cursor="hand2",command=lambda v=var:v.set(255)).pack(side="left")

    def _sync_selection(self, source="live"):
        """Synchronise l'état sélectionné entre spots LIVE et twins CONTROL"""
        twins = getattr(self, "_ctrl_spot_widgets", [])
        if source == "live":
            for i, sp in enumerate(self.spots):
                if i < len(twins):
                    twins[i]._selected = sp._selected
                    twins[i]._refresh_btn_only()
        else:
            for i, tw in enumerate(twins):
                if i < len(self.spots):
                    self.spots[i]._selected = tw._selected
                    self.spots[i]._refresh_btn_only()


    def _fit_window(self, delay=80):
        """Redimensionne après un court délai pour laisser tkinter finir le rendu"""
        self.root.after(delay, self._do_fit)

    def _do_fit(self):
        """Mesure la hauteur visible de l'onglet actif sans influence des autres onglets"""
        self.root.update_idletasks()
        w = self.root.winfo_width()
        if w < 10: w = 600

        try:
            tab_id  = self._nb.select()
            tab_frm = self.root.nametowidget(tab_id)
        except Exception:
            return

        # Astuce : détache temporairement les autres onglets du notebook
        # pour que reqheight ne soit pas pollué par eux
        tabs = self._nb.tabs()
        hidden = []
        for t in tabs:
            if t != tab_id:
                state = self._nb.tab(t, "state")
                if state != "hidden":
                    self._nb.tab(t, state="hidden")
                    hidden.append(t)

        self.root.update_idletasks()
        tab_h = tab_frm.winfo_reqheight()

        # Restaure les onglets
        for t in hidden:
            self._nb.tab(t, state="normal")

        # Header
        hdr_h = 0
        for child in self.root.winfo_children():
            if isinstance(child, tk.Frame) and child.winfo_ismapped():
                hdr_h = child.winfo_reqheight()
                break

        tab_bar_h = 32
        self.root.geometry(f"{w}x{hdr_h + tab_bar_h + tab_h + 8}")

    def _update_dot(self):
        """Synchronise les voyants live et config"""
        if self.connected:
            col="#22ff77"; txt="CONNECTÉ"
        elif self.simulation:
            col="#ffffff"; txt="SIMULATION"
        else:
            col="#ff3355"; txt="NON CONNECTÉ"
        self.dot.config(fg=col)
        self._dot_cfg.config(fg=col)
        self.status_dmx.config(text=txt,fg=col)

    def _update_midi_dot(self):
        if self.midi_running:
            col="#22ff77"; txt=self.midi_port_var.get()
        else:
            col="#ff3355"; txt="NON CONNECTÉ"
        self.midi_dot.config(fg=col)
        self._midi_dot_cfg.config(fg=col)
        self.status_midi.config(text=txt[:22],fg=col)

    # ── Sélection ─────────────────────────────────────────────────────────────

    def _selected_spots(self): return [sp for sp in self.spots if sp.is_selected() and sp.enabled]

    def _select_all(self):
        for sp in self.spots:
            if sp.enabled: sp.set_selected(True)

    def _select_none(self):
        for sp in self.spots: sp.set_selected(False)

    def _select_row(self, row):
        row_spots = self.spots[row*3:row*3+3]
        if not any(sp.enabled for sp in row_spots): return
        self._select_none()
        for sp in row_spots:
            if sp.enabled: sp.set_selected(True)
        if hasattr(self,"_midi_lookup"): self._build_midi_lookup()

    # ── Connexion DMX ─────────────────────────────────────────────────────────

    def _refresh_devices(self):
        devs=self.dmx.list_devices(); self._devices=devs
        entries=[f"[{i}] {desc}" for i,desc in devs]+["— SIMULATION —"]
        self.dev_combo["values"]=entries
        if devs: self.dev_combo.current(0); self.dev_idx.set(devs[0][0])
        else: self.dev_combo.current(len(entries)-1)

    def _on_dev_select(self,*_):
        sel=self.dev_combo.current()
        if self._devices and sel<len(self._devices):
            self.dev_idx.set(self._devices[sel][0])

    def _is_simulation_selected(self): return self.dev_combo.get()=="— SIMULATION —"

    def _auto_simulation(self):
        """Démarre automatiquement en simulation si ENTTEC non disponible"""
        # Sélectionne simulation dans le combo
        vals = list(self.dev_combo["values"])
        if "— SIMULATION —" in vals:
            self.dev_combo.set("— SIMULATION —")
        # Active la simulation sans popup
        self.simulation = True
        self.btn.config(text="  STOP  ", bg="#ff3355", fg="white")
        self._update_dot()
        self._send()

    def _toggle(self):
        if not self.connected and not self.simulation:
            if self._is_simulation_selected():
                self.simulation=True
                self.btn.config(text="  STOP  ",bg="#ff3355",fg="white")
                self._update_dot(); self._send()
            else:
                if not FTD2XX_OK:
                    messagebox.showerror("Erreur","ftd2xx non installé.\n\npip install ftd2xx"); return
                if not self._devices:
                    messagebox.showwarning("Device","Aucun device FTDI D2XX trouvé."); return
                if self.dmx.connect(self.dev_idx.get()):
                    self.connected=True
                    self.btn.config(text="  DÉCONNECTER  ",bg="#ff3355",fg="white")
                    self._update_dot(); self._send()
                else:
                    messagebox.showerror("Erreur","Impossible d'ouvrir le device FTDI.")
        else:
            if self.connected: self.dmx.disconnect(); self.connected=False
            if self.simulation: self.simulation=False
            self.btn.config(text="  CONNECTER  ",bg="#e8e0ff",fg="#0a0a0f")
            self._update_dot()

    # ── MIDI ──────────────────────────────────────────────────────────────────

    def _refresh_midi_ports(self):
        if not MIDO_OK:
            self.midi_combo["values"]=["(mido non installé)"]; self.midi_combo.current(0); return
        ports=mido.get_input_names()
        if not ports:
            self.midi_combo["values"]=["(Aucun port MIDI)"]; self.midi_combo.current(0)
        else:
            self.midi_combo["values"]=ports
            for p in ports:
                if "loopbe" in p.lower() or "loop" in p.lower():
                    self.midi_combo.set(p); return
            self.midi_combo.current(0)

    def _toggle_midi(self):
        if not self.midi_running:
            if not MIDO_OK:
                messagebox.showerror("Erreur","mido non installé.\n\nUtilise py -3.12 pour lancer."); return
            port=self.midi_port_var.get()
            if not port or "Aucun" in port or "non installé" in port:
                messagebox.showwarning("MIDI","Sélectionnez un port MIDI valide."); return
            try:
                self.midi_in=mido.open_input(port); self.midi_running=True
                self.midi_thread=threading.Thread(target=self._midi_loop,daemon=True); self.midi_thread.start()
                self.midi_btn.config(text="  STOP MIDI  ",bg="#ff3355",fg="white")
                self._update_midi_dot()
            except Exception as e: messagebox.showerror("Erreur MIDI",str(e))
        else:
            self.midi_running=False
            if self.midi_in:
                try: self.midi_in.close()
                except: pass
                self.midi_in=None
            self.midi_btn.config(text="  ÉCOUTER  ",bg="#e8e0ff",fg="#0a0a0f")
            self.midi_last.set("—"); self._update_midi_dot()

    def _build_midi_lookup(self):
        """Précalcule note_midi -> [(spot_idx, canal_idx)]
        Ignore : cellules vides et spots désactivés (enabled=False)"""
        self._midi_lookup={}
        for si,spot_notes in enumerate(self.midi_map):
            if si>=len(self.spots): continue
            sp=self.spots[si]
            if not sp.enabled: continue  # spot désactivé uniquement
            for ci,note_var in enumerate(spot_notes):
                raw=note_var.get().strip()
                if not raw: continue
                n=note_name_to_midi(raw)
                if n is not None:
                    self._midi_lookup.setdefault(n,[]).append((si,ci))

    def _midi_loop(self):
        self._build_midi_lookup()
        while self.midi_running and self.midi_in:
            try:
                for msg in self.midi_in.iter_pending():
                    if msg.type in ("note_on","note_off"):
                        note    = msg.note
                        vel     = msg.velocity if msg.type=="note_on" else 0
                        dmx_val = min(255,vel*2)
                        # O(1) au lieu de O(36)
                        for si,ci in self._midi_lookup.get(note,[]):
                            self._apply_midi(si,ci,dmx_val,note,vel)
                time.sleep(0.005)
            except Exception as e: print(f"Erreur MIDI: {e}"); break

    def _apply_midi(self,spot_idx,canal_idx,dmx_val,note,vel):
        # Bypass dimmer : ignore les notes du canal 0 (DIM)
        if canal_idx==0 and self.bypass_dimmer.get(): return
        sp=self.spots[spot_idx]
        if not sp.enabled: return
        vals=[sp.dim,sp.r,sp.g,sp.b,getattr(sp,'s',0)]; vals[canal_idx]=dmx_val
        sp.update(*vals)
        if self.connected and not self.simulation:
            offs=[v.get() for v in sp.ch_offsets]
            self.dmx.set_channels(sp.ch_var.get(),vals[0],vals[1],vals[2],vals[3],
                                  getattr(sp,'special',0),offsets=offs)
        nm=midi_note_name(note)
        msg=f"{nm} vel={vel} → SPOT {spot_idx+1} {['DIM','R','G','B'][canal_idx]}={dmx_val}"
        self.root.after(0,lambda m=msg:self.midi_last.set(m))

    # ── Envoi ─────────────────────────────────────────────────────────────────

    def _send(self,*_):
        dim=self.dimmer.get(); r=self.r.get(); g=self.g.get(); b=self.b.get(); s=self.s.get()
        self.val_labels["DIM"].config(text=f"{dim:03d}")
        self.val_labels["R"].config(text=f"{r:03d}")
        self.val_labels["G"].config(text=f"{g:03d}")
        self.val_labels["B"].config(text=f"{b:03d}")
        if "S" in self.val_labels: self.val_labels["S"].config(text=f"{s:03d}")
        if "S" in self.val_labels: self.val_labels["S"].config(text=f"{s:03d}")
        self._update_wheel_cursor(r,g,b)
        for sp in self._selected_spots():
            if not sp.enabled: continue
            sp.update(dim,r,g,b,s)
            if self.connected and not self.simulation:
                offs=[v.get() for v in sp.ch_offsets]
                self.dmx.set_channels(sp.ch_var.get(),dim,r,g,b,s,offs)

    def _update_wheel_cursor(self, r, g, b):
        """Déplace le curseur du wheel selon la couleur RGB courante"""
        if not hasattr(self, '_wheel_cursor'): return
        WHEEL=100; cx=cy=WHEEL//2; radius=WHEEL//2-2
        # Convertit RGB -> HSV
        r2=r/255.0; g2=g/255.0; b2=b/255.0
        maxc=max(r2,g2,b2); minc=min(r2,g2,b2)
        v=maxc
        if maxc==0: s=0; h=0
        else:
            s=(maxc-minc)/maxc
            rc=(maxc-r2)/(maxc-minc+1e-9)
            gc=(maxc-g2)/(maxc-minc+1e-9)
            bc=(maxc-b2)/(maxc-minc+1e-9)
            if r2==maxc: h=bc-gc
            elif g2==maxc: h=2.0+rc-bc
            else: h=4.0+gc-rc
            h=(h/6.0)%1.0
        # Position dans le cercle
        angle=math.radians(h*360)
        dist=s*radius
        px=int(cx+dist*math.cos(angle))
        py=int(cy+dist*math.sin(angle))
        self.wheel_canvas.coords(self._wheel_cursor, px-4,py-4, px+4,py+4)
        self.wheel_canvas.itemconfig(self._wheel_cursor, fill="#ffffff", outline="#000000")
        self.wheel_canvas.tag_raise(self._wheel_cursor)

    def _draw_wheel(self, size):
        """Dessine le cercle chromatique HSV sur le canvas"""
        cx=cy=size//2; radius=size//2-2
        # Dessine pixel par pixel via des arcs très fins
        steps=360
        for deg in range(steps):
            angle_rad = math.radians(deg)
            # Couleur HSV : teinte=deg, saturation=1, valeur=1
            h=deg/360.0
            r2,g2,b2=self._hsv_to_rgb(h,1.0,1.0)
            color=f"#{r2:02x}{g2:02x}{b2:02x}"
            # Trait du centre vers le bord
            x1=cx+int(2*math.cos(angle_rad))
            y1=cy+int(2*math.sin(angle_rad))
            x2=cx+int(radius*math.cos(angle_rad))
            y2=cy+int(radius*math.sin(angle_rad))
            self.wheel_canvas.create_line(x1,y1,x2,y2,fill=color,width=2)
        # Centre blanc
        self.wheel_canvas.create_oval(cx-4,cy-4,cx+4,cy+4,fill="#ffffff",outline="")
        # Curseur position
        self._wheel_cursor=self.wheel_canvas.create_oval(
            cx-4,cy-4,cx+4,cy+4,fill="#ffffff",outline="#000000",width=2)

    def _hsv_to_rgb(self, h, s, v):
        if s==0: r=g=b=int(v*255); return r,g,b
        i=int(h*6); f=h*6-i; p=v*(1-s); q=v*(1-f*s); t=v*(1-(1-f)*s)
        i%=6
        if i==0: r,g,b=v,t,p
        elif i==1: r,g,b=q,v,p
        elif i==2: r,g,b=p,v,t
        elif i==3: r,g,b=p,q,v
        elif i==4: r,g,b=t,p,v
        else: r,g,b=v,p,q
        return int(r*255),int(g*255),int(b*255)

    def _on_wheel_click(self, event):
        """Clic sur le cercle : extrait la couleur et l'applique aux spots actifs"""
        WHEEL=100; cx=cy=WHEEL//2; radius=WHEEL//2-2
        dx=event.x-cx; dy=event.y-cy
        dist=math.sqrt(dx*dx+dy*dy)
        if dist>radius: return
        # Teinte selon l'angle
        angle=math.degrees(math.atan2(dy,dx))%360
        h=angle/360.0
        # Saturation selon la distance au centre
        s=min(1.0,dist/radius)
        r2,g2,b2=self._hsv_to_rgb(h,s,1.0)
        # Applique R/G/B sans changer le dimmer
        self.r.set(r2); self.g.set(g2); self.b.set(b2)
        # Déplace le curseur
        cx2=cx+int(dist*math.cos(math.radians(angle)))
        cy2=cy+int(dist*math.sin(math.radians(angle)))
        self.wheel_canvas.coords(self._wheel_cursor,cx2-4,cy2-4,cx2+4,cy2+4)
        self.wheel_canvas.itemconfig(self._wheel_cursor, fill="#ffffff", outline="#000000")
        self.wheel_canvas.tag_raise(self._wheel_cursor)

    def _off(self):
        self.dimmer.set(0); self.r.set(0); self.g.set(0); self.b.set(0); self.s.set(0)

    def _p(self,dim,r,g,b,s=0):
        self.dimmer.set(dim); self.r.set(r); self.g.set(g); self.b.set(b); self.s.set(s)


def main():
    root=tk.Tk()
    app=App(root)
    # Remplir la table d'adresses après création des spots
    app._finish_config()
    root.protocol("WM_DELETE_WINDOW",
        lambda:(app.dmx.disconnect(),app._toggle_midi() if app.midi_running else None,root.destroy()))
    root.mainloop()

if __name__=="__main__":
    main()
