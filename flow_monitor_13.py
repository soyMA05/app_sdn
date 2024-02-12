#librerias
from the_switch_13 import TheSwitch13
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib import hub
import requests


#CLASES / METODOS

#Monitor de flujos
class Monitor13(TheSwitch13):
    #IP del servidor donde esta el modelo
    URL = 'http://10.0.1.8:5000'
    #constructor
    def __init__(self,  *args, **kwargs):
        super(Monitor13, self).__init__( *args, **kwargs)#inicializamos la clase padre con atri
        #atributos
        #dicc de sw (origen de los datos), cada vez que ocurra un evento se almacenan aqui los sw activos
        self.datapaths = {} 
        #inicializar monitor de flujos
        self.monitor_thread = hub.spawn(self._monitor)
        #dicc para almacenar los valores de las caracteristicas
        self.caracteriticas = {'Dur': '', 'Proto':'', 'Dport':'', 'TotPkts':'', 'SrcPkts':'', 'DstPkts':'','TotBytes':'', 'SrcBytes':'', 'DstBytes':''}
        #lista para almacenar flujos ( unidireccionales)
        self.list_flujos_uni = [] 

        #contadores
        self.cont_tot_amenazas = 0
        self.cont_tot_flow = 0
        self.cont_tot_normal = 0
    
    #controlar el cambio de estados del sw (eventos de confirmacion/activo y desconexion)
    @set_ev_cls(ofp_event.EventOFPStateChange,
            [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def control_cambio_estado(self, ev):#(ev es el evento recibido)
        #datapath es un conjunto de sws
        datapath = ev.datapath
        #si el estado de los eventos estan activos
        if ev.state == MAIN_DISPATCHER:
            if datapath.id not in self.datapaths: #si el sw no esta en el dicc de sws se lo agrega
                self.datapaths[datapath.id] = datapath
        #si el estado de los eventos estan inactivos
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:#se elimina del dicc de sws
                del self.datapaths[datapath.id]
                
    #metodo para enviar solicitudes a los sws periodicamente
    def _monitor(self):
        #siempre se envian solicitudes
        while True:
            #k es el nro del sw y valdp es el id
            for k, valdp in self.datapaths.items():
                #se envia la solicitud al sw 1 (concentrador de la topologia)
                if k == 1:
                    self.crear_solicitudes(valdp)#enviar solicitudes permanente cada 10 sec por sw que se encuentre en el dicc
            hub.sleep(1)#aqui se ponen los segundos que deseemos
            
    #metodo para crear solicitudes a los sw
    def crear_solicitudes(self, datapath):
        ofproto_parser = datapath.ofproto_parser #informacion de los sw(s) OF  

        solicitud = ofproto_parser.OFPFlowStatsRequest(datapath) #se pasa el sw al cual queremos obtener estadisticas
        datapath.send_msg(solicitud) #enviamos la solicitud y el sw las guarda en cola de mensajes

    #eliminar flujos de los sw [por corregir, porque si eliminaba se borrraban todo el trafico(tabla de flujo) y no recibia eventos, se elimina solo el trafico procesado al modelo]
    def delete_flow(self, eth_src):
        #obtengo info del sw concentrador
        ofproto_parser = self.datapaths['0000000000000001'].ofproto_parser
        #obtengo la mac del host en el sw
        match = ofproto_parser.OFPMatch(eth_dst=eth_src)
        #obtengo el cuerpo del mensaje donde modifica el flujo para eliminarlo
        mod = ofproto_parser.OFPFlowMod(
        self.datapaths['0000000000000001'], command=ofproto_parser.OFPFC_DELETE,
        out_port=ofproto_parser.OFPP_ANY, out_group=ofproto_parser.OFPG_ANY,
        priority=1, match=match)
        #envia mensaje para eliminar
        self.datapaths['0000000000000001'].send_msg(mod)

    #caracteristicas a nivel de flujo
    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def obtener_estadisticas_flujos(self,ev):
        #obtener todo el conjunto de flujos de la cola de mensajes
        body = ev.msg.body
        #lista para obtener flujo uno a uno
        flujos_sw = [flow for flow in body]
        #contador para emparejar los flujos bidireccionales
        cont_flujo_uni = -1
        #medir la longitud de los flujos en la lista de flujos unidireccionales
        long_flujos_uni = 0
        #variable par eliminar flujo actual(recibido)
        srcDelete = None
        #mostrar los flujos de la lista
        self.logger.info('Longitud:%8d', len(flujos_sw))
        respuesta = None

        
        #Lectura de flujos unidireccionales
        """
        Se agregan flujos unidirecionales en list_flujos_uni que no se encuentren en la lista de flujos y que sean menores a 20 secs. 
        A pesar de ello se agregan flujos duplicados bajo los 20 secs.
        """
        self.logger.info('------------------------Flow Stats-----------------------------------')
        #obtengo todo el conjunto de caracteristicas de un flujo
        for stat in flujos_sw:
            #compruebo solo 2 protocolos L4
            if stat.match.get('ip_proto') == 6 or stat.match.get('ip_proto') == 17: 
                #si el flujo actual no esta en la lista y la duracion sea menor al tiempo de 20 sec
                if flujos_sw[cont_flujo_uni+1] not in self.list_flujos_uni and ( flujos_sw[cont_flujo_uni+1].duration_sec <= 20):
                    self.logger.info('Agrego flujo unidireccional')
                    #agrego las caracteristicas del flujo actual en el atributo de la lista de flujos unidireccionales
                    self.list_flujos_uni.append(flujos_sw[cont_flujo_uni+1])
            cont_flujo_uni+=1
            
        
            #lectura, muestra y almacenamiento de flujos bidireccionales para enviarlos al modelo y obtener la respuesta

            #si la longitud mayor a cero y el nro de flujos almacenados sean pares y la longitud actual sea mayot a la anterior
            if len(self.list_flujos_uni) > 0 and len(self.list_flujos_uni) %2 == 0 and len(self.list_flujos_uni) > long_flujos_uni:
                self.cont_tot_flow+=1 #aumenta un flujo bidireccional
                #recorrer flujos pares
                for i in range(len(self.list_flujos_uni)-2,len(self.list_flujos_uni),2):
                    #obtener las caracteristicas de cada flujo actual + 1 lo que lo convierte bidireccional
                    self.caracteriticas['Dur'] = self.list_flujos_uni[i].duration_sec
                    self.caracteriticas['Proto'] = proto = self.list_flujos_uni[i].match['ip_proto']
                    src = self.list_flujos_uni[i].match['eth_src']
                    dst = self.list_flujos_uni[i].match['eth_dst']
                    self.caracteriticas['Dport'] = dport = self.list_flujos_uni[i].match.get('tcp_dst') or self.list_flujos_uni[i].match.get('udp_dst')
                    self.caracteriticas['TotPkts']  = self.list_flujos_uni[i].packet_count + self.list_flujos_uni[i+1].packet_count
                    self.caracteriticas['SrcPkts']  = self.list_flujos_uni[i].packet_count
                    self.caracteriticas['DstPkts']  = self.list_flujos_uni[i+1].packet_count
                    self.caracteriticas['TotBytes'] = self.list_flujos_uni[i].byte_count + self.list_flujos_uni[i+1].byte_count
                    self.caracteriticas['SrcBytes'] = self.list_flujos_uni[i].byte_count
                    self.caracteriticas['DstBytes'] = self.list_flujos_uni[i+1].byte_count
                    """ Si queremos utilizar las 12 caracteristicas descomentar esto y agregar al diccionario de caracteristicas 'Rate':'', 'SrcRate':'', 'DstRate':''
                    try:
                        self.caracteriticas['Rate'] = (self.list_flujos_uni[i].packet_count + self.list_flujos_uni[i+1].packet_count) / self.list_flujos_uni[i].duration_sec
                        self.caracteriticas['SrcRate'] = self.list_flujos_uni[i].packet_count / self.list_flujos_uni[i].duration_sec
                        self.caracteriticas['DstRate'] = self.list_flujos_uni[i+1].packet_count / self.list_flujos_uni[i].duration_sec
                    except:
                        self.caracteriticas['Rate'] = 0
                        self.caracteriticas['SrcRate'] = 0 
                        self.caracteriticas['DstRate'] = 0
                    """
                    #consultar al modelo con el valor de las caracteristicas almacenadas (cambiar el metodo segun las caracteristicas)
                    consulta_flujo = requests.post(self.URL +'/predict',self.caracteriticas)
                    #recibir respuesta
                    consulta_flujo = consulta_flujo.json()

                    #comparar a que valor corresponde la Y
                    if consulta_flujo['Label'] == str(0):
                        respuesta = 'Normal'
                        self.cont_tot_amenazas+=1
                    elif consulta_flujo['Label'] == str(1):
                        respuesta = 'DoS'
                        self.cont_tot_amenazas+=1
                    elif consulta_flujo['Label'] == str(2):
                        respuesta = 'DDoS'
                        self.cont_tot_normal+=1
                    elif consulta_flujo['Label'] == str(3):
                        respuesta = 'Probe'
                        self.cont_tot_amenazas+=1
                    else:
                        respuesta = 'Botnet'
                        self.cont_tot_amenazas+=1

                    #mostramos los valores de las caracteristicas    
                    self.logger.info('Src:%14s <-> Dst%14s Proto:%6d Dport:%6d TotPkts:%7d SrcPkts:%6d DstPkts:%6d TotBytes:%7d SrcBytes:%6d DstBytes:%6d',
                    src, dst, proto, dport, (self.list_flujos_uni[i].packet_count + self.list_flujos_uni[i+1].packet_count), 
                    self.list_flujos_uni[i].packet_count, self.list_flujos_uni[i+1].packet_count, (self.list_flujos_uni[i].byte_count + self.list_flujos_uni[i+1].byte_count), 
                    self.list_flujos_uni[i].byte_count, self.list_flujos_uni[i+1].byte_count)
                    #mostrar respuesta de consulta
                    if consulta_flujo != 0:
                        self.logger.info('Tipo:%7s',respuesta)
                        self.logger.info('Nro de Ataques:%7d/%7d', self.cont_tot_amenazas, self.cont_tot_flow)
                    else:
                        self.logger.info('Tipo:%7s',respuesta)
                        self.logger.info('Nro de Normal:%7d/%7d', self.cont_tot_normal, self.cont_tot_flow)
                    #valor del dispositivo de origen
                    srcDelete = src
                    #limpiar el dicc de la consulta
                    consulta_flujo.clear()
                    #limpiar el dicc de las caracteristicas
                    self.caracteriticas.clear()
            #actualizamos el valor de la longitud de la lista de flujos unidireccionales
            long_flujos_uni = len(self.list_flujos_uni)

        #elimino el flujo que genera un dispositivo despues de haber enviado el trafico
        try:
            self.delete_flow(srcDelete)
        except:
            self.logger.info('Flujo inexistente')
        
