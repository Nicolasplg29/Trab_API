import tkinter as tk
from tkinter import ttk, messagebox
import requests
import csv
import os
import threading
from datetime import date
from PIL import Image, ImageTk
from io import BytesIO
import ssl
import urllib3
urllib3.disable_warnings()
# ─────────────────────────────────────────
#  CONFIGURAÇÕES
# ─────────────────────────────────────────
API_KEY    = "uU0HtIuSrObhlCycbYJGo2NhSph7mBOVnj8j05Jc"
API_URL    = "https://api.nasa.gov/planetary/apod"
PASTA      = "fotos_nasa"
HISTORICO  = "historico.csv"

os.makedirs(PASTA, exist_ok=True)

# ─────────────────────────────────────────
#  FUNÇÕES DE NEGÓCIO
# ─────────────────────────────────────────
def buscar_apod(data_str):
    """Busca dados do APOD na API da NASA para uma data."""
    params = {"api_key": API_KEY, "date": data_str}
    resposta = requests.get(API_URL, params=params, timeout=30)
    resposta.raise_for_status()
    return resposta.json()


def baixar_imagem(url, nome_arquivo):
    """Baixa a imagem e salva na pasta fotos_nasa."""
    caminho = os.path.join(PASTA, nome_arquivo)
    if os.path.exists(caminho):
        return caminho
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    with open(caminho, "wb") as f:
        f.write(r.content)
    return caminho


def salvar_historico(dados):
    """Salva a entrada no histórico CSV."""
    novo = not os.path.exists(HISTORICO)
    with open(HISTORICO, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["data", "titulo", "url", "arquivo"])
        if novo:
            writer.writeheader()
        writer.writerow(dados)


def carregar_historico():
    """Retorna todas as entradas do histórico CSV."""
    if not os.path.exists(HISTORICO):
        return []
    with open(HISTORICO, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ─────────────────────────────────────────
#  INTERFACE TKINTER
# ─────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("NASA APOD Explorer — Nícolas, Tiago, Jhonatan")
        self.geometry("900x680")
        self.resizable(True, True)
        self.configure(bg="#050810")

        self._img_ref = None  # evita garbage collection da imagem
        self._dados_atual = None

        self._build_ui()

    # ── Layout principal ──────────────────
    def _build_ui(self):
        # Cabeçalho
        header = tk.Frame(self, bg="#0d1117", pady=14)
        header.pack(fill="x")

        tk.Label(
            header, text="NASA  APOD  EXPLORER",
            font=("Courier", 16, "bold"),
            bg="#0d1117", fg="#58a6ff"
        ).pack()

        tk.Label(
            header, text="Nícolas · Tiago · Jhonatan",
            font=("Courier", 10),
            bg="#0d1117", fg="#7d8590"
        ).pack()

        # Abas
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook",         background="#050810", borderwidth=0)
        style.configure("TNotebook.Tab",     background="#0d1117", foreground="#7d8590",
                        padding=[14, 6], font=("Courier", 10))
        style.map("TNotebook.Tab",
                  background=[("selected", "#161b22")],
                  foreground=[("selected", "#58a6ff")])

        self.abas = ttk.Notebook(self)
        self.abas.pack(fill="both", expand=True, padx=16, pady=12)

        self.aba_busca    = tk.Frame(self.abas, bg="#050810")
        self.aba_hist     = tk.Frame(self.abas, bg="#050810")

        self.abas.add(self.aba_busca, text="  🔭  Buscar foto  ")
        self.abas.add(self.aba_hist,  text="  📋  Histórico  ")

        self._build_aba_busca()
        self._build_aba_historico()

    # ── Aba Buscar ────────────────────────
    def _build_aba_busca(self):
        f = self.aba_busca

        # Controles
        ctrl = tk.Frame(f, bg="#050810", pady=10)
        ctrl.pack(fill="x", padx=20)

        tk.Label(ctrl, text="Data (AAAA-MM-DD):",
                 font=("Courier", 11), bg="#050810", fg="#e6edf3").pack(side="left")

        self.entry_data = tk.Entry(ctrl, font=("Courier", 11), width=14,
                                   bg="#161b22", fg="#e6edf3",
                                   insertbackground="#58a6ff",
                                   relief="flat", bd=6)
        self.entry_data.insert(0, str(date.today()))
        self.entry_data.pack(side="left", padx=10)

        self.btn_buscar = tk.Button(
            ctrl, text="▶  BUSCAR",
            font=("Courier", 11, "bold"),
            bg="#58a6ff", fg="#000000",
            relief="flat", padx=14, pady=4,
            cursor="hand2",
            command=self._buscar_thread
        )
        self.btn_buscar.pack(side="left")

        self.btn_baixar = tk.Button(
            ctrl, text="⬇  BAIXAR IMAGEM",
            font=("Courier", 10),
            bg="#161b22", fg="#58a6ff",
            relief="flat", padx=12, pady=4,
            cursor="hand2",
            state="disabled",
            command=self._baixar
        )
        self.btn_baixar.pack(side="left", padx=8)

        self.lbl_status = tk.Label(ctrl, text="", font=("Courier", 10),
                                   bg="#050810", fg="#7d8590")
        self.lbl_status.pack(side="left", padx=6)

        # Área de resultado
        resultado = tk.Frame(f, bg="#050810")
        resultado.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # Imagem
        self.lbl_img = tk.Label(resultado, bg="#0d1117",
                                 width=42, height=18, cursor="hand2")
        self.lbl_img.pack(side="left", padx=(0, 16))
        self.lbl_img.bind("<Button-1>", self._abrir_imagem_grande)

        # Texto
        info = tk.Frame(resultado, bg="#050810")
        info.pack(side="left", fill="both", expand=True)

        self.lbl_titulo = tk.Label(
            info, text="", font=("Courier", 13, "bold"),
            bg="#050810", fg="#e6edf3",
            wraplength=400, justify="left", anchor="w"
        )
        self.lbl_titulo.pack(fill="x", pady=(0, 6))

        self.lbl_data_foto = tk.Label(
            info, text="", font=("Courier", 10),
            bg="#050810", fg="#58a6ff", anchor="w"
        )
        self.lbl_data_foto.pack(fill="x", pady=(0, 10))

        # Descrição com scroll
        txt_frame = tk.Frame(info, bg="#050810")
        txt_frame.pack(fill="both", expand=True)

        scrollbar = tk.Scrollbar(txt_frame)
        scrollbar.pack(side="right", fill="y")

        self.txt_desc = tk.Text(
            txt_frame, font=("Courier", 10),
            bg="#0d1117", fg="#7d8590",
            relief="flat", wrap="word",
            yscrollcommand=scrollbar.set,
            state="disabled", padx=10, pady=10
        )
        self.txt_desc.pack(fill="both", expand=True)
        scrollbar.config(command=self.txt_desc.yview)

    # ── Aba Histórico ─────────────────────
    def _build_aba_historico(self):
        f = self.aba_hist

        topo = tk.Frame(f, bg="#050810", pady=10)
        topo.pack(fill="x", padx=20)

        tk.Label(topo, text="Fotos buscadas nesta sessão e anteriores:",
                 font=("Courier", 11), bg="#050810", fg="#e6edf3").pack(side="left")

        tk.Button(
            topo, text="↺  Atualizar",
            font=("Courier", 10),
            bg="#161b22", fg="#58a6ff",
            relief="flat", padx=10, pady=3,
            cursor="hand2",
            command=self._atualizar_historico
        ).pack(side="right")

        # Tabela
        cols = ("Data", "Título", "Arquivo salvo")
        style = ttk.Style()
        style.configure("Treeview",
                        background="#0d1117", foreground="#e6edf3",
                        fieldbackground="#0d1117", font=("Courier", 10),
                        rowheight=26)
        style.configure("Treeview.Heading",
                        background="#161b22", foreground="#58a6ff",
                        font=("Courier", 10, "bold"))
        style.map("Treeview", background=[("selected", "#1f3a5c")])

        frame_tree = tk.Frame(f, bg="#050810")
        frame_tree.pack(fill="both", expand=True, padx=20, pady=(0, 14))

        sb = tk.Scrollbar(frame_tree)
        sb.pack(side="right", fill="y")

        self.tree = ttk.Treeview(frame_tree, columns=cols, show="headings",
                                  yscrollcommand=sb.set)
        for col in cols:
            self.tree.heading(col, text=col)
        self.tree.column("Data",         width=100, anchor="center")
        self.tree.column("Título",       width=340)
        self.tree.column("Arquivo salvo",width=200)
        self.tree.pack(fill="both", expand=True)
        sb.config(command=self.tree.yview)

        self._atualizar_historico()

    # ── Ações ─────────────────────────────
    def _buscar_thread(self):
        """Roda a busca em thread separada pra não travar a UI."""
        self.btn_buscar.config(state="disabled")
        self.lbl_status.config(text="buscando...", fg="#d29922")
        t = threading.Thread(target=self._buscar, daemon=True)
        t.start()

    def _buscar(self):
        data_str = self.entry_data.get().strip()
        try:
            dados = buscar_apod(data_str)

            # Carrega imagem (apenas se for imagem, não vídeo)
            foto_tk = None
            if dados.get("media_type") == "image":
                r = requests.get(dados["url"], timeout=30)
                img = Image.open(BytesIO(r.content))
                img.thumbnail((380, 260))
                foto_tk = ImageTk.PhotoImage(img)

            self._dados_atual = dados
            self.after(0, lambda: self._atualizar_ui(dados, foto_tk))

        except requests.HTTPError as e:
            self.after(0, lambda: self._erro(f"Erro HTTP: {e}"))
        except Exception as e:
            self.after(0, lambda: self._erro(str(e)))

    def _atualizar_ui(self, dados, foto_tk):
        titulo = dados.get("title", "—")
        data   = dados.get("date", "—")
        desc   = dados.get("explanation", "")

        self.lbl_titulo.config(text=titulo)
        self.lbl_data_foto.config(text=f"📅  {data}")

        self.txt_desc.config(state="normal")
        self.txt_desc.delete("1.0", "end")
        self.txt_desc.insert("end", desc)
        self.txt_desc.config(state="disabled")

        if foto_tk:
            self._img_ref = foto_tk
            self.lbl_img.config(image=foto_tk, text="")
        else:
            self._img_ref = None
            self.lbl_img.config(image="", text="[vídeo — sem preview]",
                                 fg="#7d8590", font=("Courier", 10))

        self.btn_baixar.config(state="normal")
        self.btn_buscar.config(state="normal")
        self.lbl_status.config(text="✓ carregado", fg="#3fb950")

    def _baixar(self):
        if not self._dados_atual:
            return
        dados = self._dados_atual
        if dados.get("media_type") != "image":
            messagebox.showinfo("Aviso", "Este APOD é um vídeo — não é possível baixar a imagem.")
            return
        try:
            url  = dados.get("hdurl") or dados.get("url")
            ext  = url.split(".")[-1].split("?")[0]
            nome = f"{dados['date']}.{ext}"
            caminho = baixar_imagem(url, nome)

            salvar_historico({
                "data":    dados["date"],
                "titulo":  dados["title"],
                "url":     url,
                "arquivo": caminho
            })

            self._atualizar_historico()
            self.lbl_status.config(text=f"✓ salvo em {caminho}", fg="#3fb950")
            messagebox.showinfo("Sucesso", f"Imagem salva em:\n{caminho}")
        except Exception as e:
            messagebox.showerror("Erro", str(e))

    def _atualizar_historico(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for entry in reversed(carregar_historico()):
            self.tree.insert("", "end", values=(
                entry["data"],
                entry["titulo"],
                entry.get("arquivo", "—")
            ))

    def _erro(self, msg):
        self.btn_buscar.config(state="normal")
        self.lbl_status.config(text="✗ erro", fg="#f85149")
        messagebox.showerror("Erro", msg)

    def _abrir_imagem_grande(self, _event):
        """Abre a imagem em tamanho maior numa nova janela."""
        if not self._dados_atual or self._dados_atual.get("media_type") != "image":
            return
        try:
            url = self._dados_atual.get("hdurl") or self._dados_atual.get("url")
            r   = requests.get(url, timeout=20)
            img = Image.open(BytesIO(r.content))
            img.thumbnail((1000, 750))
            foto = ImageTk.PhotoImage(img)

            win = tk.Toplevel(self)
            win.title(self._dados_atual.get("title", "Foto"))
            win.configure(bg="#050810")
            lbl = tk.Label(win, image=foto, bg="#050810")
            lbl.image = foto
            lbl.pack(padx=10, pady=10)
        except Exception as e:
            messagebox.showerror("Erro", str(e))


# ─────────────────────────────────────────
#  INICIAR
# ─────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()
