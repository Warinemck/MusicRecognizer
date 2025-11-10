import sounddevice as sd
import wavio
import asyncio
from shazamio import Shazam
try:
    from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as SessionManager
    from winsdk.windows.media import MediaPlaybackType
    from winsdk.windows.media import control as media_control # <-- AÑADE ESTA LÍNEA
    # ELIMINA la línea que daba error (la de GetMediaPropertiesStatus)
    WINS_SDK_DISPONIBLE = True
except ImportError:
    WINS_SDK_DISPONIBLE = False
# ------------------------------------------------
import tkinter as tk
import tkinter as tk
from tkinter import font  # Importar para fuentes modernas
from PIL import Image, ImageTk, ImageDraw
from io import BytesIO
import requests
import threading
import tempfile
import random
import numpy as np
import time
import sys
import signal
from collections import deque
import os
from pynput import keyboard
import math  # Para las funciones de easing

# Variable global para la función de logging (se definirá después)
agregar_log = None

import ctypes

# --- (Las funciones y clases de aquí hasta "ToggleSwitch" no han cambiado) ---

def habilitar_antialiasing():
    """Habilita el antialiasing para las ventanas en Windows"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per monitor DPI aware
        except:
            pass
        print("Antialiasing habilitado para Windows")
    except Exception as e:
        print(f"No se pudo habilitar antialiasing: {e}")

habilitar_antialiasing()

def setup_ffmpeg():
    import subprocess
    import shutil
    possible_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ffmpeg', 'bin', 'ffmpeg.exe'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ffmpeg', 'ffmpeg.exe'),
        'ffmpeg.exe',
        'ffmpeg',
        'C:\\ffmpeg\\bin\\ffmpeg.exe',
        'C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe',
        'C:\\Program Files (x86)\\ffmpeg\\bin\\ffmpeg.exe',
    ]
    ffmpeg_path = None
    for path in possible_paths:
        try:
            if shutil.which(path) or os.path.exists(path):
                result = subprocess.run([path, '-version'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    ffmpeg_path = path
                    print(f"- ffmpeg: {path}")
                    break
        except:
            continue
    if ffmpeg_path:
        os.environ['FFMPEG_BINARY'] = ffmpeg_path
        os.environ['PATH'] = os.path.dirname(ffmpeg_path) + ';' + os.environ['PATH']
        print(f"- ffmpeg configurado: {ffmpeg_path}")
    else:
        print("- ffmpeg NO encontrado")

setup_ffmpeg()

fs = 44100
duration = 4
rotation_speed = 2
rotation_delay = 33
fondo_ventana = "green"
scroll_speed = 3

def ease_out_quad(t):
    return 1 - (1 - t) * (1 - t)

def ease_in_out_quad(t):
    if t < 0.5:
        return 2 * t * t
    else:
        return 1 - math.pow(-2 * t + 2, 2) / 2

def ease_out_back(t):
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * math.pow(t - 1, 3) + c1 * math.pow(t - 1, 2)

class GlobalHotkey:
    def __init__(self):
        self.keys_pressed = set()
        self.recognition_callback = None
        self.exit_callback = None
        self.listener = None
        
    def start(self, recognition_callback, exit_callback):
        self.recognition_callback = recognition_callback
        self.exit_callback = exit_callback
        self.listener = keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release
        )
        self.listener.start()
        
    def on_press(self, key):
        try:
            key_name = self.get_key_name(key)
            if key_name:
                self.keys_pressed.add(key_name)
                self.check_combinations()
        except Exception as e:
            if agregar_log: agregar_log(f"Error en on_press: {e}")

    def on_release(self, key):
        try:
            key_name = self.get_key_name(key)
            if key_name and key_name in self.keys_pressed:
                self.keys_pressed.remove(key_name)
        except Exception as e:
            if agregar_log: agregar_log(f"Error en on_release: {e}")

    def get_key_name(self, key):
        if hasattr(key, 'name'):
            if key.name in ['shift', 'shift_r', 'shift_l']:
                return key.name
            if key.name == 'page_down':
                return 'page_down'
            return key.name
        elif hasattr(key, 'char') and key.char:
            return key.char.lower()
        return None

    def check_combinations(self):
        shift_keys = {'shift', 'shift_l', 'shift_r'}
        has_any_shift = any(shift in self.keys_pressed for shift in shift_keys)
        has_z_x = {'z', 'x'}.issubset(self.keys_pressed)
        
        if has_any_shift and has_z_x:
            if self.recognition_callback:
                self.recognition_callback()
            keys_to_remove = [k for k in self.keys_pressed if k in ['z', 'x'] or 'shift' in k]
            for key in keys_to_remove:
                self.keys_pressed.discard(key)
            return
        
        if 'shift_r' in self.keys_pressed and 'page_down' in self.keys_pressed:
            if self.exit_callback:
                self.exit_callback()
            self.keys_pressed.discard('shift_r')
            self.keys_pressed.discard('page_down')

    def stop(self):
        if self.listener:
            self.listener.stop()

class APIManager:
    def __init__(self):
        self.last_recognition_time = 0
        self.cooldown_after_request = 10
        self.recent_songs = deque(maxlen=5)
        self.is_processing = False
        
    def can_make_request(self):
        current_time = time.time()
        return (current_time - self.last_recognition_time) >= self.cooldown_after_request and not self.is_processing
    
    def update_after_request(self, song_info=None):
        self.last_recognition_time = time.time()
        self.is_processing = False
        if song_info:
            self.recent_songs.append(song_info)
    
    def is_duplicate(self, artist, title):
        if not artist or not title:
            return False
        current_song = f"{artist} - {title}"
        return any(current_song == song for song in self.recent_songs)

def encontrar_mezcla_estereo():
    dispositivos = sd.query_devices()
    for i, d in enumerate(dispositivos):
        if "mezcla estéreo" in d['name'].lower() or "stereo mix" in d['name'].lower():
            return i
    return None

def grabar_audio(filename):
    idx = encontrar_mezcla_estereo()
    if idx is None:
        raise Exception("No se encontró Mezcla estéreo.")
    sd.default.device = idx
    if agregar_log: agregar_log("- Comienzo de la muestra de audio")
    audio = sd.rec(int(duration * fs), samplerate=fs, channels=2, dtype='int16')
    
    for i in range(duration):
        time.sleep(1)
        if agregar_log: agregar_log(f"- Muestra: {i+1}/{duration}s")
    
    sd.wait()
    wavio.write(filename, audio, fs, sampwidth=2)
    if agregar_log: agregar_log("- Muestra de audio completa")
    return audio

async def reconocer_cancion(filename):
    try:
        if agregar_log: agregar_log("- Inicio de reconocimiento")
        shazam = Shazam()
        
        try:
            out = await asyncio.wait_for(shazam.recognize(filename), timeout=15.0)
            if agregar_log: agregar_log("- Reconocimiento completo")
        except asyncio.TimeoutError:
            if agregar_log: agregar_log("- Reconocimiento tardó demasiado")
            return None, None, None
        
        if out and out.get('track'):
            artista = out['track']['subtitle']
            titulo = out['track']['title']
            caratula = out['track'].get('images', {}).get('coverart', '')
            return artista, titulo, caratula
        else:
            return None, None, None
            
    except Exception as e:
        if agregar_log: agregar_log(f"- Error al reconocer: {e}")
        return None, None, None

def crear_vinilo(caratula_url):
    disco_size = 300
    centro_size = 100
    
    try:
        if os.path.exists("vinilo.png"):
            disco = Image.open("vinilo.png").convert("RGBA")
            if disco.size != (disco_size, disco_size):
                disco = disco.resize((disco_size, disco_size), Image.LANCZOS)
            if agregar_log: agregar_log("- Vinilo cargado desde PNG")
        else:
            if agregar_log: agregar_log("- No se encontró vinilo.png, usando fallback")
            disco = Image.new("RGBA", (disco_size, disco_size), (40, 40, 40, 255))
            draw = ImageDraw.Draw(disco)
            draw.ellipse((0, 0, disco_size, disco_size), fill=(40, 40, 40, 255))
        
        if caratula_url:
            try:
                response = requests.get(caratula_url, timeout=5)
                if response.status_code == 200:
                    caratula = Image.open(BytesIO(response.content)).convert("RGBA")
                    caratula = caratula.resize((centro_size, centro_size), Image.LANCZOS)
                    mask = Image.new("L", caratula.size, 0)
                    draw_mask = ImageDraw.Draw(mask)
                    draw_mask.ellipse((0, 0, centro_size, centro_size), fill=255)
                    caratula.putalpha(mask)
                    pos = (disco_size//2 - centro_size//2, disco_size//2 - centro_size//2)
                    disco.paste(caratula, pos, caratula)
                    if agregar_log: agregar_log("- Carátula agregada al vinilo")
                else:
                    if agregar_log: agregar_log(f"- Error HTTP {response.status_code} al cargar carátula")
            except Exception as e:
                if agregar_log: agregar_log(f"- Error al cargar la carátula: {e}")
        
        return disco
        
    except Exception as e:
        if agregar_log: agregar_log(f"- Error al crear vinilo: {e}")
        disco = Image.new("RGBA", (disco_size, disco_size), (40, 40, 40, 255))
        return disco

class VentanaDisco:
    def __init__(self, caja_toggle_widget=None):
        self.root = tk.Toplevel()
        self.root.title("Vinilo")
        self.root.configure(bg=fondo_ventana)
        # Iniciar en tamaño pequeño
        self.root.geometry("350x350+100+100") 
        self.root.resizable(False, False)
        
        # Iniciar en tamaño pequeño
        self.canvas = tk.Canvas(self.root, width=350, height=350, bg=fondo_ventana, highlightthickness=0)
        self.canvas.pack()

        self.fondo_caja_item = self.canvas.create_image(180, 20, anchor="nw")
        self.disco_item = self.canvas.create_image(-400, 20, anchor="nw")
        self.caja_item = self.canvas.create_image(180, 20, anchor="nw")
        
        self.caja_img_tk = None
        self.fondo_caja_img_tk = None
        self.cargar_caja_vinilo() 
        self.cargar_fondo_caja()

        # --- Estado inicial: Oculto ---
        self.caja_elementos_visible = False
        self.canvas.itemconfig(self.fondo_caja_item, state='hidden')
        self.canvas.itemconfig(self.caja_item, state='hidden')
        # -----------------------------
        
        self.disco_img = None
        self.disco_rotacion = 0
        self.running = True
        self.current_image_tk = None
        self.is_visible = True

        self.is_animating_resize = False
        
        # --- NUEVO: Estado de Animación ---
        self.anim_alternativa_active = False 

        self.caja_toggle_widget = caja_toggle_widget
        # ---------------------------------
        
        self.animar_disco()
        self.root.deiconify()

    def cargar_caja_vinilo(self):
        try:
            caja_pil = Image.open("caja_vinilo.png").convert("RGBA")
            caja_pil = caja_pil.resize((300, 300), Image.LANCZOS) 
            self.caja_img_tk = ImageTk.PhotoImage(caja_pil)
            self.canvas.itemconfig(self.caja_item, image=self.caja_img_tk)
        except FileNotFoundError:
            if agregar_log: agregar_log("- No se encontro caja_vinilo.png.")
            self.canvas.create_text(175, 175, text="Falta caja_vinilo.png", 
                                     fill="red", anchor="center")
        except Exception as e:
            if agregar_log: agregar_log(f"- Error al cargar la imagen: {e}")

    def cargar_fondo_caja(self):
        try:
            fondo_pil = Image.open("fondo_caja.png").convert("RGBA")
            fondo_pil = fondo_pil.resize((300, 300), Image.LANCZOS) 
            self.fondo_caja_img_tk = ImageTk.PhotoImage(fondo_pil)
            self.canvas.itemconfig(self.fondo_caja_item, image=self.fondo_caja_img_tk)
        except FileNotFoundError:
            if agregar_log: agregar_log("- No se encontro fondo_caja.png.")
        except Exception as e:
            if agregar_log: agregar_log(f"- Error al cargar la imagen: {e}")
    
    # --- MÉTODO NUEVO ---
    def set_anim_alternativa(self, state: bool):
        """Establece el modo de animación (True=Alternativa, False=Normal)."""
        self.anim_alternativa_active = state
        if state:
            if agregar_log: agregar_log("- Animación alternativa: ACTIVADA")
        else:
            if agregar_log: agregar_log("- Animación alternativa: DESACTIVADA")
    # --------------------

    def toggle_caja_completa(self):
        """Muestra u oculta la caja Y el fondo de la caja."""
        if self.caja_elementos_visible:
            # --- Va a Ocultar ---
            self.canvas.itemconfig(self.fondo_caja_item, state='hidden')
            self.canvas.itemconfig(self.caja_item, state='hidden') 
            self.caja_elementos_visible = False
            if agregar_log: agregar_log("- Caja oculta")
            
            self._animar_ventana(target_width=350)
            
        else:
            # --- Va a Mostrar ---
            self.canvas.itemconfig(self.fondo_caja_item, state='normal')
            self.canvas.itemconfig(self.caja_item, state='normal') 
            self.caja_elementos_visible = True
            if agregar_log: agregar_log("- Caja mostrada")
            
            self._animar_ventana(target_width=500)
    
    def _animar_ventana(self, target_width, duration_ms=500):
        """Anima suavemente el ancho de la ventana y el canvas."""
        
        # Prevenir animaciones duplicadas si se pulsa rápido
        if hasattr(self, 'is_animating_resize') and self.is_animating_resize:
            return 

        self.is_animating_resize = True
        
        # Obtener tamaño actual
        start_width = self.root.winfo_width()
        current_height = self.root.winfo_height() # La altura no cambia (350)
        
        steps = 60 # Número de fotogramas para la animación
        step_delay = max(1, duration_ms // steps) # Evitar división por cero
        
        # Calcular el cambio total
        delta_width = target_width - start_width

        # --- Esta es la función que pediste ---
        def animar_paso(step):
            # Asegurarse de que la ventana exista y la app esté corriendo
            if not self.running or not self.root.winfo_exists():
                self.is_animating_resize = False
                # --- Reactivar en caso de error/cierre ---
                if self.caja_toggle_widget:
                    self.caja_toggle_widget.config(state='normal')
                # ----------------------------------------
                return

            progress = step / steps
            eased_progress = ease_in_out_quad(progress) # Usamos tu easing

            # Calcular el nuevo ancho
            current_width = int(start_width + (delta_width * eased_progress))

            try:
                # Aplicar el nuevo tamaño a la ventana y al canvas
                self.root.geometry(f"{current_width}x{current_height}")
                self.canvas.config(width=current_width, height=current_height)
            except tk.TclError:
                # La ventana fue destruida, detener animación
                self.is_animating_resize = False
                # --- Reactivar en caso de error ---
                if self.caja_toggle_widget:
                    self.caja_toggle_widget.config(state='normal')
                # --------------------------------
                return

            if step < steps:
                # Siguiente fotograma
                self.root.after(step_delay, lambda: animar_paso(step + 1))
            else:
                # Asegurar tamaño final exacto
                self.root.geometry(f"{target_width}x{current_height}")
                self.canvas.config(width=target_width, height=current_height)
                self.is_animating_resize = False
                
                # --- Reactivar al finalizar ---
                if self.caja_toggle_widget:
                    self.caja_toggle_widget.config(state='normal')
                # ------------------------------

        # Iniciar la animación
        animar_paso(0)

    def actualizar_color(self, nuevo_color):
        self.root.configure(bg=nuevo_color)
        self.canvas.configure(bg=nuevo_color)

    def mostrar_disco(self, caratula_url=None):
        if agregar_log: agregar_log("- Creando vinilo")
        vinilo = crear_vinilo(caratula_url)
        self.disco_img = vinilo
        
        if not self.is_visible:
            self.root.deiconify()
            self.is_visible = True
        
        self.animacion_entrada()

    def animar_disco(self):
        if self.disco_img and self.running:
            try:
                self.disco_rotacion = (self.disco_rotacion + rotation_speed) % 360
                rotada = self.disco_img.rotate(self.disco_rotacion, resample=Image.BICUBIC, expand=False)
                img_tk = ImageTk.PhotoImage(rotada)
                self.canvas.itemconfig(self.disco_item, image=img_tk)
                self.current_image_tk = img_tk
            except Exception as e:
                if agregar_log: agregar_log(f"- Error en la animacion: {e}")
        
        if self.running:
            self.root.after(rotation_delay, self.animar_disco)

    def animacion_entrada(self):
        """Animación de entrada con lógica de estado."""
        
        # --- LÓGICA MODIFICADA ---
        target_x = 25 # El destino siempre es 25
        
        # Si la anim. alternativa está activa Y la caja está visible...
        if self.anim_alternativa_active and self.caja_elementos_visible:
            start_x = 180 # Empezar "dentro" de la caja
        else:
            start_x = -400 # Empezar fuera de la pantalla
        # -------------------------
            
        duration_ms = 600
        steps = 40
        step_delay = duration_ms // steps
        
        def animar_paso(step):
            progress = step / steps
            eased_progress = ease_out_quad(progress)
            current_x = start_x + (target_x - start_x) * eased_progress
            self.canvas.coords(self.disco_item, current_x, 20)
            
            if step < steps:
                self.root.after(step_delay, lambda: animar_paso(step + 1))
            else:
                if agregar_log: agregar_log("- Disco mostrado")
        
        animar_paso(0)

    def animacion_salida(self):
        """Animación de salida con lógica de estado."""
        try:
            start_x = self.canvas.coords(self.disco_item)[0]
        except:
            start_x = 25
            
        # Lógica para decidir el destino
        if self.anim_alternativa_active and self.caja_elementos_visible:
            target_x = 180 # Ocultarse "dentro" de la caja
        else:
            target_x = -400 # Ocultarse fuera de la pantalla

        duration_ms = 450
        steps = 30
        step_delay = duration_ms // steps
        
        def animar_paso(step):
            progress = step / steps
            eased_progress = ease_in_out_quad(progress)
            current_x = start_x + (target_x - start_x) * eased_progress
            
            try:
                self.canvas.coords(self.disco_item, current_x, 20)
            except tk.TclError:
                 # La ventana fue destruida
                 return
            
            if step < steps:
                self.root.after(step_delay, lambda: animar_paso(step + 1))
            else:
                # --- ¡AQUÍ ESTÁ EL ARREGLO! ---
                # Solo borra la imagen si el destino era fuera de la pantalla
                if target_x == -400:
                    self.disco_img = None
                    self.canvas.itemconfig(self.disco_item, image="")
                    self.current_image_tk = None
                
                if agregar_log: agregar_log("- Vinilo / texto ocultos")
                # ---------------------------------
        
        animar_paso(0)

    def ocultar_ventana(self):
        self.root.withdraw()
        self.is_visible = False

    def mostrar_ventana(self):
        self.root.deiconify()
        self.is_visible = True

class VentanaTexto:
    def __init__(self):
        self.root = tk.Toplevel()
        self.root.title("Titulo")
        self.root.configure(bg="black")
        self.root.geometry("400x120+100+500")
        self.root.resizable(False, False)
        self.root.configure(padx=10, pady=10)
        
        self.canvas = tk.Canvas(self.root, width=580, height=100, 
                                 bg="black", highlightthickness=0)
        self.canvas.pack()

        self.text_id = None
        self.recuadro = None
        self.x_actual = 0
        self.scroll_speed = 2
        self.texto_moviendo = False
        self.is_visible = True
        
        self.box_width = 300
        self.box_height = 60
        self.canvas_width = 380
        self.canvas_height = 100
        
        self.root.deiconify()

    def actualizar_color(self, nuevo_color):
        self.root.configure(bg=nuevo_color)
        self.canvas.configure(bg=nuevo_color)

    def mostrar_texto(self, texto):
        self.canvas.delete("all")
        color = random.choice(["#FF69B4", "#800080", "#913378", "#405CA5"])
        x0 = self.canvas_width + 100
        x1 = x0 + self.box_width
        y0 = (self.canvas_height - self.box_height) // 2
        y1 = y0 + self.box_height
        self.x_actual = self.canvas_width + 100

        if not self.is_visible:
            self.root.deiconify()
            self.is_visible = True

        self.recuadro = self._crear_recuadro_redondeado(x0, y0, x1, y1, 15, color)
        self.text_id = self.canvas.create_text(
            (x0 + x1) // 2, (y0 + y1) // 2,
            text=texto, fill="black",
            font=("Arial", 14, "bold"), anchor="center"
        )
        self.animacion_entrada()

    def _crear_recuadro_redondeado(self, x0, y0, x1, y1, r, color):
        items = []
        items.append(self.canvas.create_rectangle(x0 + r, y0, x1 - r, y1, fill=color, outline=""))
        items.append(self.canvas.create_rectangle(x0, y0 + r, x1, y1 - r, fill=color, outline=""))
        items.append(self.canvas.create_oval(x0, y0, x0 + 2 * r, y0 + 2 * r, fill=color, outline=""))
        items.append(self.canvas.create_oval(x1 - 2 * r, y0, x1, y0 + 2 * r, fill=color, outline=""))
        items.append(self.canvas.create_oval(x0, y1 - 2 * r, x0 + 2 * r, y1, fill=color, outline=""))
        items.append(self.canvas.create_oval(x1 - 2 * r, y1 - 2 * r, x1, y1, fill=color, outline=""))
        return items

    def animacion_entrada(self):
        start_x = self.x_actual
        target_x = (self.canvas_width - self.box_width) // 2
        duration_ms = 600
        steps = 30
        step_delay = duration_ms // steps
        
        def animar_paso(step):
            progress = step / steps
            eased_progress = ease_out_quad(progress)
            current_x = start_x + (target_x - start_x) * eased_progress
            
            if self.recuadro and self.text_id:
                for item in self.recuadro + [self.text_id]:
                    self.canvas.move(item, current_x - self.x_actual, 0)
                self.x_actual = current_x
            
            if step < steps:
                self.root.after(step_delay, lambda: animar_paso(step + 1))
            else:
                if not self.texto_moviendo:
                    self.texto_moviendo = True
                    self.scroll_text()
        animar_paso(0)

    def scroll_text(self):
        if not self.text_id: return
        bbox = self.canvas.bbox(self.text_id)
        if not bbox: return
        
        text_width = bbox[2] - bbox[0]
        canvas_width = self.canvas_width

        if text_width <= self.box_width - 40:
            if self.recuadro:
                box_bbox = self.canvas.bbox(self.recuadro[0])
                if box_bbox:
                    box_center_x = (box_bbox[0] + box_bbox[2]) // 2
                    box_center_y = (box_bbox[1] + box_bbox[3]) // 2
                    self.canvas.coords(self.text_id, box_center_x, box_center_y)
            return

        self.canvas.move(self.text_id, -self.scroll_speed, 0)
        bbox = self.canvas.bbox(self.text_id)
        
        if bbox[2] < 0:
            self.canvas.move(self.text_id, canvas_width + text_width, 0)
        if self.texto_moviendo:
            self.canvas.after(33, self.scroll_text)

    def animacion_salida(self):
        start_x = self.x_actual
        target_x = self.canvas_width + 100
        duration_ms = 450
        steps = 30
        step_delay = duration_ms // steps
        
        def animar_paso(step):
            progress = step / steps
            eased_progress = ease_in_out_quad(progress)
            current_x = start_x + (target_x - start_x) * eased_progress
            
            if self.recuadro and self.text_id:
                for item in self.recuadro + [self.text_id]:
                    self.canvas.move(item, current_x - self.x_actual, 0)
                self.x_actual = current_x
                
            if step < steps:
                self.root.after(step_delay, lambda: animar_paso(step + 1))
            else:
                self.canvas.delete("all")
                self.recuadro = None
                self.text_id = None
                self.texto_moviendo = False
        animar_paso(0)

    def ocultar_ventana(self):
        self.root.withdraw()
        self.is_visible = False

    def mostrar_ventana(self):
        self.root.deiconify()
        self.is_visible = True

class NowPlaying:
    def __init__(self, root, caja_toggle_widget=None, dummy_toggle_widget=None, anim_alternativa_toggle_widget=None, auto_event_toggle_widget=None):
        self.root = root
        
        # --- ARREGLO: Guarda las referencias PRIMERO ---
        self.caja_toggle_widget = caja_toggle_widget
        self.dummy_toggle_widget = dummy_toggle_widget
        self.anim_alternativa_toggle_widget = anim_alternativa_toggle_widget
        self.auto_event_toggle_widget = auto_event_toggle_widget
        # ---------------------------------------------

        # --- Ahora sí puedes usarlas ---
        self.ventana_disco = VentanaDisco(caja_toggle_widget=self.caja_toggle_widget) 
        self.ventana_texto = VentanaTexto()
        # ---------------------------------------------
        
        self.cancion_actual = None
        self.api_manager = APIManager()
        self.dummy_is_active = False
        
        self.hotkey = GlobalHotkey()
# ... (el resto de la función sigue igual)
        self.hotkey.start(
            recognition_callback=self.trigger_shazam_recognition,
            exit_callback=self.trigger_exit_animation
        )
        
        self.last_activation_time = 0
        self.activation_cooldown = 2

        # --- NUEVO: Estado del monitor de EVENTOS ---
        self.auto_event_is_active = False
        self.media_event_thread = None
        self.async_loop = None           # Loop para el hilo de eventos
        self.manager = None              # El manager de sesiones de media
        self.current_session = None      # La sesión actual (Spotify, Chrome, etc.)
        self.last_media_title = None     # Para evitar disparos duplicados
        self.last_logged_title = None
        
        if not WINS_SDK_DISPONIBLE:
            if self.auto_event_toggle_widget:
                self.auto_event_toggle_widget.config(state='disabled')
        # ------------------------------------------

    # --- MÉTODO NUEVO (Reemplaza a toggle_auto_reconocimiento) ---
    def toggle_auto_event_listener(self):
        """Inicia o detiene el monitor de eventos de media."""
        if not self.auto_event_toggle_widget or not WINS_SDK_DISPONIBLE:
            return

        if self.auto_event_toggle_widget.is_on:
            self.start_media_event_listener()
        else:
            self.stop_media_event_listener()

    # --- MÉTODO NUEVO (Reemplaza a start_audio_monitor) ---
    def start_media_event_listener(self):
        """Inicia el hilo que escucha los eventos de media de Windows."""
        if self.media_event_thread is not None and self.media_event_thread.is_alive():
            return # Ya está corriendo

        if agregar_log: agregar_log("- Iniciando monitor de eventos multimedia...")
        self.auto_event_is_active = True
        self.media_event_thread = threading.Thread(target=self._media_event_loop, daemon=True)
        self.media_event_thread.start()

    # --- MÉTODO NUEVO (Reemplaza a stop_audio_monitor) ---
    def stop_media_event_listener(self):
        """Detiene el hilo del monitor de eventos."""
        self.auto_event_is_active = False
        
        if self.async_loop:
            # Programamos la detención y limpieza en el hilo de asyncio
            self.async_loop.call_soon_threadsafe(self.async_loop.stop)
            
        self.media_event_thread = None
        if agregar_log: agregar_log("- Monitor de eventos multimedia detenido.")

    # --- MÉTODO NUEVO (Hilo principal del monitor de eventos) ---
    def _media_event_loop(self):
        """
        Función que corre en un hilo. Inicia un loop de asyncio
        para registrar los event handlers de WinSDK.
        """
        self.async_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.async_loop)
        
        try:
            # Registra los handlers
            self.async_loop.run_until_complete(self._setup_event_handlers())
            # Mantiene el hilo vivo para recibir eventos
            self.async_loop.run_forever()
        except Exception as e:
            if agregar_log: agregar_log(f"- Error en hilo de eventos: {e}")
        finally:
            # Cuando run_forever() se detiene (por self.stop_media_event_listener)
            if agregar_log: agregar_log("- Limpiando hilo de eventos...")
            self.async_loop.run_until_complete(self._cleanup_event_handlers())
            self.async_loop.close()
            self.async_loop = None

    # --- MÉTODO NUEVO (Se ejecuta en el hilo de asyncio) ---
    async def _setup_event_handlers(self):
        """Se conecta al SessionManager de Windows."""
        try:
            self.manager = await SessionManager.request_async()
            # Suscribirse al evento de "cambio de sesión"
            self.manager.add_current_session_changed(self._on_session_changed_handler)
            
            # --- LÓGICA CORREGIDA ---
            # Procesar la sesión que ya esté activa al iniciar
            self.current_session = self.manager.get_current_session()
            
            if self.current_session:
                # Suscribirse a los cambios de esa sesión (ej. cambio de canción)
                self.current_session.add_media_properties_changed(self._on_media_properties_changed_handler)
                self.root.after(0, lambda: agregar_log("- Monitor: Suscrito a la sesión activa."))
                # Comprobar la canción actual inmediatamente
                asyncio.run_coroutine_threadsafe(self._check_media_properties(self.current_session), self.async_loop)
            # --- FIN DE CORRECCIÓN ---
                
            self.root.after(0, lambda: agregar_log("- Monitor de eventos: Abierto"))
        except Exception as e:
             self.root.after(0, lambda: agregar_log(f"- Error al conectar con WinSDK: {e}"))

    # --- MÉTODO NUEVO (Se ejecuta en el hilo de asyncio) ---
    async def _cleanup_event_handlers(self):
        """Se desconecta de los eventos para una salida limpia."""
        if self.current_session:
            try:
                self.current_session.remove_media_properties_changed(self._on_media_properties_changed_handler)
            except Exception as e: pass # El evento ya podría no ser válido
        
        if self.manager:
            try:
                self.manager.remove_current_session_changed(self._on_session_changed_handler)
            except Exception as e: pass
            
        self.current_session = None
        self.manager = None
        self.last_media_title = None
        self.root.after(0, lambda: agregar_log("- Monitor de eventos: Cerrado"))

    # --- MÉTODO NUEVO (Handler llamado por WinSDK en hilo asyncio) ---
    def _on_session_changed_handler(self, sender, args): # Ignoramos sender y args
        """Ocurre cuando cambias de app (ej. de Spotify a Chrome)."""
        if not self.auto_event_is_active: return

        # Pedirle al manager la nueva sesión
        new_session = self.manager.get_current_session()
        self.root.after(0, lambda: agregar_log("- Monitor: Cambio de sesión"))

        # Limpiar handler de la sesión anterior
        if self.current_session:
            try:
                self.current_session.remove_media_properties_changed(self._on_media_properties_changed_handler)
            except Exception as e:
                pass 

        self.current_session = new_session

        # Suscribirse a la nueva sesión
        if self.current_session:
            try:
                self.current_session.add_media_properties_changed(self._on_media_properties_changed_handler)
                self.root.after(0, lambda: agregar_log("- Monitor: Suscrito a nueva sesión."))
                
                # --- LÓGICA CORREGIDA ---
                # Le decimos que use la sesión que acabamos de guardar
                asyncio.run_coroutine_threadsafe(self._check_media_properties(None), self.async_loop)
            except Exception as e:
                pass
                
    # --- MÉTODO NUEVO (Handler llamado por WinSDK en hilo asyncio) ---
    def _on_media_properties_changed_handler(self, sender, args): # Ignoramos sender y args
        """Ocurre cuando la canción cambia DENTRO de una app."""
        if not self.auto_event_is_active: 
            return
        asyncio.run_coroutine_threadsafe(self._check_media_properties(None), self.async_loop)

    # --- MÉTODO NUEVO (Función Async que comprueba la canción) ---
    async def _check_media_properties(self, session_arg): # 'session_arg' ahora se ignora
        """Obtiene los metadatos de la sesión y decide si lanzar Shazam."""
        
        session = self.current_session

        if not session or not self.auto_event_is_active:
            return
            
        try:
            props = await session.try_get_media_properties_async()

            if not props:
                return # El evento no tiene propiedades, ignorar

            if not props.playback_type:
                return # El evento es 'fantasma' (no tiene tipo), ignorar

            title = props.title
            if not title:
                return # El evento no tiene título (ej. un anuncio), ignorar

            artist = props.artist
            full_title = f"{artist} - {title}"
            safe_type_name = props.playback_type.name # Ahora esto es seguro

            if full_title == self.last_logged_title:
                return
            self.last_logged_title = full_title
            self.root.after(0, lambda t=full_title, tn=safe_type_name: agregar_log(f"- Evento: Título='{t}', Tipo='{tn}'"))

            current_playback_type = props.playback_type
            if current_playback_type != MediaPlaybackType.MUSIC and current_playback_type != MediaPlaybackType.VIDEO:
                self.root.after(0, lambda: agregar_log(f"- Evento: Ignorado "))
                return
            if full_title != self.last_media_title:
                if self.api_manager.can_make_request():
                    self.last_media_title = full_title
                    
                    self.root.after(0, lambda: agregar_log(f"- Evento: Nuevo titulo"))
                    self.root.after(0, self.trigger_shazam_recognition)
                else:
                    self.root.after(0, lambda: agregar_log(f"- Evento: No se pudo verificar disponibilidad"))
            
        except Exception as e_obj:
            error_message = str(e_obj)
            self.root.after(0, lambda: agregar_log(f"- Error al chequear propiedades: {error_message}"))
            pass

    # --- MÉTODO MODIFICADO ---
    def trigger_shazam_recognition(self): # Ya no necesita 'triggered_by_auto_monitor'
        
        current_time = time.time()
        
        # Cooldown de activación (evita spam de hotkey)
        if current_time - self.last_activation_time < self.activation_cooldown:
            return
        
        if self.api_manager.is_processing:
            if agregar_log: agregar_log("- Ya hay un reconocimiento en cola")
            return
            
        if not self.api_manager.can_make_request():
            time_since_last = time.time() - self.api_manager.last_recognition_time
            remaining = max(0, self.api_manager.cooldown_after_request - time_since_last)
            if agregar_log: agregar_log(f"- Coldown: {remaining:.1f} segundos")
            return
        
        self.ventana_disco.mostrar_ventana()
        self.ventana_texto.mostrar_ventana()
        
        self.api_manager.is_processing = True
        self.last_activation_time = current_time
        
        thread = threading.Thread(target=self._execute_shazam_recognition, daemon=True)
        thread.start()

    # ... (trigger_exit_animation, _execute_exit_animation, _execute_shazam_recognition,
    #      actualizar_interfaz permanecen SIN CAMBIOS) ...

    # --- MÉTODO MODIFICADO ---
    def cleanup(self):
        if self.hotkey:
            self.hotkey.stop()
        self.stop_media_event_listener()

    def toggle_dummy_display(self):
        """Activa o desactiva la vista de prueba."""
        
        if self.dummy_is_active:
            # Si el modo prueba está ACTIVO, lo desactiva
            if agregar_log: agregar_log("- Modo de prueba desactivado")
            self._execute_exit_animation() # Llama a la animación de salida
            self.dummy_is_active = False
            
        else:
            # Si el modo prueba está INACTIVO, lo activa
            if agregar_log: agregar_log("- Modo de prueba activado")
            
            if self.cancion_actual:
                self._execute_exit_animation()
            
            self.dummy_is_active = True
            
            def show_dummy():
                if not self.dummy_is_active:
                    return
                    
                self.ventana_disco.mostrar_ventana()
                self.ventana_texto.mostrar_ventana()
                
                self.ventana_disco.mostrar_disco(caratula_url=None)
                self.ventana_texto.mostrar_texto("Test - Modo de Prueba")
                
                self.cancion_actual = "DUMMY_MODE" 

            self.root.after(500, show_dummy)

    # --- MÉTODO NUEVO ---
    def toggle_anim_alternativa(self):
        """Pasa el estado de la animación alternativa a la VentanaDisco."""
        if self.anim_alternativa_toggle_widget and self.ventana_disco:
            is_on = self.anim_alternativa_toggle_widget.is_on
            self.ventana_disco.set_anim_alternativa(is_on)
    # --------------------

    def toggle_caja_completa(self):
        """Controla el toggle de la caja Y el de la animación alternativa."""

        if self.caja_toggle_widget and self.caja_toggle_widget.cget('state') == 'disabled':
            return 
        # Deshabilitar el toggle para prevenir spam
        if self.caja_toggle_widget:
            self.caja_toggle_widget.config(state='disabled')
        
        # --- NUEVA LÓGICA DE CONTROL ---
        if self.caja_toggle_widget and self.anim_alternativa_toggle_widget:
            # Revisa el estado actual del toggle que se acaba de presionar
            is_caja_now_on = self.caja_toggle_widget.is_on
            
            if is_caja_now_on:
                # Si la caja se ENCIENDE, habilita el toggle de animación
                self.anim_alternativa_toggle_widget.config(state='normal')
            else:
                # Si la caja se APAGA, deshabilita y resetea el toggle de animación
                self.anim_alternativa_toggle_widget.config(state='disabled')
                # Llama a set_state para apagarlo visualmente
                self.anim_alternativa_toggle_widget.set_state(False, animate=True)
                # Sincroniza el estado en VentanaDisco también
                if self.ventana_disco:
                    self.ventana_disco.set_anim_alternativa(False)
        # -------------------------------

        # Llama a la acción original de VentanaDisco
        if self.ventana_disco:
            self.ventana_disco.toggle_caja_completa()

    def actualizar_color_ventanas(self, nuevo_color):
        self.ventana_disco.actualizar_color(nuevo_color)
        self.ventana_texto.actualizar_color(nuevo_color)

    def trigger_shazam_recognition(self):
        current_time = time.time()
        
        if current_time - self.last_activation_time < self.activation_cooldown:
            return
        
        if self.api_manager.is_processing:
            if agregar_log: agregar_log("- Ya hay un reconocimiento en cola")
            return
            
        if not self.api_manager.can_make_request():
            time_since_last = time.time() - self.api_manager.last_recognition_time
            remaining = max(0, self.api_manager.cooldown_after_request - time_since_last)
            if agregar_log: agregar_log(f"- Coldown: {remaining:.1f} segundos")
            return
        
        self.ventana_disco.mostrar_ventana()
        self.ventana_texto.mostrar_ventana()
        
        self.api_manager.is_processing = True
        self.last_activation_time = current_time
        
        thread = threading.Thread(target=self._execute_shazam_recognition, daemon=True)
        thread.start()

    def trigger_exit_animation(self):
        self.root.after(0, self._execute_exit_animation)

    def _execute_exit_animation(self):
        """Oculta el vinilo y el texto con animación."""
        if self.cancion_actual:
            if agregar_log: agregar_log("- Ocultando vinilo y texto")
            
            self.ventana_disco.animacion_salida()
            self.ventana_texto.animacion_salida()
            
            self.cancion_actual = None
            self.dummy_is_active = False
            
            # Sincroniza la UI del toggle (ponlo en OFF)
            if self.dummy_toggle_widget:
                self.dummy_toggle_widget.set_state(False, animate=True)
            
        else:
            if agregar_log: agregar_log("- No hay un vinilo o texto para ocultar")

    def _execute_shazam_recognition(self):
        temp_file = None
        try:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            temp_path = temp_file.name
            temp_file.close()
            
            if agregar_log: agregar_log("- Grabando muestra de audio")
            grabar_audio(temp_path)
            
            file_size = os.path.getsize(temp_path)
            if agregar_log: agregar_log(f"- Muestra de audio: {file_size} bytes")
            
            if file_size == 0:
                if agregar_log: agregar_log("- Muestra de audio sin datos")
                self.api_manager.update_after_request()
                return
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            if agregar_log: agregar_log("- Enviando a la api")
            artista, titulo, caratula = loop.run_until_complete(reconocer_cancion(temp_path))
            
            if artista and titulo:
                if agregar_log: agregar_log(f"- Cancion: {artista} - {titulo}")
                self.actualizar_interfaz(artista, titulo, caratula)
                self.api_manager.update_after_request(f"{artista} - {titulo}")
            else:
                if agregar_log: agregar_log("- Error al reconocer la cancion")
                self.api_manager.update_after_request()
                
            loop.close()
            
        except Exception as e:
            if agregar_log: agregar_log(f"- Error en el proceso: {e}")
            self.api_manager.update_after_request()
        finally:
            if temp_file and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except:
                    pass
            
            self.api_manager.is_processing = False
            if agregar_log: agregar_log("- Proceso termiado")

    def actualizar_interfaz(self, artista, titulo, caratula):
        def actualizar():
            self.dummy_is_active = False
            if self.dummy_toggle_widget:
                self.dummy_toggle_widget.set_state(False, animate=True)
                
            nueva = f"{artista} - {titulo}"
            if nueva == self.cancion_actual: return

            if nueva:
                if agregar_log: agregar_log(f"- Mostrando: {nueva}")
                
                self.ventana_disco.mostrar_ventana()
                self.ventana_texto.mostrar_ventana()
                
                self.ventana_disco.animacion_salida()
                self.ventana_texto.animacion_salida()
                self.cancion_actual = nueva

                def cargar():
                    self.ventana_disco.mostrar_disco(caratula)
                    self.ventana_texto.mostrar_texto(nueva)
                self.root.after(1000, cargar)
            else:
                if self.cancion_actual:
                    self.ventana_disco.animacion_salida()
                    self.ventana_texto.animacion_salida()
                    self.cancion_actual = None
        
        self.root.after(0, actualizar)

    def cleanup(self):
        if self.hotkey:
            self.hotkey.stop()

# ---------------------------------------------------------------
# --- 🎨 NUEVA CLASE: ToggleSwitch (Botón moderno) ---
# ---------------------------------------------------------------
class ToggleSwitch(tk.Canvas):
    """Un widget de interruptor moderno hecho con Canvas."""
    def __init__(self, parent, command=None, initial_state=False, **kwargs):
        self.bg = parent.cget("bg")
        self.on_color = "#007AFF"
        self.off_color = "#555555"
        self.knob_color = "#FFFFFF"
        
        super().__init__(parent, width=50, height=26, 
                         highlightthickness=0, bg=self.bg, **kwargs)
        
        self.is_on = initial_state
        self.command = command
        
        self.track_oval_l = self.create_oval(3, 3, 23, 23, fill=self.off_color, width=0)
        self.track_oval_r = self.create_oval(27, 3, 47, 23, fill=self.off_color, width=0)
        self.track_rect = self.create_rectangle(13, 3, 37, 23, fill=self.off_color, width=0)
        self.knob = self.create_oval(4, 4, 22, 22, fill=self.knob_color, width=0)
        
        self.bind("<Button-1>", self.toggle)
        self.set_state(initial_state, animate=False)

    def set_state(self, state, animate=True):
        """Establece el estado del interruptor (on/off)"""
        self.is_on = state
        if self.is_on:
            target_x = 28
            track_color = self.on_color
        else:
            target_x = 4
            track_color = self.off_color
            
        self.itemconfig(self.track_oval_l, fill=track_color)
        self.itemconfig(self.track_oval_r, fill=track_color)
        self.itemconfig(self.track_rect, fill=track_color)

        if animate:
            self._animate_knob(target_x)
        else:
            self.coords(self.knob, target_x, 4, target_x+18, 22)

    def toggle(self, event=None):
        """Cambia el estado del interruptor."""
        # No hacer nada si está deshabilitado
        if self.cget('state') == 'disabled':
            return
            
        self.set_state(not self.is_on)
        if self.command:
            self.command()

    def _animate_knob(self, target_x):
        """Animación suave de la perilla."""
        current_coords = self.coords(self.knob)
        current_x = current_coords[0]
        
        steps = 5 
        pixels_per_step = (target_x - current_x) / steps
        
        def _step(i):
            if i < steps:
                self.move(self.knob, pixels_per_step, 0)
                self.after(15, _step, i+1)
            else:
                self.coords(self.knob, target_x, 4, target_x+18, 22)
        
        _step(0)

# ---------------------------------------------------------------
# --- FIN DE ToggleSwitch ---
# ---------------------------------------------------------------

def signal_handler(sig, frame):
    if agregar_log: agregar_log("\n- Programa finalizado por el usuario")
    if 'app' in globals():
        app.cleanup()
        app.ventana_disco.running = False
        app.ventana_texto.texto_moviendo = False
    root.quit()
    root.destroy()
    sys.exit(0)
    
if __name__ == "__main__":
    try:
        import pynput
    except ImportError:
        print("Instalando pynput...")
        os.system("pip install pynput")
        import pynput

    signal.signal(signal.SIGINT, signal_handler)
    
    root = tk.Tk()

    # --- 🎨 Paleta de colores y Fuentes ---
    BG_COLOR = "#2B2B2B"       # Fondo oscuro
    CARD_COLOR = "#3C3C3C"     # Fondo de tarjeta
    TEXT_COLOR = "#E0E0E0"     # Texto claro
    ACCENT_COLOR = "#007AFF"   # Azul de acento (como en la imagen)
    YELLOW_COLOR = "#FFD60A"   # Amarillo para hotkeys
    
    try:
        TITLE_FONT = font.Font(family="Arial", size=16, weight="bold")
        HEADER_FONT = font.Font(family="Arial", size=12, weight="bold")
        BODY_FONT = font.Font(family="Arial", size=10)
        SMALL_FONT = font.Font(family="Arial", size=9)
        LOG_FONT = font.Font(family="Consolas", size=9)
    except:
        TITLE_FONT = ("Arial", 16, "bold")
        HEADER_FONT = ("Arial", 12, "bold")
        BODY_FONT = ("Arial", 10)
        SMALL_FONT = ("Arial", 9)
        LOG_FONT = ("Consolas", 9)
    # ---------------------------------
    
    try:
        root.tk.call('tk', 'scaling', 1.5)
        root.attributes('-alpha', 0.99)
        root.wm_attributes('-doublebuffer', 1)
        default_font = ("Arial", 10)
        root.option_add("*Font", default_font)
    except Exception as e:
        print(f"Configuración de renderizado no disponible: {e}")

    root.title("Reconocimiento de musica")
    root.configure(bg=BG_COLOR)
    root.geometry("600x900+650+100") 
    root.resizable(False, False)
    root.attributes('-topmost', False)
    
    label = tk.Label(root, text="Reconocimiento de musica", bg=BG_COLOR, fg=TEXT_COLOR, font=TITLE_FONT)
    label.pack(pady=(20, 15))
    
    # --- Tarjeta 1: Atajos de Teclado ---
    hotkey_card = tk.Frame(root, bg=CARD_COLOR, padx=20, pady=15)
    hotkey_card.pack(pady=5, padx=20, fill="x")
    
    tk.Label(hotkey_card, text="Atajos de Teclado", bg=CARD_COLOR, fg=TEXT_COLOR, font=HEADER_FONT).pack(anchor="w", pady=(0, 10))
    
    hotkey_frame_1 = tk.Frame(hotkey_card, bg=CARD_COLOR)
    hotkey_frame_1.pack(fill="x")
    tk.Label(hotkey_frame_1, text="SHIFT + Z + X", bg=CARD_COLOR, fg=YELLOW_COLOR, font=BODY_FONT).pack(side="left")
    tk.Label(hotkey_frame_1, text="Reconocer canción", bg=CARD_COLOR, fg=TEXT_COLOR, font=BODY_FONT).pack(side="right")
    
    hotkey_frame_2 = tk.Frame(hotkey_card, bg=CARD_COLOR)
    hotkey_frame_2.pack(fill="x", pady=(5,0))
    tk.Label(hotkey_frame_2, text="RSHIFT + PgDn", bg=CARD_COLOR, fg=YELLOW_COLOR, font=BODY_FONT).pack(side="left")
    tk.Label(hotkey_frame_2, text="Ocultar vinilo/texto", bg=CARD_COLOR, fg=TEXT_COLOR, font=BODY_FONT).pack(side="right")

    # --- Tarjeta 2: Controles ---
    control_card = tk.Frame(root, bg=CARD_COLOR, padx=20, pady=15)
    control_card.pack(pady=5, padx=20, fill="x")
    
    def on_toggle_caja():
        if 'app' in globals() and app:
            app.toggle_caja_completa()
        else:
            if agregar_log: agregar_log("- Error: 'app' no está lista.")

    toggle_frame = tk.Frame(control_card, bg=CARD_COLOR)
    toggle_frame.pack(fill="x")
    tk.Label(toggle_frame, text="Mostrar/Ocultar Caja", bg=CARD_COLOR, fg=TEXT_COLOR, font=BODY_FONT).pack(side="left", pady=2)
    caja_toggle = ToggleSwitch(toggle_frame, command=on_toggle_caja, initial_state=False)
    caja_toggle.pack(side="right")

    dummy_frame = tk.Frame(control_card, bg=CARD_COLOR)
    dummy_frame.pack(fill="x", pady=(10, 0)) 
    tk.Label(dummy_frame, text="Vinilo/Titulo (Prueba)", bg=CARD_COLOR, fg=TEXT_COLOR, font=BODY_FONT).pack(side="left", pady=2)
    def on_toggle_dummy():
        if 'app' in globals() and app:
            app.toggle_dummy_display()
    dummy_toggle = ToggleSwitch(dummy_frame, command=on_toggle_dummy, initial_state=False)
    dummy_toggle.pack(side="right")

    # --- NUEVO: Toggle de Animación Alternativa ---
    anim_frame = tk.Frame(control_card, bg=CARD_COLOR)
    anim_frame.pack(fill="x", pady=(10, 0)) 
    tk.Label(anim_frame, text="Animación Alternativa", bg=CARD_COLOR, fg=TEXT_COLOR, font=BODY_FONT).pack(side="left", pady=2)
    def on_toggle_anim_alternativa():
        if 'app' in globals() and app:
            app.toggle_anim_alternativa()
    anim_alternativa_toggle = ToggleSwitch(anim_frame, command=on_toggle_anim_alternativa, initial_state=False)
    anim_alternativa_toggle.pack(side="right")
    anim_alternativa_toggle.config(state='disabled') # Empezar deshabilitado
    # --- FIN DEL BLOQUE NUEVO ---

    auto_event_frame = tk.Frame(control_card, bg=CARD_COLOR)
    auto_event_frame.pack(fill="x", pady=(10, 0)) 
    tk.Label(auto_event_frame, text="Reconocimiento basado en eventos", bg=CARD_COLOR, fg=TEXT_COLOR, font=BODY_FONT).pack(side="left", pady=2)
    def on_toggle_auto_event():
        if 'app' in globals() and app:
            app.toggle_auto_event_listener()
    auto_event_toggle = ToggleSwitch(auto_event_frame, command=on_toggle_auto_event, initial_state=False)
    auto_event_toggle.pack(side="right")

    # --- Tarjeta 3: Color de Fondo ---
    color_card = tk.Frame(root, bg=CARD_COLOR, padx=20, pady=15)
    color_card.pack(pady=5, padx=20, fill="x")

    tk.Label(color_card, text="Color de Fondo", 
             bg=CARD_COLOR, fg=TEXT_COLOR, font=HEADER_FONT).pack(anchor="w", pady=(0, 10))

    predef_frame = tk.Frame(color_card, bg=CARD_COLOR)
    predef_frame.pack()

    def cambiar_color(nuevo_color):
        global fondo_ventana
        fondo_ventana = nuevo_color
        app.actualizar_color_ventanas(nuevo_color)
        if agregar_log: agregar_log(f"- Color cambiado a: {nuevo_color}")
        color_entry.delete(0, "end")
        if nuevo_color.startswith("#"):
            color_entry.insert(0, nuevo_color)
        else:
             color_entry.insert(0, nuevo_color)

    color_options = ["green", "blue", "red", "purple", "black", "gray", "orange", "pink"]
    
    for i, color in enumerate(color_options):
        color_c = tk.Canvas(predef_frame, width=28, height=28, bg=CARD_COLOR, highlightthickness=0, cursor="hand2")
        color_c.create_oval(4, 4, 24, 24, fill=color, outline=color)
        color_c.grid(row=0, column=i, padx=4)
        color_c.bind("<Button-1>", lambda e, c=color: cambiar_color(c))

    custom_frame = tk.Frame(color_card, bg=CARD_COLOR)
    custom_frame.pack(pady=(12, 5))
    
    tk.Label(custom_frame, text="Hex:", bg=CARD_COLOR, fg=TEXT_COLOR, font=BODY_FONT).pack(side="left")
    
    color_entry = tk.Entry(custom_frame, width=10, font=BODY_FONT, 
                           bg="#555555", fg=TEXT_COLOR, relief="flat",
                           insertbackground=TEXT_COLOR)
    color_entry.pack(side="left", padx=5)
    color_entry.insert(0, "#00FF00")

    def aplicar_color_personalizado():
        color_hex = color_entry.get()
        if color_hex.startswith('#') and len(color_hex) == 7:
            try:
                cambiar_color(color_hex)
            except:
                if agregar_log: agregar_log("- Color hexadecimal inválido")
        else:
            if agregar_log: agregar_log("- Formato inválido. Usa #RRGGBB")

    custom_btn = tk.Button(custom_frame, text="Aplicar", command=aplicar_color_personalizado, font=SMALL_FONT,bg=ACCENT_COLOR, fg="#FFFFFF", relief="flat", borderwidth=0,padx=8, pady=2, activebackground="#0056B3", activeforeground="#FFFFFF")
    custom_btn.pack(side="left")

    # --- Tarjeta 4: Registro de Actividad ---
    log_card = tk.Frame(root, bg=CARD_COLOR, padx=15, pady=15)
    log_card.pack(pady=5, padx=20, fill="both", expand=True) 

    tk.Label(log_card, text="Registro de Actividad", bg=CARD_COLOR, fg=TEXT_COLOR, font=HEADER_FONT).pack(anchor="w", pady=(0, 10), padx=5)
    
    log_inner_frame = tk.Frame(log_card, bg=CARD_COLOR)
    log_inner_frame.pack(fill="both", expand=True)
    
    scrollbar = tk.Scrollbar(log_inner_frame, orient=tk.VERTICAL,relief="flat", troughcolor=CARD_COLOR, bg=CARD_COLOR,width=10, activebackground=CARD_COLOR)
    
    log_text = tk.Text(log_inner_frame, height=8, bg=BG_COLOR, fg=TEXT_COLOR, font=LOG_FONT, wrap=tk.WORD, state=tk.DISABLED,relief="flat", borderwidth=0, highlightthickness=0,yscrollcommand=scrollbar.set)
    
    scrollbar.config(command=log_text.yview)
    
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0,5), pady=5)
    log_text.pack(side=tk.LEFT, fill="both", expand=True, padx=5, pady=5)

    def agregar_log(mensaje):
        if not 'log_text' in globals(): return 
        log_text.configure(state=tk.NORMAL)
        hora_actual = time.strftime("%H:%M:%S")
        log_text.insert(tk.END, f"[{hora_actual}] {mensaje}\n")
        log_text.see(tk.END)
        lineas = log_text.get(1.0, tk.END).split('\n')
        if len(lineas) > 100:
            log_text.delete(1.0, f"{len(lineas)-100}.0")
        log_text.configure(state=tk.DISABLED)
        global agregar_log
        agregar_log = agregar_log

    def limpiar_logs():
        log_text.configure(state=tk.NORMAL)
        log_text.delete(1.0, tk.END)
        log_text.configure(state=tk.DISABLED)
        agregar_log("Logs limpiados")

    clear_btn = tk.Button(log_card, text="Limpiar Logs", command=limpiar_logs, font=SMALL_FONT,bg="#555555", fg=TEXT_COLOR, relief="flat", borderwidth=0,padx=8, pady=2, activebackground="#666666", activeforeground=TEXT_COLOR)
    clear_btn.pack(pady=(5, 5))
    
    status_label = tk.Label(root, text="- Listo para usar -", bg=BG_COLOR, fg="green", font=HEADER_FONT)
    status_label.pack(pady=(10, 20))
    
    # --- Inicialización de la App ---
    app = NowPlaying(root, caja_toggle_widget=caja_toggle, dummy_toggle_widget=dummy_toggle, anim_alternativa_toggle_widget=anim_alternativa_toggle, auto_event_toggle_widget=auto_event_toggle)
    
    def update_status():
        NORMAL_UPDATE_MS = 500
        FAST_UPDATE_MS = 50
        
        try:
            if app.api_manager.is_processing:
                status_label.config(text="- Grabando / Procesando -", fg="orange")
                root.after(NORMAL_UPDATE_MS, update_status)
                
            elif not app.api_manager.can_make_request():
                time_since_last = time.time() - app.api_manager.last_recognition_time
                remaining = max(0, app.api_manager.cooldown_after_request - time_since_last)
                
                if remaining > 0:
                    status_label.config(text=f"- Cooldown: {remaining:.1f}s -", fg="red")
                    root.after(FAST_UPDATE_MS, update_status)
                else:
                    # El cooldown de 10s terminó
                    if app.auto_event_is_active:
                         status_label.config(text="- Escuchando Eventos -", fg="#00AFFF") # Azul
                    else:
                         status_label.config(text="- Listo para usar -", fg="green")
                    root.after(NORMAL_UPDATE_MS, update_status)
            
            # --- NUEVO ESTADO ---
            elif app.auto_event_is_active:
                # No está procesando y puede hacer request...
                status_label.config(text="- Escuchando Eventos -", fg="#00AFFF") # Azul
                root.after(NORMAL_UPDATE_MS, update_status)
            # --- FIN ---
            
            else:
                status_label.config(text="- Listo para usar -", fg="green")
                root.after(NORMAL_UPDATE_MS, update_status)
        
        except Exception as e:
            pass
    
    update_status()
    
    agregar_log("●----------------------------------------------●")
    agregar_log("|Atajo de teclado \t | \tFuncion                 |")
    agregar_log("|----------------------------------------------|")
    agregar_log("|SHIFT + Z + X \t\t\t  | \tLlamar reconocimiento   |")
    agregar_log("|RSHIFT + PgDn \t\t\t  | \tEsconder vinilo y titulo|")
    agregar_log("●----------------------------------------------●")
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        signal_handler(None, None)
    except Exception as e:
        if agregar_log: agregar_log(f"Error: {e}")
        sys.exit(1)