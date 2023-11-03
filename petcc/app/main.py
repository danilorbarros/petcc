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

# [PeT Instance]
class PeT():
    def __init__(self):
        self.lat = None
        self.lng = None
        self.dataset = None
        self.duplicate_distances = {}
        self.current_channel_and_angle = [None, None]
        self.address = None
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tv_controller = None

    # Seta a localizacao do usuario
    def set_location(self, lat, lng):
        self.lat, self.lng = float(lat), float(lng)

    # Define a lista de canais segundo ANATEL.
    def set_dataset(self):
        cgpb = pd.DataFrame({'Canal':[3,7,9,11,13,19,23,40], 
                             'Entidade':['TV Paraíba','TV Bandeirantes','TV Borborema','TV Maior','TV Correios','TV Itararé','Rede Vida','TV Arapuan'],
                             'Latitude':[-7.196070686076691,-7.123883803736,-7.217070207424,-7.222914069005,-7.122831775000,-7.237743934188,-7.123883803736,-7.213289372426],
                             'Longitude':[-35.89568718950067,-34.876077492192,-35.885146445421,-35.881199368674,-34.877917127244,-35.878669875343,-34.876077492192,-35.892873245577]})
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
        channel_name = [nome for nome in row.loc[row['Canal'] == channel]["Entidade"]][0]

        if channel_name in self.duplicate_distances:
            angle = self.get_bearingangle(self.duplicate_distances[channel_name][2],self.duplicate_distances[channel_name][3])
            self.current_channel_and_angle[0], self.current_channel_and_angle[1] = channel, angle

            return angle
        else:
            angle = self.get_bearingangle(float(row["Latitude"]), float(row["Longitude"]))
            self.current_channel_and_angle[0], self.current_channel_and_angle[1] = channel, angle

            return angle

    # Busca o servidor broadcast
    def find_server(self, sock):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        delay = 1  
        mb = 65535

        while True:
            sock.sendto(b"DISCOVERY", ('192.168.0.255',53530))
            sock.settimeout(delay)
            
            try:
                data , address = sock.recvfrom(mb)
            except socket.timeout:
                delay = delay + 1
            else:
                break
        
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 0)
        
        sock.settimeout(0.0)
        
        return address

    # Estabelece um socket de conexao com o ESP via broadcast
    def set_espsocket(self):
        sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        #self.address = (self.find_server(sock)[0],53540)
        self.address = ("127.0.0.1",53540)

        time.sleep(1)
        print("Conectando-se a {}".format(self.address))
        self.client_socket.connect(self.address)

    # Estabelece um socket de conexao com a TV
    def set_tvsocket(self, tv_address):
        config = {"name": "samsungctl","description": "PC","id": "","host": tv_address,"port": 55000,"method": "legacy","timeout": 0,}
        print("Configuração do controle:{}".format(config))
        print("self.tv_controller = samsungctl.Remote(config)")
        #self.tv_controller = samsungctl.Remote(config)
        
# [HUD Instance]
class MainWindow(Screen):
    tvip = ObjectProperty(None)

    # Inicializa as conexoes com ESP (broadcast) e TV (Direta)
    def set_connections(self):
        PCore.set_espsocket()
        PCore.set_tvsocket(self.tvip.text)

class SecondWindow(Screen):
    channel_list = ""

    # Soma os valores selecionados pelo usuário para definir o canal
    def get_channel(self, channel):
        self.channel_list = self.channel_list + str(channel)
        self.channel_angle.text = self.channel_list

    # Define o canal selecionado
    def set_channel(self):
        # Envia o canal para a TV
        for channel in self.channel_list:
            print("PCore.tv_controller.control(\"KEY_{}\".format(channel))".format(channel))
            #PCore.tv_controller.control("KEY_{}".format(channel))
            time.sleep(0.5)

        # Envia o angulo calculado para o ESP
        try:
            angle = str(np.floor(float(PCore.set_positioning(int(self.channel_list)))))
            self.channel_angle.text = angle

            PCore.client_socket.sendall(angle.encode())
        except IndexError:
            self.channel_angle.text = "Canal não encontrado"
            pass
        self.channel_list = ""

    # Limpa do ângulo printado
    def blank_menu(self):
        self.channel_angle.text = ""

class WindowManager(ScreenManager):
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
            # Retorno, por exemplo, caso tente rodar no PC (windows, linux, etc)
            self.gps_status = 'GPS is not implemented for your platform'

        # Caso a plataforma seja um android, solicitar as permissões de acesso ao GPS
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
    PCore.set_location('-7.2399191559291545','-35.91621378231747')
    MyApp().run()