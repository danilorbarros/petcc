# [Library Instance]
import kivy
import pandas as pd
import numpy as np
import math
import socket
import samsungctl
import time
from kivy.lang import Builder
from plyer import gps
from kivy.app import App
from kivy.properties import StringProperty
from kivy.clock import mainthread
from kivy.utils import platform
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import ObjectProperty
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.popup import Popup

ANGLE_FIRST=0
CHANNEL_FIRST=1

# [PeT Instance]
class PeT():
    def __init__(self):
        self.lat = None
        self.lng = None
        self.dataset = None
        self.current_channel_and_angle = [None, None]
        self.address = None
        self.client_socket = None
        self.tv_controller = None
        self.change_order = CHANNEL_FIRST

    # Seta a localizacao do usuario
    def set_location(self, lat, lng):
        self.lat, self.lng = float(lat), float(lng)

    # Define a lista de canais segundo ANATEL.
    def set_dataset(self):
        cgpb = pd.read_csv('canaispet.csv')
        self.dataset = cgpb

    # Calcula o angulo entre dois pontos, usando o norte como referencia
    def get_bearingangle(self, lat, lng):
        dlng = (float(lng) - self.lng)
        x = math.cos(math.radians(float(lat))) * math.sin(math.radians(dlng))
        y = math.cos(math.radians(self.lat)) * math.sin(math.radians(float(lat))) - \
            math.sin(math.radians(self.lat)) * math.cos(math.radians(float(lat))) * math.cos(math.radians(dlng))
        brng = np.arctan2(x, y)
        return np.degrees(brng)

    # Calcula a angulacao da antena com base no canal seleiconado
    def set_positioning(self, channel):
        row = self.dataset.loc[self.dataset['Canal'] == channel]
        latitude, longitude = self.get_coordinate(row, "Latitude"), self.get_coordinate(row, "Longitude")
        angle = self.get_bearingangle(latitude, longitude)

        self.current_channel_and_angle[0], self.current_channel_and_angle[1] = channel, angle

        return angle

    # Funcao auxiliar para formatacao da coordenada
    def get_coordinate(self, row, column):
        return float(row[column].values[0].replace(',', "."))
    
    def send_to_server(self, sock, angle):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        delay = 5  
        mb = 65535

        sock.sendto(angle.encode(), ('192.168.0.255',53530))
        
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 0)
        
        sock.settimeout(0.0)

    # Estabelece um socket de conexao com o ESP via broadcast
    def set_espsocket(self):
        self.client_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)

    # Estabelece um socket de conexao com a TV
    def set_tvsocket(self, tv_address):
        config = {"name": "samsungctl","description": "PC","id": "","host": tv_address,"port": 55000,"method": "legacy","timeout": 0,}
        print("Configuração do controle:{}".format(config))
        try:
            self.tv_controller = samsungctl.Remote(config)
        except ConnectionRefusedError:
            self.show_popup("Conexao recusada.")
            pass
        except TimeoutError:
            self.show_popup("Timeout na conexao.")
            pass

    def exit(self):
        self.send_to_server(self.client_socket,"0.0")

    def show_popup(self, msg):
        show = P()
        popupWindow = Popup(title="Mensagem de erro!", content=show, size_hint=(None,None),size=(400,400))
        popupWindow.open()
        
# [HUD Instance]
class MainWindow(Screen):
    tvip = ObjectProperty(None)

    # Inicializa as conexoes com ESP (broadcast) e TV (Direta)
    def set_connections(self):
        if PCore.address == None:
            PCore.set_espsocket()
        
        if PCore.tv_controller == None and len(self.tvip.text) > 1:
            PCore.set_tvsocket(self.tvip.text)

    def set_change_order(self, order):
        if order == CHANNEL_FIRST:
            print("PCore alterado para CHANNEL_FIRST")
            PCore.change_order = CHANNEL_FIRST
        elif order == ANGLE_FIRST:
            print("PCore alterado para ANGLE_FIRST")
            PCore.change_order = ANGLE_FIRST

class SecondWindow(Screen):
    channel_list = ""

    # Soma os valores selecionados pelo usuário para definir o canal
    def get_channel(self, channel):
        self.channel_list = self.channel_list + str(channel)
        self.channel_angle.text = self.channel_list

    # Define o canal selecionado
    def set_channel(self):
        if PCore.change_order == CHANNEL_FIRST:
            self.send_channel_tv()
            self.send_channel_motor()
        elif PCore.change_order == ANGLE_FIRST:
            self.send_channel_motor()
            self.send_channel_tv()
        self.channel_list = ""
        
    def send_channel_tv(self):
        print("Executando send_channel_tv().")
        if PCore.tv_controller != None:
            for channel in self.channel_list:
                print("PCore.tv_controller.control(\"KEY_{}\")".format(channel))
                PCore.tv_controller.control("KEY_{}".format(channel))
                time.sleep(0.5)
        else:
            self.channel_angle.text = "TV não conectada."

    def send_channel_motor(self):
        print("Executando send_channel_motor().")
        try:
            angle = str(np.floor(float(PCore.set_positioning(int(self.channel_list)))))
            self.channel_angle.text = angle

            PCore.send_to_server(PCore.client_socket,angle)
        except IndexError:
            self.channel_angle.text = "Canal não encontrado"
            pass

    # Limpa do ângulo printado
    def blank_menu(self):
        self.channel_angle.text = ""

    def exit(self):
        PCore.exit()

class WindowManager(ScreenManager):
    pass

class P(FloatLayout):
    pass

# Inicializacao da HUD
kv = Builder.load_file("my.kv")

# [PeTdroid aplication Instance]
class MyApp(App):

    # Definicao de variaveis do GPS
    gps_location = StringProperty()
    gps_status = StringProperty('Click Start to get GPS location updates')

    # Permissao android
    def request_android_permissions(self):
        from android.permissions import request_permissions, Permission

        def callback(permissions, results):
            if all([res for res in results]):
                print("callback. All permissions granted.")
            else:
                print("callback. Some permissions refused.")

        request_permissions([Permission.ACCESS_COARSE_LOCATION,
                             Permission.ACCESS_FINE_LOCATION], callback)

    # Criacao do nucleo do aplicativo
    def build(self):
        try:
            gps.configure(on_location=self.on_location,
                          on_status=self.on_status)
        except NotImplementedError:
            import traceback
            traceback.print_exc()
            self.gps_status = 'GPS is not implemented for your platform'

        if platform == "android":
            print("gps.py: Android detected. Requesting permissions")
            self.request_android_permissions()

        return kv

    # Start e Stop usados na leitura da localização
    def start(self, minTime, minDistance):
        gps.start(minTime, minDistance)
    def stop(self):
        gps.stop()

    # Coleta informacoes do GPS
    @mainthread
    def on_location(self, **kwargs):
        count = 0
        latlng = []
        while count <= 1:
            for k, v in kwargs.items():
                self.gps_location = '\n'.join(['{}={}'.format(k, v)])
                latlng.append(v)
            count = count + 1

        PCore.set_location(latlng[0],latlng[1])
    @mainthread
    def on_status(self, stype, status):
        self.gps_status = 'type={}\n{}'.format(stype, status)

    # Metodos complementares
    def on_pause(self):
        gps.stop()
        return True
    def on_resume(self):
        gps.start(1000, 0)
        pass

# [Inicialization Instance]
if __name__ == "__main__":
    PCore = PeT()
    PCore.set_dataset()
    MyApp().run()
